/** Who is at the table, and the things done about the table rather than a bet. */
import { useState } from "react";
import type { Intent } from "../connection";
import type { State } from "../protocol.gen";
import { COLORS, initial } from "./Dots";

interface Props {
  table: State;
  busy: boolean;
  send: (intent: Intent) => void;
  close: () => void;
}

export function Panel({ table, busy, send, close }: Props) {
  const [link, setLink] = useState<{ url: string; copied: boolean } | null>(null);
  const [leaving, setLeaving] = useState(false);

  const invite = async () => {
    const url = `${location.origin}/#t=${table.table}`;
    // Sharing and the clipboard only exist on HTTPS; the link is always shown as well.
    let copied = false;
    try {
      if (navigator.share) await navigator.share({ title: "Crapless", url });
      else {
        await navigator.clipboard.writeText(url);
        copied = true;
      }
    } catch {
      // Cancelled, or not allowed. The link below can still be copied by hand.
    }
    setLink({ url, copied });
  };

  return (
    <div className="sheet" role="dialog" aria-label="Players">
      <ul>
        {table.players.map((p) => (
          <li key={p.seat} className={p.away ? "away" : undefined}>
            <span className="swatch" style={{ background: COLORS[p.color] }}>
              {initial(p.name)}
            </span>
            <span className="name">
              {p.name}
              {p.seat === table.you && " (you)"}
              <small>
                {[p.shooter && "has the dice", p.away && "away"].filter(Boolean).join(" · ")}
              </small>
            </span>
            <span className="net">
              {p.net === null ? "" : p.net < 0 ? `−${-p.net}` : `+${p.net}`}
            </span>
            <span className="bankroll">{p.bankroll}</span>
          </li>
        ))}
      </ul>
      {link && (
        <label className="link">
          {link.copied ? "Link copied" : "Invite link"}
          <input readOnly value={link.url} onFocus={(e) => e.target.select()} />
        </label>
      )}
      <div className="actions">
        <button onClick={() => void invite()}>Invite</button>
        <button disabled={busy || !table.can_refill} onClick={() => send({ type: "refill" })}>
          Refill
        </button>
        <button
          disabled={busy || !table.can_pass}
          onClick={() => send({ type: "pass", roll: table.roll })}
        >
          Pass dice
        </button>
        <button
          disabled={busy || table.leave_blocked !== null}
          onClick={() => (leaving ? send({ type: "leave" }) : setLeaving(true))}
        >
          {leaving ? "Tap again to leave" : "Leave"}
        </button>
      </div>
      {table.leave_blocked && <p>{table.leave_blocked}</p>}
      <button className="close" onClick={close}>
        Back to the table
      </button>
    </div>
  );
}
