
import sqlite3
import hashlib
import hmac
import os
import secrets
import json
import smtplib

import streamlit as st

from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from email.message import EmailMessage


# -------------------------------------------------
# CONFIGURATION
# -------------------------------------------------

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "storybank.db"

load_dotenv(BASE_DIR / ".env", override=True)

OTP_EXPIRY_MINUTES = 10
OTP_RESEND_SECONDS = 60
MAX_OTP_ATTEMPTS = 5
PASSWORD_ITERATIONS = 200000


# -------------------------------------------------
# DATABASE CONNECTION
# -------------------------------------------------

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def add_column_if_missing(conn, table, column, definition):
    columns = {
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }

    if column not in columns:
        conn.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


# -------------------------------------------------
# PASSWORD SECURITY
# -------------------------------------------------

def hash_password(password):
    salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS
    ).hex()

    return f"{salt}${password_hash}"


def verify_password(password, stored_hash):
    try:
        salt, original_hash = stored_hash.split("$", 1)

        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            PASSWORD_ITERATIONS
        ).hex()

        return hmac.compare_digest(new_hash, original_hash)

    except (ValueError, AttributeError):
        return False


# -------------------------------------------------
# SECRET CONFIGURATION
# -------------------------------------------------

def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, "")

        if value:
            return str(value).strip()

    except Exception:
        pass

    return str(os.getenv(name, default)).strip()


def get_admin_credentials():
    admin_email = get_secret("ADMIN_EMAIL").lower()
    admin_password = get_secret("ADMIN_PASSWORD")

    return admin_email, admin_password


# -------------------------------------------------
# DATABASE INITIALIZATION
# -------------------------------------------------

def initialize_database():

    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS login_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                login_time TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS story_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                terms TEXT NOT NULL,
                genre TEXT NOT NULL,
                word_count INTEGER NOT NULL,
                story TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_otps (
                email TEXT PRIMARY KEY,
                otp_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                verified_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                requested_at TEXT NOT NULL,
                reviewed_at TEXT,
                reviewed_by INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (reviewed_by) REFERENCES users(id)
            )
        """)

        add_column_if_missing(
            conn, "users", "google_sub", "TEXT"
        )

        add_column_if_missing(
            conn, "users", "verified_at", "TEXT"
        )

        add_column_if_missing(
            conn, "password_reset_otps", "verified_at", "TEXT"
        )

        # Create or maintain the configured administrator.

        admin_email, admin_password = get_admin_credentials()

        if admin_email and admin_password:

            existing_admin = conn.execute("""
                SELECT id
                FROM users
                WHERE LOWER(TRIM(email)) = ?
            """, (admin_email,)).fetchone()

            if existing_admin:

                conn.execute("""
                    UPDATE users
                    SET role = 'admin',
                        password_hash = ?,
                        is_active = 1
                    WHERE id = ?
                """, (
                    hash_password(admin_password),
                    existing_admin["id"]
                ))

            else:

                conn.execute("""
                    INSERT INTO users
                    (
                        name,
                        email,
                        password_hash,
                        role,
                        is_active,
                        created_at
                    )
                    VALUES (?, ?, ?, 'admin', 1, ?)
                """, (
                    "Administrator",
                    admin_email,
                    hash_password(admin_password),
                    datetime.now().isoformat(timespec="seconds")
                ))


# -------------------------------------------------
# USER REGISTRATION
# -------------------------------------------------

def register_user(name, email, password):

    name = name.strip()
    email = email.strip().lower()

    if not name or not email or not password:
        return False, "Please fill in all fields."

    if len(password) < 6:
        return False, "Password must contain at least 6 characters."

    try:

        with get_connection() as conn:

            existing = conn.execute("""
                SELECT id
                FROM users
                WHERE email = ?
            """, (email,)).fetchone()

            if existing:
                return False, "An account with this email already exists."

            conn.execute("""
                INSERT INTO users
                (
                    name,
                    email,
                    password_hash,
                    role,
                    is_active,
                    created_at
                )
                VALUES (?, ?, ?, 'user', 1, ?)
            """, (
                name,
                email,
                hash_password(password),
                datetime.now().isoformat(timespec="seconds")
            ))

        return True, "Account created successfully. You can now log in."

    except sqlite3.Error as error:
        return False, f"Registration failed: {error}"


# -------------------------------------------------
# USER LOGIN
# -------------------------------------------------

def authenticate_user(email, password):

    email = email.strip().lower()

    with get_connection() as conn:

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE LOWER(TRIM(email)) = ?
        """, (email,)).fetchone()

    if not user:
        return None

    if not user["is_active"]:
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    return dict(user)


