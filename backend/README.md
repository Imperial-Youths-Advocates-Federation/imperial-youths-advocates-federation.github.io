# IYAF Live Platform Backend

This is the live backend for Imperial Youth Advocates Federation.

## What it provides
- PostgreSQL database
- Registration and secure password hashing
- Login/logout with HTTP-only cookie
- Email verification
- Contact request storage + email notification
- Application storage + email notification
- Admin dashboard
- Opt-in announcement email
- Health endpoint

## Important
GitHub Pages cannot run this Python backend. Deploy the `backend` folder to a Python-capable host such as Render or Railway.

## Deploy on Render
1. Create a new Web Service.
2. Connect the GitHub repository containing this backend.
3. Set the root directory to `backend` if the backend is in a subfolder.
4. Runtime: Docker (recommended) or Python.
5. Add a PostgreSQL database and use its DATABASE_URL.
6. Add all variables from `.env.example`.
7. Generate a strong SECRET_KEY.
8. Set FRONTEND_URL to the exact GitHub Pages URL.
9. Set FRONTEND_ORIGIN to the origin only:
   https://imperial-youth-advocates-federation.github.io
10. Add your Resend API key.
11. Deploy.

## Email
For production, verify an IYAF-owned sending domain with your email provider. Do not put RESEND_API_KEY in HTML or JavaScript.

## Admin account
For safety, the application does not allow someone to register as admin.
Use the database to promote the first trusted IYAF account:
UPDATE users SET role='admin' WHERE email='YOUR-ADMIN-EMAIL';

Do this only after registration, and use the actual IYAF administrator email.

## Frontend
Copy `frontend/iyaf-api.js` into the existing GitHub Pages site and add the small forms described in `frontend/README.md`.
