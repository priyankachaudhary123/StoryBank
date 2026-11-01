
import sqlite3
import hashlib
import hmac
import os
import secrets
import smtplib
import json

import streamlit as st

from pathlib import Path
from datetime import datetime, timedelta
from email.message import EmailMessage
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


# -------------------------------------------------
# Database connection
# -------------------------------------------------

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


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
# Admin credentials
# -------------------------------------------------

def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value).strip()
    except Exception:
        pass

    return os.getenv(name, default).strip()


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
                attempts INTEGER DEFAULT 0
            )
        """)

        # Migrate older database versions safely.
        user_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        if "google_sub" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN google_sub TEXT"
            )

        if "verified_at" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN verified_at TEXT"
            )

        # Create or update the administrator account.
        admin_email, admin_password = get_admin_credentials()

        if admin_email and admin_password:

            existing_admin = conn.execute(
                "SELECT id FROM users WHERE LOWER(TRIM(email)) = ?",
                (admin_email,)
            ).fetchone()

            password_hash = hash_password(admin_password)

            if existing_admin:
                conn.execute("""
                    UPDATE users
                    SET role = 'admin',
                        password_hash = ?,
                        is_active = 1
                    WHERE id = ?
                """, (password_hash, existing_admin["id"]))

            else:
                conn.execute("""
                    INSERT INTO users
                    (name, email, password_hash, role, is_active, created_at)
                    VALUES (?, ?, ?, 'admin', 1, ?)
                """, (
                    "Administrator",
                    admin_email,
                    password_hash,
                    datetime.now().isoformat(timespec="seconds")
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

    if not user:
        return None

    if not user["is_active"]:
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

def set_user_active(user_id, is_active):

    with get_connection() as conn:

        conn.execute("""
            UPDATE users
            SET is_active = ?
            WHERE id = ? AND role = 'user'
        """, (
            1 if is_active else 0,
            user_id
        ))


# -------------------------------------------------
# Send OTP email
# -------------------------------------------------

def send_otp_email(email, otp):

    smtp_email = get_secret("SMTP_EMAIL")
    smtp_password = get_secret("SMTP_APP_PASSWORD")

    if not smtp_email or not smtp_password:
        raise ValueError(
            "Email settings are missing. Configure SMTP_EMAIL "
            "and SMTP_APP_PASSWORD in Streamlit Secrets."
        )

    message = EmailMessage()
    message["Subject"] = "StoryBank Password Reset OTP"
    message["From"] = smtp_email
    message["To"] = email

    message.set_content(
        f"""
Hello,

Your StoryBank password reset OTP is:

{otp}

This OTP is valid for {OTP_EXPIRY_MINUTES} minutes.

If you did not request this password reset, ignore this email.

StoryBank Team
"""
    )

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(message)


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
            previous_time = datetime.fromisoformat(existing["created_at"])
            elapsed = (datetime.now() - previous_time).total_seconds()

            if elapsed < OTP_RESEND_SECONDS:
                remaining = int(OTP_RESEND_SECONDS - elapsed) + 1
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
        send_otp_email(email, otp)

        with get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO password_reset_otps
                (email, otp_hash, expires_at, created_at, attempts)
                VALUES (?, ?, ?, ?, 0)
            """, (
                email,
                otp_hash,
                expires_at,
                now.isoformat(timespec="seconds")
            ))

        return True, "OTP sent successfully to your email."

    except ValueError as error:
        print("OTP email error:", repr(error))
        return False, str(error)

    except smtplib.SMTPAuthenticationError as error:
        print("OTP email authentication error:", repr(error))
        return False, (
            "Gmail rejected the SMTP login. Check your Gmail App Password."
        )

    except (smtplib.SMTPException, OSError) as error:
        print("OTP email connection error:", repr(error))
        return False, (
            "Could not connect to Gmail SMTP. "
            f"Check your settings ({type(error).__name__})."
        )


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

        if not hmac.compare_digest(entered_hash, record["otp_hash"]):

            conn.execute("""
                UPDATE password_reset_otps
                SET attempts = attempts + 1
                WHERE email = ?
            """, (email,))

            return False, "Incorrect OTP. Please try again."

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
            SELECT expires_at, attempts
            FROM password_reset_otps
            WHERE email = ?
        """, (email,)).fetchone()

        if not record:
            return False, "Please verify your OTP again."

        if record["attempts"] >= MAX_OTP_ATTEMPTS:
            return False, "Too many attempts. Please request a new OTP."

        if datetime.now() > datetime.fromisoformat(record["expires_at"]):
            conn.execute(
                "DELETE FROM password_reset_otps WHERE email = ?",
                (email,)
            )
            return False, "OTP has expired. Please request a new OTP."

        # IMPORTANT:
        # The app calls this function only after OTP verification.
        conn.execute("""
            UPDATE users
            SET password_hash = ?
            WHERE LOWER(TRIM(email)) = ?
              AND is_active = 1
        """, (
            hash_password(new_password),
            email
        ))

        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            return False, "Unable to update the password. Account not found."

        conn.execute(
            "DELETE FROM password_reset_otps WHERE email = ?",
            (email,)
        )

    return True, "Password reset successfully. Please log in."