# -------------------------------------------------
# LOGIN HISTORY
# -------------------------------------------------

def record_login(user_id):

    with get_connection() as conn:

        conn.execute("""
            INSERT INTO login_history
            (user_id, login_time)
            VALUES (?, ?)
        """, (
            user_id,
            datetime.now().isoformat(timespec="seconds")
        ))


def get_login_history():

    with get_connection() as conn:

        rows = conn.execute("""
            SELECT
                users.name,
                users.email,
                login_history.login_time
            FROM login_history
            JOIN users
                ON users.id = login_history.user_id
            ORDER BY login_history.id DESC
        """).fetchall()

    return [
        (
            row["name"],
            row["email"],
            row["login_time"]
        )
        for row in rows
    ]


# -------------------------------------------------
# SAVE GENERATED STORIES
# -------------------------------------------------

def save_story(user_id, terms, genre, word_count, story):

    if isinstance(terms, (list, tuple)):
        terms = json.dumps(
            list(terms),
            ensure_ascii=False
        )
    else:
        terms = str(terms)

    with get_connection() as conn:

        conn.execute("""
            INSERT INTO story_history
            (
                user_id,
                terms,
                genre,
                word_count,
                story,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            terms,
            genre,
            word_count,
            story,
            datetime.now().isoformat(timespec="seconds")
        ))


# -------------------------------------------------
# USER STORY HISTORY
# -------------------------------------------------

def get_user_stories(user_id):

    with get_connection() as conn:

        rows = conn.execute("""
            SELECT
                id,
                terms,
                genre,
                word_count,
                story,
                created_at
            FROM story_history
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user_id,)).fetchall()

    return [
        (
            row["id"],
            row["terms"],
            row["genre"],
            row["word_count"],
            row["story"],
            row["created_at"]
        )
        for row in rows
    ]


# -------------------------------------------------
# ALL REGISTERED USERS
# -------------------------------------------------

def get_all_users():

    with get_connection() as conn:

        rows = conn.execute("""
            SELECT
                id,
                name,
                email,
                role,
                is_active,
                created_at
            FROM users
            ORDER BY id DESC
        """).fetchall()

    return [
        (
            row["id"],
            row["name"],
            row["email"],
            row["role"],
            row["is_active"],
            row["created_at"]
        )
        for row in rows
    ]


# -------------------------------------------------
# ACTIVATE / DEACTIVATE USERS
# -------------------------------------------------

def set_user_active(user_id, is_active):

    with get_connection() as conn:

        conn.execute("""
            UPDATE users
            SET is_active = ?
            WHERE id = ?
            AND role = 'user'
        """, (
            1 if is_active else 0,
            user_id
        ))


# -------------------------------------------------
# ALL GENERATED STORIES
# -------------------------------------------------

def get_all_stories():

    with get_connection() as conn:

        rows = conn.execute("""
            SELECT
                story_history.id,
                users.name,
                users.email,
                story_history.terms,
                story_history.genre,
                story_history.word_count,
                story_history.story,
                story_history.created_at
            FROM story_history
            JOIN users
                ON users.id = story_history.user_id
            ORDER BY story_history.id DESC
        """).fetchall()

    return [
        (
            row["id"],
            row["name"],
            row["email"],
            row["terms"],
            row["genre"],
            row["word_count"],
            row["story"],
            row["created_at"]
        )
        for row in rows
    ]


# -------------------------------------------------
# DASHBOARD STATISTICS
# -------------------------------------------------

