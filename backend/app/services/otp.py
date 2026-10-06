# Email OTP. Twilio Verify generates, sends, stores and checks the code.
# We never see or store the code. DevOtp is used locally when Twilio is not set.
import asyncio
import logging
from fastapi import HTTPException
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client
from app.config import settings

log = logging.getLogger("otp")


class TwilioOtp:
    def __init__(self) -> None:
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self.svc = client.verify.v2.services(settings.twilio_verify_sid)

    async def send(self, email: str) -> None:
        try:
            # Twilio's SDK is blocking, so run it in a thread.
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


use_dev = not settings.twilio_verify_sid and settings.env != "prod"
otp = DevOtp() if use_dev else TwilioOtp()
