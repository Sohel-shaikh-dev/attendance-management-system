# app.py
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify, Response, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime as dt
from sqlalchemy import func, case, cast, or_, text
from sqlalchemy.sql.sqltypes import Date
import csv
import io
import os
import secrets
import string
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# Load environment variables from .env file (safely ignored if not present in production)
load_dotenv()

app = Flask(__name__)

# Secure Application Secret Key
app.secret_key = os.environ.get('SECRET_KEY', '9a8fee50cea11a5b23dd8f8c66a51d5631e4ae339f0f1473687ad456047b5c40')

# Session settings
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # 30 days tak session rahega
# Secure cookie enforced in production, False for local HTTP development
app.config['SESSION_COOKIE_SECURE'] = (os.environ.get('FLASK_ENV') == 'production')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_REFRESH_EACH_REQUEST'] = True  # Har request pe session refresh

# Secure Database Connection String
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:passwordd@localhost/attendance_db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_size': 10,
    'max_overflow': 20
}

# ─── Email / SMTP Configuration ───────────────────────────────────────────────
# Set these via environment variables in production.
# For Gmail: enable 2FA and create an App Password at
#   https://myaccount.google.com/apppasswords
#app.config['MAIL_SENDER']      = os.environ.get('MAIL_SENDER',   'shaikhsonu1772003@gmail.com')
#app.config['MAIL_PASSWORD']    = os.environ.get('MAIL_PASSWORD',  'itte pinf wqte iaja')          # Gmail App Password
#app.config['MAIL_SMTP_HOST']   = os.environ.get('MAIL_SMTP_HOST', 'smtp.gmail.com')
#app.config['MAIL_SMTP_PORT']   = int(os.environ.get('MAIL_SMTP_PORT', '587'))
#app.config['MAIL_SEND_HOUR']   = int(os.environ.get('MAIL_SEND_HOUR',  '12'))  # 12 = noon
#app.config['MAIL_SEND_MINUTE'] = int(os.environ.get('MAIL_SEND_MINUTE', '0'))

db = SQLAlchemy(app)

SUBJECT_MASTER = {
    # ── Subjects are synced with actual DB values ──────────────────────────────
    "BSc IT": {
        "1": ["Fundamentals of IT", "Programming in C", "Digital Electronics", "Mathematics I", "Communication Skills"],
        "2": ["Discrete Mathematics", "Environmental Studies", "Mathematics II", "Programming in C II", "Web Technology"],
        "3": ["Computer Networks", "Cyber Security", "Operating Systems", "Python Programming", "Software Engineering"],
        "4": ["Artificial Intelligence", "Cloud Computing", "DBMS", "Java Programming", "Research Methodology"],
        "5": ["Data Analytics", "Information Security", "Mobile Application Development", "Networking", "Project I"],
        "6": ["Advanced Cloud Computing", "Big Data", "IoT", "Machine Learning", "Project II"],
    },
    "BBA": {
        "1": ["Principles of Management", "Business Communication", "Fundamentals of IT", "Mathematics I", "Communication Skills", "Digital Electronics", "Programming in C"],
        "2": ["Discrete Mathematics", "Environmental Studies", "Mathematics II", "Programming in C II", "Web Technology"],
        "3": ["Computer Networks", "Cyber Security", "Operating Systems", "Python Programming", "Software Engineering"],
        "4": ["Artificial Intelligence", "Cloud Computing", "DBMS", "Java Programming", "Research Methodology"],
        "5": ["Data Analytics", "Information Security", "Mobile Application Development", "Networking", "Project I"],
        "6": ["Advanced Cloud Computing", "Big Data", "IoT", "Machine Learning", "Project II"],
    },
    "BCom": {
        "1": ["Financial Accounting", "Fundamentals of IT", "Mathematics I", "Communication Skills", "Digital Electronics", "Programming in C"],
        "2": ["Discrete Mathematics", "Environmental Studies", "Mathematics II", "Programming in C II", "Web Technology"],
        "3": ["Corporate Accounting", "Computer Networks", "Cyber Security", "Operating Systems", "Python Programming", "Software Engineering"],
        "4": ["Artificial Intelligence", "Cloud Computing", "DBMS", "Java Programming", "Research Methodology"],
        "5": ["Data Analytics", "Information Security", "Mobile Application Development", "Networking", "Project I"],
        "6": ["Advanced Cloud Computing", "Big Data", "IoT", "Machine Learning", "Project II"],
    },
    "BA": {
        "1": ["Communication Skills", "Digital Electronics", "Fundamentals of IT", "Mathematics I", "Programming in C"],
        "2": ["Discrete Mathematics", "Environmental Studies", "Mathematics II", "Programming in C II", "Web Technology"],
        "3": ["Computer Networks", "Cyber Security", "Operating Systems", "Python Programming", "Software Engineering"],
        "4": ["Artificial Intelligence", "Cloud Computing", "DBMS", "Java Programming", "Research Methodology"],
        "5": ["Data Analytics", "Information Security", "Mobile Application Development", "Networking", "Project I"],
        "6": ["Advanced Cloud Computing", "Big Data", "IoT", "Machine Learning", "Project II"],
    },
}

COURSE_KEY_ALIASES = {
    "bscit": "BSc IT",
    "bsc it": "BSc IT",
    "b.com": "BCom",
    "bcom": "BCom",
    "b.b.a": "BBA",
    "bba": "BBA",
    "b.a": "BA",
    "ba": "BA"
}

# 🧑‍🎓 Student Table
class Student(db.Model):
    __tablename__ = 'students'
    student_id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100))
    gmail_id = db.Column(db.String(100))
    parent_email = db.Column(db.String(100))
    guardian_email = db.Column(db.String(100))
    mobile_number = db.Column(db.String(20))
    course = db.Column(db.String(50))
    class_yr = db.Column(db.String(10))  # FY/SY/TY
    semester = db.Column(db.String(10))
    profile_photo = db.Column(db.String(255))  # relative path inside static/

class Attendance(db.Model):
    __tablename__ = 'attendance'
    attendance_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.student_id'))
    date = db.Column(db.Date)
    status = db.Column(db.String(10))
    marked_by = db.Column(db.String(100))
    course = db.Column(db.String(50))
    class_yr = db.Column(db.String(10))
    semester = db.Column(db.String(10))
    subject = db.Column(db.String(100))
    marked_time = db.Column(db.Time)

    @property
    def time(self):
        return self.marked_time

    @time.setter
    def time(self, value):
        self.marked_time = value

    @property
    def remarks(self):
        return None

    @remarks.setter
    def remarks(self, value):
        return None
    
class Notice(db.Model):
    __tablename__ = 'notices'
    
    notice_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    posted_by = db.Column(db.String(100), default='Teacher')
    is_active = db.Column(db.Boolean, default=True)
    is_pinned = db.Column(db.Boolean, default=False)
    is_important = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(50))
    attachment_path = db.Column(db.String(200))
    views = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"Notice('{self.title}', '{self.date_posted}')"
    
  # models.py ya app.py mein
