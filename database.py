
import sqlite3
import hashlib
import hmac
import os
import secrets
import smtplib

from pathlib import Path
from datetime import datetime, timedelta
from email.message import EmailMessage
from dotenv import load_dotenv

# -----------------------------
# Environment configuration
# -----------------------------
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = BASE_DIR / "storybank.db"

OTP_EXPIRY_MINUTES = 10
OTP_RESEND_SECONDS = 60
MAX_OTP_ATTEMPTS = 5


# -----------------------------
# Database connection
# -----------------------------
def get_connection():
    return sqlite3.connect(DB_PATH)


# -----------------------------
# Password hashing
# -----------------------------
def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200000
    )

    return salt.hex() + ":" + password_hash.hex()


def verify_password(password, stored_hash):
    try:
        salt_hex, hash_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)

        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            200000
        )

        return hmac.compare_digest(new_hash.hex(), hash_hex)

    except (ValueError, TypeError, AttributeError):
        return False


# -----------------------------
# Initialize database
# -----------------------------
def initialize_database():

    with get_connection() as conn:

        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                google_sub TEXT
            )
        """)

        # Migrate existing databases safely
        columns = [
            row[1] for row in cursor.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        ]

        if "google_sub" not in columns:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN google_sub TEXT"
            )

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_users_google_sub
            ON users(google_sub)
            WHERE google_sub IS NOT NULL
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                login_time TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_otps (
                email TEXT PRIMARY KEY,
                otp_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                verified_at TEXT
            )
        """)

        otp_columns = [
            row[1] for row in cursor.execute(
                "PRAGMA table_info(password_reset_otps)"
            ).fetchall()
        ]

        if "verified_at" not in otp_columns:
            cursor.execute(
                "ALTER TABLE password_reset_otps ADD COLUMN verified_at TEXT"
            )

        # Create admin account
        admin_email = os.getenv("ADMIN_EMAIL")
        admin_password = os.getenv("ADMIN_PASSWORD")

        if admin_email and admin_password:

            admin_email = admin_email.strip().lower()

            cursor.execute(
                "SELECT id FROM users WHERE email = ?",
                (admin_email,)
            )

            if cursor.fetchone() is None:

                cursor.execute("""
                    INSERT INTO users
                    (name, email, password_hash, role, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    "Administrator",
                    admin_email,
                    hash_password(admin_password),
                    "admin",
                    datetime.now().isoformat(timespec="seconds")
                ))


# -----------------------------
# Google sign-in
# -----------------------------
def get_or_create_google_user(email, name, google_sub):

    email = (email or "").strip().lower()
    name = (name or "").strip()
    google_sub = (google_sub or "").strip()

    if not email or not name or not google_sub:
        return None, "Google did not provide all required account details."

    try:

        with get_connection() as conn:

            # Check whether this Google account already exists
            user = conn.execute("""
                SELECT id, name, email, role, is_active, google_sub
                FROM users
                WHERE google_sub = ?
            """, (google_sub,)).fetchone()

            if user:

                if not user[4]:
                    return None, "Your account is inactive. Contact the administrator."

                return {
                    "id": user[0],
                    "name": user[1],
                    "email": user[2],
                    "role": user[3]
                }, None

            # Check whether an email/password account already exists
            user = conn.execute("""
                SELECT id, name, email, role, is_active, google_sub
                FROM users
                WHERE email = ?
            """, (email,)).fetchone()

            if user:

                if not user[4]:
                    return None, "Your account is inactive. Contact the administrator."

                if user[5] and user[5] != google_sub:
                    return None, "This email is linked to another Google account."

                # Link the verified Google identity to the existing account
                conn.execute("""
                    UPDATE users
                    SET google_sub = ?
                    WHERE id = ?
                """, (google_sub, user[0]))

                return {
                    "id": user[0],
                    "name": user[1],
                    "email": user[2],
                    "role": user[3]
                }, None

            # Create a new Google user
            random_password = secrets.token_urlsafe(32)

            cursor = conn.execute("""
                INSERT INTO users
                (name, email, password_hash, role, is_active,
                 created_at, google_sub)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                email,
                hash_password(random_password),
                "user",
                1,
                datetime.now().isoformat(timespec="seconds"),
                google_sub
            ))

            return {
                "id": cursor.lastrowid,
                "name": name,
                "email": email,
                "role": "user"
            }, None

    except sqlite3.IntegrityError:
        return None, "This Google account is already linked to another account."

    except sqlite3.Error:
        return None, "A database error occurred during Google sign-in."


