import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { Connection, seatKey, type Socket, TABLE_KEY } from "./connection";
import "./styles.css";

const NAME_KEY = "crapless.name";
const url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;

// Some private windows throw on any use of localStorage. Play without remembering the seat.
function storage(): Pick<Storage, "getItem" | "setItem"> {
  try {
    localStorage.getItem(NAME_KEY);
    return localStorage;
  } catch {
    const kept = new Map<string, string>();
    return { getItem: (k) => kept.get(k) ?? null, setItem: (k, v) => void kept.set(k, v) };
  }
}
const kept = storage();

/** The table code in an invite link. It sits after #, which browsers never send in requests. */
const linked = () => /^#t=([A-Za-z0-9_-]{12,32})$/.exec(location.hash)?.[1] ?? null;

function join(name: string): Connection {
  kept.setItem(NAME_KEY, name);
  const connection = new Connection(
    // The handlers differ only in what their events carry beyond what Connection reads.
    () => new WebSocket(url) as unknown as Socket,
    kept,
    { name, table: linked() ?? (kept.getItem(TABLE_KEY) || null) },
    (table) => history.replaceState(null, "", `#t=${table}`),
  );
  connection.open();
  // A phone that slept may hold a dead socket without knowing it, so start a fresh one.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") connection.wake();
  });
  return connection;
}

// Pasting another table's link into the same tab only changes what follows the #.
addEventListener("hashchange", () => location.reload());

const name = kept.getItem(NAME_KEY) ?? "";
// Someone who already holds a seat here goes straight back to it, without being asked again.
const table = linked() ?? kept.getItem(TABLE_KEY);
const resumed = name && table && kept.getItem(seatKey(table)) ? join(name) : null;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App name={name} join={join} resumed={resumed} />
  </StrictMode>,
);
