import EmojiPicker from "emoji-picker-react";
import { useEffect, useRef, useState } from "react";
import Avatar from "./Avatar.jsx";

export default function ChatWindow({ conv, meId, messages, hasMore, online, onSend, onBack, onLoadOlder }) {
  const [text, setText] = useState("");
  const [showEmoji, setShowEmoji] = useState(false);
  const bottom = useRef(null);

  useEffect(() => { bottom.current?.scrollIntoView({ block: "end" }); }, [messages.length, conv.id]);
  useEffect(() => { setText(""); setShowEmoji(false); }, [conv.id]);

  function submit() {
    if (!text.trim()) return;
    if (onSend(text)) setText("");
  }

  function onKeyDown(e) {
    // While typing Hindi with an IME, Enter confirms the word. Do not send then.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <section className="window">
      <header className="row head">
        <button type="button" className="link back" onClick={onBack} aria-label="Back">&lt;</button>
        <Avatar initials={conv.other.initials} seed={conv.other.username} />
        <span><b>{conv.other.display_name}</b><br /><span className="muted small">@{conv.other.username}</span></span>
        {!online && <span className="muted small grow right">Reconnecting...</span>}
      </header>
      <div className="messages">
        {hasMore && <button className="link" onClick={onLoadOlder}>Load older messages</button>}
        {messages.map((m) => (
          <div key={m.client_msg_id} className={`bubble ${m.sender_id === meId ? "mine" : "theirs"} ${m.pending ? "pending" : ""}`}>
            {m.text}
            <span className="stamp">{m.pending ? "sending..." : new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
          </div>
        ))}
        <div ref={bottom} />
      </div>
      {showEmoji && (
        <div className="emoji">
          <EmojiPicker height={320} width="100%" onEmojiClick={(e) => setText((t) => t + e.emoji)} />
        </div>
      )}
      <div className="composer">
        <button type="button" className="icon" onClick={() => setShowEmoji((s) => !s)} aria-label="Emoji">:)</button>
        <textarea rows={1} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={onKeyDown}
          placeholder="Type a message" maxLength={2000} />
        <button onClick={submit} disabled={!text.trim()}>Send</button>
      </div>
    </section>
  );
}