# ─── Transcript Request Table ────────────────────────────────────────────────
class TranscriptRequest(db.Model):
    __tablename__ = 'transcript_requests'

    id           = db.Column(db.Integer, primary_key=True)
    student_id   = db.Column(db.Integer, db.ForeignKey('students.student_id'), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    course       = db.Column(db.String(50))
    class_yr     = db.Column(db.String(10))
    semester     = db.Column(db.String(10))
    status       = db.Column(db.String(20), nullable=False, default='Pending')  # Pending / Approved / Rejected
    remarks      = db.Column(db.Text)
    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship('Student', backref=db.backref('transcript_requests', lazy=True))

    def __repr__(self):
        return f"<TranscriptRequest {self.id} [{self.status}]>"


# ─── Coupon / Reward Table ────────────────────────────────────────────────────
class Coupon(db.Model):
    __tablename__ = 'coupons'

    id                  = db.Column(db.Integer, primary_key=True)
    student_id          = db.Column(db.Integer, db.ForeignKey('students.student_id'), nullable=False)
    coupon_code         = db.Column(db.String(30), unique=True, nullable=False)
    discount_percentage = db.Column(db.Integer, nullable=False)   # 45 or 50
    issued_at           = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expiry_date         = db.Column(db.DateTime, nullable=False)
    is_used             = db.Column(db.Boolean, nullable=False, default=False)
    attendance_pct      = db.Column(db.Numeric(5, 2))             # snapshot of % at issue time

    student = db.relationship('Student', backref=db.backref('coupons', lazy=True))

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expiry_date

    @property
    def is_active(self):
        return not self.is_used and not self.is_expired

    def __repr__(self):
        return f"<Coupon {self.coupon_code} [{self.discount_percentage}%]>"


class Fees(db.Model):
    fee_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.student_id'), nullable=False)
    amount_paid = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    payment_method = db.Column(db.String(50))

    student = db.relationship('Student', backref=db.backref('fees', lazy=True))  

@app.before_request
def check_valid_session():
    print(f"\nBefore Request - Current Session: {dict(session)}\n")
    print(f"Request Path: {request.path}")

@app.after_request
def print_session(response):
    print(f"\nAfter Request - Session: {dict(session)}\n")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

def format_lecture_time(value):
    if value is None:
        return "-"
    if hasattr(value, "strftime"):
        return value.strftime("%I:%M %p")
    return str(value)


def normalize_status(value):
    s = (value or "").strip().lower()
    if s in {"present", "p", "1", "true", "yes"}:
        return "present"
    if s in {"absent", "a", "0", "false", "no"}:
        return "absent"
    return s


def calculate_current_streak(records):
    """Consecutive present attendance days from latest available attendance date."""
    if not records:
        return 0

    day_status = {}
    for rec in records:
        if not rec.date:
            continue
        status = normalize_status(rec.status)
        if rec.date not in day_status:
            day_status[rec.date] = False
        if status == "present":
            day_status[rec.date] = True

    if not day_status:
        return 0

    streak = 0
    for d in sorted(day_status.keys(), reverse=True):
        if day_status[d]:
            streak += 1
        else:
            break
    return streak


def resolve_period_dates(period, start_date_str="", end_date_str="", reference_date=None):
    today = reference_date or date.today()
    start = end = None

    if start_date_str or end_date_str:
        try:
            start = date.fromisoformat(start_date_str) if start_date_str else None
            end = date.fromisoformat(end_date_str) if end_date_str else None
        except ValueError:
            start = end = None

    if start or end:
        if start and end and end < start:
            start, end = end, start
        return start, end

    if period == "today":
        return today, today
    if period == "yesterday":
        y = today - timedelta(days=1)
        return y, y
    if period == "7":
        return today - timedelta(days=7), today
    if period == "30":
        return today - timedelta(days=30), today
    if period == "month":
        return today.replace(day=1), today

    return None, None


def normalized_text_expr(column):
    return func.lower(
        func.replace(
            func.replace(
                func.replace(
                    func.trim(func.coalesce(column, "")),
                    " ",
                    ""
                ),
                "-",
                ""
            ),
            "_",
            ""
        )
    )


def apply_semester_filter(query, semester):
    sem_raw = (semester or "").strip()
    sem = canonical_semester(sem_raw)
    if not sem:
        return query

    # Normalize DB values so variants like "2", "Sem2", "Sem 2", "Semester-2"
    # are treated as the same semester.
    normalized_db_sem = normalized_text_expr(Attendance.semester)

    if sem.isdigit():
        return query.filter(or_(
            Attendance.semester == sem,
            Attendance.semester == sem_raw,
            Attendance.semester.ilike(f"Sem{sem}"),
            Attendance.semester.ilike(f"Sem {sem}"),
            Attendance.semester.ilike(f"Semester{sem}"),
            Attendance.semester.ilike(f"Semester {sem}")
            ,
            normalized_db_sem == sem,
            normalized_db_sem == f"sem{sem}",
            normalized_db_sem == f"semester{sem}"
        ))
    normalized_input = sem_raw.lower().replace(" ", "").replace("-", "").replace("_", "")
    return query.filter(or_(
        Attendance.semester == sem_raw,
        Attendance.semester == sem,
        normalized_db_sem == normalized_input
    ))


def apply_student_semester_filter(query, semester):
    sem_raw = (semester or "").strip()
    sem = canonical_semester(sem_raw)
    if not sem:
        return query

    normalized_db_sem = normalized_text_expr(Student.semester)

    if sem.isdigit():
        return query.filter(or_(
            Student.semester == sem,
            Student.semester == sem_raw,
            Student.semester.ilike(f"Sem{sem}"),
            Student.semester.ilike(f"Sem {sem}"),
            Student.semester.ilike(f"Semester{sem}"),
            Student.semester.ilike(f"Semester {sem}"),
            normalized_db_sem == sem,
            normalized_db_sem == f"sem{sem}",
            normalized_db_sem == f"semester{sem}"
        ))

    normalized_input = sem_raw.lower().replace(" ", "").replace("-", "").replace("_", "")
    return query.filter(or_(
        Student.semester == sem_raw,
        Student.semester == sem,
        normalized_db_sem == normalized_input
    ))


def get_logged_in_student_email():
    return (session.get('email') or session.get('gmail_id') or '').strip()


# ─── Global Academic Filter ───────────────────────────────────────────────────
def get_active_filter(gmail_id=""):
    """
    Resolve (active_class, active_semester) with priority:
      1. Query-string params  (?class_yr=, ?semester=)   — local override
      2. Session              (active_class, active_semester)
      3. Student's DB row     (fallback when session is empty)

    Returns a tuple (class_str, semester_str) — both may be empty strings.
    """
    qp_class = (request.args.get('class_yr') or '').strip().upper()
    qp_sem   = canonical_semester(request.args.get('semester') or '')

    if qp_class or qp_sem:
        # Merge with session so partial overrides still work
        resolved_class = qp_class or session.get('active_class', '')
        resolved_sem   = qp_sem   or session.get('active_semester', '')
        return resolved_class, resolved_sem

    sess_class = (session.get('active_class') or '').strip().upper()
    sess_sem   = canonical_semester(session.get('active_semester') or '')
    if sess_class or sess_sem:
        return sess_class, sess_sem

    # Fallback: read from the student's DB row
    if gmail_id:
        email = gmail_id.strip().lower()
        s = Student.query.filter(
            func.lower(func.coalesce(Student.gmail_id, '')) == email
        ).order_by(Student.student_id.desc()).first()
        if s:
            return (s.class_yr or '').strip().upper(), canonical_semester(s.semester or '')

    return '', ''


def save_active_filter(active_class, active_semester):
    """Persist the resolved class/semester into the session."""
    session['active_class']    = (active_class    or '').strip().upper()
    session['active_semester'] = (active_semester or '').strip()
    session.modified = True


def get_student_for_email_semester(gmail_id, semester=""):
    email = (gmail_id or "").strip().lower()
    if not email:
        return None, ""

    students = Student.query.filter(
        func.lower(func.coalesce(Student.gmail_id, "")) == email
    ).order_by(Student.student_id.asc()).all()
    if not students:
        return None, ""

    highest_student = max(
        students,
        key=lambda s: int(canonical_semester(s.semester))
        if canonical_semester(s.semester).isdigit()
        else -1
    )

    selected_sem = canonical_semester(semester)
    if not selected_sem:
        selected_sem = canonical_semester(highest_student.semester) or "1"

    for s in students:
        if canonical_semester(s.semester) == selected_sem:
            return s, selected_sem

    return highest_student, selected_sem


def build_student_attendance_base_query(gmail_id, semester=""):
    email = (gmail_id or "").strip().lower()
    sem = canonical_semester(semester)
    q = Attendance.query.join(
        Student, Attendance.student_id == Student.student_id
    ).filter(
        func.lower(func.coalesce(Student.gmail_id, "")) == email
    )
    return apply_student_semester_filter(q, sem)


def apply_period_subject_filters(query, period, start_date_str="", end_date_str="", subject="", reference_date=None):
    start, end = resolve_period_dates(period, start_date_str, end_date_str, reference_date=reference_date)
    if start and end:
        query = query.filter(Attendance.date.between(start, end))
    elif start:
        query = query.filter(Attendance.date >= start)
    elif end:
        query = query.filter(Attendance.date <= end)

    if subject:
        query = query.filter(Attendance.subject.ilike(f"%{subject}%"))
    return query


def apply_student_dashboard_period_filter(query, period):
    """Strict DB-side date windows for student dashboard."""
    p = (period or "all").strip().lower()
    if p == "today":
        return query.filter(Attendance.date == func.current_date())
    if p == "yesterday":
        return query.filter(Attendance.date == (func.current_date() - text("INTERVAL '1 day'")))
    if p in {"last7", "7"}:
        return query.filter(Attendance.date >= (func.current_date() - text("INTERVAL '7 days'")))
    if p in {"last30", "30"}:
        return query.filter(Attendance.date >= (func.current_date() - text("INTERVAL '30 days'")))
    return query


def build_student_dashboard_filtered_query(gmail_id, semester, period, subject=""):
    """
    Shared student dashboard query for list + pie + subject-wise data.
    Base filters are always applied in this order:
    1) student gmail_id
    2) student semester
    3) strict period date window
    """
    email = (gmail_id or "").strip()
    sem = canonical_semester(semester)
    q = Attendance.query.join(
        Student, Attendance.student_id == Student.student_id
    ).filter(
        Student.gmail_id == email
    )
    if sem:
        # Strict semester lock on BOTH joined tables to prevent cross-semester bleed.
        q = q.filter(
            Student.semester == sem,
            Attendance.semester == sem
        )
    q = apply_student_dashboard_period_filter(q, period)
    if subject:
        q = q.filter(Attendance.subject.ilike(f"%{subject}%"))
    return q


def canonical_semester(semester):
    sem = (semester or "").strip()
    if not sem:
        return ""
    if sem in {"1", "2", "3", "4", "5", "6"}:
        return sem

    lower = sem.lower()
    for d in ("1", "2", "3", "4", "5", "6"):
        if lower == f"sem {d}" or lower == f"semester {d}" or lower.endswith(f" {d}"):
            return d

    for ch in sem:
        if ch in "123456":
            return ch
    return sem


def get_subjects_for_course_semester(course, semester):
    sem = canonical_semester(semester)
    if not sem:
        return []
    raw_course = (course or "").strip()
    normalized = raw_course.lower().replace(".", "").replace("-", " ").replace("_", " ")
    normalized = " ".join(normalized.split())
    compact = "".join(ch for ch in normalized if ch.isalnum())

    mapped_course = COURSE_KEY_ALIASES.get(normalized) or COURSE_KEY_ALIASES.get(compact) or raw_course
    if mapped_course in SUBJECT_MASTER:
        return SUBJECT_MASTER.get(mapped_course, {}).get(sem, [])

    # Fuzzy fallback: map variants like "B.Sc. IT FY", "BCOM-UG", etc.
    for key in SUBJECT_MASTER.keys():
        key_compact = "".join(ch for ch in key.lower() if ch.isalnum())
        if compact == key_compact or compact.startswith(key_compact) or key_compact in compact:
            return SUBJECT_MASTER.get(key, {}).get(sem, [])
    return []


def apply_attendance_filters(query, period, start_date_str="", end_date_str="", subject="", semester="", reference_date=None):
    start, end = resolve_period_dates(period, start_date_str, end_date_str, reference_date=reference_date)
    if start and end:
        query = query.filter(Attendance.date.between(start, end))
    elif start:
        query = query.filter(Attendance.date >= start)
    elif end:
        query = query.filter(Attendance.date <= end)

    if subject:
        query = query.filter(Attendance.subject.ilike(f"%{subject}%"))
    query = apply_semester_filter(query, semester)
    return query


@app.route('/')
def home():
    # Always show login UI, but don't clear session
    return redirect(url_for('login', force=1))

@app.route('/login', methods=['GET', 'POST'])
def login():
    print(f"\nLogin Route - Current Session: {dict(session)}\n")

    force_login = (request.args.get('force') == '1')
    role = (request.args.get('role') or '').lower()

    # Agar force=1 nahi hai aur pehle se logged in ho to respective dashboard pe bhejo.
    # Guard against old/broken student sessions with no email (prevents redirect loops).
    if session.get('logged_in') and not force_login:
        if session.get('user_type') == 'student':
            if not get_logged_in_student_email():
                session.clear()
                flash('Please login first', 'error')
                return render_template('login.html', role=role)
            return redirect(url_for('student_dashboard'))
        return redirect(url_for('teacher_dashboard'))

    if request.method == 'POST':
        user_type = (request.form.get('user_type') or role or '').lower().strip()
        username = (request.form.get('username') or '').strip()
        password = (request.form.get('password') or '').strip()

        # 1) Teacher credentials ko ALWAYS prioritize karo (radio selection pe depend na kare)
        if username == 'admin' and password == 'admin123':
            session.clear()
            session.permanent = True
            session['user_id'] = 1
            session['user_type'] = 'teacher'
            session['logged_in'] = True
            session['username'] = 'Teacher'
            session.modified = True
            print(f"\nTeacher Session Created: {dict(session)}\n")
            flash('Teacher login successful', 'success')
            return redirect(url_for('teacher_dashboard'))

        # 2) Student login
        if user_type == 'student':
            student = Student.query.filter_by(gmail_id=username, mobile_number=password).first()
            if student:
                session.clear()
                session.permanent = True
                session['gmail_id'] = (student.gmail_id or '').strip()
                session['email'] = (student.gmail_id or '').strip()
                session['user_type'] = 'student'
                session['logged_in'] = True
                session['username'] = student.full_name
                session.modified = True
                print(f"\nStudent Session Created: {dict(session)}\n")
                flash('Login successful!', 'success')
                return redirect(url_for('student_dashboard'))
            else:
                flash('Invalid student credentials', 'error')
        else:
            # Agar user_type galat ya blank aaya ho to
            flash('Please select correct user type', 'error')

    # GET: force=1 pe hamesha login form dikhao (redirect mat karo)
    return render_template('login.html', role=role)

@app.route('/login/student')
def login_student():
    return redirect(url_for('login', role='student', force=1))

@app.route('/login/teacher')
def login_teacher():
    return redirect(url_for('login', role='teacher', force=1))


@app.route('/student_dashboard')
def student_dashboard():
    print(f"\nDashboard Access Attempt - Session: {dict(session)}\n")
    
    # Authentication check
    required_keys = ['logged_in', 'user_type']
    if not all(key in session for key in required_keys):
        print("Missing session keys:", [key for key in required_keys if key not in session])
        flash('Please login first', 'error')
        return redirect(url_for('login'))
    
    if session['user_type'] != 'student':
        print("Invalid user type, redirecting to login")
        flash('Unauthorized access', 'error')
        return redirect(url_for('login'))
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        print("Student session missing email identifier, forcing re-login")
        session.clear()
        flash('Please login first', 'error')
        return redirect(url_for('login'))
    if not session.get('gmail_id'):
        session['gmail_id'] = gmail_id

    # ── Global academic filter: query param overrides session, session overrides DB ──
    # Local override: if ?semester= is explicitly passed, use it and update session.
    qp_semester = canonical_semester(
        request.args.get('semester') or request.form.get('selected_semester') or ''
    )
    _, sess_sem = get_active_filter(gmail_id)

    # Priority: explicit query param > session > DB (handled inside get_student_for_email_semester)
    selected_semester = qp_semester or sess_sem

    # If a local override was provided, persist it to session
    if qp_semester and qp_semester != sess_sem:
        save_active_filter(session.get('active_class', ''), qp_semester)

    selected_period = (request.args.get('period') or 'all').strip().lower()
    selected_subject = (request.args.get('subject') or '').strip()
    student, selected_semester = get_student_for_email_semester(
        gmail_id,
        selected_semester
    )
    if not student:
        print("Student not found in DB, clearing session")
        session.clear()
        flash('Student not found', 'error')
        return redirect(url_for('login'))


    print("Dashboard access granted")

    # ── Resolve semester value ────────────────────────────────────────────────
    semester_value = canonical_semester(student.semester or selected_semester or "")

    # ── Apply global academic filter (session overrides DB row) ──────────────
    active_class, active_sem = get_active_filter(gmail_id)
    if active_sem:
        semester_value = active_sem
    if not semester_value:
        semester_value = selected_semester or "1"

    print(f"[dashboard] Active Class: {active_class!r}")
    print(f"[dashboard] Active Semester: {semester_value!r}")
    print(f"[dashboard] Period: {selected_period!r}  Subject filter: {selected_subject!r}")

    # ── Build attendance query ────────────────────────────────────────────────
    # IMPORTANT: Do NOT filter by SUBJECT_MASTER — master subjects may differ
    # from actual DB subjects, causing zero results.
    # Fetch all records for this student+semester, then let JS handle subject filter.
    records_q = build_student_dashboard_filtered_query(
        gmail_id,
        semester_value,
        selected_period,
        selected_subject
    )

    records = records_q.order_by(Attendance.date.desc(), Attendance.attendance_id.desc()).all()

    total_classes    = len(records)
    attended_classes = sum(1 for r in records if normalize_status(r.status) == "present")
    percentage       = round((attended_classes / total_classes) * 100, 2) if total_classes > 0 else 0
    current_streak   = calculate_current_streak(records)

    print(f"[dashboard] Total Records: {total_classes}  Present: {attended_classes}  Pct: {percentage}%")

    notices = Notice.query.filter_by(is_active=True)\
               .order_by(Notice.is_pinned.desc(), Notice.date_posted.desc())\
               .all()

    initial_records = [{
        "date":      r.date.isoformat() if r.date else "",
        "time":      format_lecture_time(r.time),
        "subject":   r.subject or "",
        "status":    r.status or "",
        "marked_by": r.marked_by or "",
        "remarks":   r.remarks or ""
    } for r in records]

    return render_template('student_dashboard.html',
                           student=student,
                           notices=notices,
                           records=records,
                           initial_records=initial_records,
                           selected_semester=semester_value,
                           percentage=percentage,
                           attended_classes=attended_classes,
                           total_classes=total_classes,
                           current_streak=current_streak)
    

@app.route('/teacher', methods=['GET', 'POST'])
def teacher():
    if 'user_type' not in session or session['user_type'] != 'teacher':
      flash("Please login first as Teacher!", "error")
      return redirect(url_for('login'))
    students = []
    attendance_status = None
    
    # Form se saari values get karein, GET request ke liye None default hoga
    selected_course = request.form.get('selected_course')
    selected_class = request.form.get('selected_class')
    selected_semester = request.form.get('selected_semester')
    selected_subject = request.form.get('selected_subject')
    attendance_time_str = (request.form.get('attendance_time') or '').strip()
    try:
        attendance_time = dt.strptime(attendance_time_str, '%H:%M').time() if attendance_time_str else None
    except ValueError:
        attendance_time = None
    
    # Date ko form se get karein, agar form se nahi aa rahi to aaj ki date lein
    attendance_date_str = request.form.get('attendance_date', date.today().isoformat())
    attendance_date = date.fromisoformat(attendance_date_str)

    if request.method == 'POST' and all([selected_course, selected_class, selected_semester, selected_subject]):
        
        # Check karein ki is date aur subject ki attendance pehle se mark hai ya nahi
        existing_attendance = Attendance.query.filter(
            Attendance.subject == selected_subject, 
            Attendance.date == attendance_date,
            Attendance.marked_time == attendance_time
        ).first()

        if existing_attendance:
            attendance_status = "Already Marked"
            students = [] # Koi student list nahi dikhani
        else:
            attendance_status = "Not Marked Yet"
            # Aapka original logic: Students ko filter karein
            all_students = Student.query.filter_by(
                course=selected_course,
                class_yr=selected_class,
                semester=selected_semester
            ).order_by(Student.student_id).all() # Roll no. se sort karein

            # Aapka unique student wala logic (optional, but good practice)
            student_ids_seen = set()
            unique_students = []
            for s in all_students:
                if s.student_id not in student_ids_seen:
                    unique_students.append(s)
                    student_ids_seen.add(s.student_id)
            students = unique_students

    return render_template(
        'teacher_attendance_mark.html',
        students=students,
        attendance_status=attendance_status,
        selected_course=selected_course,
        selected_class=selected_class,
        selected_semester=selected_semester,
        selected_subject=selected_subject,
        attendance_date=attendance_date.isoformat(),
        attendance_time=attendance_time_str
    )

@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    selected_course = request.form.get('selected_course')
    selected_class = request.form.get('selected_class')
    selected_semester = request.form.get('selected_semester')
    selected_subject = request.form.get('selected_subject')
    attendance_date_str = request.form.get('attendance_date', date.today().isoformat())
    attendance_time_str = (request.form.get('attendance_time') or '').strip()
    attendance_date = date.fromisoformat(attendance_date_str)
    try:
        attendance_time = dt.strptime(attendance_time_str, '%H:%M').time() if attendance_time_str else None
    except ValueError:
        attendance_time = None

    students = Student.query.filter_by(
        course=selected_course,
        class_yr=selected_class,
        semester=selected_semester
    ).all()

    for student in students:
        checkbox_name = f"status_{student.student_id}"
        status = "Present" if checkbox_name in request.form else "Absent"

        existing = Attendance.query.filter_by(
            student_id=student.student_id,
            date=attendance_date,
            subject=selected_subject,
            marked_time=attendance_time
        ).first()

        if not existing:
            new_attendance = Attendance(
                student_id=student.student_id,
                date=attendance_date,
                status=status,
                marked_by="Teacher",
                course=selected_course,
                class_yr=selected_class,
                semester=selected_semester,
                subject=selected_subject,
                marked_time=attendance_time
            )
            db.session.add(new_attendance)

    db.session.commit()

    # Build summary for success page
    total_students = len(students)
    present_count  = sum(
        1 for s in students if f"status_{s.student_id}" in request.form
    )
    absent_count   = total_students - present_count
    attendance_pct = round((present_count / total_students * 100), 1) if total_students > 0 else 0.0

    time_display = ""
    if attendance_time:
        try:
            time_display = attendance_time.strftime("%I:%M %p")
        except Exception:
            time_display = attendance_time_str

    return render_template(
        'success.html',
        message="Attendance saved successfully!",
        summary={
            "course":          selected_course   or "—",
            "class_yr":        selected_class    or "—",
            "semester":        selected_semester or "—",
            "subject":         selected_subject  or "—",
            "date":            attendance_date.strftime("%d %b %Y"),
            "time":            time_display      or "—",
            "total_students":  total_students,
            "present":         present_count,
            "absent":          absent_count,
            "percentage":      attendance_pct,
        }
    )

@app.route('/success')
def success_page():
    return render_template('success.html', message="Attendance saved successfully!", summary=None)

# app.py mein
@app.route('/attendance_summary', methods=['GET', 'POST'])
def attendance_summary():
    student_records = []
    summary_data = {}
    
    today = date.today()
    default_start_date = today - timedelta(days=30)

    # Get raw strings (can be '') 
    start_date_str = (request.form.get('start_date') or '').strip()
    end_date_str   = (request.form.get('end_date') or '').strip()

    # Helper: parse multiple formats or fallback to default
    def parse_or_default(s, default_val):
        if not s:
            return default_val
        # Try ISO (YYYY-MM-DD)
        try:
            return date.fromisoformat(s)
        except ValueError:
            pass
        # Try mm/dd/yyyy
        try:
            return dt.strptime(s, '%m/%d/%Y').date()
        except ValueError:
            pass
        # Try dd/mm/yyyy (just in case)
        try:
            return dt.strptime(s, '%d/%m/%Y').date()
        except ValueError:
            pass
        # Fallback to default if nothing matched
        return default_val

    start_date = parse_or_default(start_date_str, default_start_date)
    end_date   = parse_or_default(end_date_str, today)

    # If user inverted dates, fix it
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    # Form values
    selected_course = request.form.get('selected_course')
    selected_class = request.form.get('selected_class')
    selected_semester = request.form.get('selected_semester')
    selected_subject = request.form.get('selected_subject')

    if request.method == 'POST' and all([selected_course, selected_class, selected_semester, selected_subject]):
        students_in_class = Student.query.filter_by(
            course=selected_course, 
            class_yr=selected_class,
            semester=selected_semester
        ).all()
        student_ids = [s.student_id for s in students_in_class]

        if student_ids:
            attendance_query = db.session.query(
                Attendance.student_id,
                func.count(Attendance.attendance_id).label('total_days'),
                func.sum(case((Attendance.status == 'Present', 1), else_=0)).label('present_days')
            ).filter(
                Attendance.student_id.in_(student_ids),
                Attendance.subject == selected_subject,
                Attendance.date.between(start_date, end_date)
            ).group_by(Attendance.student_id).all()

            attendance_map = {r.student_id: r for r in attendance_query}
            
            total_present_class = 0
            total_days_class = 0
            low_attendance_count = 0

            for student in students_in_class:
                record = attendance_map.get(student.student_id)
                if record and record.total_days > 0:
                    total = record.total_days
                    present = record.present_days
                    absent = total - present
                    percentage = (present / total * 100)

                    if percentage < 75:
                        low_attendance_count += 1

                    total_present_class += present
                    total_days_class += total

                    student_records.append({
                        'name': student.full_name,
                        'roll_no': student.student_id,
                        'total': total,
                        'present': present,
                        'absent': absent,
                        'percentage': round(percentage, 2)
                    })

            overall_percentage = (total_present_class / total_days_class * 100) if total_days_class > 0 else 0
            summary_data = {
                'total_students': len(students_in_class),
                'overall_percentage': round(overall_percentage, 2),
                'low_attendance_count': low_attendance_count,
                # Optional: totals for charts
                'present_total': int(total_present_class),
                'absent_total': int(total_days_class - total_present_class)
            }

    # IMPORTANT: Template ko valid ISO values bhejo (so inputs fill ho jaye)
    return render_template(
        'teacher_attendance_summary.html', 
        student_records=student_records,
        summary_data=summary_data,
        selected_course=selected_course, 
        selected_class=selected_class,
        selected_semester=selected_semester, 
        selected_subject=selected_subject,
        start_date=start_date.isoformat(),  # <-- always a valid date string
        end_date=end_date.isoformat()       # <-- always a valid date string
    )
# app.py mein

@app.route('/export_attendance')
def export_attendance():
    # URL se saare filters get karein
    selected_course = request.args.get('course')
    selected_class = request.args.get('s_class')
    selected_semester = request.args.get('semester')
    selected_subject = request.args.get('subject')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not all([selected_course, selected_class, selected_semester, selected_subject, start_date_str, end_date_str]):
        return "Missing filters for export.", 400

    start_date = date.fromisoformat(start_date_str)
    end_date = date.fromisoformat(end_date_str)

    # Wahi database query jo summary page par hai
    students_in_class = Student.query.filter_by(
        course=selected_course, 
        class_yr=selected_class,
        semester=selected_semester
    ).all()
    student_ids = [s.student_id for s in students_in_class]

    if not student_ids:
        return "No students found for export.", 404

    attendance_query = db.session.query(
        Attendance.student_id,
        func.count(Attendance.attendance_id).label('total_days'),
        func.sum(case((Attendance.status == 'Present', 1), else_=0)).label('present_days')
    ).filter(
        Attendance.student_id.in_(student_ids),
        Attendance.subject == selected_subject,
        Attendance.date.between(start_date, end_date)
    ).group_by(Attendance.student_id).all()

    attendance_map = {record.student_id: record for record in attendance_query}

    # CSV file ko memory mein banayein
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Roll No', 'Name', 'Total Days', 'Present', 'Absent', 'Attendance %'])

    for student in students_in_class:
        record = attendance_map.get(student.student_id)
        if record and record.total_days > 0:
            total = record.total_days
            present = record.present_days
            absent = total - present
            percentage = round((present / total * 100), 2)
            writer.writerow([student.student_id, student.full_name, total, present, absent, f"{percentage}%"])

    output.seek(0)
    
    # --- YAHAN PAR BADLAAV KIYA GAYA HAI ---
    # `today` variable ko define karein
    today = date.today()
    filename = f"attendance_{selected_course.replace(' ', '_')}_{selected_class}_{today.strftime('%Y-%m-%d')}.csv"

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


# ─────────────────────────────────────────────────────────────────────────────
# /export_full_report  →  Professional PDF attendance report (ReportLab)
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/export_full_report')
def export_full_report():
    """Generate a professional PDF attendance report with summary + full table."""
    if 'user_type' not in session or session['user_type'] != 'teacher':
        flash("Please login first as Teacher!", "error")
        return redirect(url_for('login'))

    # ── 1. Collect query-string filters ──────────────────────────────────────
    selected_course   = request.args.get('course',    '').strip()
    selected_class    = request.args.get('s_class',   '').strip()
    selected_semester = request.args.get('semester',  '').strip()
    selected_subject  = request.args.get('subject',   '').strip()
    start_date_str    = request.args.get('start_date','').strip()
    end_date_str      = request.args.get('end_date',  '').strip()

    if not all([selected_course, selected_class, selected_semester,
                selected_subject, start_date_str, end_date_str]):
        return "Missing filters for PDF export.", 400

    try:
        start_date = date.fromisoformat(start_date_str)
        end_date   = date.fromisoformat(end_date_str)
    except ValueError:
        return "Invalid date format.", 400

    # ── 2. Database query (same logic as export_attendance) ──────────────────
    students_in_class = Student.query.filter_by(
        course=selected_course,
        class_yr=selected_class,
        semester=selected_semester
    ).order_by(Student.student_id).all()

    student_ids = [s.student_id for s in students_in_class]
    if not student_ids:
        return "No students found for the selected filters.", 404

    att_rows = db.session.query(
        Attendance.student_id,
        func.count(Attendance.attendance_id).label('total_days'),
        func.sum(case((Attendance.status == 'Present', 1), else_=0)).label('present_days')
    ).filter(
        Attendance.student_id.in_(student_ids),
        Attendance.subject == selected_subject,
        Attendance.date.between(start_date, end_date)
    ).group_by(Attendance.student_id).all()

    att_map = {r.student_id: r for r in att_rows}

    # Build student records list
    records = []
    total_present_all = 0
    total_days_all    = 0
    low_count         = 0

    for s in students_in_class:
        r = att_map.get(s.student_id)
        if r and r.total_days > 0:
            total   = int(r.total_days)
            present = int(r.present_days)
            absent  = total - present
            pct     = round(present / total * 100, 2)
            total_present_all += present
            total_days_all    += total
            if pct < 75:
                low_count += 1
            records.append({
                'id':      s.student_id,
                'name':    s.full_name or '—',
                'total':   total,
                'present': present,
                'absent':  absent,
                'pct':     pct,
            })

    overall_pct = round(total_present_all / total_days_all * 100, 2) if total_days_all else 0.0

    # ── 3. Build PDF with ReportLab ──────────────────────────────────────────
    from io import BytesIO
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether
    )
    from reportlab.lib                import colors
    from reportlab.lib.styles         import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units          import inch, cm
    from reportlab.lib.pagesizes      import A4
    from reportlab.lib.enums          import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.graphics.shapes    import Drawing, Rect, String, Circle
    from reportlab.graphics.charts.piecharts  import Pie
    from reportlab.graphics.charts.barcharts  import VerticalBarChart
    from reportlab.graphics           import renderPDF

    # Colour palette (matches page theme)
    C_PRIMARY   = colors.HexColor('#4361ee')
    C_SECONDARY = colors.HexColor('#3f37c9')
    C_SUCCESS   = colors.HexColor('#4cc9f0')
    C_DANGER    = colors.HexColor('#e63946')
    C_WARNING   = colors.HexColor('#f72585')
    C_GRAY_DARK = colors.HexColor('#343a40')
    C_GRAY_MID  = colors.HexColor('#6c757d')
    C_GRAY_LITE = colors.HexColor('#f1f5f9')
    C_WHITE     = colors.white
    C_HEADER_BG = colors.HexColor('#4361ee')

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=0.65*inch, rightMargin=0.65*inch,
        topMargin=0.6*inch,   bottomMargin=0.6*inch,
        title="Attendance Report",
        author="Navneet College"
    )
    W = doc.width   # usable width

    # ── Styles ────────────────────────────────────────────────────────────────
    base = getSampleStyleSheet()

    def style(name, **kw):
        s = ParagraphStyle(name, parent=base['Normal'], **kw)
        return s

    sTitle    = style('sTitle',    fontName='Helvetica-Bold', fontSize=18,
                      textColor=C_WHITE, alignment=TA_CENTER, leading=22)
    sSubtitle = style('sSubtitle', fontName='Helvetica',      fontSize=10,
                      textColor=colors.HexColor('#c7d2fe'), alignment=TA_CENTER, leading=14)
    sSection  = style('sSection',  fontName='Helvetica-Bold', fontSize=12,
                      textColor=C_PRIMARY, spaceBefore=14, spaceAfter=6)
    sBody     = style('sBody',     fontName='Helvetica',      fontSize=9,
                      textColor=C_GRAY_DARK, leading=13)
    sSmall    = style('sSmall',    fontName='Helvetica',      fontSize=8,
                      textColor=C_GRAY_MID, leading=11)
    sCenter   = style('sCenter',   fontName='Helvetica',      fontSize=9,
                      textColor=C_GRAY_DARK, alignment=TA_CENTER)
    sFooter   = style('sFooter',   fontName='Helvetica',      fontSize=8,
                      textColor=C_GRAY_MID, alignment=TA_CENTER)

    elems = []

    # ── 3a. Gradient-style header banner ─────────────────────────────────────
    def make_header_banner():
        d = Drawing(W, 90)
        # background rectangle
        d.add(Rect(0, 0, W, 90, fillColor=C_PRIMARY, strokeColor=None))
        # accent strip
        d.add(Rect(0, 0, W, 6, fillColor=C_SECONDARY, strokeColor=None))
        # decorative circle
        d.add(Circle(W - 50, 55, 38, fillColor=colors.HexColor('#3a0ca3'),
                     strokeColor=None))
        d.add(Circle(W - 50, 55, 22, fillColor=colors.HexColor('#4361ee'),
                     strokeColor=None))
        # title text
        d.add(String(W/2, 56, "ATTENDANCE ANALYTICS REPORT",
                     fontName='Helvetica-Bold', fontSize=16,
                     fillColor=colors.white, textAnchor='middle'))
        d.add(String(W/2, 38, "Navneet College of Arts, Science & Commerce",
                     fontName='Helvetica', fontSize=10,
                     fillColor=colors.HexColor('#c7d2fe'), textAnchor='middle'))
        d.add(String(W/2, 22, f"Generated on {date.today().strftime('%d %B %Y')}",
                     fontName='Helvetica', fontSize=8,
                     fillColor=colors.HexColor('#a5b4fc'), textAnchor='middle'))
        return d

    elems.append(make_header_banner())
    elems.append(Spacer(1, 14))

    # ── 3b. Filter details table ──────────────────────────────────────────────
    elems.append(Paragraph("Report Filters", sSection))
    filter_data = [
        ['Course', selected_course,   'Class',    selected_class],
        ['Semester', selected_semester,'Subject',  selected_subject],
        ['From Date', start_date_str,  'To Date',  end_date_str],
    ]
    filter_col_w = [W*0.14, W*0.36, W*0.14, W*0.36]
    ft = Table(filter_data, colWidths=filter_col_w, hAlign='LEFT')
    ft.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,-1), C_GRAY_LITE),
        ('BACKGROUND',  (0,0), (0,-1), colors.HexColor('#e0e7ff')),
        ('BACKGROUND',  (2,0), (2,-1), colors.HexColor('#e0e7ff')),
        ('FONTNAME',    (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME',    (2,0), (2,-1), 'Helvetica-Bold'),
        ('FONTNAME',    (1,0), (1,-1), 'Helvetica'),
        ('FONTNAME',    (3,0), (3,-1), 'Helvetica'),
        ('FONTSIZE',    (0,0), (-1,-1), 9),
        ('TEXTCOLOR',   (0,0), (0,-1), C_PRIMARY),
        ('TEXTCOLOR',   (2,0), (2,-1), C_PRIMARY),
        ('TEXTCOLOR',   (1,0), (-1,-1), C_GRAY_DARK),
        ('GRID',        (0,0), (-1,-1), 0.5, colors.HexColor('#c7d2fe')),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [C_GRAY_LITE, colors.white]),
        ('TOPPADDING',  (0,0), (-1,-1), 7),
        ('BOTTOMPADDING',(0,0),(-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING',(0,0), (-1,-1), 10),
        ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
        ('ROUNDEDCORNERS', [4]),
    ]))
    elems.append(ft)
    elems.append(Spacer(1, 16))

    # ── 3c. KPI summary cards (3 side-by-side) ───────────────────────────────
    elems.append(Paragraph("Summary", sSection))

    def kpi_cell(label, value, sub, bg, accent):
        """Returns a mini-table acting as a KPI card."""
        inner = Table([
            [Paragraph(f'<font color="{accent.hexval()}" size="20"><b>{value}</b></font>', sCenter)],
            [Paragraph(f'<b>{label}</b>', sCenter)],
            [Paragraph(sub, sSmall)],
        ], colWidths=[W/3 - 12])
        inner.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,-1), bg),
            ('TOPPADDING',   (0,0), (-1,-1), 10),
            ('BOTTOMPADDING',(0,0), (-1,-1), 10),
            ('LEFTPADDING',  (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('ALIGN',        (0,0), (-1,-1), 'CENTER'),
            ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
            ('ROUNDEDCORNERS', [6]),
            ('BOX',          (0,0), (-1,-1), 1.5, accent),
        ]))
        return inner

    kpi_row = Table([[
        kpi_cell("Overall Attendance", f"{overall_pct}%",
                 "Average attendance rate",
                 colors.HexColor('#eef2ff'), C_PRIMARY),
        kpi_cell("Total Students", str(len(records)),
                 "Registered in class",
                 colors.HexColor('#ecfeff'), C_SUCCESS),
        kpi_cell("Low Attendance", str(low_count),
                 "Students below 75%",
                 colors.HexColor('#fff1f2'), C_DANGER),
    ]], colWidths=[W/3, W/3, W/3], hAlign='LEFT')
    kpi_row.setStyle(TableStyle([
        ('LEFTPADDING',  (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING',   (0,0), (-1,-1), 0),
        ('BOTTOMPADDING',(0,0), (-1,-1), 0),
    ]))
    elems.append(kpi_row)
    elems.append(Spacer(1, 18))

    # ── 3d. Charts (Pie + Bar) side by side ──────────────────────────────────
    elems.append(Paragraph("Attendance Charts", sSection))

    # Pie chart
    def make_pie():
        d = Drawing(220, 160)
        pie = Pie()
        pie.x, pie.y = 30, 20
        pie.width = pie.height = 120
        total_p = sum(r['present'] for r in records)
        total_a = sum(r['absent']  for r in records)
        pie.data   = [total_p or 1, total_a or 1]
        pie.labels = [f'Present\n{total_p}', f'Absent\n{total_a}']
        pie.slices[0].fillColor = C_SUCCESS
        pie.slices[1].fillColor = C_WARNING
        pie.slices[0].strokeColor = colors.white
        pie.slices[1].strokeColor = colors.white
        pie.slices[0].strokeWidth = 2
        pie.slices[1].strokeWidth = 2
        pie.slices[0].popout = 5
        pie.sideLabels = True
        pie.simpleLabels = False
        d.add(pie)
        d.add(String(110, 148, "Present vs Absent",
                     fontName='Helvetica-Bold', fontSize=9,
                     fillColor=C_GRAY_DARK, textAnchor='middle'))
        return d

    # Bar chart (performance bands)
    def make_bar():
        d = Drawing(260, 160)
        bc = VerticalBarChart()
        bc.x, bc.y = 30, 20
        bc.width, bc.height = 210, 110
        excellent = sum(1 for r in records if r['pct'] >= 90)
        good      = sum(1 for r in records if 75 <= r['pct'] < 90)
        average   = sum(1 for r in records if 50 <= r['pct'] < 75)
        poor      = sum(1 for r in records if r['pct'] < 50)
        bc.data   = [[excellent, good, average, poor]]
        bc.categoryAxis.categoryNames = ['>90%', '75-89%', '50-74%', '<50%']
        bc.bars[0].fillColor = C_PRIMARY
        bc.bars[0].strokeColor = None
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueStep = max(1, max(excellent, good, average, poor, 1) // 4)
        bc.categoryAxis.labels.fontName  = 'Helvetica'
        bc.categoryAxis.labels.fontSize  = 8
        bc.categoryAxis.labels.fillColor = C_GRAY_DARK
        bc.valueAxis.labels.fontName     = 'Helvetica'
        bc.valueAxis.labels.fontSize     = 8
        bc.groupSpacing = 10
        d.add(bc)
        d.add(String(145, 148, "Performance Distribution",
                     fontName='Helvetica-Bold', fontSize=9,
                     fillColor=C_GRAY_DARK, textAnchor='middle'))
        return d

    chart_row = Table([[make_pie(), make_bar()]],
                      colWidths=[W*0.42, W*0.58], hAlign='LEFT')
    chart_row.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,-1), colors.white),
        ('BOX',          (0,0), (-1,-1), 0.5, colors.HexColor('#e0e7ff')),
        ('TOPPADDING',   (0,0), (-1,-1), 6),
        ('BOTTOMPADDING',(0,0), (-1,-1), 6),
        ('LEFTPADDING',  (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('ROUNDEDCORNERS', [6]),
    ]))
    elems.append(chart_row)
    elems.append(Spacer(1, 18))

    # ── 3e. Full student table ────────────────────────────────────────────────
    elems.append(Paragraph("Detailed Student Attendance", sSection))

    # Table header
    th_style = ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=8,
                               textColor=colors.white, alignment=TA_CENTER)
    td_style = ParagraphStyle('td', fontName='Helvetica', fontSize=8,
                               textColor=C_GRAY_DARK, alignment=TA_CENTER)

    col_w = [W*0.08, W*0.28, W*0.10, W*0.10, W*0.10, W*0.14, W*0.20]
    tbl_data = [[
        Paragraph('Roll No', th_style),
        Paragraph('Student Name', th_style),
        Paragraph('Total', th_style),
        Paragraph('Present', th_style),
        Paragraph('Absent', th_style),
        Paragraph('Attend %', th_style),
        Paragraph('Status', th_style),
    ]]

    for i, r in enumerate(records):
        if r['pct'] >= 75:
            status_txt = 'Good'
            status_col = colors.HexColor('#0e7490')
        elif r['pct'] >= 50:
            status_txt = 'Warning'
            status_col = colors.HexColor('#be185d')
        else:
            status_txt = 'Critical'
            status_col = C_DANGER

        pct_col = (colors.HexColor('#0e7490') if r['pct'] >= 75
                   else C_WARNING if r['pct'] >= 50 else C_DANGER)

        name_style = ParagraphStyle(f'n{i}', fontName='Helvetica-Bold',
                                     fontSize=8, textColor=C_GRAY_DARK)
        pct_style  = ParagraphStyle(f'p{i}', fontName='Helvetica-Bold',
                                     fontSize=8, textColor=pct_col,
                                     alignment=TA_CENTER)
        st_style   = ParagraphStyle(f's{i}', fontName='Helvetica-Bold',
                                     fontSize=8, textColor=status_col,
                                     alignment=TA_CENTER)

        tbl_data.append([
            Paragraph(str(r['id']),      td_style),
            Paragraph(r['name'],         name_style),
            Paragraph(str(r['total']),   td_style),
            Paragraph(str(r['present']), td_style),
            Paragraph(str(r['absent']),  td_style),
            Paragraph(f"{r['pct']}%",    pct_style),
            Paragraph(status_txt,        st_style),
        ])

    # Alternating row colours
    row_styles = [
        ('BACKGROUND',   (0,0), (-1,0),  C_HEADER_BG),
        ('TEXTCOLOR',    (0,0), (-1,0),  colors.white),
        ('FONTNAME',     (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',     (0,0), (-1,-1), 8),
        ('GRID',         (0,0), (-1,-1), 0.4, colors.HexColor('#c7d2fe')),
        ('TOPPADDING',   (0,0), (-1,-1), 6),
        ('BOTTOMPADDING',(0,0), (-1,-1), 6),
        ('LEFTPADDING',  (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',        (0,0), (-1,-1), 'CENTER'),
        ('ALIGN',        (1,0), (1,-1),  'LEFT'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1),
         [colors.white, colors.HexColor('#f5f7ff')]),
    ]
    # Highlight critical rows
    for idx, r in enumerate(records, start=1):
        if r['pct'] < 50:
            row_styles.append(('BACKGROUND', (0,idx), (-1,idx),
                                colors.HexColor('#fff1f2')))
        elif r['pct'] < 75:
            row_styles.append(('BACKGROUND', (0,idx), (-1,idx),
                                colors.HexColor('#fff7ed')))

    data_tbl = Table(tbl_data, colWidths=col_w, repeatRows=1, hAlign='LEFT')
    data_tbl.setStyle(TableStyle(row_styles))
    elems.append(data_tbl)
    elems.append(Spacer(1, 20))

    # ── 3f. Footer ────────────────────────────────────────────────────────────
    elems.append(HRFlowable(width=W, thickness=0.5,
                             color=colors.HexColor('#c7d2fe')))
    elems.append(Spacer(1, 6))
    elems.append(Paragraph(
        f"Navneet College of Arts, Science & Commerce &nbsp;|&nbsp; "
        f"Report generated: {date.today().strftime('%d %B %Y')} &nbsp;|&nbsp; "
        f"Confidential — for internal use only",
        sFooter
    ))

    # ── 4. Build & stream ─────────────────────────────────────────────────────
    doc.build(elems)
    buf.seek(0)

    safe_course  = selected_course.replace(' ', '_')
    safe_subject = selected_subject.replace(' ', '_')[:20]
    pdf_filename = (f"Attendance_Report_{safe_course}_{selected_class}"
                    f"_Sem{selected_semester}_{date.today().strftime('%Y%m%d')}.pdf")

    return send_file(
        buf,
        as_attachment=True,
        download_name=pdf_filename,
        mimetype='application/pdf'
    )


# ================================teacher dashboard ka analysis section hai
# API: Course-wise attendance (Present vs Absent)
# Default: ALL-TIME unless start_date/end_date/range passed
# Supports range in {all, week, month, quarter, year, custom}
# Params: start_date, end_date (YYYY-MM-DD), class_yr, semester, subject, range
# ================================
@app.get('/api/teacher-dashboard/course-attendance')
def api_course_attendance():
    if 'user_type' not in session or session['user_type'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    def parse_date(s):
        try: return date.fromisoformat(s) if s else None
        except Exception: return None

    try:
        # Filters
        today = date.today()
        range_preset = (request.args.get('range') or 'all').lower()

        start = parse_date(request.args.get('start_date'))
        end   = parse_date(request.args.get('end_date'))

        # If range preset is provided and not custom/all, compute start/end
        if range_preset in ('week','month','quarter','year'):
            end = today
            if range_preset == 'week':
                start = today - timedelta(days=6)   # last 7 days
            elif range_preset == 'month':
                start = today.replace(day=1)        # this month
            elif range_preset == 'quarter':
                q_start_month = ((today.month - 1)//3)*3 + 1
                start = date(today.year, q_start_month, 1)
            elif range_preset == 'year':
                start = date(today.year, 1, 1)
        elif range_preset == 'all':
            start = start if start else None
            end = end if end else None
        # range=custom just uses given start/end (or none if blank -> all-time)

        class_yr = request.args.get('class_yr')
        semester = request.args.get('semester')
        subject  = request.args.get('subject')

        q = db.session.query(
            func.coalesce(Attendance.course, 'Unknown').label('course'),
            func.sum(
                case((func.lower(Attendance.status).in_(['present', 'p', '1', 'true']), 1), else_=0)
            ).label('present'),
            func.sum(
                case((func.lower(Attendance.status).in_(['absent', 'a', '0', 'false']), 1), else_=0)
            ).label('absent')
        )

        # Apply filters
        if start and end:
            q = q.filter(Attendance.date.between(start, end))
        elif start:
            q = q.filter(Attendance.date >= start)
        elif end:
            q = q.filter(Attendance.date <= end)
        # else: all-time

        if class_yr:
            q = q.filter(Attendance.class_yr == class_yr)
        if semester:
            q = q.filter(Attendance.semester == semester)
        if subject:
            q = q.filter(Attendance.subject == subject)

        rows = q.group_by('course').order_by('course').all()

        labels, present, absent = [], [], []
        for course, p, a in rows:
            labels.append(course or 'Unknown')
            present.append(int(p or 0))
            absent.append(int(a or 0))

        return jsonify({
            "filters": {
                "start_date": start.isoformat() if start else None,
                "end_date": end.isoformat() if end else None,
                "range": range_preset,
                "class_yr": class_yr, "semester": semester, "subject": subject
            },
            "labels": labels,
            "present": present,
            "absent": absent,
            "totals": {
                "present": int(sum(present)),
                "absent": int(sum(absent))
            }
        })
    except Exception as e:
        print("COURSE ATTENDANCE API ERROR:", e)
        return jsonify({"labels": [], "present": [], "absent": [], "totals": {"present": 0, "absent": 0}}), 500  
    
    
# ===================== Dashboard Analytics Helpers =====================
def _parse_date(s):
    try:
        return date.fromisoformat(s) if s else None
    except Exception:
        return None

def _resolve_range_and_filters():
    # range presets: all, week, month, quarter, year, custom
    args = request.args
    today = date.today()
    preset = (args.get('range') or 'all').lower()

    start = _parse_date(args.get('start_date'))
    end   = _parse_date(args.get('end_date'))

    if preset in ('week','month','quarter','year'):
        end = today
        if preset == 'week':
            start = today - timedelta(days=6)
        elif preset == 'month':
            start = today.replace(day=1)
        elif preset == 'quarter':
            q_start_month = ((today.month - 1)//3)*3 + 1
            start = date(today.year, q_start_month, 1)
        elif preset == 'year':
            start = date(today.year, 1, 1)
    # preset == 'custom' => use given start/end
    # preset == 'all' => no dates => all-time

    course   = args.get('course')
    class_yr = args.get('class_yr')
    semester = args.get('semester')
    subject  = args.get('subject')

    filters = []
    if start and end:
        filters.append(Attendance.date.between(start, end))
    elif start:
        filters.append(Attendance.date >= start)
    elif end:
        filters.append(Attendance.date <= end)

    if course:
        filters.append(Attendance.course == course)
    if class_yr:
        filters.append(Attendance.class_yr == class_yr)
    if semester:
        filters.append(Attendance.semester == semester)
    if subject:
        filters.append(Attendance.subject == subject)

    return {
        "start": start, "end": end, "preset": preset,
        "course": course, "class_yr": class_yr, "semester": semester, "subject": subject,
        "filters": filters
    }

# ===================== KPIs + Snapshot =====================
@app.get('/api/teacher-dashboard/analytics/kpis')
def analytics_kpis():
    if 'user_type' not in session or session['user_type'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        spec = _resolve_range_and_filters()
        f = spec['filters'][:]

        present_expr = func.sum(case((func.lower(Attendance.status).in_(['present','p','1','true']), 1), else_=0))
        absent_expr  = func.sum(case((func.lower(Attendance.status).in_(['absent','a','0','false']), 1), else_=0))

        q = db.session.query(
            present_expr.label('present'),
            absent_expr.label('absent'),
            func.count(Attendance.attendance_id).label('total')
        )
        if f: q = q.filter(*f)
        row = q.one()
        present = int(row.present or 0); absent = int(row.absent or 0); total = int(row.total or 0)

        # Distinct class dates in scope
        dq = db.session.query(func.count(func.distinct(Attendance.date)))
        if f: dq = dq.filter(*f)
        total_days = dq.scalar() or 0

        # Students in scope (Student filters if provided)
        sf = []
        if spec['course']: sf.append(Student.course == spec['course'])
        if spec['class_yr']: sf.append(Student.class_yr == spec['class_yr'])
        if spec['semester']: sf.append(Student.semester == spec['semester'])
        sq = db.session.query(func.count(func.distinct(Student.student_id)))
        if sf: sq = sq.filter(*sf)
        students = sq.scalar() or 0

        avg = round((present / total * 100), 2) if total > 0 else 0.0

        return jsonify({
            "present": present, "absent": absent, "total": total,
            "avg_attendance_percent": avg,
            "total_days": int(total_days),
            "students": int(students),
            "range": {
                "start_date": spec['start'].isoformat() if spec['start'] else None,
                "end_date": spec['end'].isoformat() if spec['end'] else None,
                "preset": spec['preset']
            }
        })
    except Exception as e:
        print("KPIS API ERROR:", e)
        return jsonify({"present":0,"absent":0,"total":0,"avg_attendance_percent":0,"total_days":0,"students":0}), 500

# ===================== Student-wise (Top 15 lowest %) =====================
@app.get('/api/teacher-dashboard/analytics/student-wise')
def analytics_student_wise():
    if 'user_type' not in session or session['user_type'] != 'teacher':
        return jsonify({'error':'Unauthorized'}), 401
    try:
        spec = _resolve_range_and_filters()
        f = spec['filters'][:]

        sq = db.session.query(
            Attendance.student_id.label('sid'),
            func.sum(case((func.lower(Attendance.status).in_(['present','p','1','true']), 1), else_=0)).label('present'),
            func.count(Attendance.attendance_id).label('total')
        )
        if f: sq = sq.filter(*f)
        if spec['course'] or spec['class_yr'] or spec['semester']:
            sq = sq.join(Student, Student.student_id == Attendance.student_id)
            if spec['course']: sq = sq.filter(Student.course == spec['course'])
            if spec['class_yr']: sq = sq.filter(Student.class_yr == spec['class_yr'])
            if spec['semester']: sq = sq.filter(Student.semester == spec['semester'])
        sq = sq.group_by(Attendance.student_id).subquery()

        q = db.session.query(
            Student.student_id, Student.full_name,
            sq.c.present, sq.c.total
        ).join(sq, sq.c.sid == Student.student_id)

        rows = q.all()
        data = []
        for sid, name, pres, tot in rows:
            pres = int(pres or 0); tot = int(tot or 0)
            pct = round((pres/tot*100), 2) if tot>0 else 0.0
            data.append({
                "student_id": sid,
                "name": name or f"SID {sid}",
                "present": pres,
                "total": tot,
                "percentage": pct
            })
        limit = int(request.args.get('limit', 15))
        data_sorted = sorted(data, key=lambda x: x['percentage'])[:limit]

        return jsonify({
            "labels": [f"{d['student_id']} - {d['name']}" for d in data_sorted],
            "percentages": [d['percentage'] for d in data_sorted],
            "present": [d['present'] for d in data_sorted],
            "totals": [d['total'] for d in data_sorted]
        })
    except Exception as e:
        print("STUDENT-WISE API ERROR:", e)
        return jsonify({"labels":[],"percentages":[],"present":[],"totals":[]}), 500

# ===================== Trend by Day =====================
@app.get('/api/teacher-dashboard/analytics/trend')
def analytics_trend():
    if 'user_type' not in session or session['user_type'] != 'teacher':
        return jsonify({'error':'Unauthorized'}), 401
    try:
        spec = _resolve_range_and_filters()
        f = spec['filters'][:]

        present_expr = func.sum(case((func.lower(Attendance.status).in_(['present','p','1','true']), 1), else_=0))
        absent_expr  = func.sum(case((func.lower(Attendance.status).in_(['absent','a','0','false']), 1), else_=0))

        q = db.session.query(
            Attendance.date,
            present_expr.label('present'),
            absent_expr.label('absent')
        )
        if f: q = q.filter(*f)
        q = q.group_by(Attendance.date).order_by(Attendance.date.asc())

        rows = q.all()
        labels = [r[0].isoformat() for r in rows]
        present = [int(r[1] or 0) for r in rows]
        absent  = [int(r[2] or 0) for r in rows]
        return jsonify({"labels":labels, "present":present, "absent":absent})
    except Exception as e:
        print("TREND API ERROR:", e)
        return jsonify({"labels":[],"present":[],"absent":[]}), 500

# ===================== Heatmap: Subject x Week =====================
@app.get('/api/teacher-dashboard/analytics/heatmap')
def analytics_heatmap():
    if 'user_type' not in session or session['user_type'] != 'teacher':
        return jsonify({'error':'Unauthorized'}), 401
    try:
        spec = _resolve_range_and_filters()
        f = spec['filters'][:]

        week_start = cast(func.date_trunc('week', Attendance.date), Date)

        present_expr = func.sum(case((func.lower(Attendance.status).in_(['present','p','1','true']), 1), else_=0))
        total_expr   = func.count(Attendance.attendance_id)

        q = db.session.query(
            func.coalesce(Attendance.subject, 'N/A').label('subject'),
            week_start.label('wstart'),
            present_expr.label('present'),
            total_expr.label('total')
        )
        if f: q = q.filter(*f)
        q = q.group_by('subject','wstart').order_by('subject', 'wstart')
        rows = q.all()

        subjects = sorted(list({r[0] for r in rows}))
        weeks = sorted(list({r[1] for r in rows}))
        week_labels = [w.isoformat() for w in weeks]

        cells = []
        for sub, w, p, t in rows:
            pct = round((int(p or 0)/int(t or 1))*100, 2) if t else 0
            cells.append({"x": w.isoformat(), "y": sub, "v": pct})

        return jsonify({"subjects": subjects, "weeks": week_labels, "cells": cells})
    except Exception as e:
        print("HEATMAP API ERROR:", e)
        return jsonify({"subjects":[],"weeks":[],"cells":[]}), 500    
    
        

@app.route('/notice')
def notice():
    return render_template("admin_notice_add.html")  # Dummy notice page

# ─── Student: Request Transcript ─────────────────────────────────────────────
@app.route('/request_transcript', methods=['POST'])
def request_transcript():
    """Student submits a transcript request — inserts row with status=Pending."""
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    student = Student.query.filter(
        func.lower(func.coalesce(Student.gmail_id, "")) == gmail_id.lower()
    ).order_by(Student.student_id.asc()).first()
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    # Prevent duplicate pending requests
    existing = TranscriptRequest.query.filter_by(
        student_id=student.student_id,
        status='Pending'
    ).first()
    if existing:
        return jsonify({
            'success': False,
            'message': 'You already have a pending transcript request (Ref #{}).'.format(existing.id)
        }), 400

    # Use global academic filter for class/semester on the request row
    active_class, active_sem = get_active_filter(gmail_id)
    req_class_yr = active_class or student.class_yr or ''
    req_semester = active_sem   or canonical_semester(student.semester or '') or student.semester or ''

    try:
        req = TranscriptRequest(
            student_id   = student.student_id,
            student_name = student.full_name or '',
            course       = student.course or '',
            class_yr     = req_class_yr,
            semester     = req_semester,
            status       = 'Pending',
        )
        db.session.add(req)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Transcript request submitted successfully.',
            'request_id': req.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500


# ─── Teacher: Pending Transcript Count (sidebar badge) ───────────────────────
@app.route('/teacher/transcripts/pending-count')
def teacher_transcript_pending_count():
    if 'user_type' not in session or session['user_type'] != 'teacher':
        return jsonify({'count': 0})
    try:
        count = TranscriptRequest.query.filter_by(status='Pending').count()
        return jsonify({'count': count})
    except Exception:
        return jsonify({'count': 0})


# ─── Teacher: View All Transcript Requests ────────────────────────────────────
@app.route('/teacher/transcripts')
def teacher_transcripts():
    if 'user_type' not in session or session['user_type'] != 'teacher':
        flash('Please login first as Teacher!', 'error')
        return redirect(url_for('login'))

    status_filter = request.args.get('status', 'all').strip().lower()

    q = TranscriptRequest.query.order_by(TranscriptRequest.requested_at.desc())
    if status_filter == 'pending':
        q = q.filter(TranscriptRequest.status == 'Pending')
    elif status_filter == 'approved':
        q = q.filter(TranscriptRequest.status == 'Approved')
    elif status_filter == 'rejected':
        q = q.filter(TranscriptRequest.status == 'Rejected')

    requests_list = q.all()

    counts = {
        'all':      TranscriptRequest.query.count(),
        'pending':  TranscriptRequest.query.filter_by(status='Pending').count(),
        'approved': TranscriptRequest.query.filter_by(status='Approved').count(),
        'rejected': TranscriptRequest.query.filter_by(status='Rejected').count(),
    }

    return render_template(
        'teacher_transcript.html',
        requests_list  = requests_list,
        status_filter  = status_filter,
        counts         = counts,
    )


# ─── Teacher: Approve / Reject Transcript Request ────────────────────────────
@app.route('/teacher/transcripts/<int:req_id>/update', methods=['POST'])
def teacher_transcript_update(req_id):
    if 'user_type' not in session or session['user_type'] != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    tr = TranscriptRequest.query.get_or_404(req_id)

    data       = request.get_json(silent=True) or {}
    new_status = (data.get('status') or '').strip()
    remarks    = (data.get('remarks') or '').strip()

    if new_status not in ('Approved', 'Rejected'):
        return jsonify({'success': False, 'message': 'Invalid status value'}), 400

    tr.status     = new_status
    tr.remarks    = remarks
    tr.updated_at = datetime.utcnow()

    try:
        db.session.commit()
        return jsonify({
            'success':    True,
            'new_status': tr.status,
            'remarks':    tr.remarks,
            'updated_at': tr.updated_at.strftime('%d %b %Y, %I:%M %p'),
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500


# ─── Class → Semester mapping (ERP logic) ────────────────────────────────────
CLASS_SEM_MAP = {
    'FY': [1, 2],
    'SY': [3, 4],
    'TY': [5, 6],
}

def allowed_sems_for_class(class_yr):
    """Return list of valid semester ints for a given class string."""
    return CLASS_SEM_MAP.get((class_yr or '').strip().upper(), [1, 2, 3, 4, 5, 6])

def autocorrect_sem(class_yr, semester_str):
    """
    If semester_str is not valid for class_yr, return the first valid semester.
    Returns the corrected semester as a string.
    """
    allowed = allowed_sems_for_class(class_yr)
    try:
        sem_int = int(semester_str)
    except (ValueError, TypeError):
        sem_int = None
    if sem_int in allowed:
        return str(sem_int)
    # Auto-correct: pick first allowed semester for this class
    return str(allowed[0]) if allowed else semester_str


# ─── Student Profile ──────────────────────────────────────────────────────────
@app.route('/student_profile')
def student_profile():
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        return redirect('/')

    # ── Fetch ALL student rows for this email (one per class/semester) ────────
    all_student_rows = Student.query.filter(
        func.lower(func.coalesce(Student.gmail_id, "")) == gmail_id.lower()
    ).order_by(Student.student_id.asc()).all()

    if not all_student_rows:
        return redirect('/')

    # Primary student row (lowest student_id — used as fallback)
    student = all_student_rows[0]

    # All student_ids belonging to this email (for attendance query)
    all_student_ids = [s.student_id for s in all_student_rows]

    # ── Raw filter params from query string ───────────────────────────────────
    filter_class_yr = (request.args.get('class_yr') or '').strip().upper()
    filter_semester = (request.args.get('semester') or '').strip()

    # Normalise class to known values only
    if filter_class_yr not in CLASS_SEM_MAP:
        filter_class_yr = ''

    # ── Resolve selected_class ────────────────────────────────────────────────
    # Priority: query param → session → student DB
    if filter_class_yr:
        selected_class = filter_class_yr
    elif session.get('active_class') and session['active_class'] in CLASS_SEM_MAP:
        selected_class = session['active_class']
    else:
        selected_class = (student.class_yr or '').strip().upper()

    # ── Allowed semesters for the resolved class ──────────────────────────────
    allowed_semesters = allowed_sems_for_class(selected_class)  # e.g. [1,2] for FY

    # ── Resolve selected_sem ──────────────────────────────────────────────────
    # Priority: query param → session → student DB
    if filter_semester:
        if filter_class_yr:
            # Both class and semester explicitly chosen — validate combination
            selected_sem = autocorrect_sem(selected_class, filter_semester)
            if selected_sem != filter_semester:
                # Mismatch — redirect to corrected URL
                from urllib.parse import urlencode
                params = {'class_yr': filter_class_yr, 'semester': selected_sem}
                return redirect('/student_profile?' + urlencode(params))
        else:
            # Only semester chosen, no class filter — accept as-is
            selected_sem = canonical_semester(filter_semester) or filter_semester
    elif session.get('active_semester'):
        # Use session value when no query param provided
        sess_sem = canonical_semester(session['active_semester'])
        # Validate it belongs to the resolved class
        try:
            if int(sess_sem) in allowed_semesters:
                selected_sem = sess_sem
            else:
                selected_sem = canonical_semester(student.semester or '') or \
                               (str(allowed_semesters[0]) if allowed_semesters else '')
        except (ValueError, TypeError):
            selected_sem = canonical_semester(student.semester or '') or \
                           (str(allowed_semesters[0]) if allowed_semesters else '')
    else:
        # No filter at all — use student's own stored semester (trust the DB)
        selected_sem = canonical_semester(student.semester or '') or \
                       (str(allowed_semesters[0]) if allowed_semesters else '')

    # ── Persist resolved filter to session (global academic filter) ───────────
    save_active_filter(selected_class, selected_sem)

    # ── Roll number: find the student row matching selected_class ─────────────
    class_specific_student = next(
        (s for s in all_student_rows
         if (s.class_yr or '').strip().upper() == selected_class),
        student  # fallback to primary row
    )
    display_roll = int(class_specific_student.student_id)

    # ── Attendance query — use ALL student_ids for this email ─────────────────
    # This handles the case where different semesters are stored under
    # different student_id rows for the same person.
    att_query = Attendance.query.filter(
        Attendance.student_id.in_(all_student_ids)
    )

    # Apply class_yr filter only when explicitly requested
    if filter_class_yr:
        att_query = att_query.filter(Attendance.class_yr == filter_class_yr)

    # Apply semester filter using the fuzzy helper so variants like
    # "Sem 3", "Semester 3", "3" all match correctly
    if selected_sem:
        att_query = apply_semester_filter(att_query, selected_sem)

    # Debug logs (remove after confirming fix)
    print(f"[student_profile] gmail={gmail_id}")
    print(f"[student_profile] all_student_ids={all_student_ids}")
    print(f"[student_profile] selected_class={selected_class!r}  selected_sem={selected_sem!r}")
    print(f"[student_profile] filter_class_yr={filter_class_yr!r}  filter_semester={filter_semester!r}")

    att_records   = att_query.order_by(Attendance.date.desc()).limit(50).all()
    total_classes = att_query.count()
    present_count = att_query.filter(Attendance.status == 'Present').count()
    absent_count  = total_classes - present_count
    att_pct       = round((present_count / total_classes * 100), 1) if total_classes > 0 else 0.0

    print(f"[student_profile] total={total_classes}  present={present_count}  absent={absent_count}  pct={att_pct}")

    # ── Transcript requests for this student ─────────────────────────────────
    my_transcripts = TranscriptRequest.query.filter(
        TranscriptRequest.student_id.in_(all_student_ids)
    ).order_by(TranscriptRequest.requested_at.desc()).all()

    return render_template(
        'student_profile.html',
        student           = student,
        filter_class_yr   = filter_class_yr,
        filter_semester   = filter_semester,
        selected_class    = selected_class,
        selected_sem      = selected_sem,
        allowed_semesters = allowed_semesters,
        display_roll      = display_roll,
        att_records       = att_records,
        total_classes     = total_classes,
        present_count     = present_count,
        absent_count      = absent_count,
        att_pct           = att_pct,
        my_transcripts    = my_transcripts,
    )


# ─── Profile Photo Upload ────────────────────────────────────────────────────
@app.route('/upload_profile_photo', methods=['POST'])
def upload_profile_photo():
    """Save uploaded profile photo and update students.profile_photo column."""
    import os, uuid
    from werkzeug.utils import secure_filename

    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    student = Student.query.filter(
        func.lower(func.coalesce(Student.gmail_id, "")) == gmail_id.lower()
    ).order_by(Student.student_id.asc()).first()
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    if 'photo' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'}), 400

    photo = request.files['photo']
    if photo.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400

    # Validate MIME type
    allowed_mimes = {'image/jpeg', 'image/png'}
    if photo.mimetype not in allowed_mimes:
        return jsonify({'success': False, 'message': 'Only JPG and PNG files are allowed'}), 400

    # Validate size (2 MB)
    photo.seek(0, 2)          # seek to end
    file_size = photo.tell()
    photo.seek(0)             # reset
    if file_size > 2 * 1024 * 1024:
        return jsonify({'success': False, 'message': 'File size must not exceed 2 MB'}), 400

    # Build safe filename: <student_id>_<uuid>.<ext>
    ext = 'jpg' if photo.mimetype == 'image/jpeg' else 'png'
    filename = f"{student.student_id}_{uuid.uuid4().hex[:8]}.{ext}"

    # Ensure upload directory exists
    upload_dir = os.path.join(app.root_path, 'static', 'uploads', 'profile_photos')
    os.makedirs(upload_dir, exist_ok=True)

    # Delete old photo if it exists
    if student.profile_photo:
        old_path = os.path.join(app.root_path, 'static', student.profile_photo)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    # Save new file
    save_path = os.path.join(upload_dir, filename)
    photo.save(save_path)

    # Update DB — store path relative to static/
    relative_path = f"uploads/profile_photos/{filename}"
    student.profile_photo = relative_path
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500

    photo_url = f"/static/{relative_path}"
    return jsonify({'success': True, 'photo_url': photo_url})


# ─── Change Password (mobile_number is the password) ────────────────────────
@app.route('/change_password', methods=['POST'])
def change_password():
    """
    Verify current_password == student.mobile_number,
    then update mobile_number to new_password (must be exactly 10 digits).
    """
    import re

    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    student = Student.query.filter(
        func.lower(func.coalesce(Student.gmail_id, "")) == gmail_id.lower()
    ).order_by(Student.student_id.asc()).first()
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    data = request.get_json(silent=True) or {}
    current_password = (data.get('current_password') or '').strip()
    new_password     = (data.get('new_password')     or '').strip()

    # Verify current password matches stored mobile_number
    stored_mobile = (student.mobile_number or '').strip()
    if current_password != stored_mobile:
        return jsonify({'success': False, 'message': 'Current password (mobile number) is incorrect'}), 400

    # Validate new password: exactly 10 digits (numbers only)
    digit_pattern = re.compile(r'[0-9]{10}')
    if not (len(new_password) == 10 and digit_pattern.fullmatch(new_password)):
        return jsonify({
            'success': False,
            'message': 'New password must be exactly 10 digits (numbers only)'
        }), 400

    # Prevent reuse of same number
    if new_password == stored_mobile:
        return jsonify({
            'success': False,
            'message': 'New password must be different from the current one'
        }), 400

    # Update mobile_number in DB
    student.mobile_number = new_password
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500

    return jsonify({'success': True, 'message': 'Password updated successfully'})


@app.route('/student_notice')
def student_notice():
    if not get_logged_in_student_email():
        flash('Please login first', 'error')
        return redirect(url_for('login'))
    
    # Agar student login hai tab ye chalega
    notices = Notice.query.filter_by(is_active=True) \
               .order_by(Notice.is_pinned.desc(), Notice.date_posted.desc()) \
               .all()
    return render_template('student_notice.html', notices=notices)



@app.route('/student_fees')
def student_fees():
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        flash('Please login first', 'error')
        return redirect(url_for('login'))

    student = Student.query.filter(
        func.lower(func.coalesce(Student.gmail_id, "")) == gmail_id.lower()
    ).order_by(Student.student_id.asc()).first()
    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('login'))

    session['student_id'] = student.student_id

    payment_rows = db.session.execute(text("""
        SELECT
            fee_id,
            student_id,
            semester,
            payment_date,
            payment_method,
            COALESCE(total_fee, 0) AS total_fee,
            COALESCE(amount_paid, 0) AS amount_paid
        FROM fees
        WHERE student_id = :student_id
        ORDER BY semester
    """), {"student_id": student.student_id}).mappings().all()

    summary_row = db.session.execute(text("""
        SELECT
            COALESCE(SUM(total_fee), 0) AS total_fee,
            COALESCE(SUM(amount_paid), 0) AS paid_amount
        FROM fees
        WHERE student_id = :student_id
    """), {"student_id": student.student_id}).first()

    total_fee = float(summary_row[0] or 0) if summary_row else 0.0
    paid_amount = float(summary_row[1] or 0) if summary_row else 0.0
    due_amount = total_fee - paid_amount
    progress_percent = (paid_amount / total_fee * 100.0) if total_fee > 0 else 0.0

    payments = []
    for row in payment_rows:
        total_fee_row = float(row["total_fee"] or 0)
        amount_paid_row = float(row["amount_paid"] or 0)
        if amount_paid_row >= total_fee_row and total_fee_row > 0:
            status = "Paid"
        elif amount_paid_row > 0:
            status = "Partial"
        else:
            status = "Pending"

        payments.append({
            "fee_id": int(row["fee_id"]),
            "semester": int(row["semester"]) if row["semester"] is not None else 0,
            "total_fee": total_fee_row,
            "amount_paid": amount_paid_row,
            "payment_date": row["payment_date"],
            "payment_method": row["payment_method"] or "",
            "status": status
        })

    summary = {
        "total_fee": total_fee,
        "paid_amount": paid_amount,
        "due_amount": due_amount
    }

    return render_template(
        'student_fees.html',
        student=student,
        summary=summary,
        payments=payments,
        progress_percent=progress_percent
    )


@app.route('/student_receipt/<int:fee_id>')
def student_receipt(fee_id):
    from flask import send_file, current_app
    from datetime import date
    import os
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.lib.pagesizes import A4
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase import pdfmetrics

    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        flash('Please login first', 'error')
        return redirect(url_for('login'))

    row = db.session.execute(text("""
        SELECT
            f.*,
            s.full_name,
            s.course,
            s.class_yr,
            s.gmail_id,
            COALESCE(f.total_fee, 0) AS total_fee_safe,
            COALESCE(f.amount_paid, 0) AS amount_paid_safe
        FROM fees f
        JOIN students s ON s.student_id = f.student_id
        WHERE f.fee_id = :fee_id
          AND LOWER(COALESCE(s.gmail_id, '')) = :gmail
        LIMIT 1
    """), {
        "fee_id": fee_id,
        "gmail": gmail_id.lower()
    }).mappings().first()

    if not row:
        return "Receipt not found", 404

    total_fee = float(row["total_fee_safe"] or 0)
    paid_amount = float(row["amount_paid_safe"] or 0)
    due_amount = total_fee - paid_amount
    current_year = date.today().year
    receipt_no = f"NAV/{current_year}/{int(fee_id):04d}"

    if paid_amount >= total_fee and total_fee > 0:
        payment_status = "PAID"
        status_bg = colors.HexColor("#16a34a")
    elif paid_amount > 0:
        payment_status = "PARTIAL"
        status_bg = colors.HexColor("#ea580c")
    else:
        payment_status = "PENDING"
        status_bg = colors.HexColor("#dc2626")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch
    )

    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    try:
        arial_path = r"C:\Windows\Fonts\arial.ttf"
        arial_bold_path = r"C:\Windows\Fonts\arialbd.ttf"
        if os.path.exists(arial_path) and os.path.exists(arial_bold_path):
            pdfmetrics.registerFont(TTFont("ArialUnicode", arial_path))
            pdfmetrics.registerFont(TTFont("ArialUnicode-Bold", arial_bold_path))
            font_regular = "ArialUnicode"
            font_bold = "ArialUnicode-Bold"
    except Exception:
        pass

    styles = getSampleStyleSheet()
    header_text_style = ParagraphStyle(
        "HeaderText",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=13,
        alignment=1,
        leading=18,
        textColor=colors.white
    )
    section_title_style = ParagraphStyle(
        "SectionTitlePremium",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=12,
        alignment=0,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=8
    )
    normal_style = ParagraphStyle(
        "NormalPremium",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#0f172a")
    )
    center_note_style = ParagraphStyle(
        "CenterNotePremium",
        parent=styles["Normal"],
        fontName=font_regular,
        fontSize=9,
        alignment=1,
        leading=13,
        textColor=colors.HexColor("#64748b")
    )
    watermark_style = ParagraphStyle(
        "WatermarkStyle",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=44,
        alignment=1,
        textColor=colors.HexColor("#e5e7eb"),
        leading=44
    )

    elements = []

    header_content = Paragraph(
        "Navneet College of Arts, Science & Commerce<br/>"
        "Mumbai Central, Mumbai, Maharashtra 400008",
        header_text_style
    )
    header_table = Table([[header_content]], colWidths=[doc.width])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0b3a75")),
        ("BOX", (0, 0), (-1, -1), 0, colors.HexColor("#0b3a75")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 12))

    logo_path = os.path.join(current_app.root_path, 'static', 'navneetcollege.png')
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=90, height=90)
        logo.hAlign = "CENTER"
        elements.append(logo)
        elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>PAYMENT RECEIPT</b>", styles["Heading2"]))
    elements.append(Spacer(1, 12))

    divider = Table([[""]], colWidths=[doc.width])
    divider.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, -1), 1, colors.HexColor("#94a3b8"))
    ]))
    elements.append(divider)
    elements.append(Spacer(1, 12))

    status_style = ParagraphStyle(
        "StatusStyle",
        parent=styles["Normal"],
        fontName=font_bold,
        fontSize=10,
        alignment=1,
        textColor=colors.white
    )
    receipt_info = Paragraph(
        f"<b>Receipt No:</b> {receipt_no}<br/><b>Transaction ID:</b> {row['fee_id']}<br/>"
        f"<b>Date Generated:</b> {date.today().isoformat()}",
        ParagraphStyle(
            "ReceiptInfoStyle",
            parent=normal_style,
            alignment=0,
            leading=14
        )
    )
    status_badge = Table([[Paragraph(payment_status, status_style)]], colWidths=[1.35 * inch])
    status_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), status_bg),
        ("BOX", (0, 0), (-1, -1), 0.5, status_bg),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    receipt_head = Table([[receipt_info, status_badge]], colWidths=[doc.width - 1.5 * inch, 1.5 * inch])
    receipt_head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    elements.append(receipt_head)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("NAVNEET COLLEGE", watermark_style))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Student Details", section_title_style))
    student_table_data = [
        ["Field", "Value"],
        ["Student Name", row["full_name"] or "-"],
        ["Course", row["course"] or "-"],
        ["Class", row["class_yr"] or "-"],
        ["Semester", str(row["semester"] or "-")]
    ]
    student_table = Table(student_table_data, colWidths=[2.1 * inch, 4.7 * inch])
    student_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("FONTNAME", (0, 0), (-1, 0), font_bold),
        ("FONTNAME", (0, 1), (0, -1), font_bold),
        ("FONTNAME", (1, 1), (1, -1), font_regular),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    elements.append(student_table)
    elements.append(Spacer(1, 14))

    elements.append(Paragraph("Payment Details", section_title_style))
    payment_date_str = row["payment_date"].strftime("%Y-%m-%d") if row["payment_date"] else "-"
    payment_table_data = [
        ["Field", "Value"],
        ["Total Fee", f"\u20B9 {total_fee:,.2f}"],
        ["Paid Amount", f"\u20B9 {paid_amount:,.2f}"],
        ["Due Amount", f"\u20B9 {due_amount:,.2f}"],
        ["Payment Date", payment_date_str],
        ["Payment Method", row["payment_method"] or "-"]
    ]
    payment_table = Table(payment_table_data, colWidths=[2.1 * inch, 4.7 * inch])
    payment_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("FONTNAME", (0, 0), (-1, 0), font_bold),
        ("FONTNAME", (0, 1), (0, -1), font_bold),
        ("FONTNAME", (1, 1), (1, -1), font_regular),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    elements.append(payment_table)
    elements.append(Spacer(1, 16))

    qr_payload = (
        f"Student Name: {row['full_name'] or '-'}\n"
        f"Transaction ID: {row['fee_id']}\n"
        f"Paid Amount: \u20B9 {paid_amount:,.2f}\n"
        f"Date: {payment_date_str}"
    )
    qr_code = qr.QrCodeWidget(qr_payload)
    qr_bounds = qr_code.getBounds()
    qr_size = 1.3 * inch
    qr_width = qr_bounds[2] - qr_bounds[0]
    qr_height = qr_bounds[3] - qr_bounds[1]
    qr_drawing = Drawing(
        qr_size,
        qr_size,
        transform=[qr_size / qr_width, 0, 0, qr_size / qr_height, 0, 0]
    )
    qr_drawing.add(qr_code)

    signature_block = Paragraph(
        "<b>Authorized Signature</b><br/>"
        "Accounts Department<br/>"
        "Navneet College",
        ParagraphStyle(
            "SignatureStyle",
            parent=normal_style,
            alignment=0,
            leading=15
        )
    )
    sign_qr_table = Table([[signature_block, qr_drawing]], colWidths=[doc.width - 1.5 * inch, 1.5 * inch])
    sign_qr_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    elements.append(sign_qr_table)
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("Thank you for your payment.", center_note_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("This is a system generated receipt.", center_note_style))

    doc.build(elements)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Receipt_{fee_id}.pdf",
        mimetype="application/pdf"
    )
