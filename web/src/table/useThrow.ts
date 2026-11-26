/**
 * Holds the table back while the dice are in the air, so that the bankroll and chips do not
 * give the result away before the dice land.
 */
import { useEffect, useRef, useState } from "react";
import type { State } from "../protocol.gen";
import { isThrow, type Outcome, outcome } from "./outcome";

export const THROW_MS = 800;

export interface Thrown {
  /** The table to draw. */
  shown: State;
  throwing: boolean;
  /** What the latest throw did, once the dice are down. */
  result: Outcome | null;
}

export function useThrow(
  table: State,
  live: boolean,
  duration = reducedMotion() ? 0 : THROW_MS,
): Thrown {
  const [seen, setSeen] = useState<Thrown>({ shown: table, throwing: false, result: null });
  // Others may bet while the dice are in the air; they land on whatever is newest.
  const latest = useRef(table);
  latest.current = table;

  // Adjusting state while rendering, so the new table is never painted before the throw.
  if (table !== seen.shown && (!seen.throwing || !live)) {
    if (isThrow(seen.shown, table, live)) {
      const result = outcome(seen.shown, table);
      setSeen(
        duration > 0
          ? { shown: seen.shown, throwing: true, result: null }
          : { shown: table, throwing: false, result },
      );
    } else {
      // The same roll with more bets on it keeps the result in view.
      const same = live && table.roll === seen.shown.roll && table.ack === null;
      setSeen({ shown: table, throwing: false, result: same ? seen.result : null });
    }
  }

  useEffect(() => {
    if (!seen.throwing) return;
    const timer = setTimeout(() => {
      const after = latest.current;
      setSeen({ shown: after, throwing: false, result: outcome(seen.shown, after) });
    }, duration);
    return () => clearTimeout(timer);
  }, [seen, duration]);

  return seen;
}

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
