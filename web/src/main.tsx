import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { Connection, type Socket } from "./connection";
import "./styles.css";

const url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;

// Some private windows throw on any use of localStorage. Play without remembering the seat.
function storage(): Pick<Storage, "getItem" | "setItem"> {
  try {
    localStorage.getItem("crapless.token");
    return localStorage;
  } catch {
    const kept = new Map<string, string>();
    return { getItem: (k) => kept.get(k) ?? null, setItem: (k, v) => void kept.set(k, v) };
  }
}

// The handlers differ only in what their events carry beyond what Connection reads.
const connection = new Connection(() => new WebSocket(url) as unknown as Socket, storage());
connection.open();

// A phone that slept may hold a dead socket without knowing it, so start a fresh one.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") connection.wake();
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App connection={connection} />
  </StrictMode>,
);