# -----------------------------
# Register user
# -----------------------------
def register_user(name, email, password):

    name = name.strip()
    email = email.strip().lower()

    if not name or not email or not password:
        return False, "All fields are required."

    if len(password) < 8:
        return False, "Password must contain at least 8 characters."

    try:

        with get_connection() as conn:

            conn.execute("""
                INSERT INTO users
                (name, email, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                name,
                email,
                hash_password(password),
                "user",
                datetime.now().isoformat(timespec="seconds")
            ))

        return True, "Registration successful."

    except sqlite3.IntegrityError:
        return False, "This email is already registered."


# -----------------------------
# Authenticate user
# -----------------------------
def authenticate_user(email, password):

    email = email.strip().lower()

    with get_connection() as conn:

        user = conn.execute("""
            SELECT id, name, email, password_hash, role, is_active
            FROM users
            WHERE email = ?
        """, (email,)).fetchone()

    if not user:
        return None

    if not user[5] or not verify_password(password, user[3]):
        return None

    return {
        "id": user[0],
        "name": user[1],
        "email": user[2],
        "role": user[4]
    }


# -----------------------------
# Send OTP email
# -----------------------------
def send_otp_email(email, otp):

    smtp_email = (os.getenv("SMTP_EMAIL") or "").strip()
    smtp_password = "".join(
        (os.getenv("SMTP_APP_PASSWORD") or "").split()
    )

    if not smtp_email or not smtp_password:
        raise ValueError(
            "SMTP_EMAIL or SMTP_APP_PASSWORD is missing in .env."
        )

    message = EmailMessage()

    message["Subject"] = "StoryBank - Password Reset OTP"
    message["From"] = smtp_email
    message["To"] = email

    message.set_content(f"""
Hello,

We received a request to reset your StoryBank password.

Your verification OTP is: {otp}

This OTP is valid for 10 minutes.

Do not share this OTP with anyone.

If you did not request a password reset, you can ignore this email.

Regards,
StoryBank Team
""")

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:

        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(message)


# -----------------------------
# Generate and send OTP
# -----------------------------
def send_password_reset_otp(email):

    email = email.strip().lower()

    if not email:
        return False, "Please enter your email address."

    with get_connection() as conn:

        user = conn.execute(
            "SELECT id FROM users WHERE email = ? AND is_active = 1",
            (email,)
        ).fetchone()

        if not user:
            return False, "Unable to process this request. Check your email address."

        existing = conn.execute("""
            SELECT created_at
            FROM password_reset_otps
            WHERE email = ?
        """, (email,)).fetchone()

    if existing:

        try:
            previous_time = datetime.fromisoformat(existing[0])

            elapsed = (
                datetime.now() - previous_time
            ).total_seconds()

            if elapsed < OTP_RESEND_SECONDS:
                remaining = int(OTP_RESEND_SECONDS - elapsed) + 1

                return False, (
                    f"Please wait {remaining} seconds before requesting another OTP."
                )

        except ValueError:
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
            "Gmail rejected the SMTP login. Check that SMTP_EMAIL is the "
            "Google account address and SMTP_APP_PASSWORD is a valid Gmail "
            "App Password (2-Step Verification must be enabled)."
        )

    except (smtplib.SMTPException, OSError) as error:

        print("OTP email connection error:", repr(error))

        return False, (
            "Could not connect to Gmail SMTP. Check your internet connection "
            f"and Gmail SMTP settings ({type(error).__name__})."
        )


# -----------------------------
# Verify password reset OTP
# -----------------------------
def verify_password_reset_otp(email, otp):

    email = email.strip().lower()
    otp = otp.strip()

    if not email or not otp:
        return False, "Email and OTP are required."

    if not otp.isdigit() or len(otp) != 6:
        return False, "Please enter a valid 6-digit OTP."

    with get_connection() as conn:

        record = conn.execute("""
            SELECT otp_hash, expires_at, attempts
            FROM password_reset_otps
            WHERE email = ?
        """, (email,)).fetchone()

        if not record:
            return False, "OTP not found. Please request a new OTP."

        stored_hash, expires_at, attempts = record

        if attempts >= MAX_OTP_ATTEMPTS:
            conn.execute(
                "DELETE FROM password_reset_otps WHERE email = ?",
                (email,)
            )

            return False, "Too many attempts. Please request a new OTP."

        if datetime.now() > datetime.fromisoformat(expires_at):

            conn.execute(
                "DELETE FROM password_reset_otps WHERE email = ?",
                (email,)
            )

            return False, "OTP has expired. Please request a new OTP."

        entered_hash = hashlib.sha256(
            otp.encode("utf-8")
        ).hexdigest()

        if not hmac.compare_digest(entered_hash, stored_hash):

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

    return True, "OTP verified. You can now create a new password."


# -----------------------------
# Reset password after OTP verification
# -----------------------------
def reset_password_with_verified_otp(email, new_password):

    email = email.strip().lower()

    if not email or not new_password:
        return False, "Email and new password are required."

    if len(new_password) < 8:
        return False, "Password must contain at least 8 characters."

    with get_connection() as conn:

        record = conn.execute("""
            SELECT expires_at, verified_at
            FROM password_reset_otps
            WHERE email = ?
        """, (email,)).fetchone()

        if not record:
            return False, "OTP not found. Please request a new OTP."

        expires_at, verified_at = record

        if not verified_at:
            return False, "Please verify your OTP before resetting your password."

        if datetime.now() > datetime.fromisoformat(expires_at):

            conn.execute(
                "DELETE FROM password_reset_otps WHERE email = ?",
                (email,)
            )

            return False, "OTP has expired. Please request a new OTP."

        cursor = conn.execute("""
            UPDATE users
            SET password_hash = ?
            WHERE email = ? AND is_active = 1
        """, (
            hash_password(new_password),
            email
        ))

        if cursor.rowcount == 0:
            return False, "Unable to reset password for this account."

        conn.execute(
            "DELETE FROM password_reset_otps WHERE email = ?",
            (email,)
        )

    return True, "Password reset successful. You can now log in."


# -----------------------------
# Record login
# -----------------------------
def record_login(user_id):

    with get_connection() as conn:

        conn.execute("""
            INSERT INTO login_history (user_id, login_time)
            VALUES (?, ?)
        """, (
            user_id,
            datetime.now().isoformat(timespec="seconds")
        ))


# -----------------------------
# Save generated story
# -----------------------------
def save_story(user_id, terms, genre, word_count, story):

    with get_connection() as conn:

        conn.execute("""
            INSERT INTO story_history
            (user_id, terms, genre, word_count, story, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            ", ".join(terms),
            genre,
            word_count,
            story,
            datetime.now().isoformat(timespec="seconds")
        ))