def _parse_teacher_fee_filters(req):
    selected_course = (req.values.get('course') or req.values.get('selected_course') or '').strip()
    selected_class = (req.values.get('class_yr') or req.values.get('selected_class') or '').strip()
    raw_sem = (req.values.get('semester') or req.values.get('selected_semester') or '').strip()
    selected_semester = int(raw_sem) if raw_sem.isdigit() and 1 <= int(raw_sem) <= 6 else None
    return selected_course, selected_class, selected_semester


def _get_teacher_fee_filter_options():
    courses = [
        row[0] for row in db.session.execute(text("""
            SELECT DISTINCT course
            FROM students
            WHERE course IS NOT NULL AND TRIM(course) <> ''
            ORDER BY course
        """)).all()
    ]

    classes = [
        row[0] for row in db.session.execute(text("""
            SELECT DISTINCT class_yr
            FROM students
            WHERE class_yr IS NOT NULL AND TRIM(class_yr) <> ''
            ORDER BY class_yr
        """)).all()
    ]

    semesters = [
        int(row[0]) for row in db.session.execute(text("""
            SELECT DISTINCT sem
            FROM (
                SELECT NULLIF(regexp_replace(COALESCE(s.semester, ''), '[^0-9]', '', 'g'), '')::int AS sem
                FROM students s
                UNION
                SELECT f.semester AS sem
                FROM fees f
            ) x
            WHERE sem BETWEEN 1 AND 6
            ORDER BY sem
        """)).all() if row[0] is not None
    ]
    return courses, classes, semesters


