/** The page: a name, then the table, with messages laid over it so that nothing moves. */
import { useState, useSyncExternalStore } from "react";
import type { Connection } from "./connection";
import { HowToPlay } from "./HowToPlay";
import { Felt } from "./table/Felt";

interface Props {
  /** The name used last time, if any. */
  name: string;
  join: (name: string) => Connection;
  /** Already connected, for someone coming back to their seat. */
  resumed: Connection | null;
}

export function App({ name, join, resumed }: Props) {
  const [connection, setConnection] = useState<Connection | null>(resumed);

  if (!connection) {
    return <Join name={name} sit={(chosen) => setConnection(join(chosen))} />;
  }
  return <Play connection={connection} />;
}

function Join({ name, sit }: { name: string; sit: (name: string) => void }) {
  const [typed, setTyped] = useState(name);
  const [rules, setRules] = useState(false);
  return (
    <main>
      <form
        className="join"
        onSubmit={(e) => {
          e.preventDefault();
          if (typed.trim()) sit(typed.trim());
        }}
      >
        <h1>CRAPLESS</h1>
        <p>Play money only. Nothing is sold and nothing can be won.</p>
        <input
          aria-label="Your name"
          placeholder="Your name"
          maxLength={12}
          autoComplete="nickname"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
        />
        <button disabled={!typed.trim()}>Sit down</button>
        <button type="button" className="quiet" onClick={() => setRules(true)}>
          How to play
        </button>
      </form>
      {rules && <HowToPlay close={() => setRules(false)} />}
    </main>
  );
}

function Play({ connection }: { connection: Connection }) {
  const view = useSyncExternalStore(connection.subscribe, connection.snapshot);
  const { table, status, pending } = view;

  return (
    <main>
      {status === "connecting" && (
        <p role="status" className={table ? "banner connecting" : "banner"}>
          Connecting… a sleeping server can take about a minute to wake.
        </p>
      )}
      {status === "elsewhere" && (
        <p role="status" className="banner">
          This seat is open somewhere else.{" "}
          <button onClick={() => connection.open()}>Play here</button>
        </p>
      )}
      {status === "outdated" && (
        <p role="status" className="banner">
          The game has been updated. <button onClick={() => location.reload()}>Reload</button>
        </p>
      )}
      {status === "full" && (
        <p role="status" className="banner">
          That table is full. <a href="/">Open your own</a>
        </p>
      )}
      {status === "left" && (
        <p role="status" className="banner">
          You left the table. <button onClick={() => connection.open()}>Sit down again</button>
        </p>
      )}
      {view.notice && (
        <p role="status" className="banner passing">
          {view.notice}
        </p>
      )}

      {/* Keyed, so that each new one starts its few seconds afresh. */}
      {view.announcement && (
        <p key={view.announcement.n} role="status" className="banner passing announce">
          {view.announcement.text}
        </p>
      )}

      {table && status !== "left" && status !== "full" && (
        <Felt
          table={table}
          live={view.live}
          busy={pending || status !== "open"}
          refusal={view.refusal}
          send={(intent) => connection.send(intent)}
        />
      )}
    </main>
  );
}
