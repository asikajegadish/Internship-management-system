from functools import wraps
from datetime import date
import os
from uuid import uuid4

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, abort
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB maximum upload
RESUME_FOLDER = os.path.join(app.root_path, "uploads", "resumes")
os.makedirs(RESUME_FOLDER, exist_ok=True)
ALLOWED_RESUME_EXTENSIONS = {"pdf", "doc", "docx"}


def allowed_resume(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_RESUME_EXTENSIONS

# Set these values to match your local MySQL installation.
app.config["MYSQL_HOST"] = os.environ.get("MYSQL_HOST", "localhost")
app.config["MYSQL_USER"] = os.environ.get("MYSQL_USER", "root")
app.config["MYSQL_PASSWORD"] = os.environ.get("MYSQL_PASSWORD", "achu")
app.config["MYSQL_DB"] = os.environ.get("MYSQL_DB", "internship_db")
app.config["MYSQL_CURSORCLASS"] = "DictCursor"
mysql = MySQL(app)

VALID_STATUSES = {"Under Review", "Shortlisted", "Selected", "Rejected"}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))
            if session.get("role") not in allowed_roles:
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.route("/")
def index():
    return redirect(url_for("dashboard" if session.get("user_id") else "login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "student")

        if not name or not email or not password:
            flash("Please fill in every field.", "danger")
            return redirect(url_for("register"))
        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "danger")
            return redirect(url_for("register"))
        if role not in {"student", "company"}:
            flash("Self-registration is available for students and companies only.", "danger")
            return redirect(url_for("register"))

        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            cur.close()
            flash("This email is already registered.", "warning")
            return redirect(url_for("register"))

        cur.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (%s,%s,%s,%s)",
            (name, email, generate_password_hash(password), role)
        )
        mysql.connection.commit()
        cur.close()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        cur = mysql.connection.cursor()
        # Allow login by registered email for everyone, or company name for company accounts.
        cur.execute(
            "SELECT * FROM users WHERE LOWER(email)=%s OR (LOWER(name)=LOWER(%s) AND role='company') LIMIT 1",
            (identifier.lower(), identifier)
        )
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            flash("Welcome back, " + user["name"] + "!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM internships WHERE is_active=1 AND (deadline IS NULL OR deadline >= CURDATE())")
    total_internships = cur.fetchone()["total"]
    applications = 0
    status_counts = {"Under Review": 0, "Shortlisted": 0, "Selected": 0, "Rejected": 0}

    if session["role"] == "student":
        cur.execute("SELECT COUNT(*) AS total FROM applications WHERE student_id=%s", (session["user_id"],))
        applications = cur.fetchone()["total"]
        cur.execute("SELECT status, COUNT(*) AS total FROM applications WHERE student_id=%s GROUP BY status", (session["user_id"],))
        for row in cur.fetchall():
            status_counts[row["status"]] = row["total"]
    elif session["role"] in {"company", "admin"}:
        if session["role"] == "admin":
            cur.execute("SELECT COUNT(*) AS total FROM applications")
            applications = cur.fetchone()["total"]
            cur.execute("SELECT status, COUNT(*) AS total FROM applications GROUP BY status")
        else:
            cur.execute("""SELECT COUNT(*) AS total FROM applications a
                           JOIN internships i ON i.id=a.internship_id WHERE i.company_id=%s""",
                        (session["user_id"],))
            applications = cur.fetchone()["total"]
            cur.execute("""SELECT a.status, COUNT(*) AS total FROM applications a
                           JOIN internships i ON i.id=a.internship_id
                           WHERE i.company_id=%s GROUP BY a.status""", (session["user_id"],))
        for row in cur.fetchall():
            status_counts[row["status"]] = row["total"]
    cur.close()
    return render_template("dashboard.html", total_internships=total_internships,
                           applications=applications, status_counts=status_counts)


