# IYAF Security Checklist

- Never commit `.env` files or API keys.
- Never store passwords in plain text.
- Keep the admin role restricted.
- Use HTTPS in production.
- Verify your sending domain with the email provider.
- Only email users who have opted in to non-essential announcements.
- Collect only information necessary for IYAF programmes.
- Review retention/deletion requirements for member data.
- Change the generated SECRET_KEY if you ever suspect exposure.
- Do not expose the PostgreSQL database publicly.
