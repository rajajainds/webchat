# Text helpers shared by profile and chat validation.
import re
import unicodedata

MAX_MSG = 2000
USERNAME_RE = re.compile(r"(?![._])(?!.*[._]{2})[a-z0-9._]{3,20}(?<![._])")
RESERVED = {"admin", "support", "webchat", "root", "system", "me"}


def clean_text(s: str) -> str:
    """NFC-normalize so the same Hindi text is always stored one way, then strip.
    Control chars are dropped. Format chars (ZWJ/ZWNJ) are KEPT: Hindi conjuncts
    and combined emoji need them."""
    s = unicodedata.normalize("NFC", s).strip()
    return "".join(ch for ch in s if ch in "\n\t" or unicodedata.category(ch) != "Cc")


def check_username(v: str) -> str:
    v = v.strip().lower()  # usernames are always lowercase
    if not USERNAME_RE.fullmatch(v) or v in RESERVED:
        raise ValueError("Username: 3-20 chars, a-z 0-9 . _ only, no leading/trailing/double . or _")
    return v


def initials(first: str | None, last: str | None) -> str:
    """'Raja Kumar' -> 'RK'. No last name -> 'R'. No profile yet -> '?'."""
    a = first.strip()[:1].upper() if first else ""
    b = last.strip()[:1].upper() if last else ""
    return (a + b) or "?"


def display_name(first: str | None, last: str | None) -> str:
    return " ".join(p for p in (first, last) if p)