# -----------------------------
# Get user's stories
# -----------------------------
def get_user_stories(user_id):

    with get_connection() as conn:

        return conn.execute("""
            SELECT id, terms, genre, word_count, story, created_at
            FROM story_history
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user_id,)).fetchall()


# -----------------------------
# Get all users
# -----------------------------
def get_all_users():

    with get_connection() as conn:

        return conn.execute("""
            SELECT id, name, email, role, is_active, created_at
            FROM users
            ORDER BY id DESC
        """).fetchall()


# -----------------------------
# Get all stories
# -----------------------------
def get_all_stories():

    with get_connection() as conn:

        return conn.execute("""
            SELECT story_history.id, users.name, users.email,
                   story_history.terms, story_history.genre,
                   story_history.word_count, story_history.story,
                   story_history.created_at
            FROM story_history
            JOIN users ON users.id = story_history.user_id
            ORDER BY story_history.id DESC
        """).fetchall()


# -----------------------------
# Get login history
# -----------------------------
def get_login_history():

    with get_connection() as conn:

        return conn.execute("""
            SELECT users.name, users.email, login_history.login_time
            FROM login_history
            JOIN users ON users.id = login_history.user_id
            ORDER BY login_history.id DESC
        """).fetchall()


# -----------------------------
# Activate / deactivate user
# -----------------------------
def set_user_active(user_id, is_active):

    with get_connection() as conn:

        conn.execute("""
            UPDATE users
            SET is_active = ?
            WHERE id = ? AND role = 'user'
        """, (1 if is_active else 0, user_id))
