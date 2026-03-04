"""
Email service — sends transactional emails via SMTP.
If SMTP is not configured, all emails are logged to the terminal instead
(useful for local development without an email provider).
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.settings import settings

logger = logging.getLogger(__name__)


def _is_smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def _send(to: str, subject: str, html: str, plain: str) -> None:
    """Low-level SMTP send."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = to
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.email_from, to, msg.as_string())


# ---------------------------------------------------------------------------
# Email verification OTP
# ---------------------------------------------------------------------------
def send_verification_otp(to: str, otp: str) -> None:
    """Send a 6-digit OTP for email address verification."""
    subject = "Your verification code"
    plain = f"Your verification code is: {otp}\n\nIt expires in 24 hours."
    html = f"""
<!DOCTYPE html><html><body style="font-family:sans-serif;max-width:480px;margin:auto;padding:24px">
  <h2 style="color:#1e293b">Verify your email</h2>
  <p style="color:#475569">Enter the code below to verify your email address.</p>
  <div style="background:#f1f5f9;border-radius:12px;padding:24px;text-align:center;margin:24px 0">
    <span style="font-size:2.5rem;font-weight:700;letter-spacing:0.5rem;color:#1e293b">{otp}</span>
  </div>
  <p style="color:#94a3b8;font-size:0.875rem">This code expires in 24 hours. If you didn't create an account, ignore this email.</p>
</body></html>
"""

    if _is_smtp_configured():
        try:
            _send(to, subject, html, plain)
            logger.info(f"Verification OTP sent to {to}")
        except Exception as e:
            logger.error(f"Failed to send verification OTP to {to}: {e}")
            _log_to_terminal("VERIFICATION OTP", to, otp)
    else:
        _log_to_terminal("VERIFICATION OTP", to, otp)


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------
def send_password_reset_email(to: str, token: str) -> None:
    """Send a password-reset link."""
    reset_url = f"{settings.app_base_url}/reset-password?token={token}"
    subject = "Reset your password"
    plain = f"Reset your password by visiting:\n{reset_url}\n\nThis link expires in 1 hour."
    html = f"""
<!DOCTYPE html><html><body style="font-family:sans-serif;max-width:480px;margin:auto;padding:24px">
  <h2 style="color:#1e293b">Reset your password</h2>
  <p style="color:#475569">Click the button below to choose a new password. The link expires in 1 hour.</p>
  <div style="text-align:center;margin:32px 0">
    <a href="{reset_url}"
       style="background:#3b82f6;color:#fff;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:1rem">
      Reset Password
    </a>
  </div>
  <p style="color:#94a3b8;font-size:0.875rem">
    Or copy this link: <a href="{reset_url}" style="color:#3b82f6">{reset_url}</a>
  </p>
  <p style="color:#94a3b8;font-size:0.875rem">If you didn't request a password reset, ignore this email.</p>
</body></html>
"""

    if _is_smtp_configured():
        try:
            _send(to, subject, html, plain)
            logger.info(f"Password reset email sent to {to}")
        except Exception as e:
            logger.error(f"Failed to send reset email to {to}: {e}")
            _log_to_terminal("PASSWORD RESET LINK", to, reset_url)
    else:
        _log_to_terminal("PASSWORD RESET LINK", to, reset_url)


# ---------------------------------------------------------------------------
# Welcome email (optional — called after email is verified)
# ---------------------------------------------------------------------------
def send_welcome_email(to: str, name: str | None = None) -> None:
    greeting = f"Hi {name}," if name else "Welcome!"
    subject = "Welcome!"
    plain = f"{greeting}\n\nYour account is verified and ready to use."
    html = f"""
<!DOCTYPE html><html><body style="font-family:sans-serif;max-width:480px;margin:auto;padding:24px">
  <h2 style="color:#1e293b">{greeting}</h2>
  <p style="color:#475569">Your account is verified and ready to use. Jump in any time.</p>
</body></html>
"""

    if _is_smtp_configured():
        try:
            _send(to, subject, html, plain)
        except Exception as e:
            logger.error(f"Failed to send welcome email to {to}: {e}")
    else:
        logger.info(f"[EMAIL] Welcome email → {to}")


# ---------------------------------------------------------------------------
# Terminal fallback
# ---------------------------------------------------------------------------
def _log_to_terminal(label: str, to: str, value: str) -> None:
    bar = "─" * 56
    logger.warning(
        f"\n{bar}\n"
        f"  📧  {label}\n"
        f"  To : {to}\n"
        f"  Val: {value}\n"
        f"  (SMTP not configured — showing in terminal)\n"
        f"{bar}"
    )
