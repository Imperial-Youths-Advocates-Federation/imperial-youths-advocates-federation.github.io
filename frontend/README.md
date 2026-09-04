# Connect the existing IYAF website

Do NOT replace the existing IYAF design.

1. Upload `iyaf-api.js` and `verify.html` to the root of your GitHub Pages repository.
2. Edit `iyaf-api.js` and replace:
   https://REPLACE-WITH-YOUR-IYAF-BACKEND.onrender.com
   with your actual backend URL.
3. Add `<script src="iyaf-api.js"></script>` to pages that use the API.
4. Your registration form must use these field names:
   full_name, email, password, phone, country, announcement_opt_in
   and call `iyafRegister(this)`.
5. Your login form uses:
   email, password
   and calls `iyafLogin(this)`.
6. Your contact form uses:
   name, email, phone, subject, category, message
   and calls `iyafContact(this)`.

Example:

<form onsubmit="event.preventDefault(); iyafContact(this).then(x=>alert(x.message)).catch(e=>alert(e.message))">
  <input name="name" required>
  <input name="email" type="email" required>
  <input name="subject" required>
  <select name="category"><option>General</option><option>Partnership</option><option>Programme</option></select>
  <textarea name="message" required></textarea>
  <button>Send</button>
</form>

The backend sends notifications to iyafzim003@gmail.com.

IMPORTANT:
The current website's existing visual design is not included in this backend package because it should not be overwritten. Merge these integration files into the existing site.