def get_dashboard_stats():

    with get_connection() as conn:

        total_users = conn.execute("""
            SELECT COUNT(*) FROM users
        """).fetchone()[0]

        total_admins = conn.execute("""
            SELECT COUNT(*)
            FROM users
            WHERE role = 'admin'
        """).fetchone()[0]

        total_regular_users = conn.execute("""
            SELECT COUNT(*)
            FROM users
            WHERE role = 'user'
        """).fetchone()[0]

        total_stories = conn.execute("""
            SELECT COUNT(*) FROM story_history
        """).fetchone()[0]

    return {
        "total_users": total_users,
        "total_admins": total_admins,
        "total_regular_users": total_regular_users,
        "total_stories": total_stories
    }


# -------------------------------------------------
# USER STORY COUNTS
# -------------------------------------------------

def get_user_story_counts():

    with get_connection() as conn:

        rows = conn.execute("""
            SELECT
                users.id,
                users.name,
                users.email,
                users.role,
                users.is_active,
                COUNT(story_history.id) AS story_count
            FROM users
            LEFT JOIN story_history
                ON users.id = story_history.user_id
            GROUP BY users.id
            ORDER BY story_count DESC
        """).fetchall()

    return [
        (
            row["id"],
            row["name"],
            row["email"],
            row["role"],
            row["is_active"],
            row["story_count"]
        )
        for row in rows
    ]


# -------------------------------------------------
# GET USER ADMIN REQUEST
# -------------------------------------------------

def get_user_admin_request(user_id):

    with get_connection() as conn:

        row = conn.execute("""
            SELECT
                id,
                status,
                requested_at,
                reviewed_at
            FROM admin_requests
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
        """, (user_id,)).fetchone()

    return dict(row) if row else None


# -------------------------------------------------
# REQUEST ADMIN ACCESS
# -------------------------------------------------

