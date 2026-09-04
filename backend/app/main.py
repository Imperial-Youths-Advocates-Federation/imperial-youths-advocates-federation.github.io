
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, String, Boolean, DateTime, Text, ForeignKey, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from pwdlib import PasswordHash
import jwt
import httpx
import secrets
import hashlib

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./iyaf_dev.db")
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE-ME-IN-PRODUCTION")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "https://imperial-youth-advocates-federation.github.io")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "iyafzim003@gmail.com")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "IYAF <onboarding@resend.dev>")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(30), default="member")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    announcement_opt_in: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class ContactRequest(Base):
    __tablename__ = "contact_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference_id: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    subject: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(80), default="General")
    message: Mapped[str] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    programme: Mapped[str] = mapped_column(String(200))
    application_data: Mapped[str] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(30), default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class EmailLog(Base):
    __tablename__ = "email_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    recipient: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(300))
    email_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Token(Base):
    __tablename__ = "tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(30))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)

Base.metadata.create_all(engine)

pwd = PasswordHash.recommended()
ALGORITHM = "HS256"
SESSION_COOKIE = "iyaf_session"

def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "jti": str(uuid4()),
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def current_user(request: Request, db: Session = Depends(lambda: Session(engine))) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Account not found")
    return user

def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user

def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

def make_action_token(db: Session, user_id: int, kind: str, hours: int = 24) -> str:
    raw = secrets.token_urlsafe(40)
    db.add(Token(token_hash=hash_token(raw), user_id=user_id, kind=kind,
                 expires_at=datetime.now(timezone.utc) + timedelta(hours=hours)))
    db.commit()
    return raw

async def send_email(to: str, subject: str, html: str, email_type: str, db: Session):
    if not RESEND_API_KEY:
        db.add(EmailLog(recipient=to, subject=subject, email_type=email_type, status="not_configured"))
        db.commit()
        return False
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={"from": EMAIL_FROM, "to": [to], "subject": subject, "html": html},
            )
            ok = r.status_code < 300
        db.add(EmailLog(recipient=to, subject=subject, email_type=email_type,
                        status="sent" if ok else f"failed_{r.status_code}"))
        db.commit()
        return ok
    except Exception:
        db.add(EmailLog(recipient=to, subject=subject, email_type=email_type, status="failed"))
        db.commit()
        return False

class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=40)
    country: str | None = Field(default=None, max_length=100)
    announcement_opt_in: bool = True
    consent: bool

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class ContactIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    subject: str = Field(min_length=2, max_length=200)
    category: str = Field(default="General", max_length=80)
    message: str = Field(min_length=2, max_length=5000)

class ApplicationIn(BaseModel):
    programme: str = Field(min_length=2, max_length=200)
    application_data: str = Field(min_length=2, max_length=20000)

class BroadcastIn(BaseModel):
    subject: str = Field(min_length=2, max_length=300)
    html: str = Field(min_length=2, max_length=50000)

app = FastAPI(title="IYAF Live Platform API", version="1.0.0")

origins = [x.strip() for x in FRONTEND_ORIGIN.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type"],
)

def get_db():
    with Session(engine) as db:
        yield db

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "IYAF Live Platform"}

