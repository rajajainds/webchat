import pytest
from starlette.websockets import WebSocketDisconnect
from tests.conftest import signup


def open_chat(client, h, username):
    r = client.post("/api/conversations", headers=h, json={"username": username})
    assert r.status_code == 200, r.text
    return r.json()


def connect(client, tok):
    ws = client.websocket_connect("/ws")
    s = ws.__enter__()
    s.send_json({"type": "auth", "token": tok})
    assert s.receive_json() == {"type": "auth_ok"}
    return ws, s


def test_live_chat_hindi_emoji_and_multi_device(client):
    ha, ta, a, _ = signup(client, "alice1", "Alice")
    hb, tb, b, _ = signup(client, "bobby1", "Bob", "Roy")
    conv = open_chat(client, ha, "bobby1")
    assert open_chat(client, hb, "alice1")["id"] == conv["id"]  # same room from both sides
    assert client.get("/api/conversations", headers=ha).json() == []  # empty chats are hidden

    ws_a1, a1 = connect(client, ta)
    ws_a2, a2 = connect(client, ta)  # alice's second device
    ws_b, b1 = connect(client, tb)
    text = "नमस्ते Bob 😊👨\u200d👩\u200d👧"
    a1.send_json({"type": "send_message", "conversation_id": conv["id"], "client_msg_id": "cid-000001", "text": text})
    for s in (a1, a2, b1):
        ev = s.receive_json()
        assert ev["type"] == "new_message"
        assert ev["message"]["text"] == text and ev["message"]["seq"] == 1
        assert ev["message"]["client_msg_id"] == "cid-000001"

    # retry with same client_msg_id: no duplicate, same seq
    a1.send_json({"type": "send_message", "conversation_id": conv["id"], "client_msg_id": "cid-000001", "text": text})
    assert a1.receive_json()["message"]["seq"] == 1
    for s in (a2, b1):
        s.receive_json()

    # bob replies; alice sees unread 1 on list? no: she is online but has not read
    b1.send_json({"type": "send_message", "conversation_id": conv["id"], "client_msg_id": "cid-000002", "text": "hi"})
    for s in (a1, a2, b1):
        assert s.receive_json()["message"]["seq"] == 2
    lst = client.get("/api/conversations", headers=ha).json()
    assert lst[0]["unread"] == 1 and lst[0]["last_text"] == "hi" and lst[0]["other"]["initials"] == "BR"
    # alice marks read on device 1 -> device 2 is told
    a1.send_json({"type": "mark_read", "conversation_id": conv["id"]})
    assert a1.receive_json()["type"] == "read_state"
    assert client.get("/api/conversations", headers=ha).json()[0]["unread"] == 0
    for w in (ws_b, ws_a2, ws_a1):
        w.__exit__(None, None, None)


def test_offline_messages_wait_in_database(client):
    ha, ta, *_ = signup(client, "sender1", "Sam")
    hb, *_ = signup(client, "sleeper1", "Sia")
    hc, *_ = signup(client, "latecomer", "Lee")
    conv = open_chat(client, ha, "sleeper1")
    ws, a = connect(client, ta)
    for i in range(3):  # bob is offline the whole time
        a.send_json({"type": "send_message", "conversation_id": conv["id"], "client_msg_id": f"offline-{i:03d}", "text": f"m{i}"})
        a.receive_json()
    ws.__exit__(None, None, None)

    # "new device" for bob: log in fresh, everything is there
    lst = client.get("/api/conversations", headers=hb).json()
    assert lst[0]["unread"] == 3 and lst[0]["last_text"] == "m2"
    msgs = client.get(f"/api/conversations/{conv['id']}/messages", headers=hb).json()
    assert [m["text"] for m in msgs] == ["m0", "m1", "m2"] and [m["seq"] for m in msgs] == [1, 2, 3]
    older = client.get(f"/api/conversations/{conv['id']}/messages?before_seq=3&limit=1", headers=hb).json()
    assert [m["seq"] for m in older] == [2]
    assert client.post(f"/api/conversations/{conv['id']}/read", headers=hb).status_code == 204
    assert client.get("/api/conversations", headers=hb).json()[0]["unread"] == 0
    # a stranger cannot read or mark this chat
    assert client.get(f"/api/conversations/{conv['id']}/messages", headers=hc).status_code == 404
    assert client.post(f"/api/conversations/{conv['id']}/read", headers=hc).status_code == 404


def test_ws_rules(client):
    ha, ta, *_ = signup(client, "rules_a", "A")
    hb, tb, *_ = signup(client, "rules_b", "B")
    hc, tc, *_ = signup(client, "rules_c", "C")
    conv = open_chat(client, ha, "rules_b")
    # bad token is closed with 4401
    with client.websocket_connect("/ws") as s:
        s.send_json({"type": "auth", "token": "nope"})
        with pytest.raises(WebSocketDisconnect) as e:
            s.receive_json()
        assert e.value.code == 4401
    ws, c = connect(client, tc)  # outsider tries to write into A-B chat
    c.send_json({"type": "send_message", "conversation_id": conv["id"], "client_msg_id": "intruder01", "text": "hi"})
    ev = c.receive_json()
    assert ev["type"] == "error"
    ws2, a = connect(client, ta)
    a.send_json({"type": "send_message", "conversation_id": conv["id"], "client_msg_id": "emptyone01", "text": "  "})
    assert a.receive_json()["type"] == "error"
    a.send_json({"type": "send_message", "conversation_id": conv["id"], "client_msg_id": "toolong001", "text": "x" * 2001})
    assert a.receive_json()["type"] == "error"
    a.send_json({"type": "bogus"})
    assert a.receive_json()["type"] == "error"
    assert client.get(f"/api/conversations/{conv['id']}/messages", headers=ha).json() == []  # nothing saved
    for w in (ws2, ws):
        w.__exit__(None, None, None)
    self_chat = client.post("/api/conversations", headers=ha, json={"username": "rules_a"})
    assert self_chat.status_code == 400
    assert client.post("/api/conversations", headers=ha, json={"username": "ghost_user"}).status_code == 404
