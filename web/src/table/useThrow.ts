/**
 * Holds the table back while the dice are in the air, so that the bankroll and chips do not
 * give the result away before the dice land.
 */
import { useEffect, useState } from "react";
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

export function useThrow(table: State, duration = reducedMotion() ? 0 : THROW_MS): Thrown {
  const [seen, setSeen] = useState<Thrown>({ shown: table, throwing: false, result: null });

  // Adjusting state while rendering, so the new table is never painted before the throw.
  if (!seen.throwing && table !== seen.shown) {
    if (isThrow(seen.shown, table)) {
      const result = outcome(seen.shown, table);
      setSeen(
        duration > 0
          ? { shown: seen.shown, throwing: true, result: null }
          : { shown: table, throwing: false, result },
      );
    } else {
      // A bet keeps the last result on show only until the table changes under it.
      setSeen({ shown: table, throwing: false, result: null });
    }
  }

  useEffect(() => {
    if (!seen.throwing) return;
    const timer = setTimeout(
      () => setSeen({ shown: table, throwing: false, result: outcome(seen.shown, table) }),
      duration,
    );
    return () => clearTimeout(timer);
  }, [seen, table, duration]);

  return seen;
}

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