@app.post("/api/auth/register")
async def register(data: RegisterIn, response: Response, db: Session = Depends(get_db)):
    if not data.consent:
        raise HTTPException(400, "You must accept the registration consent.")
    email = data.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    user = User(
        full_name=data.full_name.strip(), email=email, phone=data.phone,
        country=data.country, password_hash=pwd.hash(data.password),
        announcement_opt_in=data.announcement_opt_in
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    verify = make_action_token(db, user.id, "verify", 24)
    # Use your deployed frontend URL here for the verification page.
    frontend = os.getenv("FRONTEND_URL", FRONTEND_ORIGIN)
    verify_url = f"{frontend.rstrip('/')}/verify.html?token={verify}"
    await send_email(
        user.email, "Welcome to IYAF — verify your email",
        f"<h2>Welcome to the Imperial Youth Advocates Federation</h2>"
        f"<p>Hello {user.full_name},</p><p>Please verify your email:</p>"
        f'<p><a href="{verify_url}">Verify my email</a></p>',
        "registration_confirmation", db
    )
    await send_email(
        ADMIN_EMAIL, "New IYAF registration",
        f"<h2>New IYAF registration</h2><p><b>Name:</b> {user.full_name}</p>"
        f"<p><b>Email:</b> {user.email}</p><p><b>Phone:</b> {user.phone or 'Not provided'}</p>"
        f"<p><b>Country:</b> {user.country or 'Not provided'}</p>",
        "admin_registration", db
    )
    response.set_cookie(SESSION_COOKIE, create_token(user), httponly=True, secure=True,
                        samesite="none", max_age=86400, path="/")
    return {"message": "Account created. Check your email to verify it.", "user": {"id": user.id, "name": user.full_name}}

@app.post("/api/auth/login")
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower().strip()))
    if not user or not pwd.verify(data.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    response.set_cookie(SESSION_COOKIE, create_token(user), httponly=True, secure=True,
                        samesite="none", max_age=86400, path="/")
    return {"message": "Logged in", "user": {"id": user.id, "name": user.full_name, "email": user.email, "role": user.role}}

@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"message": "Logged out"}

@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.full_name, "email": user.email, "role": user.role, "verified": user.email_verified}

@app.get("/api/auth/verify")
def verify_email(token: str, db: Session = Depends(get_db)):
    row = db.scalar(select(Token).where(Token.token_hash == hash_token(token), Token.kind == "verify", Token.used == False))
    if not row or row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, "Verification link is invalid or expired.")
    user = db.get(User, row.user_id)
    user.email_verified = True
    row.used = True
    db.commit()
    return {"message": "Email verified successfully."}

@app.post("/api/contact")
async def contact(data: ContactIn, db: Session = Depends(get_db)):
    ref = "IYAF-" + secrets.token_hex(5).upper()
    item = ContactRequest(reference_id=ref, name=data.name.strip(), email=data.email.lower(),
                          phone=data.phone, subject=data.subject.strip(), category=data.category,
                          message=data.message.strip())
    db.add(item)
    db.commit()
    await send_email(
        ADMIN_EMAIL, f"New IYAF contact request [{ref}]",
        f"<h2>New IYAF Contact Request</h2><p><b>Reference:</b> {ref}</p>"
        f"<p><b>Name:</b> {data.name}</p><p><b>Email:</b> {data.email}</p>"
        f"<p><b>Phone:</b> {data.phone or 'Not provided'}</p><p><b>Category:</b> {data.category}</p>"
        f"<p><b>Subject:</b> {data.subject}</p><hr><p>{data.message}</p>",
        "contact_admin", db
    )
    await send_email(
        data.email, f"IYAF received your request [{ref}]",
        f"<h2>Thank you for contacting IYAF</h2><p>Your request has been received.</p>"
        f"<p>Your reference is <b>{ref}</b>.</p>",
        "contact_confirmation", db
    )
    return {"message": "Your request has been received.", "reference_id": ref}

@app.post("/api/applications")
async def application(data: ApplicationIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = Application(user_id=user.id, programme=data.programme, application_data=data.application_data)
    db.add(item)
    db.commit()
    await send_email(
        ADMIN_EMAIL, f"New IYAF application — {data.programme}",
        f"<h2>New IYAF Application</h2><p><b>Applicant:</b> {user.full_name}</p>"
        f"<p><b>Email:</b> {user.email}</p><p><b>Programme:</b> {data.programme}</p>"
        f"<hr><p>{data.application_data}</p>",
        "application_admin", db
    )
    await send_email(
        user.email, "IYAF application received",
        f"<h2>Application received</h2><p>Hello {user.full_name}, your application for "
        f"<b>{data.programme}</b> has been received by IYAF.</p>",
        "application_confirmation", db
    )
    return {"message": "Application received.", "id": item.id}

@app.get("/api/user/requests")
def user_requests(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ContactRequest).where(ContactRequest.user_id == user.id).order_by(ContactRequest.created_at.desc())).all()
    return [{"reference_id": x.reference_id, "subject": x.subject, "status": x.status, "created_at": x.created_at} for x in rows]

