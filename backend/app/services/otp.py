# Email OTP. Three interchangeable providers, same two methods: send(email), check(email, code).
#   EmailOtp  - we make, store and check the code ourselves; any SMTP server sends the mail
#   TwilioOtp - Twilio Verify does all of it (needs a SendGrid account behind it)
#   DevOtp    - local only: code is always 123456
import asyncio
import hmac
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from fastapi import HTTPException
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client
from app.config import settings
from app.db.postgres import SessionLocal
from app.models.user import OtpCode

log = logging.getLogger("otp")
MAX_ATTEMPTS = 5  # wrong tries allowed per code
COOLDOWN_S = 60  # minimum gap between two codes for the same email


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # sqlite (tests) returns naive


# ---------- sending the mail (any SMTP server: Gmail, Brevo, AWS SES, ...) ----------
def _smtp_send_sync(to: str, code: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = "Your Web Chat verification code"
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.set_content(
        f"Your Web Chat verification code is {code}\n\n"
        f"It expires in {settings.otp_minutes} minutes. If you did not ask for it, ignore this email."
    )
    if settings.smtp_port == 465:  # implicit TLS
        server = smtplib.SMTP_SSL(settings.smtp_host, 465, timeout=10)
    else:  # STARTTLS (587)
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
        server.starttls()
    with server:
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


async def _smtp_send(to: str, code: str) -> None:
    await asyncio.to_thread(_smtp_send_sync, to, code)  # smtplib blocks, so use a thread


class EmailOtp:
    def __init__(self, sender=None) -> None:
        self.sender = sender or _smtp_send  # tests pass a fake sender

    @staticmethod
    def _digest(email: str, code: str) -> str:
        # Keyed hash: a leaked table alone cannot be used to guess codes offline.
        return hmac.new(settings.jwt_secret.encode(), f"{email}:{code}".encode(), "sha256").hexdigest()

    async def send(self, email: str) -> None:
        now = _now()
        code = f"{secrets.randbelow(10**6):06d}"  # secure random, always 6 digits
        async with SessionLocal() as db:
            row = await db.get(OtpCode, email)
            if row and (now - _utc(row.sent_at)).total_seconds() < COOLDOWN_S:
                raise HTTPException(429, "Please wait a minute before asking for a new code.")
            if row:  # a new code replaces the old one
                row.code_hash, row.attempts = self._digest(email, code), 0
                row.sent_at, row.expires_at = now, now + timedelta(minutes=settings.otp_minutes)
            else:
                db.add(OtpCode(email=email, code_hash=self._digest(email, code), sent_at=now,
                               expires_at=now + timedelta(minutes=settings.otp_minutes)))
            await db.commit()
        try:
            await self.sender(email, code)
        except Exception as e:
            log.warning("email send failed: %s", type(e).__name__)
            async with SessionLocal() as db:  # let the user retry at once
                row = await db.get(OtpCode, email)
                if row:
                    await db.delete(row)
                    await db.commit()
            raise HTTPException(503, "Could not send the code. Try again.")

    async def check(self, email: str, code: str) -> bool:
        async with SessionLocal() as db:
            row = await db.get(OtpCode, email)
            if not row or _utc(row.expires_at) < _now() or row.attempts >= MAX_ATTEMPTS:
                return False
            row.attempts += 1  # every try counts, right or wrong
            ok = hmac.compare_digest(row.code_hash, self._digest(email, code))
            if ok:
                await db.delete(row)  # one-time: a used code is gone
            await db.commit()
            return ok


class TwilioOtp:
    def __init__(self) -> None:
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self.svc = client.verify.v2.services(settings.twilio_verify_sid)

    async def send(self, email: str) -> None:
        try:
            await asyncio.to_thread(self.svc.verifications.create, to=email, channel="email")
        except TwilioRestException as e:
            log.warning("twilio send failed: %s", e.code)
            if e.status == 429:
                raise HTTPException(429, "Too many codes requested. Try again later.")
            raise HTTPException(503, "Could not send the code. Try again.")

    async def check(self, email: str, code: str) -> bool:
        try:
            r = await asyncio.to_thread(self.svc.verification_checks.create, to=email, code=code)
        except TwilioRestException as e:
            if e.status == 404:  # code expired or never sent
                return False
            log.warning("twilio check failed: %s", e.code)
            raise HTTPException(503, "Could not verify the code. Try again.")
        return r.status == "approved"


class DevOtp:
    async def send(self, email: str) -> None:
        log.warning("DEV OTP for %s is 123456", email)

    async def check(self, email: str, code: str) -> bool:
        return code == "123456"


def _pick():
    name = settings.otp_provider
    if name == "auto":  # first one that is configured
        name = "twilio" if settings.twilio_verify_sid else "email" if settings.smtp_host else "dev"
    if name == "dev" and settings.env == "prod":
        raise RuntimeError("DevOtp must not run in prod")
    return {"twilio": TwilioOtp, "email": EmailOtp, "dev": DevOtp}[name]()


otp = _pick()
