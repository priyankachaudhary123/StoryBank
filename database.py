
def send_password_reset_otp(email):

    email = (email or "").strip().lower()

    if not email:
        return False, "Please enter your email address."

    # Check for an active account, ignoring email case and extra spaces.
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
            previous_time = datetime.fromisoformat(existing[0])
            elapsed = (datetime.now() - previous_time).total_seconds()

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
            "Gmail rejected the SMTP login. Check your Gmail App Password."
        )

    except (smtplib.SMTPException, OSError) as error:
        print("OTP email connection error:", repr(error))
        return False, (
            "Could not connect to Gmail SMTP. "
            f"Check your settings ({type(error).__name__})."
        )
