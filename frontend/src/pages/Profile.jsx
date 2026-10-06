// Create the profile (first time) or edit it later. Initials show live.
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import Avatar from "../components/Avatar.jsx";

export default function Profile() {
  const { user, setUser, logout } = useAuth();
  const nav = useNavigate();
  const isNew = !user.profile_complete;
  const [form, setForm] = useState({
    username: user.username ?? "",
    first_name: user.first_name ?? "",
    last_name: user.last_name ?? "",
    bio: user.bio ?? "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: k === "username" ? e.target.value.toLowerCase() : e.target.value });

  const initials = (form.first_name.trim()[0] ?? "?").toUpperCase() + (form.last_name.trim()[0] ?? "").toUpperCase();

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setUser(await api("/users/me/profile", { method: "PUT", body: form }));
      nav("/");
    } catch (err) { setError(err.message); }
    setBusy(false);
  }

  return (
    <form className="card" onSubmit={submit}>
      <h1>{isNew ? "Create your profile" : "Edit profile"}</h1>
      <div className="center"><Avatar initials={initials} seed={form.username} size={72} /></div>
      <input placeholder="Username (a-z, 0-9, . _)" value={form.username} onChange={set("username")} maxLength={20} autoFocus />
      <input placeholder="First name" value={form.first_name} onChange={set("first_name")} maxLength={50} />
      <input placeholder="Last name (optional)" value={form.last_name} onChange={set("last_name")} maxLength={50} />
      <input placeholder="Bio (optional)" value={form.bio} onChange={set("bio")} maxLength={160} />
      {error && <p className="error">{error}</p>}
      <button disabled={busy || !form.username || !form.first_name.trim()}>{isNew ? "Continue" : "Save"}</button>
      {!isNew && <Link to="/" className="muted">Back to chats</Link>}
      <button type="button" className="link" onClick={logout}>Log out</button>
    </form>
  );
}
