# Settings come from environment variables (or .env). Validated at startup.
from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"  # dev | test | prod
    database_url: str = "postgresql+asyncpg://webchat:webchat@localhost:5432/webchat"
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "webchat"
    jwt_secret: str = "change-me"
    access_minutes: int = 15
    refresh_days: int = 7
    signup_minutes: int = 15
    allowed_origins: str = "http://localhost:5173"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_verify_sid: str = ""
    otp_provider: str = "auto"  # auto | twilio | email | dev
    otp_minutes: int = 10
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _prod_checks(self):
        # Refuse to start in prod with weak or missing secrets.
        if self.env == "prod":
            if self.jwt_secret == "change-me" or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be 32+ characters in prod")
            twilio_ok = self.twilio_account_sid and self.twilio_auth_token and self.twilio_verify_sid
            smtp_ok = self.smtp_host and self.smtp_from
            if not (twilio_ok or smtp_ok):
                raise ValueError("Set Twilio or SMTP settings in prod (needed to send OTP emails)")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
