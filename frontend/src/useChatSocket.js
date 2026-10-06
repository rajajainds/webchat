// One WebSocket per tab. Authenticates with the first message, auto-reconnects.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, getTokens } from "./api.js";

const WS_URL = import.meta.env.VITE_WS_URL || `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;

export function useChatSocket(onEvent) {
  const wsRef = useRef(null);
  const handler = useRef(onEvent);
  handler.current = onEvent; // always call the latest handler
  const [online, setOnline] = useState(false);

  useEffect(() => {
    let closed = false, retry = 0, timer;
    async function connect() {
      await api("/users/me").catch(() => {}); // refreshes the token if it expired
      if (closed || !getTokens()) return;
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => ws.send(JSON.stringify({ type: "auth", token: getTokens().access_token }));
      ws.onmessage = (e) => {
        const ev = JSON.parse(e.data);
        if (ev.type === "auth_ok") { retry = 0; setOnline(true); }
        handler.current(ev);
      };
      ws.onclose = () => {
        setOnline(false);
        if (!closed) timer = setTimeout(connect, Math.min(1000 * 2 ** retry++, 15000));
      };
    }
    connect();
    return () => { closed = true; clearTimeout(timer); wsRef.current?.close(); };
  }, []);

  const send = useCallback((obj) => {
    const ws = wsRef.current;
    if (ws?.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(obj));
    return true;
  }, []);

  return { send, online };
}
