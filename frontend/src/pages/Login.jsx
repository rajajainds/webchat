import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try { await login(identifier, password); nav("/"); }
    catch (err) { setError(err.message); }
    setBusy(false);
  }

  return (
    <form className="card" onSubmit={submit}>
      <h1>Web Chat</h1>
      <p className="muted">Log in with your email or username</p>
      <input placeholder="Email or username" value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoFocus />
      <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
      {error && <p className="error">{error}</p>}
      <button disabled={busy || !identifier || !password}>Log in</button>
      <p className="muted">New here? <Link to="/signup">Create an account</Link></p>
    </form>
  );
}