def _get_teacher_fee_rows(selected_course, selected_class, selected_semester):
    rows = db.session.execute(text("""
        WITH filtered_students AS (
            SELECT
                s.student_id,
                s.full_name,
                s.course,
                s.class_yr,
                NULLIF(regexp_replace(COALESCE(s.semester, ''), '[^0-9]', '', 'g'), '')::int AS semester_num
            FROM students s
            WHERE (:course = '' OR s.course = :course)
              AND (:class_yr = '' OR s.class_yr = :class_yr)
              AND (:semester IS NULL OR NULLIF(regexp_replace(COALESCE(s.semester, ''), '[^0-9]', '', 'g'), '')::int = :semester)
        ),
        fee_rollup AS (
            SELECT
                fs.student_id,
                COALESCE(MAX(f.total_fee), 0) AS total_fee,
                COALESCE(SUM(f.amount_paid), 0) AS paid_amount
            FROM filtered_students fs
            LEFT JOIN fees f
              ON f.student_id = fs.student_id
             AND (:semester IS NULL OR f.semester = :semester)
            GROUP BY fs.student_id
        )
        SELECT
            fs.student_id,
            fs.full_name,
            fs.course,
            fs.class_yr,
            COALESCE(fs.semester_num, :semester, 0) AS semester,
            fr.total_fee,
            fr.paid_amount,
            (fr.total_fee - fr.paid_amount) AS due_amount,
            CASE
                WHEN fr.paid_amount >= fr.total_fee AND fr.total_fee > 0 THEN 'Paid'
                WHEN fr.paid_amount > 0 AND fr.paid_amount < fr.total_fee THEN 'Partial'
                ELSE 'Pending'
            END AS status
        FROM filtered_students fs
        LEFT JOIN fee_rollup fr ON fr.student_id = fs.student_id
        ORDER BY fs.student_id
    """), {
        "course": selected_course or "",
        "class_yr": selected_class or "",
        "semester": selected_semester
    }).mappings().all()

    result = []
    for row in rows:
        result.append({
            "student_id": int(row["student_id"]),
            "full_name": row["full_name"] or "",
            "course": row["course"] or "",
            "class_yr": row["class_yr"] or "",
            "semester": int(row["semester"]) if row["semester"] is not None else 0,
            "total_fee": float(row["total_fee"] or 0),
            "paid_amount": float(row["paid_amount"] or 0),
            "due_amount": float(row["due_amount"] or 0),
            "status": row["status"] or "Pending"
        })
    return result


