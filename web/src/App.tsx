/** A plain page that can play a full turn. The table look arrives in slice 3. */
import { useState, useSyncExternalStore } from "react";
import { lowered, raised } from "./amounts";
import type { Connection, Intent } from "./connection";
import { settlementText, spotName } from "./labels";
import type { Spot, SpotView, State } from "./protocol.gen";

const CHIPS = [1, 5, 25, 100];

export function App({ connection }: { connection: Connection }) {
  const view = useSyncExternalStore(connection.subscribe, connection.snapshot);
  const [chip, setChip] = useState(5);
  const { table, status, pending } = view;
  const busy = pending || status !== "open";

  return (
    <main>
      <header>
        <h1>Crapless</h1>
        <p className="small">Play money only. Nothing is sold and nothing can be won.</p>
      </header>

      {status === "connecting" && (
        <p role="status" className="banner connecting">
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
        <p role="status" className="banner">
          The server restarted, so your old table is gone. This is a new one.
        </p>
      )}

      {table && (
        <Table
          table={table}
          chip={chip}
          setChip={setChip}
          busy={busy}
          refusal={view.refusal}
          send={(intent) => connection.send(intent)}
        />
      )}
    </main>
  );
}

interface TableProps {
  table: State;
  chip: number;
  setChip: (chip: number) => void;
  busy: boolean;
  refusal: string | null;
  send: (intent: Intent) => void;
}

function Table({ table, chip, setChip, busy, refusal, send }: TableProps) {
  const { roll, point, last_roll: last } = table;
  const bet = (spot: Spot, amount: number) => send({ type: "bet", spot, amount, roll });
  const row = (view: SpotView) => (
    <SpotRow
      key={`${view.spot.kind}-${view.spot.number}`}
      view={view}
      chip={chip}
      busy={busy}
      bet={bet}
      setWorking={(number, working) => send({ type: "working", number, working, roll })}
    />
  );
  const place = table.spots.filter((s) => s.spot.kind === "place");
  // Come bets on a number come and go, so they are listed last, where they move nothing else.
  const moved = table.spots.filter((s) => s.spot.kind.startsWith("come") && s.spot.number !== null);
  const line = table.spots.filter((s) => !place.includes(s) && !moved.includes(s));
  const total = last ? last.die1 + last.die2 : 0;

  return (
    <>
      <section className="status">
        <p>
          Bankroll <strong>{table.bankroll}</strong>
        </p>
        <p>
          {point === null ? (
            "Come-out roll"
          ) : (
            <>
              Point <strong>{point}</strong>
            </>
          )}
        </p>
        {table.can_refill && (
          <button disabled={busy} onClick={() => send({ type: "refill" })}>
            Refill
          </button>
        )}
      </section>

      <section className="last" aria-live="polite">
        {last ? (
          <>
            <p className="dice">
              {last.die1} + {last.die2} = <strong>{total}</strong>
            </p>
            <ul>
              {last.settlements.map((s) => (
                <li key={`${s.spot.kind}-${s.spot.number}`}>{settlementText(s, total)}</li>
              ))}
            </ul>
          </>
        ) : (
          <p>Make a Pass bet, then roll.</p>
        )}
      </section>

      <fieldset className="chips">
        <legend>Chip</legend>
        {CHIPS.map((value) => (
          <button key={value} aria-pressed={chip === value} onClick={() => setChip(value)}>
            {value}
          </button>
        ))}
      </fieldset>

      <section>{line.map(row)}</section>
      <h2>Place</h2>
      <section>{place.map(row)}</section>
      {moved.length > 0 && (
        <>
          <h2>Come bets on numbers</h2>
          <section>{moved.map(row)}</section>
        </>
      )}

      <footer>
        {/* The dice stay in view however far the player has scrolled. */}
        <p className="summary">
          {last ? `Rolled ${total}` : "No roll yet"} · {point === null ? "Come-out" : `Point ${point}`}{" "}
          · Bankroll {table.bankroll}
        </p>
        <p role="alert" className="small">
          {refusal ?? table.roll_blocked ?? ""}
        </p>
        <button
          className="roll"
          disabled={busy || table.roll_blocked !== null}
          onClick={() => send({ type: "roll", roll })}
        >
          Roll
        </button>
      </footer>
      <p className="small">
        Your table is kept only while the server is running. After a quiet spell or an update it
        starts over.
      </p>
    </>
  );
}

interface RowProps {
  view: SpotView;
  chip: number;
  busy: boolean;
  bet: (spot: Spot, amount: number) => void;
  setWorking: (number: number, working: boolean) => void;
}

function SpotRow({ view, chip, busy, bet, setWorking }: RowProps) {
  const { spot, amount, working } = view;
  const name = spotName(spot);
  const up = raised(view, chip);
  const down = lowered(view, chip);

  return (
    <div className={amount ? "spot held" : "spot"}>
      <span className="name">{name}</span>
      {working !== null && spot.number !== null && (
        <label>
          <input
            type="checkbox"
            checked={working}
            disabled={busy}
            onChange={(e) => setWorking(spot.number!, e.target.checked)}
          />
          on at come-out
        </label>
      )}
      <span className="amount">{amount}</span>
      <button
        aria-label={`Take chips off ${name}`}
        disabled={busy || down === null}
        onClick={() => down !== null && bet(spot, down)}
      >
        −
      </button>
      <button
        aria-label={`Add chips to ${name}`}
        disabled={busy || up === null}
        onClick={() => up !== null && bet(spot, up)}
      >
        +
      </button>
    </div>
  );
}
