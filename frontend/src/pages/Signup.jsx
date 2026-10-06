// 3 steps: email -> OTP code -> password. Account is created at the last step.
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";

export default function Signup() {
  const { afterSignup } = useAuth();
  const nav = useNavigate();
  const [step, setStep] = useState("email"); // email | code | password
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [signupToken, setSignupToken] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(fn) {
    setBusy(true);
    setError("");
    try { await fn(); } catch (err) { setError(err.message); }
    setBusy(false);
  }

  const sendCode = (e) => { e.preventDefault(); run(async () => {
    await api("/auth/register", { method: "POST", body: { email } }, false);
    setStep("code");
  }); };

  const verify = (e) => { e.preventDefault(); run(async () => {
    const r = await api("/auth/verify-otp", { method: "POST", body: { email, code } }, false);
    setSignupToken(r.signup_token);
    setStep("password");
  }); };

  const createAccount = (e) => { e.preventDefault(); run(async () => {
    const tokens = await api("/auth/set-password", { method: "POST", body: { signup_token: signupToken, password } }, false);
    await afterSignup(tokens);
    nav("/profile"); // next: create the profile
  }); };

  return (
    <form className="card" onSubmit={step === "email" ? sendCode : step === "code" ? verify : createAccount}>
      <h1>Create account</h1>
      {step === "email" && (<>
        <p className="muted">Enter your email. We will send you a code.</p>
        <input type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
        <button disabled={busy || !email}>Send code</button>
      </>)}
      {step === "code" && (<>
        <p className="muted">Enter the code sent to {email}</p>
        <input inputMode="numeric" placeholder="Code" value={code} onChange={(e) => setCode(e.target.value.trim())} autoFocus />
        <button disabled={busy || code.length < 4}>Verify</button>
        <button type="button" className="link" onClick={() => setStep("email")}>Use a different email</button>
      </>)}
      {step === "password" && (<>
        <p className="muted">Choose a password (8+ characters, with a letter and a number)</p>
        <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus />
        <button disabled={busy || password.length < 8}>Create account</button>
      </>)}
      {error && <p className="error">{error}</p>}
      <p className="muted">Have an account? <Link to="/login">Log in</Link></p>
    </form>
  );
}
