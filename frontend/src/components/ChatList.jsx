import Avatar from "./Avatar.jsx";

function when(iso) {
  const d = new Date(iso);
  const today = new Date().toDateString() === d.toDateString();
  return today ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : d.toLocaleDateString();
}

export default function ChatList({ convs, activeId, meId, onPick }) {
  if (convs.length === 0) return <p className="muted pad">No chats yet. Search a username to start.</p>;
  return convs.map((c) => (
    <button key={c.id} className={`row ${c.id === activeId ? "active" : ""}`} onClick={() => onPick(c)}>
      <Avatar initials={c.other.initials} seed={c.other.username} />
      <span className="grow">
        <b>{c.other.display_name}</b>
        <span className="muted small time">{when(c.last_message_at)}</span>
        <br />
        <span className="muted small preview">{c.last_sender_id === meId ? "You: " : ""}{c.last_text}</span>
      </span>
      {c.unread > 0 && <span className="badge">{c.unread}</span>}
    </button>
  ));
}
