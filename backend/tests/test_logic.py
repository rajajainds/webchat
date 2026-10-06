import pytest
from pydantic import ValidationError
from app.core.text import clean_text, initials
from app.schemas.chat import SendIn
from app.schemas.user import ProfileIn


def test_initials():
    assert initials("Raja", "Kumar") == "RK"
    assert initials("raja", None) == "R"
    assert initials("raja", "") == "R"
    assert initials(None, None) == "?"
    assert initials("राजा", "कुमार") == "रक"


def test_username_is_lowercased():
    assert ProfileIn(username="  Raja_K ", first_name="R").username == "raja_k"


@pytest.mark.parametrize("bad", ["ab", "a" * 21, "..abc", "abc.", "a..b", "ab cd", "admin", "राजा123"])
def test_username_rejects(bad):
    with pytest.raises(ValidationError):
        ProfileIn(username=bad, first_name="R")


def test_clean_text():
    assert clean_text("e\u0301") == "\u00e9"  # NFC
    assert clean_text("a\x00b") == "ab"  # control char removed
    assert clean_text("👨\u200d👩\u200d👧") == "👨\u200d👩\u200d👧"  # ZWJ kept


def test_message_rules():
    ok = SendIn(conversation_id="x", client_msg_id="abcdefgh", text="नमस्ते hello 😊")
    assert ok.text == "नमस्ते hello 😊"
    with pytest.raises(ValidationError):
        SendIn(conversation_id="x", client_msg_id="abcdefgh", text="   ")
    with pytest.raises(ValidationError):
        SendIn(conversation_id="x", client_msg_id="abcdefgh", text="क" * 2001)
    SendIn(conversation_id="x", client_msg_id="abcdefgh", text="क" * 2000)
