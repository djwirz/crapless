/** The page: the table, and messages laid over it so that nothing on it moves. */
import { useSyncExternalStore } from "react";
import type { Connection } from "./connection";
import { Felt } from "./table/Felt";

export function App({ connection }: { connection: Connection }) {
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
      {view.reset && (
        <p role="status" className="banner passing">
          The server restarted, so your old table is gone. This is a new one.
        </p>
      )}

      {table && (
        <Felt
          table={table}
          busy={pending || status !== "open"}
          refusal={view.refusal}
          send={(intent) => connection.send(intent)}
        />
      )}
    </main>
  );
}
