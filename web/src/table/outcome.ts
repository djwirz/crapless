/** What a roll did, worked out from the table before and after, for showing. */
import type { SettlementView, Spot, State } from "../protocol.gen";

export type Tone = "win" | "lose" | "plain";

export interface Mark {
  /** Where on the felt: the spot whose place the words are written at. */
  spot: Spot;
  tone: Tone;
  text: string;
}

export interface Outcome {
  banner: string;
  /** Winnings less losses. */
  net: number;
  marks: Mark[];
}

/**
 * Whether the dice should be seen to tumble: only for the very next roll, heard on the same
 * connection. A reconnect or reload shows the table as it is and never replays a throw.
 */
export function isThrow(before: State | null, after: State, live: boolean): boolean {
  return (
    before !== null &&
    live &&
    after.table === before.table &&
    after.roll === before.roll + 1 &&
    after.last_roll !== null
  );
}

export function outcome(before: State, after: State): Outcome {
  const last = after.last_roll;
  if (!last) return { banner: "", net: 0, marks: [] };
  const total = last.die1 + last.die2;
  const net = last.settlements.reduce(
    (sum, s) => sum + s.paid - (s.outcome === "lose" ? s.amount : 0),
    0,
  );
  return { banner: banner(before.point, after.point, total), net, marks: marks(last.settlements, total) };
}

function banner(before: number | null, after: number | null, total: number): string {
  if (before === null) {
    return after === null ? "Seven! Pass wins" : `The point is ${after}`;
  }
  if (after !== null) return "";
  return total === 7 ? "Seven out" : `Point ${before} made!`;
}

/** One mark for each place on the felt: a Come bet and its odds share one. */
function marks(settlements: SettlementView[], total: number): Mark[] {
  const places = new Map<string, { spot: Spot; paid: number; lost: number; back: number }>();
  const result: Mark[] = [];
  for (const s of settlements) {
    if (s.outcome === "moved") {
      result.push({ spot: s.spot, tone: "plain", text: `to ${total}` });
      continue;
    }
    const kind = s.spot.kind === "come_odds" ? "come" : s.spot.kind;
    const spot = { kind, number: s.spot.number };
    const key = `${kind}:${s.spot.number}`;
    const sum = places.get(key) ?? { spot, paid: 0, lost: 0, back: 0 };
    sum.paid += s.paid;
    if (s.outcome === "lose") sum.lost += s.amount;
    if (s.outcome === "returned") sum.back += s.amount;
    places.set(key, sum);
  }
  for (const { spot, paid, lost, back } of places.values()) {
    const change = paid - lost;
    // Signs and words carry the meaning, so color is never the only cue.
    if (change > 0) result.push({ spot, tone: "win", text: `+${change}` });
    else if (change < 0) result.push({ spot, tone: "lose", text: `−${-change}` });
    else if (back > 0) result.push({ spot, tone: "plain", text: `${back} back` });
  }
  return result;
}
