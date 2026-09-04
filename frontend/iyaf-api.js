
/*
 IYAF frontend API helper.
 CHANGE ONLY API_BASE_URL after deploying the Python backend.
 Example:
 const API_BASE_URL = "https://iyaf-api.onrender.com";
*/
const API_BASE_URL = "https://REPLACE-WITH-YOUR-IYAF-BACKEND.onrender.com";

async function iyafAPI(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.message || "Request failed");
  return data;
}

async function iyafRegister(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  data.consent = true;
  data.announcement_opt_in = data.announcement_opt_in !== "false";
  return iyafAPI("/api/auth/register", { method:"POST", body:JSON.stringify(data) });
}

async function iyafLogin(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  return iyafAPI("/api/auth/login", { method:"POST", body:JSON.stringify(data) });
}

async function iyafLogout() {
  return iyafAPI("/api/auth/logout", { method:"POST" });
}

async function iyafContact(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  return iyafAPI("/api/contact", { method:"POST", body:JSON.stringify(data) });
}

async function iyafMe() {
  return iyafAPI("/api/auth/me");
}
