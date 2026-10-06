// Find a person by username (prefix match) and open a chat with them.
import { useEffect, useState } from "react";
import { api } from "../api.js";
import Avatar from "./Avatar.jsx";

export default function SearchBox({ onOpen }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (q.length < 2) { setResults([]); return; }
    const t = setTimeout(async () => { // wait 300ms after typing stops
      try { setResults(await api(`/users/search?q=${encodeURIComponent(q)}`)); setError(""); }
      catch (e) { setError(e.message); }
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  async function open(username) {
    try {
      onOpen(await api("/conversations", { method: "POST", body: { username } }));
      setQ("");
    } catch (e) { setError(e.message); }
  }

  return (
    <div className="search">
      <input placeholder="Search username" value={q} onChange={(e) => setQ(e.target.value.toLowerCase())} maxLength={20} />
      {error && <p className="error small">{error}</p>}
      {q.length >= 2 && results.length === 0 && !error && <p className="muted small">No users found</p>}
      {results.map((u) => (
        <button key={u.id} className="row" onClick={() => open(u.username)}>
          <Avatar initials={u.initials} seed={u.username} size={36} />
          <span><b>{u.display_name}</b><br /><span className="muted small">@{u.username}</span></span>
        </button>
      ))}
    </div>
  );
}
