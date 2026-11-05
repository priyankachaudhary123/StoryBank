
import sqlite3
import hashlib
import hmac
import os
import secrets
import json
import requests
import smtplib
import streamlit as st

from email.message import EmailMessage
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv


# -------------------------------------------------
# Configuration
# -------------------------------------------------

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "storybank.db"

load_dotenv(BASE_DIR / ".env")

OTP_EXPIRY_MINUTES = 10
OTP_RESEND_SECONDS = 60
MAX_OTP_ATTEMPTS = 5
PASSWORD_ITERATIONS = 200000

ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_USER = "user"

VALID_ROLES = {
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_USER,
}


# -------------------------------------------------
# Database connection
# -------------------------------------------------

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------------------------------
# Safe database migration helper
# -------------------------------------------------

def add_column_if_missing(conn, table, column, definition):

    columns = {
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }

    if column not in columns:
        try:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
            )
        except sqlite3.OperationalError as error:
            if "duplicate column name" not in str(error).lower():
                raise


# -------------------------------------------------
# Password security
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
# Admin credentials and Streamlit Secrets
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
# Initialize database
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

        add_column_if_missing(
            conn, "users", "google_sub", "TEXT"
        )

        add_column_if_missing(
            conn, "users", "verified_at", "TEXT"
        )

        add_column_if_missing(
            conn, "password_reset_otps", "verified_at", "TEXT"
        )

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
                    SET role = ?,
                        password_hash = ?,
                        is_active = 1
                    WHERE id = ?
                """, (
                    ROLE_SUPER_ADMIN,
                    hash_password(admin_password),
                    existing_admin["id"]
                ))

                conn.execute("""
                    UPDATE users
                    SET role = ?
                    WHERE role = ?
                      AND id != ?
                """, (
                    ROLE_ADMIN,
                    ROLE_SUPER_ADMIN,
                    existing_admin["id"]
                ))

            else:

                conn.execute("""
                    INSERT INTO users
                    (name, email, password_hash, role, is_active, created_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                """, (
                    "Administrator",
                    admin_email,
                    hash_password(admin_password),
                    ROLE_SUPER_ADMIN,
                    datetime.now().isoformat(timespec="seconds")
                ))

                new_admin = conn.execute("""
                    SELECT id
                    FROM users
                    WHERE LOWER(TRIM(email)) = ?
                """, (admin_email,)).fetchone()

                conn.execute("""
                    UPDATE users
                    SET role = ?
                    WHERE role = ?
                      AND id != ?
                """, (
                    ROLE_ADMIN,
                    ROLE_SUPER_ADMIN,
                    new_admin["id"]
                ))


# -------------------------------------------------
# Admin diagnostic
# -------------------------------------------------

def check_admin_status():

    admin_email, admin_password = get_admin_credentials()

    with get_connection() as conn:

        user = None

        if admin_email:

            user = conn.execute("""
                SELECT role, is_active
                FROM users
                WHERE LOWER(TRIM(email)) = ?
            """, (admin_email,)).fetchone()

    return {
        "admin_email_configured": bool(admin_email),
        "admin_password_configured": bool(admin_password),
        "admin_record_found": user is not None,
        "admin_role": user["role"] if user else None,
        "admin_active": bool(user["is_active"]) if user else None
    }


# -------------------------------------------------
# User registration
# -------------------------------------------------

def register_user(name, email, password):

    name = (name or "").strip()
    email = (email or "").strip().lower()

    if not name or not email or not password:
        return False, "Please fill in all fields."

    if len(password) < 6:
        return False, "Password must contain at least 6 characters."

    try:

        with get_connection() as conn:

            conn.execute("""
                INSERT INTO users
                (name, email, password_hash, role, is_active, created_at)
                VALUES (?, ?, ?, 'user', 1, ?)
            """, (
                name,
                email,
                hash_password(password),
                datetime.now().isoformat(timespec="seconds")
            ))

        return True, "Account created successfully. Please log in."

    except sqlite3.IntegrityError:

        return False, "An account with this email already exists."

    except sqlite3.Error as error:

        print("Registration database error:", repr(error))

        return False, "Unable to create your account. Please try again."


# -------------------------------------------------
# User authentication
# -------------------------------------------------

def authenticate_user(email, password):

    email = (email or "").strip().lower()

    if not email or not password:
        return None

    with get_connection() as conn:

        user = conn.execute("""
            SELECT id, name, email, password_hash, role, is_active
            FROM users
            WHERE LOWER(TRIM(email)) = ?
        """, (email,)).fetchone()

    if not user or not user["is_active"]:
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"]
    }


# -------------------------------------------------
# Record login
# -------------------------------------------------

def record_login(user_id):

    with get_connection() as conn:

        conn.execute("""
            INSERT INTO login_history (user_id, login_time)
            VALUES (?, ?)
        """, (
            user_id,
            datetime.now().isoformat(timespec="seconds")
        ))


# -------------------------------------------------
# Save generated story
# -------------------------------------------------

def save_story(user_id, terms, genre, word_count, story):

    terms_json = json.dumps(terms)

    with get_connection() as conn:

        conn.execute("""
            INSERT INTO story_history
            (user_id, terms, genre, word_count, story, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            terms_json,
            genre,
            word_count,
            story,
            datetime.now().isoformat(timespec="seconds")
        ))