def _get_teacher_fee_collection_windows(selected_course, selected_class, selected_semester):
    row = db.session.execute(text("""
        WITH filtered_students AS (
            SELECT
                s.student_id
            FROM students s
            WHERE (:course = '' OR s.course = :course)
              AND (:class_yr = '' OR s.class_yr = :class_yr)
        )
        SELECT
            COALESCE(SUM(f.amount_paid) FILTER (
                WHERE DATE_TRUNC('month', f.payment_date) = DATE_TRUNC('month', CURRENT_DATE)
            ), 0) AS monthly_collection,
            COALESCE(SUM(f.amount_paid) FILTER (
                WHERE DATE_TRUNC('quarter', f.payment_date) = DATE_TRUNC('quarter', CURRENT_DATE)
            ), 0) AS quarterly_collection,
            COALESCE(SUM(f.amount_paid) FILTER (
                WHERE DATE_TRUNC('year', f.payment_date) = DATE_TRUNC('year', CURRENT_DATE)
            ), 0) AS yearly_collection
        FROM fees f
        INNER JOIN filtered_students fs ON fs.student_id = f.student_id
        WHERE (:semester IS NULL OR f.semester = :semester)
    """), {
        "course": selected_course or "",
        "class_yr": selected_class or "",
        "semester": selected_semester
    }).first()
    if not row:
        return {
            "monthly_collection": 0.0,
            "quarterly_collection": 0.0,
            "yearly_collection": 0.0
        }
    return {
        "monthly_collection": float(row[0] or 0),
        "quarterly_collection": float(row[1] or 0),
        "yearly_collection": float(row[2] or 0)
    }


