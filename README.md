# IYAF LIVE PLATFORM

This package contains the production-oriented Python backend, database models, email workflow, admin dashboard, and frontend API integration for the existing IYAF website.

## Files
- `backend/` — FastAPI server, PostgreSQL models, authentication, email, admin API
- `frontend/` — small files to connect the existing GitHub Pages frontend
- `render.yaml` — deployment blueprint
- `SECURITY.md` — security checklist

## The one thing this package intentionally does NOT do
It does not replace the existing IYAF homepage. Your existing homepage design should remain intact.

## Simplest deployment
1. Upload this package to a GitHub repository.
2. Deploy `backend` with Render using `render.yaml`.
3. Create/configure the Resend email service and verify a sending domain.
4. Put the deployed backend URL into `frontend/iyaf-api.js`.
5. Upload the two frontend files to the existing IYAF GitHub Pages repository.
6. Connect the existing Join/Login/Contact forms to the helper functions.