@app.route("/internships")
@login_required
def internships():
    q = request.args.get("q", "").strip()
    skill = request.args.get("skill", "").strip()
    stipend = request.args.get("min_stipend", "").strip()

    sql = """SELECT i.*, u.name AS company_name
             FROM internships i JOIN users u ON u.id=i.company_id
             WHERE i.is_active=1 AND (i.deadline IS NULL OR i.deadline >= CURDATE())"""
    params = []
    if q:
        sql += " AND (i.title LIKE %s OR i.description LIKE %s OR u.name LIKE %s)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if skill:
        sql += " AND i.required_skills LIKE %s"
        params.append(f"%{skill}%")
    if stipend:
        try:
            min_stipend = float(stipend)
            if min_stipend < 0:
                raise ValueError
            sql += " AND i.stipend >= %s"
            params.append(min_stipend)
        except ValueError:
            flash("Enter a valid minimum stipend.", "warning")
            return redirect(url_for("internships"))
    sql += " ORDER BY i.created_at DESC"

    cur = mysql.connection.cursor()
    cur.execute(sql, tuple(params))
    rows = cur.fetchall()

    # Find internships this student has already applied for.
    applied_ids = set()
    if session.get("role") == "student":
        cur.execute(
            "SELECT internship_id FROM applications WHERE student_id=%s",
            (session["user_id"],)
        )
        applied_ids = {row["internship_id"] for row in cur.fetchall()}

    cur.close()
    return render_template(
        "internships.html", internships=rows, q=q, skill=skill,
        min_stipend=stipend, applied_ids=applied_ids
    )


