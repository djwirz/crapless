/** What the + and − buttons ask for, within the step and limits the server sent. */
import type { SpotView } from "./protocol.gen";

/** The new total after adding a chip, or null if nothing can be added. */
export function raised(spot: SpotView, chip: number): number | null {
  const { amount, step, low, high } = spot;
  if (low === null || high === null) return null;
  const wanted = Math.ceil((amount + chip) / step) * step;
  const next = Math.min(Math.max(wanted, low), high);
  return next > amount ? next : null;
}

/** The new total after taking a chip off, or null if nothing can be taken. 0 takes it down. */
export function lowered(spot: SpotView, chip: number): number | null {
  const { amount, step, low, removable } = spot;
  if (!removable) return null;
  const next = Math.floor((amount - chip) / step) * step;
  return low === null || next < low ? 0 : next;
}
