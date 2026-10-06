// Holds the logged-in user for the whole app.
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getTokens, setTokens } from "./api.js";

const Ctx = createContext(null);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    try { setUser(await api("/users/me")); } catch { setUser(null); }
    setLoading(false);
  }, []);

  useEffect(() => { getTokens() ? loadMe() : setLoading(false); }, [loadMe]);

  const login = async (identifier, password) => {
    setTokens(await api("/auth/login", { method: "POST", body: { identifier, password } }, false));
    await loadMe();
  };
  const afterSignup = async (tokens) => { setTokens(tokens); await loadMe(); };
  const logout = async () => {
    try { await api("/auth/logout", { method: "POST", body: { refresh_token: getTokens()?.refresh_token } }, false); } catch { /* ignore */ }
    setTokens(null);
    setUser(null);
  };

  return <Ctx.Provider value={{ user, setUser, loading, login, afterSignup, logout }}>{children}</Ctx.Provider>;
}