def _get_teacher_fee_payment_method_data(selected_course, selected_class, selected_semester):
    rows = db.session.execute(text("""
        WITH filtered_students AS (
            SELECT
                s.student_id,
                NULLIF(regexp_replace(COALESCE(s.semester, ''), '[^0-9]', '', 'g'), '')::int AS semester_num
            FROM students s
            WHERE (:course = '' OR s.course = :course)
              AND (:class_yr = '' OR s.class_yr = :class_yr)
              AND (:semester IS NULL OR NULLIF(regexp_replace(COALESCE(s.semester, ''), '[^0-9]', '', 'g'), '')::int = :semester)
        )
        SELECT
            COALESCE(NULLIF(TRIM(f.payment_method), ''), 'Unknown') AS payment_method,
            COALESCE(SUM(f.amount_paid), 0) AS amount_collected
        FROM fees f
        INNER JOIN filtered_students fs ON fs.student_id = f.student_id
        WHERE (:semester IS NULL OR f.semester = :semester)
        GROUP BY COALESCE(NULLIF(TRIM(f.payment_method), ''), 'Unknown')
        ORDER BY payment_method
    """), {
        "course": selected_course or "",
        "class_yr": selected_class or "",
        "semester": selected_semester
    }).all()

    labels = []
    values = []
    for method, amount in rows:
        labels.append(method)
        values.append(float(amount or 0))
    return {"labels": labels, "values": values}


@app.route('/teacher_fees', methods=['GET', 'POST'])
def teacher_fees():
    if 'user_type' not in session or session['user_type'] != 'teacher':
        flash("Please login first as Teacher!", "error")
        return redirect(url_for('login'))

    selected_course, selected_class, selected_semester = _parse_teacher_fee_filters(request)
    courses, classes, semesters = _get_teacher_fee_filter_options()

    students_with_fees = _get_teacher_fee_rows(selected_course, selected_class, selected_semester)
    total_fee = sum(row["total_fee"] for row in students_with_fees)
    paid_amount = sum(row["paid_amount"] for row in students_with_fees)
    due_amount = total_fee - paid_amount
    base_conditions = []
    params = {}
    if selected_course:
        base_conditions.append("s.course = :course")
        params["course"] = selected_course
    if selected_class:
        base_conditions.append("s.class_yr = :class_yr")
        params["class_yr"] = selected_class
    if selected_semester is not None:
        base_conditions.append("f.semester = :semester")
        params["semester"] = selected_semester

    monthly_conditions = [
        "DATE_TRUNC('month', f.payment_date) = DATE_TRUNC('month', CURRENT_DATE)"
    ] + base_conditions
    monthly_query = f"""
        SELECT COALESCE(SUM(f.amount_paid),0)
        FROM fees f
        JOIN students s ON s.student_id = f.student_id
        WHERE {' AND '.join(monthly_conditions)}
    """
    monthly_row = db.session.execute(text(monthly_query), params).fetchone()
    monthly_collection = float((monthly_row[0] if monthly_row else 0) or 0)

    quarterly_conditions = [
        "DATE_TRUNC('quarter', f.payment_date) = DATE_TRUNC('quarter', CURRENT_DATE)"
    ] + base_conditions
    quarterly_query = f"""
        SELECT COALESCE(SUM(f.amount_paid),0)
        FROM fees f
        JOIN students s ON s.student_id = f.student_id
        WHERE {' AND '.join(quarterly_conditions)}
    """
    quarterly_row = db.session.execute(text(quarterly_query), params).fetchone()
    quarterly_collection = float((quarterly_row[0] if quarterly_row else 0) or 0)

    yearly_conditions = [
        "DATE_TRUNC('year', f.payment_date) = DATE_TRUNC('year', CURRENT_DATE)"
    ] + base_conditions
    yearly_query = f"""
        SELECT COALESCE(SUM(f.amount_paid),0)
        FROM fees f
        JOIN students s ON s.student_id = f.student_id
        WHERE {' AND '.join(yearly_conditions)}
    """
    yearly_row = db.session.execute(text(yearly_query), params).fetchone()
    yearly_collection = float((yearly_row[0] if yearly_row else 0) or 0)

    print(
        f"[teacher_fees] filters -> course={selected_course or 'ALL'}, "
        f"class_yr={selected_class or 'ALL'}, semester={selected_semester if selected_semester is not None else 'ALL'}"
    )
    print(
        f"[teacher_fees] collections -> monthly={monthly_collection}, "
        f"quarterly={quarterly_collection}, yearly={yearly_collection}"
    )

    payment_method_chart = _get_teacher_fee_payment_method_data(selected_course, selected_class, selected_semester)

    summary = {
        "total_students": len(students_with_fees),
        "total_fee": total_fee,
        "paid_amount": paid_amount,
        "due_amount": due_amount,
        "monthly_collection": monthly_collection,
        "quarterly_collection": quarterly_collection,
        "yearly_collection": yearly_collection
    }

    fee_distribution_chart = {
        "labels": ["Paid", "Due"],
        "values": [paid_amount, max(due_amount, 0)]
    }

    return render_template(
        'teacher_fees.html',
        students_with_fees=students_with_fees,
        summary=summary,
        quarterly_collection=quarterly_collection,
        yearly_collection=yearly_collection,
        selected_course=selected_course,
        selected_class=selected_class,
        selected_semester=selected_semester,
        course_options=courses,
        class_options=classes,
        semester_options=semesters,
        fee_distribution_chart=fee_distribution_chart,
        payment_method_chart=payment_method_chart
    )


@app.route('/teacher_fees/payment-history/<int:student_id>')
def teacher_fee_payment_history(student_id):
    if 'user_type' not in session or session['user_type'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    _, _, selected_semester = _parse_teacher_fee_filters(request)
    rows = db.session.execute(text("""
        SELECT
            f.payment_date,
            f.amount_paid,
            COALESCE(NULLIF(TRIM(f.payment_method), ''), 'Unknown') AS payment_method
        FROM fees f
        WHERE f.student_id = :student_id
          AND (:semester IS NULL OR f.semester = :semester)
        ORDER BY f.payment_date DESC, f.fee_id DESC
    """), {
        "student_id": student_id,
        "semester": selected_semester
    }).all()

    history = [{
        "payment_date": r[0].isoformat() if r[0] else "",
        "amount_paid": float(r[1] or 0),
        "payment_method": r[2] or "Unknown"
    } for r in rows]
    return jsonify({"student_id": student_id, "history": history})


@app.route('/teacher_fees/export-csv', endpoint='teacher_fee_export_csv')
def teacher_fee_export_csv():
    if 'user_type' not in session or session['user_type'] != 'teacher':
        flash("Please login first as Teacher!", "error")
        return redirect(url_for('login'))

    selected_course, selected_class, selected_semester = _parse_teacher_fee_filters(request)
    rows = _get_teacher_fee_rows(selected_course, selected_class, selected_semester)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Student ID", "Student Name", "Course", "Class", "Semester",
        "Total Fee", "Paid Amount", "Due Amount", "Status"
    ])
    for r in rows:
        writer.writerow([
            r["student_id"],
            r["full_name"],
            r["course"],
            r["class_yr"],
            r["semester"],
            f'{r["total_fee"]:.2f}',
            f'{r["paid_amount"]:.2f}',
            f'{r["due_amount"]:.2f}',
            r["status"]
        ])

    filename = f"teacher_fees_{selected_course or 'all'}_{selected_class or 'all'}_{selected_semester or 'all'}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@app.route('/logout')
def logout():
    print(f"Logging out user: {dict(session)}")  # puri session dict print kare
    session.clear()
    print("After clear session:", dict(session))  # confirm clear hua
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('login'))



@app.route('/teacher_notice', methods=['GET', 'POST'])
def teacher_notice():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        new_notice = Notice(title=title, content=content)
        db.session.add(new_notice)
        db.session.commit()
        flash('Notice posted successfully!')

    notices = Notice.query.order_by(Notice.date_posted.desc()).all()
    return render_template('admin_notice_add.html', notices=notices)


from flask import jsonify, request, redirect, url_for, flash