@app.get("/api/admin/stats")
def admin_stats(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    return {
        "members": db.scalar(select(func.count(User.id))) or 0,
        "requests": db.scalar(select(func.count(ContactRequest.id))) or 0,
        "applications": db.scalar(select(func.count(Application.id))) or 0,
    }

@app.get("/api/admin/members")
def admin_members(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [{"id": u.id, "name": u.full_name, "email": u.email, "phone": u.phone,
             "country": u.country, "role": u.role, "verified": u.email_verified,
             "created_at": u.created_at, "last_login": u.last_login} for u in rows]

@app.get("/api/admin/requests")
def admin_requests(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ContactRequest).order_by(ContactRequest.created_at.desc())).all()
    return [{"id": x.id, "reference_id": x.reference_id, "name": x.name, "email": x.email,
             "phone": x.phone, "subject": x.subject, "category": x.category,
             "message": x.message, "status": x.status, "created_at": x.created_at} for x in rows]

@app.patch("/api/admin/requests/{request_id}")
def update_request(request_id: int, status_value: str, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    if status_value not in {"pending", "in_progress", "resolved"}:
        raise HTTPException(400, "Invalid status.")
    item = db.get(ContactRequest, request_id)
    if not item:
        raise HTTPException(404, "Request not found.")
    item.status = status_value
    db.commit()
    return {"message": "Updated"}

@app.get("/api/admin/applications")
def admin_applications(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Application).order_by(Application.created_at.desc())).all()
    return [{"id": a.id, "user_id": a.user_id, "programme": a.programme,
             "application_data": a.application_data, "status": a.status,
             "created_at": a.created_at, "updated_at": a.updated_at} for a in rows]

@app.post("/api/admin/send-email")
async def broadcast(data: BroadcastIn, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    users = db.scalars(select(User).where(User.email_verified == True, User.announcement_opt_in == True)).all()
    sent = 0
    for u in users:
        if await send_email(u.email, data.subject, data.html, "broadcast", db):
            sent += 1
    return {"eligible": len(users), "sent": sent}

@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return ADMIN_HTML

ADMIN_HTML = r"""
<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>IYAF Admin</title>
<style>
body{font-family:Arial,sans-serif;margin:0;background:#f4f6fb;color:#18233a}
header{background:#172b5b;color:white;padding:20px}main{max-width:1100px;margin:20px auto;padding:0 15px}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.card{background:white;padding:20px;border-radius:12px}
button{padding:10px 14px;border:0;border-radius:8px;cursor:pointer}table{width:100%;background:white;border-collapse:collapse;margin-top:15px}
td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}#out{white-space:pre-wrap}
@media(max-width:700px){.cards{grid-template-columns:1fr}table{font-size:12px}}
</style></head>
<body><header><h1>IYAF Admin Dashboard</h1><p>Imperial Youth Advocates Federation</p></header>
<main><button onclick="load()">Refresh</button><pre id="out"></pre><div class="cards" id="cards"></div>
<h2>Members</h2><div id="members"></div><h2>Contact Requests</h2><div id="requests"></div></main>
<script>
async function api(path,opt={}){let r=await fetch(path,{credentials:'include',...opt});if(!r.ok)throw new Error(await r.text());return r.json()}
async function load(){
 try{
 let s=await api('/api/admin/stats');cards.innerHTML=Object.entries(s).map(([k,v])=>`<div class="card"><b>${k}</b><h2>${v}</h2></div>`).join('');
 let m=await api('/api/admin/members');members.innerHTML='<table><tr><th>Name</th><th>Email</th><th>Country</th><th>Verified</th></tr>'+m.map(x=>`<tr><td>${x.name}</td><td>${x.email}</td><td>${x.country||''}</td><td>${x.verified}</td></tr>`).join('')+'</table>';
 let q=await api('/api/admin/requests');requests.innerHTML='<table><tr><th>Ref</th><th>Name</th><th>Subject</th><th>Status</th></tr>'+q.map(x=>`<tr><td>${x.reference_id}</td><td>${x.name}</td><td>${x.subject}</td><td>${x.status}</td></tr>`).join('')+'</table>';
 }catch(e){out.textContent=e.message}
} load();
</script></body></html>
"""
