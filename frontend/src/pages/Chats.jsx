// Main screen: chat list (latest on top) + open chat. Live updates via WebSocket.
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import Avatar from "../components/Avatar.jsx";
import ChatList from "../components/ChatList.jsx";
import ChatWindow from "../components/ChatWindow.jsx";
import SearchBox from "../components/SearchBox.jsx";
import { useChatSocket } from "../useChatSocket.js";

const PAGE = 30;
const PENDING_SEQ = Number.MAX_SAFE_INTEGER;

// Merge messages by client_msg_id (replaces a "sending" copy with the saved one).
function merge(old = [], incoming) {
  const map = new Map(old.map((m) => [m.client_msg_id, m]));
  incoming.forEach((m) => map.set(m.client_msg_id, m));
  return [...map.values()].sort((a, b) => a.seq - b.seq);
}

export default function Chats() {
  const { user, logout } = useAuth();
  const [convs, setConvs] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [draft, setDraft] = useState(null); // chat opened from search, no messages yet
  const [msgs, setMsgs] = useState({}); // conversationId -> messages
  const [more, setMore] = useState({}); // conversationId -> maybe more older messages
  const [notice, setNotice] = useState("");

  const convsRef = useRef(convs);
  convsRef.current = convs;
  const activeRef = useRef(activeId);
  activeRef.current = activeId;

  const refreshList = useCallback(async () => { setConvs(await api("/conversations")); }, []);

  const loadHistory = useCallback(async (id, beforeSeq) => {
    const q = `limit=${PAGE}${beforeSeq ? `&before_seq=${beforeSeq}` : ""}`;
    const rows = await api(`/conversations/${id}/messages?${q}`);
    setMsgs((m) => ({ ...m, [id]: merge(m[id], rows) }));
    if (rows.length < PAGE) setMore((m) => ({ ...m, [id]: false }));
    else if (!beforeSeq) setMore((m) => ({ ...m, [id]: true }));
  }, []);

  const onEvent = useCallback((ev) => {
    if (ev.type === "auth_ok") { // first connect AND every reconnect: catch up on anything missed
      refreshList();
      if (activeRef.current) loadHistory(activeRef.current);
    } else if (ev.type === "new_message") {
      const m = ev.message;
      const mine = m.sender_id === user.id;
      const open = activeRef.current === m.conversation_id;
      setMsgs((all) => (all[m.conversation_id] || open ? { ...all, [m.conversation_id]: merge(all[m.conversation_id], [m]) } : all));
      if (!convsRef.current.some((c) => c.id === m.conversation_id)) { refreshList(); return; } // brand-new chat
      setConvs((prev) => {
        const c = prev.find((x) => x.id === m.conversation_id);
        const updated = { ...c, last_text: m.text.slice(0, 200), last_sender_id: m.sender_id, last_message_at: m.created_at,
          unread: mine || open ? 0 : c.unread + 1 };
        return [updated, ...prev.filter((x) => x.id !== c.id)]; // newest chat goes to the top
      });
      if (open && !mine) send({ type: "mark_read", conversation_id: m.conversation_id });
    } else if (ev.type === "read_state") {
      setConvs((prev) => prev.map((c) => (c.id === ev.conversation_id ? { ...c, unread: ev.unread } : c)));
    } else if (ev.type === "error") {
      setNotice(ev.detail);
      if (ev.client_msg_id) { // drop the unsent bubble
        setMsgs((all) => Object.fromEntries(Object.entries(all).map(([k, v]) => [k, v.filter((m) => m.client_msg_id !== ev.client_msg_id)])));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.id, refreshList, loadHistory]);

  const { send, online } = useChatSocket(onEvent);

  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(""), 4000);
    return () => clearTimeout(t);
  }, [notice]);

  function pick(c) {
    setActiveId(c.id);
    if (!convs.some((x) => x.id === c.id)) setDraft(c);
    if (!msgs[c.id]) loadHistory(c.id);
    if (c.unread > 0) {
      send({ type: "mark_read", conversation_id: c.id });
      setConvs((prev) => prev.map((x) => (x.id === c.id ? { ...x, unread: 0 } : x)));
    }
  }

  function sendText(text) {
    const client_msg_id = crypto.randomUUID();
    const ok = send({ type: "send_message", conversation_id: activeId, client_msg_id, text });
    if (!ok) { setNotice("Not connected. Please wait a moment."); return false; }
    const pending = { id: client_msg_id, client_msg_id, conversation_id: activeId, seq: PENDING_SEQ, sender_id: user.id,
      text, created_at: new Date().toISOString(), pending: true };
    setMsgs((all) => ({ ...all, [activeId]: merge(all[activeId], [pending]) }));
    return true;
  }

  const active = convs.find((c) => c.id === activeId) ?? (draft?.id === activeId ? draft : null);
  const list = active ? msgs[activeId] ?? [] : [];
  const firstSeq = list.find((m) => !m.pending)?.seq;

  return (
    <div className={`app ${active ? "has-active" : ""}`}>
      <aside className="side">
        <header className="row head">
          <Avatar initials={user.initials} seed={user.username} size={36} />
          <span className="grow"><b>{user.display_name}</b><br /><span className="muted small">@{user.username}</span></span>
          <Link to="/profile" className="small">Profile</Link>
          <button className="link small" onClick={logout}>Log out</button>
        </header>
        <SearchBox onOpen={pick} />
        <div className="list"><ChatList convs={convs} activeId={activeId} meId={user.id} onPick={pick} /></div>
      </aside>
      <main className="main">
        {notice && <div className="toast">{notice}</div>}
        {active ? (
          <ChatWindow conv={active} meId={user.id} messages={list} hasMore={more[activeId] && firstSeq > 1} online={online}
            onSend={sendText} onBack={() => setActiveId(null)} onLoadOlder={() => loadHistory(activeId, firstSeq)} />
        ) : (
          <p className="muted center pad">Select a chat or search a username</p>
        )}
      </main>
    </div>
  );
}