def request_admin_access(user_id):

    with get_connection() as conn:

        user = conn.execute("""
            SELECT id, role, is_active
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        if not user:
            return False, "User account not found."

        if not user["is_active"]:
            return False, "Your account is inactive."

        if user["role"] == "admin":
            return False, "You already have administrator access."

        pending = conn.execute("""
            SELECT id
            FROM admin_requests
            WHERE user_id = ?
            AND status = 'pending'
        """, (user_id,)).fetchone()

        if pending:
            return False, "Your request is already pending."

        conn.execute("""
            INSERT INTO admin_requests
            (user_id, status, requested_at)
            VALUES (?, 'pending', ?)
        """, (
            user_id,
            datetime.now().isoformat(timespec="seconds")
        ))

    return True, "Admin access request submitted successfully."


# -------------------------------------------------
# GET PENDING ADMIN REQUESTS
# -------------------------------------------------

def get_pending_admin_requests():

    with get_connection() as conn:

        rows = conn.execute("""
            SELECT
                admin_requests.id AS request_id,
                users.id AS user_id,
                users.name,
                users.email,
                admin_requests.requested_at
            FROM admin_requests
            JOIN users
                ON users.id = admin_requests.user_id
            WHERE admin_requests.status = 'pending'
            ORDER BY admin_requests.requested_at ASC
        """).fetchall()

    return [
        (
            row["request_id"],
            row["user_id"],
            row["name"],
            row["email"],
            row["requested_at"]
        )
        for row in rows
    ]


# -------------------------------------------------
# APPROVE OR REJECT ADMIN REQUEST
# -------------------------------------------------

def review_admin_request(request_id, admin_user_id, decision):

    if decision not in ("approved", "rejected"):
        return False, "Invalid decision."

    with get_connection() as conn:

        admin = conn.execute("""
            SELECT id, role, is_active
            FROM users
            WHERE id = ?
        """, (admin_user_id,)).fetchone()

        if (
            not admin
            or admin["role"] != "admin"
            or not admin["is_active"]
        ):
            return False, "Only an active administrator can review requests."

        request = conn.execute("""
            SELECT id, user_id, status
            FROM admin_requests
            WHERE id = ?
        """, (request_id,)).fetchone()

        if not request:
            return False, "Admin request not found."

        if request["status"] != "pending":
            return False, "This request has already been reviewed."

        target_user = conn.execute("""
            SELECT id, is_active
            FROM users
            WHERE id = ?
        """, (request["user_id"],)).fetchone()

        if not target_user or not target_user["is_active"]:
            return False, "The requesting user is not active."

        conn.execute("""
            UPDATE admin_requests
            SET status = ?,
                reviewed_at = ?,
                reviewed_by = ?
            WHERE id = ?
        """, (
            decision,
            datetime.now().isoformat(timespec="seconds"),
            admin_user_id,
            request_id
        ))

        if decision == "approved":

            conn.execute("""
                UPDATE users
                SET role = 'admin'
                WHERE id = ?
            """, (request["user_id"],))

    if decision == "approved":
        return True, "Admin access approved successfully."

    return True, "Admin access request rejected."


# -------------------------------------------------
# SEND PASSWORD RESET OTP USING GMAIL SMTP
# -------------------------------------------------

def send_password_reset_otp(email):

    email = email.strip().lower()

    if not email:
        return False, "Enter your email address."

    # Check whether the email belongs to a registered user.

    with get_connection() as conn:

        user = conn.execute("""
            SELECT id
            FROM users
            WHERE LOWER(TRIM(email)) = ?
        """, (email,)).fetchone()

    if not user:
        return False, "No account found with this email address."

    now = datetime.now()

    # Check OTP resend limit.

    with get_connection() as conn:

        previous = conn.execute("""
            SELECT created_at
            FROM password_reset_otps
            WHERE email = ?
        """, (email,)).fetchone()

        if previous:

            try:
                previous_time = datetime.fromisoformat(
                    previous["created_at"]
                )

                elapsed = (now - previous_time).total_seconds()

                if elapsed < OTP_RESEND_SECONDS:

                    wait = int(OTP_RESEND_SECONDS - elapsed) + 1

                    return False, (
                        f"Please wait {wait} seconds "
                        "before requesting another OTP."
                    )

            except ValueError:
                pass

    # Gmail SMTP settings.

    smtp_email = get_secret("SMTP_EMAIL")
    smtp_password = get_secret("SMTP_APP_PASSWORD").replace(" ", "")
    smtp_host = get_secret("SMTP_HOST", "smtp.gmail.com")

    try:
        smtp_port = int(get_secret("SMTP_PORT", "465"))
    except (ValueError, TypeError):
        return False, "Invalid SMTP_PORT. Use 465 or 587."

    if not smtp_email or not smtp_password:

        return False, (
            "Gmail SMTP is not configured. "
            "Check SMTP_EMAIL and SMTP_APP_PASSWORD "
            "in your .env file."
        )

    # Generate OTP.

    otp = str(secrets.randbelow(900000) + 100000)

    otp_hash = hashlib.sha256(
        otp.encode()
    ).hexdigest()

    created_at = now.isoformat(timespec="seconds")

    expires_at = (
        now + timedelta(minutes=OTP_EXPIRY_MINUTES)
    ).isoformat(timespec="seconds")

    # Prepare email.

    message = EmailMessage()

    message["Subject"] = "StoryBank Password Reset OTP"
    message["From"] = smtp_email
    message["To"] = email

    message.set_content(
        f"""
Hello,

Your StoryBank password reset OTP is: {otp}

This OTP expires in 10 minutes.

If you did not request this password reset,
please ignore this email.

Thank you,
StoryBank Team
"""
    )

    message.add_alternative(
        f"""
        <html>
            <body>
                <h2>StoryBank Password Reset</h2>
                <p>Your OTP is:</p>
                <h1>{otp}</h1>
                <p>This OTP expires in 10 minutes.</p>
                <p>If you did not request this,
                please ignore this email.</p>
                <p>Thank you,<br>StoryBank Team</p>
            </body>
        </html>
        """,
        subtype="html"
    )

    try:

        # Connect to Gmail and send the email.

        if smtp_port == 465:

            with smtplib.SMTP_SSL(
                smtp_host,
                smtp_port,
                timeout=20
            ) as server:

                server.login(smtp_email, smtp_password)
                server.send_message(message)

        else:

            with smtplib.SMTP(
                smtp_host,
                smtp_port,
                timeout=20
            ) as server:

                server.ehlo()
                server.starttls()
                server.ehlo()

                server.login(smtp_email, smtp_password)
                server.send_message(message)

        # Save OTP after successful email sending.

        with get_connection() as conn:

            conn.execute("""
                INSERT OR REPLACE INTO password_reset_otps
                (
                    email,
                    otp_hash,
                    expires_at,
                    created_at,
                    attempts,
                    verified_at
                )
                VALUES (?, ?, ?, ?, 0, NULL)
            """, (
                email,
                otp_hash,
                expires_at,
                created_at
            ))

        return True, "OTP sent successfully to your email."

    except smtplib.SMTPAuthenticationError:

        return False, (
            "Gmail authentication failed. "
            "Check your Gmail App Password."
        )

    except smtplib.SMTPRecipientsRefused:

        return False, (
            "Gmail could not send the OTP to this recipient. "
            "Please check the email address."
        )

    except (smtplib.SMTPException, OSError) as error:

        print("Gmail SMTP error:", str(error))

        return False, (
            "Unable to send OTP using Gmail. "
            "Check your SMTP settings and internet connection."
        )

    except Exception as error:

        print("Unexpected OTP email error:", str(error))

        return False, (
            "An unexpected error occurred while sending OTP."
        )


# -------------------------------------------------
# VERIFY PASSWORD RESET OTP
# -------------------------------------------------

def verify_password_reset_otp(email, otp):

    email = email.strip().lower()
    otp = otp.strip()

    with get_connection() as conn:

        record = conn.execute("""
            SELECT *
            FROM password_reset_otps
            WHERE email = ?
        """, (email,)).fetchone()

        if not record:
            return False, "Please request an OTP first."

        if record["verified_at"]:
            return True, "OTP already verified."

        if record["attempts"] >= MAX_OTP_ATTEMPTS:

            return False, (
                "Too many incorrect attempts. "
                "Request a new OTP."
            )

        if datetime.now() > datetime.fromisoformat(
            record["expires_at"]
        ):

            return False, "OTP expired. Please request a new OTP."

        entered_hash = hashlib.sha256(
            otp.encode()
        ).hexdigest()

        if not hmac.compare_digest(
            entered_hash,
            record["otp_hash"]
        ):

            conn.execute("""
                UPDATE password_reset_otps
                SET attempts = attempts + 1
                WHERE email = ?
            """, (email,))

            return False, "Incorrect OTP. Please try again."

        conn.execute("""
            UPDATE password_reset_otps
            SET verified_at = ?
            WHERE email = ?
        """, (
            datetime.now().isoformat(timespec="seconds"),
            email
        ))

    return True, "OTP verified successfully."


# -------------------------------------------------
# RESET PASSWORD AFTER OTP VERIFICATION
# -------------------------------------------------

def reset_password_with_verified_otp(email, new_password):

    email = email.strip().lower()

    if not email or not new_password:
        return False, "Please fill in all fields."

    if len(new_password) < 6:
        return False, "Password must contain at least 6 characters."

    with get_connection() as conn:

        record = conn.execute("""
            SELECT verified_at, expires_at
            FROM password_reset_otps
            WHERE email = ?
        """, (email,)).fetchone()

        if not record:
            return False, "Please request an OTP first."

        if not record["verified_at"]:
            return False, "Please verify your OTP first."

        if datetime.now() > datetime.fromisoformat(
            record["expires_at"]
        ):

            conn.execute("""
                DELETE FROM password_reset_otps
                WHERE email = ?
            """, (email,))

            return False, "OTP expired. Please request a new OTP."

        user = conn.execute("""
            SELECT id
            FROM users
            WHERE LOWER(TRIM(email)) = ?
        """, (email,)).fetchone()

        if not user:
            return False, "User account not found."

        conn.execute("""
            UPDATE users
            SET password_hash = ?
            WHERE id = ?
        """, (
            hash_password(new_password),
            user["id"]
        ))

        conn.execute("""
            DELETE FROM password_reset_otps
            WHERE email = ?
        """, (email,))

    return True, "Password reset successfully. You can now log in."
