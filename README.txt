INTERNSHIP MANAGEMENT SYSTEM — ENHANCED FLASK + MYSQL

Enhancements included:
- Responsive refreshed interface and dashboard.
- Internship search by title, description, and company.
- Skill and minimum stipend filters.
- Expired internships are hidden from browsing and cannot be applied to.
- Dashboard status summary for applications.
- Validation for stipend and application deadline.
- Fixed application status comparison in the template.
- Existing MySQL table structure is retained.

SETUP
1. Back up your current project folder first.
2. Copy app.py, templates/, static/, requirements.txt and schema.sql into your project.
3. Create/activate a virtual environment if you use one:
   python -m venv venv
   venv\Scripts\activate
4. Install packages:
   pip install -r requirements.txt
5. Run schema.sql in MySQL only if you have not already created these tables.
   It uses CREATE TABLE IF NOT EXISTS and does not delete existing records.
6. Set your MySQL settings in environment variables, or edit the MYSQL settings in app.py.
   MYSQL_HOST=localhost
   MYSQL_USER=root
   MYSQL_PASSWORD=your_mysql_password
   MYSQL_DB=internship_db
7. Run:
   python app.py
8. Open http://127.0.0.1:5000/login

IMPORTANT
- Do not share your real database password publicly. The pasted code contained a password value; replace it with your own local setting.
- Change SECRET_KEY to a long random value before deployment.
- Turn debug mode off before deployment and use HTTPS.
- Faculty and admin accounts must be created by an administrator; public registration only allows student/company.
- This is a local development project and should receive security review before public deployment.


RESUME UPLOAD FEATURE
1. In MySQL Workbench, run add_resume_column.sql ONCE for an existing database.
   If creating a brand-new database, schema.sql already includes the column.
2. Students must upload a PDF, DOC, or DOCX resume (maximum 5 MB) when applying.
3. Companies can download resumes for applications to their own internships; students can download their own, and admins can download any.
4. Uploaded files are saved in uploads/resumes and are not served as public static files.


FACULTY MONITORING TEST LOGIN
After running schema.sql, sign in at /login with:
Email: faculty@internship.local
Password: Faculty@123
This is a local demo account. Change the password before deploying anywhere public.

IMPORTANT: If your existing database was already created, run the updated schema.sql again in MySQL Workbench. It uses CREATE TABLE IF NOT EXISTS and adds/updates the faculty account.