# -------------------------------------------------
# Get user's stories
# -------------------------------------------------

def get_user_stories(user_id):

    with get_connection() as conn:

        stories = conn.execute("""
            SELECT id, terms, genre, word_count, story, created_at
            FROM story_history
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user_id,)).fetchall()

    result = []

    for story in stories:

        try:
            terms = json.loads(story["terms"])
        except (ValueError, TypeError):
            terms = story["terms"]

        result.append((
            story["id"],
            terms,
            story["genre"],
            story["word_count"],
            story["story"],
            story["created_at"]
        ))

    return result


# -------------------------------------------------
# Get all users (Admin)
# -------------------------------------------------

def get_all_users():

    with get_connection() as conn:

        users = conn.execute("""
            SELECT id, name, email, role, is_active, created_at
            FROM users
            ORDER BY id DESC
        """).fetchall()

    return [
        (
            user["id"],
            user["name"],
            user["email"],
            user["role"],
            user["is_active"],
            user["created_at"]
        )
        for user in users
    ]


# -------------------------------------------------
# Get all stories (Admin)
# -------------------------------------------------

def get_all_stories():

    with get_connection() as conn:

        stories = conn.execute("""
            SELECT
                s.id,
                u.name,
                u.email,
                s.terms,
                s.genre,
                s.word_count,
                s.story,
                s.created_at
            FROM story_history s
            JOIN users u ON s.user_id = u.id
            ORDER BY s.id DESC
        """).fetchall()

    result = []

    for story in stories:

        try:
            terms = json.loads(story["terms"])
        except (ValueError, TypeError):
            terms = story["terms"]

        result.append((
            story["id"],
            story["name"],
            story["email"],
            terms,
            story["genre"],
            story["word_count"],
            story["story"],
            story["created_at"]
        ))

    return result


# -------------------------------------------------
# Get login history (Admin)
# -------------------------------------------------

def get_login_history():

    with get_connection() as conn:

        history = conn.execute("""
            SELECT u.name, u.email, l.login_time
            FROM login_history l
            JOIN users u ON l.user_id = u.id
            ORDER BY l.id DESC
        """).fetchall()

    return [
        (
            item["name"],
            item["email"],
            item["login_time"]
        )
        for item in history
    ]


# -------------------------------------------------
# Activate / deactivate users (Admin)
# -------------------------------------------------

def _get_user_role(conn, user_id):

    user = conn.execute(
        "SELECT role FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    return user["role"] if user else None


def _can_manage_target(actor_role, target_role):

    return (
        actor_role == ROLE_SUPER_ADMIN
        and target_role in {ROLE_ADMIN, ROLE_USER}
    )


def set_user_active(actor_id, user_id, is_active):

    with get_connection() as conn:

        actor_role = _get_user_role(conn, actor_id)
        target_role = _get_user_role(conn, user_id)

        if not actor_role or not target_role:
            return False, "User account not found."

        if actor_id == user_id:
            return False, "You cannot change your own account status."

        if not _can_manage_target(actor_role, target_role):
            return False, "You do not have permission to manage this account."

        conn.execute("""
            UPDATE users
            SET is_active = ?
            WHERE id = ?
        """, (
            1 if is_active else 0,
            user_id
        ))

    return True, "Account status updated."


def set_user_role(actor_id, user_id, new_role):

    if new_role not in VALID_ROLES or new_role == ROLE_SUPER_ADMIN:
        return False, "Invalid role assignment."

    with get_connection() as conn:

        actor_role = _get_user_role(conn, actor_id)
        target_role = _get_user_role(conn, user_id)

        if not actor_role or not target_role:
            return False, "User account not found."

        if actor_id == user_id:
            return False, "You cannot change your own role."

        can_promote_user = (
            actor_role == ROLE_ADMIN
            and target_role == ROLE_USER
            and new_role == ROLE_ADMIN
        )

        can_manage_as_super_admin = (
            actor_role == ROLE_SUPER_ADMIN
            and target_role in {ROLE_ADMIN, ROLE_USER}
        )

        if not can_promote_user and not can_manage_as_super_admin:
            return False, "Only the super administrator can remove admin access."

        conn.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (new_role, user_id)
        )

    return True, "User role updated."


def delete_user(actor_id, user_id):

    with get_connection() as conn:

        actor_role = _get_user_role(conn, actor_id)
        target_role = _get_user_role(conn, user_id)

        if not actor_role or not target_role:
            return False, "User account not found."

        if actor_id == user_id:
            return False, "You cannot delete your own account."

        if not _can_manage_target(actor_role, target_role):
            return False, "You do not have permission to delete this account."

        conn.execute(
            "DELETE FROM login_history WHERE user_id = ?",
            (user_id,)
        )

        conn.execute(
            "DELETE FROM story_history WHERE user_id = ?",
            (user_id,)
        )

        conn.execute(
            "DELETE FROM users WHERE id = ?",
            (user_id,)
        )

    return True, "Account deleted."


# -------------------------------------------------
# Send OTP email using Gmail SMTP
# -------------------------------------------------

def send_otp_email(email, otp):

    smtp_email = get_secret("SMTP_EMAIL")
    smtp_password = get_secret("SMTP_APP_PASSWORD")

    if smtp_email and smtp_password:

        message = f"""
Hello,

Your StoryBank password reset OTP is:

{otp}

This OTP is valid for {OTP_EXPIRY_MINUTES} minutes.

If you did not request this password reset, ignore this email.

StoryBank Team
"""

        email_message = EmailMessage()
        email_message["Subject"] = "StoryBank Password Reset OTP"
        email_message["From"] = smtp_email
        email_message["To"] = email
        email_message.set_content(message)

        with smtplib.SMTP_SSL(
            get_secret("SMTP_HOST", "smtp.gmail.com"),
            int(get_secret("SMTP_PORT", "465")),
            timeout=30
        ) as smtp:

            smtp.login(smtp_email, smtp_password)
            smtp.send_message(email_message)

        return

    # Optional Resend fallback, only when Gmail SMTP is not configured.
    resend_api_key = get_secret("RESEND_API_KEY")

    if resend_api_key:

        sender_email = get_secret("RESEND_FROM_EMAIL")

        if not sender_email:
            raise ValueError(
                "Configure RESEND_FROM_EMAIL or Gmail SMTP settings."
            )

        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "from": sender_email,
                "to": [email],
                "subject": "StoryBank Password Reset OTP",
                "text": f"""
Hello,

Your StoryBank password reset OTP is:

{otp}

This OTP is valid for {OTP_EXPIRY_MINUTES} minutes.

If you did not request this password reset, ignore this email.

StoryBank Team
"""
            },
            timeout=30
        )

        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Resend API error ({response.status_code}): "
                f"{response.text[:500]}"
            )

        return

    raise ValueError(
        "Configure SMTP_EMAIL and SMTP_APP_PASSWORD "
        "using your Gmail App Password."
    )


# -------------------------------------------------
# Send password reset OTP
# -------------------------------------------------

def send_password_reset_otp(email):

    email = (email or "").strip().lower()

    if not email:
        return False, "Please enter your email address."

    with get_connection() as conn:

        user = conn.execute("""
            SELECT id
            FROM users
            WHERE LOWER(TRIM(email)) = ?
              AND is_active = 1
        """, (email,)).fetchone()

        existing = conn.execute("""
            SELECT created_at
            FROM password_reset_otps
            WHERE email = ?
        """, (email,)).fetchone()

    if not user:

        return False, "Unable to process this request. Check your email address."

    if existing:

        try:

            previous_time = datetime.fromisoformat(
                existing["created_at"]
            )

            elapsed = (
                datetime.now() - previous_time
            ).total_seconds()

            if elapsed < OTP_RESEND_SECONDS:

                remaining = int(
                    OTP_RESEND_SECONDS - elapsed
                ) + 1

                return False, (
                    f"Please wait {remaining} seconds before requesting another OTP."
                )

        except (ValueError, TypeError):
            pass

    otp = f"{secrets.randbelow(1000000):06d}"

    otp_hash = hashlib.sha256(
        otp.encode("utf-8")
    ).hexdigest()

    now = datetime.now()

    expires_at = (
        now + timedelta(minutes=OTP_EXPIRY_MINUTES)
    ).isoformat(timespec="seconds")

    try:

        # Send email before saving the OTP.
        send_otp_email(email, otp)

        with get_connection() as conn:

            conn.execute("""
                INSERT OR REPLACE INTO password_reset_otps
                (email, otp_hash, expires_at, created_at, attempts, verified_at)
                VALUES (?, ?, ?, ?, 0, NULL)
            """, (
                email,
                otp_hash,
                expires_at,
                now.isoformat(timespec="seconds")
            ))

        return True, "OTP sent successfully to your email."

    except ValueError as error:

        print("OTP email configuration error:", repr(error))

        return False, str(error)

    except requests.RequestException as error:

        print("Email service connection error:", repr(error))

        return False, (
            "Could not connect to the email service. Please try again."
        )

    except smtplib.SMTPException as error:

        print("Gmail SMTP error:", repr(error))

        return False, (
            "Could not send the OTP email. Check your Gmail SMTP settings."
        )

    except RuntimeError as error:

        print("Resend API error:", str(error))

        return False, str(error)

    except (sqlite3.Error, OSError) as error:

        print("OTP processing error:", repr(error))

        return False, "Email could not be processed. Please try again."


# -------------------------------------------------
# Verify password reset OTP
# -------------------------------------------------

def verify_password_reset_otp(email, otp):

    email = (email or "").strip().lower()
    otp = (otp or "").strip()

    if not email or len(otp) != 6 or not otp.isdigit():

        return False, "Please enter a valid 6-digit OTP."

    with get_connection() as conn:

        record = conn.execute("""
            SELECT otp_hash, expires_at, attempts
            FROM password_reset_otps
            WHERE email = ?
        """, (email,)).fetchone()

        if not record:

            return False, "No OTP request found. Please request a new OTP."

        if record["attempts"] >= MAX_OTP_ATTEMPTS:

            conn.execute(
                "DELETE FROM password_reset_otps WHERE email = ?",
                (email,)
            )

            return False, "Too many incorrect attempts. Please request a new OTP."

        if datetime.now() > datetime.fromisoformat(record["expires_at"]):

            conn.execute(
                "DELETE FROM password_reset_otps WHERE email = ?",
                (email,)
            )

            return False, "OTP has expired. Please request a new one."

        entered_hash = hashlib.sha256(
            otp.encode("utf-8")
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
# Reset password after OTP verification
# -------------------------------------------------

def reset_password_with_verified_otp(email, new_password):

    email = (email or "").strip().lower()

    if not email or not new_password:

        return False, "Please enter a new password."

    if len(new_password) < 6:

        return False, "Password must contain at least 6 characters."

    with get_connection() as conn:

        record = conn.execute("""
            SELECT expires_at, attempts, verified_at
            FROM password_reset_otps
            WHERE email = ?
        """, (email,)).fetchone()

        if not record:

            return False, "Please request and verify your OTP again."

        if not record["verified_at"]:

            return False, "Please verify your OTP before resetting your password."

        if record["attempts"] >= MAX_OTP_ATTEMPTS:

            return False, "Too many attempts. Please request a new OTP."

        if datetime.now() > datetime.fromisoformat(record["expires_at"]):

            conn.execute(
                "DELETE FROM password_reset_otps WHERE email = ?",
                (email,)
            )

            return False, "OTP has expired. Please request a new OTP."

        result = conn.execute("""
            UPDATE users
            SET password_hash = ?
            WHERE LOWER(TRIM(email)) = ?
              AND is_active = 1
        """, (
            hash_password(new_password),
            email
        ))

        if result.rowcount == 0:

            return False, "Unable to update the password. Account not found."

        conn.execute(
            "DELETE FROM password_reset_otps WHERE email = ?",
            (email,)
        )

    return True, "Password reset successfully. Please log in."