@app.route("/internships/add", methods=["GET", "POST"])
@login_required
@role_required("company", "admin")
def add_internship():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        skills = request.form.get("skills", "").strip()
        duration = request.form.get("duration", "").strip()
        stipend = request.form.get("stipend", "0").strip()
        deadline = request.form.get("deadline") or None

        if not title or not description:
            flash("Title and description are required.", "danger")
            return redirect(url_for("add_internship"))
        try:
            stipend_value = float(stipend or 0)
            if stipend_value < 0:
                raise ValueError
        except ValueError:
            flash("Stipend must be zero or a positive number.", "danger")
            return redirect(url_for("add_internship"))
        if deadline:
            try:
                if date.fromisoformat(deadline) < date.today():
                    flash("The application deadline cannot be in the past.", "danger")
                    return redirect(url_for("add_internship"))
            except ValueError:
                flash("Please enter a valid deadline.", "danger")
                return redirect(url_for("add_internship"))

        cur = mysql.connection.cursor()
        cur.execute("""INSERT INTO internships
                        (company_id, title, description, required_skills, duration, stipend, deadline)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (session["user_id"], title, description, skills, duration, stipend_value, deadline))
        mysql.connection.commit()
        cur.close()
        flash("Internship posted successfully.", "success")
        return redirect(url_for("internships"))
    return render_template("add_internship.html")


@app.route("/apply/<int:internship_id>", methods=["POST"])
@login_required
@role_required("student")
def apply(internship_id):
    cur = mysql.connection.cursor()
    cur.execute("""SELECT id FROM internships
                   WHERE id=%s AND is_active=1 AND (deadline IS NULL OR deadline >= CURDATE())""",
                (internship_id,))
    if not cur.fetchone():
        cur.close()
        flash("This internship is unavailable or its deadline has passed.", "danger")
        return redirect(url_for("internships"))

    cur.execute("SELECT id FROM applications WHERE student_id=%s AND internship_id=%s",
                (session["user_id"], internship_id))
    if cur.fetchone():
        cur.close()
        flash("You have already applied for this internship.", "warning")
        return redirect(url_for("internships"))

    resume = request.files.get("resume")
    if not resume or not resume.filename:
        cur.close()
        flash("Please upload your resume (PDF, DOC, or DOCX).", "danger")
        return redirect(url_for("internships"))
    if not allowed_resume(resume.filename):
        cur.close()
        flash("Resume must be a PDF, DOC, or DOCX file.", "danger")
        return redirect(url_for("internships"))

    extension = resume.filename.rsplit(".", 1)[1].lower()
    saved_filename = f"{uuid4().hex}.{extension}"
    resume.save(os.path.join(RESUME_FOLDER, saved_filename))
    try:
        cur.execute("INSERT INTO applications (student_id, internship_id, resume_path) VALUES (%s,%s,%s)",
                    (session["user_id"], internship_id, saved_filename))
        mysql.connection.commit()
    except Exception:
        mysql.connection.rollback()
        saved_path = os.path.join(RESUME_FOLDER, saved_filename)
        if os.path.exists(saved_path):
            os.remove(saved_path)
        cur.close()
        raise
    cur.close()
    flash("Application and resume submitted successfully.", "success")
    return redirect(url_for("my_applications"))


@app.route("/applications")
@login_required
def my_applications():
    cur = mysql.connection.cursor()
    role = session.get("role")
    if role == "student":
        cur.execute("""SELECT a.id, a.status, a.applied_at, a.resume_path, i.title, u.name AS company_name
                       FROM applications a JOIN internships i ON i.id=a.internship_id
                       JOIN users u ON u.id=i.company_id
                       WHERE a.student_id=%s ORDER BY a.applied_at DESC""", (session["user_id"],))
    elif role == "company":
        cur.execute("""SELECT a.id, a.status, a.applied_at, a.resume_path, i.title, s.name AS student_name,
                              u.name AS company_name
                       FROM applications a JOIN internships i ON i.id=a.internship_id
                       JOIN users s ON s.id=a.student_id JOIN users u ON u.id=i.company_id
                       WHERE i.company_id=%s ORDER BY a.applied_at DESC""", (session["user_id"],))
    elif role == "admin":
        cur.execute("""SELECT a.id, a.status, a.applied_at, a.resume_path, i.title, s.name AS student_name,
                              u.name AS company_name
                       FROM applications a JOIN internships i ON i.id=a.internship_id
                       JOIN users s ON s.id=a.student_id JOIN users u ON u.id=i.company_id
                       ORDER BY a.applied_at DESC""")
    else:
        cur.close()
        flash("Use Faculty Monitoring to view application records.", "info")
        return redirect(url_for("faculty_monitoring"))
    rows = cur.fetchall()
    cur.close()
    return render_template("applications.html", applications=rows)


@app.route("/applications/<int:application_id>/resume")
@login_required
def download_resume(application_id):
    cur = mysql.connection.cursor()
    cur.execute("""SELECT a.resume_path, a.student_id, i.company_id
                   FROM applications a JOIN internships i ON i.id=a.internship_id
                   WHERE a.id=%s""", (application_id,))
    row = cur.fetchone()
    cur.close()
    if not row or not row.get("resume_path"):
        abort(404)
    role = session.get("role")
    allowed = (role == "student" and row["student_id"] == session["user_id"]) or \
              (role == "company" and row["company_id"] == session["user_id"]) or role == "admin"
    if not allowed:
        abort(403)
    return send_from_directory(RESUME_FOLDER, row["resume_path"], as_attachment=True)


@app.route("/applications/<int:application_id>/status", methods=["POST"])
@login_required
@role_required("company", "admin")
def update_status(application_id):
    status = request.form.get("status")
    if status not in VALID_STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("my_applications"))

    cur = mysql.connection.cursor()
    if session["role"] == "admin":
        cur.execute("UPDATE applications SET status=%s WHERE id=%s", (status, application_id))
    else:
        cur.execute("""UPDATE applications a JOIN internships i ON i.id=a.internship_id
                       SET a.status=%s WHERE a.id=%s AND i.company_id=%s""",
                    (status, application_id, session["user_id"]))
    mysql.connection.commit()
    changed = cur.rowcount
    cur.close()
    flash("Application status updated." if changed else "Application not found or not yours.",
          "success" if changed else "warning")
    return redirect(url_for("my_applications"))


@app.route("/faculty")
@login_required
@role_required("faculty", "admin")
def faculty_monitoring():
    cur = mysql.connection.cursor()
    cur.execute("""SELECT s.name AS student_name, i.title, u.name AS company_name,
                          a.status, a.applied_at
                   FROM applications a JOIN users s ON s.id=a.student_id
                   JOIN internships i ON i.id=a.internship_id
                   JOIN users u ON u.id=i.company_id
                   ORDER BY a.applied_at DESC""")
    rows = cur.fetchall()
    cur.close()
    return render_template("faculty.html", applications=rows)


if __name__ == "__main__":
    # Keep debug mode for local development only. Disable it before deployment.
    app.run(debug=True)
