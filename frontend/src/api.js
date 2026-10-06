// All HTTP calls go through here. Adds the token and retries once after refreshing it.
// Tokens live in localStorage (simple). Trade-off: XSS could read them;
// React escapes output, but production-grade apps use httpOnly cookies.
const API = import.meta.env.VITE_API_URL || "";
const KEY = "webchat_tokens";

let tokens = JSON.parse(localStorage.getItem(KEY) || "null");
export const getTokens = () => tokens;
export function setTokens(t) {
  tokens = t;
  if (t) localStorage.setItem(KEY, JSON.stringify(t));
  else localStorage.removeItem(KEY);
}

let refreshing = null; // share one refresh call between parallel requests
async function refresh() {
  if (!tokens?.refresh_token) return false;
  refreshing ??= fetch(`${API}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  })
    .then(async (r) => {
      if (!r.ok) { setTokens(null); return false; }
      setTokens(await r.json());
      return true;
    })
    .finally(() => { refreshing = null; });
  return refreshing;
}

function errorText(data) {
  const d = data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d[0]?.msg) return d[0].msg.replace(/^Value error, /, "");
  return "Something went wrong";
}

export async function api(path, { method = "GET", body } = {}, auth = true) {
  const send = () =>
    fetch(`${API}/api${path}`, {
      method,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(auth && tokens ? { Authorization: `Bearer ${tokens.access_token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  let res = await send();
  if (res.status === 401 && auth && (await refresh())) res = await send();
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(errorText(data));
  return data;
}