@app.route('/add_notice', methods=['GET', 'POST'])  # Accept both GET and POST
def add_notice():
    if 'user_type' not in session or session['user_type'] != 'teacher':
      flash("Please login first as Teacher!", "error")
      return redirect(url_for('login'))
    if request.method == 'POST':
        # Handle form submission
        try:
            new_notice = Notice(
                title=request.form.get('title'),
                content=request.form.get('content'),
                category=request.form.get('category', 'Academic'),
                is_pinned='is_pinned' in request.form,
                is_important='is_important' in request.form,
                is_active='is_active' in request.form,
                posted_by="Teacher"
            )
            db.session.add(new_notice)
            db.session.commit()
            flash('Notice published successfully!', 'success')
            return redirect(url_for('all_notices'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
            return redirect(url_for('add_notice'))
    
    # Handle GET request - show the form
    return render_template('admin_notice_add.html')

@app.route('/all_notices')
def all_notices():
    if 'user_type' not in session or session['user_type'] != 'teacher':
      flash("Please login first as Teacher!", "error")
      return redirect(url_for('login'))
    try:
        # Fetch ALL notices (active + inactive) for management panel
        notices = Notice.query\
                   .order_by(Notice.is_pinned.desc(), Notice.date_posted.desc())\
                   .all()
        return render_template('admin_notice_list.html', notices=notices)
    except Exception as e:
        print("Error fetching notices:", str(e))
        flash('Error loading notices', 'error')
        return render_template('admin_notice_list.html', notices=[])
    
    
@app.route('/toggle_notice/<int:notice_id>')
def toggle_notice(notice_id):
        notice = Notice.query.get_or_404(notice_id)
        notice.is_active = not notice.is_active  # Toggle status
        db.session.commit()
        flash(f'Notice {"activated" if notice.is_active else "deactivated"} successfully!', 'success')
        return redirect(url_for('all_notices'))
        
    

@app.route('/edit_notice/<int:notice_id>', methods=['GET', 'POST'])
def edit_notice(notice_id):
    notice = Notice.query.get_or_404(notice_id)
    
    if request.method == 'POST':
        try:
            # Update existing notice instead of creating new one
            notice.title = request.form['title']
            notice.content = request.form['content']
            notice.is_active = 'is_active' in request.form  # Handles checkbox
            notice.date_updated = datetime.utcnow()  # Add this field to your model if tracking edits
            
            db.session.commit()
            flash('Notice updated successfully!', 'success')
            return redirect(url_for('all_notices'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating notice: {str(e)}', 'danger')
            return redirect(url_for('edit_notice', notice_id=notice_id))
    
    # GET request - show edit form
    return render_template('admin_notice_edit.html', notice=notice)

@app.route('/delete_notice/<int:notice_id>')
def delete_notice(notice_id):
    notice = Notice.query.get_or_404(notice_id)
    notice.is_active = False
    db.session.commit()
    return redirect('/all_notices')

@app.route('/view_notice/<int:notice_id>')
def view_notice(notice_id):
    notice = Notice.query.get_or_404(notice_id)
    return render_template('admin_notice_view.html', notice=notice)



@app.route('/teacher_panel', methods=['GET', 'POST'])
def teacher_panel():
    if 'user_type' not in session or session['user_type'] != 'teacher':
      flash("Please login first as Teacher!", "error")
      return redirect(url_for('login'))
    students = []
    selected_course = None
    selected_class = None
    selected_semester = None
    selected_subject = None
    student_records = []  # Initialize student_records here
    summary_data = {}  # Initialize summary_data here

    if request.method == 'POST':
        selected_course = request.form.get('selected_course')
        selected_class = request.form.get('selected_class')
        selected_semester = request.form.get('selected_semester')
        selected_subject = request.form.get('selected_subject')

        students = Student.query.filter_by(
            course=selected_course,
            class_yr=selected_class,
            semester=selected_semester
        ).all()

        total_present_class = 0
        total_days_class = 0

        for student in students:
            total = Attendance.query.filter_by(
                student_id=student.student_id,
                subject=selected_subject
            ).count()

            present = Attendance.query.filter_by(
                student_id=student.student_id,
                subject=selected_subject,
                status='Present'
            ).count()

            absent = Attendance.query.filter_by(
                student_id=student.student_id,
                subject=selected_subject,
                status='Absent'
            ).count()

            percentage = (present / total * 100) if total > 0 else 0

            total_present_class += present
            total_days_class += total

            student_records.append({  # Accumulate data in `student_records`
                'name': student.full_name,
                'course': student.course,
                'class_yr': student.class_yr,
                'semester': student.semester,
                'subject': selected_subject,
                'total': total,
                'present': present,
                'absent': absent,
                'percentage': round(percentage, 2)  # Round percentage
            })

        overall_percentage = (total_present_class / total_days_class * 100) if total_days_class > 0 else 0
        summary_data = {
            'total_students': len(students),
            'overall_percentage': round(overall_percentage, 2), #Round
            'low_attendance_count': sum(1 for r in student_records if r['percentage'] < 75),#Calculate
            'present_total': int(total_present_class),
            'absent_total': int(total_days_class - total_present_class)
        }

    else:
        # Initialize with empty values when the form hasn't been submitted
        summary_data = {
            'total_students': 0,
            'overall_percentage': 0,
            'low_attendance_count': 0,
            'present_total': 0,
            'absent_total': 0
        }
        student_records = [] # Need to Initialize list for GET request.

    # Render the template with both student_records and summary_data
    return render_template(
        'teacher_attendance_summary.html',
        student_records=student_records, # Use `student_records`
        summary_data=summary_data,   # Pass the summary data
        selected_course=selected_course,
        selected_class=selected_class,
        selected_semester=selected_semester,
        selected_subject=selected_subject
    )
    
    
@app.route('/teacher_dashboard')
def teacher_dashboard():
    if 'user_type' not in session or session['user_type'] != 'teacher':
      flash("Please login first as Teacher!", "error")
      return redirect(url_for('login'))
    return render_template('teacher_dashboard.html')

# ===== Teacher Dashboard JSON API =====
@app.route('/api/teacher-dashboard')
def teacher_dashboard_data():
    # Sirf teacher ke liye
    if 'user_type' not in session or session['user_type'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        # Optional filters (query params): ?course=...&class_yr=...&semester=...&subject=...&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
        course = request.args.get('course')
        class_yr = request.args.get('class_yr')
        semester = request.args.get('semester')
        subject = request.args.get('subject')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        start_date = date.fromisoformat(start_date_str) if start_date_str else None
        end_date = date.fromisoformat(end_date_str) if end_date_str else None

        filters = []
        if course:
            filters.append(Attendance.course == course)
        if class_yr:
            filters.append(Attendance.class_yr == class_yr)
        if semester:
            filters.append(Attendance.semester == semester)
        if subject:
            filters.append(Attendance.subject == subject)
        if start_date and end_date:
            filters.append(Attendance.date.between(start_date, end_date))
        elif start_date:
            filters.append(Attendance.date >= start_date)
        elif end_date:
            filters.append(Attendance.date <= end_date)

        # Status-wise breakdown (case-insensitive)
        status_col = func.lower(Attendance.status)  # 'present', 'absent', etc.
        breakdown = (
            db.session.query(status_col.label('status'), func.count(Attendance.attendance_id).label('total'))
            .filter(*filters)
            .group_by('status')
            .order_by('status')
            .all()
        )

        labels = []
        data = []
        for status, total in breakdown:
            if status is None:
                label = 'Unknown'
            else:
                s = str(status).strip().lower()
                if s in {'1', 'true', 'present', 'p'}:
                    label = 'Present'
                elif s in {'0', 'false', 'absent', 'a'}:
                    label = 'Absent'
                else:
                    label = s.capitalize()  # 'Late', 'Leave', etc.
            labels.append(label)
            data.append(int(total))

        # Summary cards (simple defaults; change as you like)
        total_users = Student.query.count()
        active_courses = db.session.query(Student.course).filter(Student.course != None, Student.course != '').distinct().count()
        # Pending actions = aaj ke din ke Absent entries (filtered set ke hisaab se)
        pending_actions = db.session.query(func.count(Attendance.attendance_id)).filter(
            Attendance.date == date.today(),
            func.lower(Attendance.status) != 'present',
            *filters
        ).scalar()

        return jsonify({
            'attendance': {'labels': labels, 'data': data},
            'summary': {
                'total_users': total_users,
                'active_courses': active_courses,
                'pending_actions': int(pending_actions or 0)
            }
        })
    except Exception as e:
        print("Dashboard API error:", str(e))
        return jsonify({'error': 'Internal Server Error'}), 500

@app.route('/student_focus')
def student_focus():
    if not get_logged_in_student_email():
        flash('Please login first', 'error')
        return redirect(url_for('login'))
    return render_template('student_focus.html')


@app.route('/about')
def about_us():
    return render_template('student_about.html')


# ---------- STUDENT-ONLY APIs (backend-driven, filter-aware) ----------
@app.route('/api/student/attendance')
def api_student_attendance():
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        return jsonify({'error': 'Not logged in'}), 401

    period = request.args.get('period', 'all')
    subject = (request.args.get('subject') or '').strip()
    # Use query param first, then fall back to global session filter
    qp_sem = canonical_semester(request.args.get('semester') or '')
    _, sess_sem = get_active_filter(gmail_id)
    requested_semester = qp_sem or sess_sem
    student, semester = get_student_for_email_semester(gmail_id, requested_semester)
    if not student:
        return jsonify({'error': 'Student not found'}), 404

    semester_value = canonical_semester(student.semester or semester or '') or '1'
    # Do NOT filter by SUBJECT_MASTER — fetch all actual DB subjects for this student+semester
    q = build_student_dashboard_filtered_query(gmail_id, semester_value, period, subject)
    records = q.order_by(Attendance.date.desc(), Attendance.marked_time.desc()).all()

    return jsonify({
        'records': [{
            'date':      r.date.isoformat() if r.date else '',
            'time':      format_lecture_time(r.time),
            'subject':   r.subject or '',
            'status':    r.status or '',
            'marked_by': r.marked_by or '',
            'remarks':   r.remarks or '',
        } for r in records]
    })


@app.route('/api/student/subjects')
def api_student_subjects():
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        return jsonify({'error': 'Not logged in'}), 401

    qp_sem = canonical_semester(request.args.get('semester') or '')
    _, sess_sem = get_active_filter(gmail_id)
    semester = qp_sem or sess_sem
    student, selected_semester = get_student_for_email_semester(gmail_id, semester)
    if not student:
        return jsonify([])

    # Return actual subjects from DB (not SUBJECT_MASTER which may be out of sync)
    sem_val = canonical_semester(selected_semester or student.semester or '') or '1'
    db_subjects = [
        r[0] for r in db.session.query(Attendance.subject)
        .join(Student, Attendance.student_id == Student.student_id)
        .filter(
            func.lower(func.coalesce(Student.gmail_id, '')) == gmail_id.strip().lower(),
            Attendance.semester == sem_val
        )
        .distinct()
        .order_by(Attendance.subject)
        .all()
        if r[0]
    ]
    return jsonify(db_subjects)


@app.route('/api/student/dashboard-data')
def api_student_dashboard_data():
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        return jsonify({'error': 'Not logged in'}), 401

    # ── Semester resolution: query param → session → DB ──────────────────────
    qp_sem = canonical_semester(request.args.get('semester') or '')
    _, sess_sem = get_active_filter(gmail_id)
    requested_semester = qp_sem or sess_sem
    student, semester = get_student_for_email_semester(gmail_id, requested_semester)
    if not student:
        return jsonify({'error': 'Student not found'}), 404

    try:
        period  = (request.args.get('period') or 'all').strip().lower()
        subject = (request.args.get('subject') or '').strip()
        semester_value = canonical_semester(semester or student.semester or '') or '1'

        print(f"[api/dashboard-data] gmail={gmail_id!r} sem={semester_value!r} period={period!r} subject={subject!r}")

        # ── Main query — NO subject.in_() filter ─────────────────────────────
        # Filtering by SUBJECT_MASTER causes zero results when master ≠ DB.
        # We fetch all records for this student+semester+period, then build
        # subject_map from the actual returned rows.
        filtered_q = build_student_dashboard_filtered_query(
            gmail_id,
            semester_value,
            period,
            subject          # passed through to ilike filter inside the helper
        )
        records = filtered_q.order_by(
            Attendance.date.desc(), Attendance.attendance_id.desc()
        ).all()

        total   = len(records)
        present = sum(1 for r in records if normalize_status(r.status) == 'present')
        absent  = total - present
        percentage = round((present / total * 100), 2) if total else 0.0

        print(f"[api/dashboard-data] total={total}  present={present}  absent={absent}  pct={percentage}%")

        # ── Streak — use all-time records (no period filter) ─────────────────
        streak_records = build_student_dashboard_filtered_query(
            gmail_id, semester_value, 'all', ''
        ).order_by(Attendance.date.desc(), Attendance.attendance_id.desc()).all()
        current_streak = calculate_current_streak(streak_records)

        # ── Subject list — from actual DB records (preserves insertion order) ─
        # Use dict.fromkeys to deduplicate while keeping order.
        actual_subjects = list(dict.fromkeys(
            r.subject for r in records if r.subject
        ))

        # ── Subject-wise counts — built from the fetched records (no extra DB hit) ─
        subject_map: dict = {sub: {'present': 0, 'absent': 0} for sub in actual_subjects}
        for r in records:
            sub = r.subject or ''
            if sub not in subject_map:
                subject_map[sub] = {'present': 0, 'absent': 0}
            if normalize_status(r.status) == 'present':
                subject_map[sub]['present'] += 1
            else:
                subject_map[sub]['absent'] += 1

        return jsonify({
            'summary': {
                'present':        present,
                'absent':         absent,
                'total':          total,
                'percentage':     percentage,
                'current_streak': current_streak,
            },
            'records': [{
                'date':      r.date.isoformat() if r.date else '',
                'time':      format_lecture_time(r.time),
                'subject':   r.subject or '',
                'status':    r.status or '',
                'marked_by': r.marked_by or '',
                'remarks':   r.remarks or '',
            } for r in records],
            'charts': {
                'present_vs_absent': {
                    'labels': ['Present', 'Absent'],
                    'data':   [present, absent],
                },
                'subject_wise': {
                    'labels':  list(subject_map.keys()),
                    'present': [subject_map[k]['present'] for k in subject_map],
                    'absent':  [subject_map[k]['absent']  for k in subject_map],
                },
            },
            'subjects':  actual_subjects,
            'semester':  semester_value,
        })
    except Exception as e:
        import traceback
        print("api_student_dashboard_data error:", str(e))
        traceback.print_exc()
        return jsonify({'error': 'Unable to load dashboard data'}), 500




# ═══════════════════════════════════════════════════════════════════════════
# HELP & SUPPORT TICKET SYSTEM
# ═══════════════════════════════════════════════════════════════════════════

# ── Models ──────────────────────────────────────────────────────────────────
class Ticket(db.Model):
    __tablename__ = 'tickets'

    ticket_id    = db.Column(db.Integer, primary_key=True)
    ticket_ref   = db.Column(db.String(20), unique=True, nullable=False)   # e.g. TKT-00042
    student_id   = db.Column(db.Integer, db.ForeignKey('students.student_id'), nullable=False)
    subject      = db.Column(db.String(200), nullable=False)
    category     = db.Column(db.String(50),  nullable=False, default='Other')
    priority     = db.Column(db.String(20),  nullable=False, default='Medium')
    message      = db.Column(db.Text,        nullable=False)
    status       = db.Column(db.String(30),  nullable=False, default='Open')
    created_at   = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship('Student', backref=db.backref('tickets', lazy=True))
    replies = db.relationship('TicketReply', backref='ticket', lazy=True,
                              order_by='TicketReply.created_at')

    def __repr__(self):
        return f"<Ticket {self.ticket_ref} [{self.status}]>"


class TicketReply(db.Model):
    __tablename__ = 'ticket_replies'

    reply_id    = db.Column(db.Integer, primary_key=True)
    ticket_id   = db.Column(db.Integer, db.ForeignKey('tickets.ticket_id'), nullable=False)
    sender_type = db.Column(db.String(20), nullable=False)   # 'student' | 'teacher'
    sender_name = db.Column(db.String(100), nullable=False)
    message     = db.Column(db.Text, nullable=False)
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<TicketReply {self.reply_id} by {self.sender_type}>"


def _generate_ticket_ref():
    """Generate unique TKT-XXXXX reference."""
    last = Ticket.query.order_by(Ticket.ticket_id.desc()).first()
    next_num = (last.ticket_id + 1) if last else 1
    return f"TKT-{next_num:05d}"


def _ensure_ticket_tables():
    """Create ticket tables if they don't exist yet."""
    try:
        with app.app_context():
            db.create_all()
    except Exception as e:
        print("Ticket table creation error:", e)


# ── Student Routes ───────────────────────────────────────────────────────────

@app.route('/student/support')
def student_support():
    """Student: Help & Support landing — redirect to my tickets."""
    return redirect(url_for('student_my_tickets'))


@app.route('/student/support/raise', methods=['GET', 'POST'])
def student_raise_ticket():
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        flash('Please login first', 'error')
        return redirect(url_for('login'))

    student = Student.query.filter(
        func.lower(func.coalesce(Student.gmail_id, '')) == gmail_id.lower()
    ).first()
    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        subject  = (request.form.get('subject')  or '').strip()
        category = (request.form.get('category') or 'Other').strip()
        priority = (request.form.get('priority') or 'Medium').strip()
        message  = (request.form.get('message')  or '').strip()

        if not subject or not message:
            flash('Subject and message are required.', 'error')
            return redirect(url_for('student_raise_ticket'))

        try:
            ticket = Ticket(
                ticket_ref  = _generate_ticket_ref(),
                student_id  = student.student_id,
                subject     = subject,
                category    = category,
                priority    = priority,
                message     = message,
                status      = 'Open',
            )
            db.session.add(ticket)
            db.session.commit()
            flash(f'Ticket {ticket.ticket_ref} raised successfully!', 'success')
            return redirect(url_for('student_my_tickets'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error raising ticket: {str(e)}', 'error')
            return redirect(url_for('student_raise_ticket'))

    return render_template('student_raise_ticket.html', student=student)


@app.route('/student/support/tickets')
def student_my_tickets():
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        flash('Please login first', 'error')
        return redirect(url_for('login'))

    student = Student.query.filter(
        func.lower(func.coalesce(Student.gmail_id, '')) == gmail_id.lower()
    ).first()
    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('login'))

    tickets = Ticket.query.filter_by(student_id=student.student_id)\
                .order_by(Ticket.created_at.desc()).all()
    return render_template('student_ticket_list.html', student=student, tickets=tickets)


@app.route('/student/support/ticket/<int:ticket_id>', methods=['GET', 'POST'])
def student_ticket_detail(ticket_id):
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        flash('Please login first', 'error')
        return redirect(url_for('login'))

    student = Student.query.filter(
        func.lower(func.coalesce(Student.gmail_id, '')) == gmail_id.lower()
    ).first()
    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('login'))

    ticket = Ticket.query.filter_by(
        ticket_id=ticket_id, student_id=student.student_id
    ).first_or_404()

    if request.method == 'POST':
        if ticket.status == 'Closed':
            return jsonify({'success': False, 'error': 'Ticket is closed'}), 400

        msg = (request.form.get('message') or '').strip()
        if not msg:
            return jsonify({'success': False, 'error': 'Message is empty'}), 400

        try:
            reply = TicketReply(
                ticket_id   = ticket.ticket_id,
                sender_type = 'student',
                sender_name = student.full_name or 'Student',
                message     = msg,
            )
            ticket.status     = 'In Progress'
            ticket.updated_at = datetime.utcnow()
            db.session.add(reply)
            db.session.commit()
            return jsonify({
                'success':     True,
                'reply_id':    reply.reply_id,
                'sender_type': reply.sender_type,
                'sender_name': reply.sender_name,
                'message':     reply.message,
                'created_at':  reply.created_at.strftime('%d %b %Y, %I:%M %p'),
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

    return render_template('student_ticket_detail.html', student=student, ticket=ticket)


@app.route('/student/support/faq')
def student_faq():
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        flash('Please login first', 'error')
        return redirect(url_for('login'))
    return render_template('student_faq.html')


# ── Teacher Routes ───────────────────────────────────────────────────────────

@app.route('/support/center')
def teacher_support_center():
    if 'user_type' not in session or session['user_type'] != 'teacher':
        flash('Please login first as Teacher!', 'error')
        return redirect(url_for('login'))

    status_filter   = request.args.get('status',   'all')
    priority_filter = request.args.get('priority', 'all')

    q = Ticket.query
    if status_filter   != 'all': q = q.filter(Ticket.status   == status_filter)
    if priority_filter != 'all': q = q.filter(Ticket.priority == priority_filter)
    tickets = q.order_by(Ticket.created_at.desc()).all()

    open_count     = Ticket.query.filter_by(status='Open').count()
    progress_count = Ticket.query.filter_by(status='In Progress').count()
    closed_count   = Ticket.query.filter_by(status='Closed').count()
    total_count    = Ticket.query.count()

    return render_template(
        'teacher_support_center.html',
        tickets        = tickets,
        open_count     = open_count,
        progress_count = progress_count,
        closed_count   = closed_count,
        total_count    = total_count,
        status_filter  = status_filter,
        priority_filter= priority_filter,
    )


@app.route('/support/ticket/<int:ticket_id>', methods=['GET', 'POST'])
def teacher_ticket_detail(ticket_id):
    if 'user_type' not in session or session['user_type'] != 'teacher':
        flash('Please login first as Teacher!', 'error')
        return redirect(url_for('login'))

    ticket = Ticket.query.get_or_404(ticket_id)

    if request.method == 'POST':
        action = request.form.get('action', 'reply')

        # Change status
        if action == 'change_status':
            new_status = request.form.get('new_status', '').strip()
            if new_status in ('Open', 'In Progress', 'Closed'):
                ticket.status     = new_status
                ticket.updated_at = datetime.utcnow()
                try:
                    db.session.commit()
                    return jsonify({'success': True, 'new_status': new_status})
                except Exception as e:
                    db.session.rollback()
                    return jsonify({'success': False, 'error': str(e)}), 500
            return jsonify({'success': False, 'error': 'Invalid status'}), 400

        # Reply
        msg = (request.form.get('message') or '').strip()
        if not msg:
            return jsonify({'success': False, 'error': 'Message is empty'}), 400

        try:
            reply = TicketReply(
                ticket_id   = ticket.ticket_id,
                sender_type = 'teacher',
                sender_name = session.get('username', 'Teacher'),
                message     = msg,
            )
            if ticket.status == 'Open':
                ticket.status = 'In Progress'
            ticket.updated_at = datetime.utcnow()
            db.session.add(reply)
            db.session.commit()
            return jsonify({
                'success':     True,
                'reply_id':    reply.reply_id,
                'sender_type': reply.sender_type,
                'sender_name': reply.sender_name,
                'message':     reply.message,
                'created_at':  reply.created_at.strftime('%d %b %Y, %I:%M %p'),
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

    return render_template('teacher_ticket_detail.html', ticket=ticket)


# ── Real-time SSE: poll new replies for a ticket ────────────────────────────
import time as _time
import json as _json

@app.route('/support/ticket/<int:ticket_id>/stream')
def ticket_stream(ticket_id):
    """
    Server-Sent Events endpoint.
    Streams new TicketReply rows as they appear, every 2 seconds.
    Both student and teacher pages connect here.
    """
    # Auth: student must own the ticket, teacher can see any
    user_type = session.get('user_type')
    if not user_type:
        return Response('data: {"error":"unauthorized"}\n\n',
                        mimetype='text/event-stream', status=401)

    # Determine the last reply_id the client already has
    try:
        since_id = int(request.args.get('since', 0))
    except (ValueError, TypeError):
        since_id = 0

    def generate():
        last_id = since_id
        # Send a keep-alive comment immediately so the browser opens the stream
        yield ': keep-alive\n\n'
        while True:
            try:
                with app.app_context():
                    # Only fetch replies newer than what client already has
                    new_replies = TicketReply.query.filter(
                        TicketReply.ticket_id == ticket_id,
                        TicketReply.reply_id  >  last_id
                    ).order_by(TicketReply.reply_id.asc()).all()

                    for r in new_replies:
                        last_id = r.reply_id
                        payload = _json.dumps({
                            'reply_id':    r.reply_id,
                            'sender_type': r.sender_type or '',
                            'sender_name': r.sender_name or 'Unknown',
                            'message':     r.message or '',
                            'created_at':  r.created_at.strftime('%d %b %Y, %I:%M %p')
                                           if r.created_at else '',
                        })
                        yield f'data: {payload}\n\n'

                    # Also stream status changes
                    ticket_obj = Ticket.query.get(ticket_id)
                    if ticket_obj:
                        status_payload = _json.dumps({
                            'type':   'status',
                            'status': ticket_obj.status,
                        })
                        yield f'data: {status_payload}\n\n'

            except Exception as _e:
                yield f'data: {{"error":"{str(_e)}"}}\n\n'

            _time.sleep(2)   # poll every 2 seconds

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control':   'no-cache',
            'X-Accel-Buffering': 'no',   # disable nginx buffering if behind proxy
        }
    )


# Student-side SSE alias (same logic, different URL prefix)
@app.route('/student/support/ticket/<int:ticket_id>/stream')
def student_ticket_stream(ticket_id):
    """Student-facing SSE — validates student owns the ticket."""
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        return Response('data: {"error":"unauthorized"}\n\n',
                        mimetype='text/event-stream', status=401)
    # Verify ownership
    student = Student.query.filter(
        func.lower(func.coalesce(Student.gmail_id, '')) == gmail_id.lower()
    ).first()
    if not student:
        return Response('data: {"error":"unauthorized"}\n\n',
                        mimetype='text/event-stream', status=401)
    ticket_check = Ticket.query.filter_by(
        ticket_id=ticket_id, student_id=student.student_id
    ).first()
    if not ticket_check:
        return Response('data: {"error":"forbidden"}\n\n',
                        mimetype='text/event-stream', status=403)

    # Reuse the same generator logic
    try:
        since_id = int(request.args.get('since', 0))
    except (ValueError, TypeError):
        since_id = 0

    def generate():
        last_id      = since_id
        last_status  = ticket_check.status
        yield ': keep-alive\n\n'
        while True:
            try:
                with app.app_context():
                    new_replies = TicketReply.query.filter(
                        TicketReply.ticket_id == ticket_id,
                        TicketReply.reply_id  >  last_id
                    ).order_by(TicketReply.reply_id.asc()).all()

                    for r in new_replies:
                        last_id = r.reply_id
                        payload = _json.dumps({
                            'reply_id':    r.reply_id,
                            'sender_type': r.sender_type or '',
                            'sender_name': r.sender_name or 'Unknown',
                            'message':     r.message or '',
                            'created_at':  r.created_at.strftime('%d %b %Y, %I:%M %p')
                                           if r.created_at else '',
                        })
                        yield f'data: {payload}\n\n'

                    t_obj = Ticket.query.get(ticket_id)
                    if t_obj and t_obj.status != last_status:
                        last_status = t_obj.status
                        yield f'data: {_json.dumps({"type":"status","status":t_obj.status})}\n\n'

            except Exception as _e:
                yield f'data: {{"error":"{str(_e)}"}}\n\n'

            _time.sleep(2)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


# Open ticket count API (for sidebar badge)
@app.route('/support/open-count')
def support_open_count():
    if 'user_type' not in session or session['user_type'] != 'teacher':
        return jsonify({'count': 0})
    try:
        count = Ticket.query.filter_by(status='Open').count()
        return jsonify({'count': count})
    except Exception:
        return jsonify({'count': 0})


# Create tables on startup (safe — only creates if not exists)
with app.app_context():
    try:
        db.create_all()
        db.session.execute(text("ALTER TABLE students ADD COLUMN IF NOT EXISTS parent_email VARCHAR(100)"))
        db.session.execute(text("ALTER TABLE students ADD COLUMN IF NOT EXISTS guardian_email VARCHAR(100)"))
        db.session.commit()
    except Exception as _e:
        db.session.rollback()
        print("db.create_all warning:", _e)


# EMAIL + COUPON SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

def _make_coupon_code():
    """Generate a unique human-readable coupon code like NAV-A3BX9K2P."""
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(8))
    return f"NAV-{suffix}"


def _get_overall_pct(student_ids):
    """Return overall attendance % across all student_ids (list of ints)."""
    if not student_ids:
        return 0.0
    total = Attendance.query.filter(
        Attendance.student_id.in_(student_ids)
    ).count()
    if total == 0:
        return 0.0
    present = Attendance.query.filter(
        Attendance.student_id.in_(student_ids),
        Attendance.status == 'Present'
    ).count()
    return round((present / total) * 100, 2)


def _get_today_records(student_ids):
    """Return today's attendance records for a list of student_ids."""
    today = date.today()
    return Attendance.query.filter(
        Attendance.student_id.in_(student_ids),
        Attendance.date == today
    ).order_by(Attendance.marked_time.asc()).all()


def _get_email_recipients(student):
    """
    Build the recipient list for attendance emails.
    Current DB guarantees student gmail_id. If a future schema adds parent/guardian
    email fields, they will automatically be included.
    """
    import re
    recipients = []
    candidate_fields = [
        'gmail_id',
        'parent_email',
        'guardian_email',
        'father_email',
        'mother_email',
    ]
    email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    for field in candidate_fields:
        value = getattr(student, field, None)
        if value:
            email = str(value).strip()
            if email and email_re.fullmatch(email) and email not in recipients:
                recipients.append(email)
    return recipients


def send_attendance_email(student, today_records, overall_pct):
    """
    Send a daily attendance summary HTML email to a student via Gmail SMTP.
    Set MAIL_SENDER and MAIL_PASSWORD in environment variables or app.config.
    For Gmail: enable 2FA and create an App Password at
      https://myaccount.google.com/apppasswords
    """
    sender   = app.config.get('MAIL_SENDER', '')
    password = app.config.get('MAIL_PASSWORD', '')
    if not sender or not password:
        print("[email] MAIL_SENDER or MAIL_PASSWORD not configured — skipping.")
        return False
    recipients = _get_email_recipients(student)
    if not recipients:
        print(f"[email] No recipient email found for student {getattr(student, 'student_id', 'N/A')}")
        return False

    today_str     = date.today().strftime('%d %B %Y')
    present_today = sum(1 for r in today_records if (r.status or '').lower() == 'present')
    total_today   = len(today_records)

    rows_html = ''
    for r in today_records:
        sc = '#16a34a' if (r.status or '').lower() == 'present' else '#dc2626'
        si = '&#10003;' if (r.status or '').lower() == 'present' else '&#10007;'
        ts = r.marked_time.strftime('%I:%M %p') if r.marked_time else '&mdash;'
        rows_html += (
            '<tr>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;">{r.subject or "&mdash;"}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;color:#64748b;">{ts}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;font-weight:700;color:{sc};">'
            f'{si} {r.status or "&mdash;"}</td>'
            '</tr>'
        )
    if not rows_html:
        rows_html = ('<tr><td colspan="3" style="padding:12px;color:#94a3b8;text-align:center;">'
                     'No lectures recorded today.</td></tr>')

    if overall_pct >= 90:
        reward_msg   = '&#127942; Excellent! You qualify for a <strong>50% canteen discount coupon</strong>!'
        reward_color = '#16a34a'
    elif overall_pct >= 85:
        reward_msg   = '&#127881; Great job! You qualify for a <strong>45% canteen discount coupon</strong>!'
        reward_color = '#2563eb'
    elif overall_pct >= 75:
        reward_msg   = '&#128200; Keep it up! Reach 85% to unlock canteen discount rewards.'
        reward_color = '#d97706'
    else:
        reward_msg   = '&#9888; Your attendance needs improvement. Minimum 75% required.'
        reward_color = '#dc2626'

    pct_w = min(int(overall_pct), 100)
    pct_c = '#16a34a' if overall_pct >= 85 else ('#d97706' if overall_pct >= 75 else '#dc2626')

    html_body = (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"></head>'
        '<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f1f5f9;">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:30px 0;">'
        '<tr><td align="center">'
        '<table width="600" cellpadding="0" cellspacing="0" '
        'style="background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.10);">'
        '<tr><td style="background:linear-gradient(135deg,#1e3a8a,#2563eb);padding:28px 32px;text-align:center;">'
        '<h1 style="margin:0;color:#fff;font-size:22px;font-weight:800;">Navneet College</h1>'
        f'<p style="margin:6px 0 0;color:rgba(255,255,255,.75);font-size:13px;">'
        f'Daily Attendance Summary &mdash; {today_str}</p>'
        '</td></tr>'
        '<tr><td style="padding:24px 32px 0;">'
        f'<p style="margin:0;font-size:16px;color:#1e293b;">Dear <strong>{student.full_name or "Student"}</strong>,</p>'
        '<p style="margin:8px 0 0;font-size:14px;color:#64748b;">Here is your attendance summary for today.</p>'
        '</td></tr>'
        '<tr><td style="padding:20px 32px 0;">'
        '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td width="50%" style="padding-right:8px;">'
        f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;padding:16px;text-align:center;">'
        f'<div style="font-size:28px;font-weight:800;color:#16a34a;">{present_today}</div>'
        f'<div style="font-size:12px;color:#64748b;margin-top:4px;">PRESENT TODAY</div></div></td>'
        f'<td width="50%" style="padding-left:8px;">'
        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;">'
        f'<div style="font-size:28px;font-weight:800;color:#1e293b;">{total_today}</div>'
        f'<div style="font-size:12px;color:#64748b;margin-top:4px;">TOTAL LECTURES</div></div></td>'
        '</tr></table></td></tr>'
        '<tr><td style="padding:20px 32px 0;">'
        '<h3 style="margin:0 0 10px;font-size:13px;font-weight:700;color:#1e293b;'
        'text-transform:uppercase;letter-spacing:.06em;">Lecture-wise Status</h3>'
        '<table width="100%" cellpadding="0" cellspacing="0" '
        'style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;">'
        '<thead><tr style="background:#f8fafc;">'
        '<th style="padding:10px 12px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;">Subject</th>'
        '<th style="padding:10px 12px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;">Time</th>'
        '<th style="padding:10px 12px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;">Status</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table></td></tr>'
        '<tr><td style="padding:20px 32px 0;">'
        '<h3 style="margin:0 0 10px;font-size:13px;font-weight:700;color:#1e293b;'
        'text-transform:uppercase;letter-spacing:.06em;">Overall Attendance</h3>'
        '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px;">'
        f'<div style="font-size:24px;font-weight:800;color:{pct_c};text-align:center;margin-bottom:10px;">'
        f'{overall_pct}%</div>'
        f'<div style="background:#e2e8f0;border-radius:99px;height:8px;overflow:hidden;">'
        f'<div style="background:{pct_c};width:{pct_w}%;height:100%;border-radius:99px;"></div></div>'
        '</div></td></tr>'
        f'<tr><td style="padding:16px 32px 0;">'
        f'<div style="background:#f8fafc;border-left:4px solid {reward_color};'
        f'border-radius:0 10px 10px 0;padding:14px 16px;">'
        f'<p style="margin:0;font-size:13px;color:{reward_color};">{reward_msg}</p></div></td></tr>'
        '<tr><td style="padding:24px 32px;text-align:center;border-top:1px solid #f1f5f9;">'
        '<p style="margin:0;font-size:12px;color:#94a3b8;">'
        'Navneet College of Arts, Science &amp; Commerce<br>'
        'Mumbai Central, Mumbai, Maharashtra 400008<br>'
        '<em>This is an automated email. Please do not reply.</em></p>'
        '</td></tr>'
        '</table></td></tr></table></body></html>'
    )

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Attendance Summary - {today_str} | Navneet College"
    msg['From']    = f"Navneet College <{sender}>"
    msg['To']      = ', '.join(recipients)
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        with smtplib.SMTP(app.config['MAIL_SMTP_HOST'], app.config['MAIL_SMTP_PORT']) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(sender, password)
            smtp.sendmail(sender, recipients, msg.as_string())
        print(f"[email] Sent to {', '.join(recipients)} ({student.full_name})")
        return True
    except Exception as e:
        print(f"[email] Failed to send to {', '.join(recipients)}: {e}")
        return False


def send_attendance_email_for_student(student):
    """
    Send attendance email for one student by resolving all linked rows
    that share the same gmail_id. This keeps semester-wise duplicate rows
    from breaking overall attendance calculations.
    """
    if not student or not student.gmail_id:
        return False

    linked_ids = [
        s.student_id for s in Student.query.filter(
            func.lower(func.coalesce(Student.gmail_id, "")) == student.gmail_id.lower()
        ).all()
    ]
    if not linked_ids:
        linked_ids = [student.student_id]

    today_records = _get_today_records(linked_ids)
    overall_pct = _get_overall_pct(linked_ids)
    return send_attendance_email(student, today_records, overall_pct)


@app.route('/update_contact_emails', methods=['POST'])
def update_contact_emails():
    """
    Allow the logged-in student to save parent/guardian emails.
    Update all semester rows linked to the same student gmail_id.
    """
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    data = request.get_json(silent=True) or {}
    parent_email = (data.get('parent_email') or '').strip()
    guardian_email = (data.get('guardian_email') or '').strip()

    def _is_valid_email(value):
        if not value:
            return True
        import re
        return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value) is not None

    if not _is_valid_email(parent_email):
        return jsonify({'success': False, 'message': 'Invalid parent email format'}), 400
    if not _is_valid_email(guardian_email):
        return jsonify({'success': False, 'message': 'Invalid guardian email format'}), 400

    students = Student.query.filter(
        func.lower(func.coalesce(Student.gmail_id, "")) == gmail_id.lower()
    ).all()
    if not students:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    for student in students:
        student.parent_email = parent_email or None
        student.guardian_email = guardian_email or None

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Parent and guardian emails updated successfully.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'}), 500


def generate_coupon_for_student(student_id, overall_pct):
    """
    Generate or upgrade a reward coupon.
    >= 90% -> 50% discount (Gold tier)
    >= 85% -> 45% discount (Silver tier)
    < 85%  -> no coupon
    One active coupon per student. Expiry = 7 days.
    """
    if overall_pct < 85:
        return None

    discount = 50 if overall_pct >= 90 else 45

    existing = Coupon.query.filter(
        Coupon.student_id == student_id,
        Coupon.is_used == False,
        Coupon.expiry_date > datetime.utcnow()
    ).first()

    if existing:
        if discount > existing.discount_percentage:
            existing.discount_percentage = discount
            existing.attendance_pct      = overall_pct
            try:
                db.session.commit()
                print(f"[coupon] Upgraded {existing.coupon_code} to {discount}% for student {student_id}")
            except Exception as e:
                db.session.rollback()
                print(f"[coupon] Upgrade error: {e}")
        return existing

    code = _make_coupon_code()
    for _ in range(10):
        if not Coupon.query.filter_by(coupon_code=code).first():
            break
        code = _make_coupon_code()

    coupon = Coupon(
        student_id          = student_id,
        coupon_code         = code,
        discount_percentage = discount,
        issued_at           = datetime.utcnow(),
        expiry_date         = datetime.utcnow() + timedelta(days=7),
        is_used             = False,
        attendance_pct      = overall_pct,
    )
    try:
        db.session.add(coupon)
        db.session.commit()
        print(f"[coupon] Generated {code} ({discount}%) for student {student_id} (pct={overall_pct}%)")
        return coupon
    except Exception as e:
        db.session.rollback()
        print(f"[coupon] Error for student {student_id}: {e}")
        return None


def daily_attendance_job():
    """
    Scheduled daily job (default 12:00 PM IST):
    For every student with attendance today — send email + generate coupon.
    """
    print(f"[scheduler] daily_attendance_job started at {datetime.now()}")
    summary = {
        'processed_students': 0,
        'sent': 0,
        'failed': 0,
        'skipped': 0,
    }
    with app.app_context():
        today = date.today()
        today_sids = [
            r[0] for r in db.session.query(Attendance.student_id)
            .filter(Attendance.date == today).distinct().all()
        ]
        if not today_sids:
            print("[scheduler] No attendance today — nothing to do.")
            return summary
        print(f"[scheduler] Processing {len(today_sids)} students.")
        for sid in today_sids:
            try:
                student = Student.query.get(sid)
                if not student or not student.gmail_id:
                    summary['skipped'] += 1
                    continue
                all_ids = [
                    s.student_id for s in Student.query.filter(
                        func.lower(func.coalesce(Student.gmail_id, "")) == student.gmail_id.lower()
                    ).all()
                ]
                if sid != min(all_ids):
                    continue
                summary['processed_students'] += 1
                today_records = _get_today_records(all_ids)
                overall_pct   = _get_overall_pct(all_ids)
                if send_attendance_email(student, today_records, overall_pct):
                    summary['sent'] += 1
                else:
                    summary['failed'] += 1
                generate_coupon_for_student(sid, overall_pct)
            except Exception as e:
                print(f"[scheduler] Error for student {sid}: {e}")
                summary['failed'] += 1
    print(f"[scheduler] daily_attendance_job finished at {datetime.now()}")
    return summary


# ─── Student Rewards Routes ───────────────────────────────────────────────────

@app.route('/student/rewards')
def student_rewards():
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        flash('Please login first', 'error')
        return redirect(url_for('login'))

    all_rows = Student.query.filter(
        func.lower(func.coalesce(Student.gmail_id, "")) == gmail_id.lower()
    ).order_by(Student.student_id.asc()).all()
    if not all_rows:
        flash('Student not found', 'error')
        return redirect(url_for('login'))

    # ── Use global academic filter to scope rewards to active semester ────────
    _, active_sem = get_active_filter(gmail_id)

    # Find the student row that matches the active semester (if any)
    primary_student = all_rows[0]
    if active_sem:
        matched = next(
            (s for s in all_rows if canonical_semester(s.semester or '') == active_sem),
            None
        )
        student = matched if matched else primary_student
    else:
        student = primary_student

    # Compute overall_pct scoped to the active semester's student_id(s)
    # If a specific semester row is matched, use only that student_id;
    # otherwise fall back to all IDs (cross-semester aggregate).
    if active_sem and student != primary_student:
        scoped_ids = [student.student_id]
    else:
        scoped_ids = [s.student_id for s in all_rows]

    all_ids     = [s.student_id for s in all_rows]   # for coupon lookup (all-time)
    overall_pct = _get_overall_pct(scoped_ids)

    active_coupon = Coupon.query.filter(
        Coupon.student_id.in_(all_ids),
        Coupon.is_used == False,
        Coupon.expiry_date > datetime.utcnow()
    ).order_by(Coupon.issued_at.desc()).first()

    all_coupons = Coupon.query.filter(
        Coupon.student_id.in_(all_ids)
    ).order_by(Coupon.issued_at.desc()).limit(10).all()

    if overall_pct >= 90:
        eligible_discount = 50
        tier_label = 'Gold'
        tier_color = '#f59e0b'
    elif overall_pct >= 85:
        eligible_discount = 45
        tier_label = 'Silver'
        tier_color = '#64748b'
    else:
        eligible_discount = 0
        tier_label = None
        tier_color = None

    if eligible_discount > 0 and not active_coupon:
        active_coupon = generate_coupon_for_student(student.student_id, overall_pct)

    return render_template(
        'student_rewards.html',
        student           = student,
        overall_pct       = overall_pct,
        active_coupon     = active_coupon,
        all_coupons       = all_coupons,
        eligible_discount = eligible_discount,
        tier_label        = tier_label,
        tier_color        = tier_color,
        active_sem        = active_sem,
        now               = datetime.utcnow(),
    )


@app.route('/student/rewards/redeem/<coupon_code>', methods=['POST'])
def redeem_coupon(coupon_code):
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    all_ids = [
        s.student_id for s in Student.query.filter(
            func.lower(func.coalesce(Student.gmail_id, "")) == gmail_id.lower()
        ).all()
    ]
    coupon = Coupon.query.filter(
        Coupon.coupon_code == coupon_code.upper(),
        Coupon.student_id.in_(all_ids)
    ).first()
    if not coupon:
        return jsonify({'success': False, 'message': 'Coupon not found'}), 404
    if coupon.is_used:
        return jsonify({'success': False, 'message': 'Coupon already redeemed'}), 400
    if coupon.is_expired:
        return jsonify({'success': False, 'message': 'Coupon has expired'}), 400
    coupon.is_used = True
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': f'Coupon {coupon_code} redeemed!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/student/rewards')
def api_student_rewards():
    gmail_id = get_logged_in_student_email()
    if not gmail_id:
        return jsonify({'error': 'Not authenticated'}), 401
    all_rows = Student.query.filter(
        func.lower(func.coalesce(Student.gmail_id, "")) == gmail_id.lower()
    ).all()
    if not all_rows:
        return jsonify({'error': 'Student not found'}), 404
    all_ids     = [s.student_id for s in all_rows]
    overall_pct = _get_overall_pct(all_ids)
    active_coupon = Coupon.query.filter(
        Coupon.student_id.in_(all_ids),
        Coupon.is_used == False,
        Coupon.expiry_date > datetime.utcnow()
    ).order_by(Coupon.issued_at.desc()).first()
    return jsonify({
        'overall_pct': overall_pct,
        'active_coupon': {
            'code':     active_coupon.coupon_code,
            'discount': active_coupon.discount_percentage,
            'expiry':   active_coupon.expiry_date.strftime('%d %b %Y'),
            'is_used':  active_coupon.is_used,
        } if active_coupon else None,
    })


@app.route('/admin/trigger-daily-email', methods=['POST'])
def trigger_daily_email():
    """Manually send today's attendance emails now (teacher only)."""
    if 'user_type' not in session or session['user_type'] != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    summary = daily_attendance_job()
    sent = int(summary.get('sent', 0))
    failed = int(summary.get('failed', 0))
    skipped = int(summary.get('skipped', 0))
    if sent == 0 and failed == 0 and skipped == 0:
        return jsonify({'success': True, 'message': "Today's marked attendance was not found, so no emails were sent."})
    return jsonify({
        'success': failed == 0,
        'message': f"Today's attendance emails sent: {sent}. Failed: {failed}. Skipped: {skipped}.",
        'summary': summary
    })


@app.route('/teacher/send-report-emails', methods=['POST'])
def teacher_send_report_emails():
    """
    Teacher can send attendance emails either:
    1) in bulk for filtered class/course/semester students
    2) one-by-one using a specific student_id
    """
    if 'user_type' not in session or session['user_type'] != 'teacher':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    student_id = request.form.get('student_id', type=int)
    selected_course = (request.form.get('selected_course') or '').strip()
    selected_class = (request.form.get('selected_class') or '').strip()
    selected_semester = (request.form.get('selected_semester') or '').strip()

    if student_id:
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        ok = send_attendance_email_for_student(student)
        if ok:
            return jsonify({'success': True, 'message': f'Email sent to {student.full_name}.'})
        return jsonify({'success': False, 'message': 'Email could not be sent for this student.'}), 500

    if not all([selected_course, selected_class, selected_semester]):
        return jsonify({'success': False, 'message': 'Missing class filters for bulk email.'}), 400

    students = Student.query.filter_by(
        course=selected_course,
        class_yr=selected_class,
        semester=selected_semester
    ).order_by(Student.student_id.asc()).all()

    sent = 0
    failed = 0
    skipped = 0
    seen_emails = set()

    for student in students:
        email = (student.gmail_id or '').strip().lower()
        if not email or email in seen_emails:
            skipped += 1
            continue
        seen_emails.add(email)
        if send_attendance_email_for_student(student):
            sent += 1
        else:
            failed += 1

    return jsonify({
        'success': sent > 0 and failed == 0,
        'message': f'Bulk email completed. Sent: {sent}, Failed: {failed}, Skipped: {skipped}.',
        'sent': sent,
        'failed': failed,
        'skipped': skipped
    })


# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP — create tables + start scheduler
# ═══════════════════════════════════════════════════════════════════════════════

# Create tables on startup (safe — only creates if not exists)
with app.app_context():
    try:
        db.create_all()
    except Exception as _e:
        print("db.create_all warning:", _e)

# ─── APScheduler ──────────────────────────────────────────────────────────────
_scheduler = BackgroundScheduler(timezone='Asia/Kolkata')
_scheduler.add_job(
    func               = daily_attendance_job,
    trigger            = CronTrigger(
        hour   = app.config.get('MAIL_SEND_HOUR', 12),
        minute = app.config.get('MAIL_SEND_MINUTE', 0),
    ),
    id                 = 'daily_attendance_email',
    name               = 'Daily Attendance Email + Coupon',
    replace_existing   = True,
    misfire_grace_time = 600,
)
try:
    _scheduler.start()
    print(f"[scheduler] Started — daily job at "
          f"{app.config.get('MAIL_SEND_HOUR', 12):02d}:{app.config.get('MAIL_SEND_MINUTE', 0):02d} IST")
except Exception as _se:
    print(f"[scheduler] Could not start: {_se}")


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
