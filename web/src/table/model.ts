/** The table's decisions, kept apart from the drawing: what a tap asks for, what to say. */
import { lowered, raised } from "../amounts";
import type { Intent } from "../connection";
import type { BetKind, SpotView, State } from "../protocol.gen";

/** What tapping a spot does: add the chosen chip, take it off, or switch a Place bet. */
export type Mode = "add" | "take" | "switch";

export function findSpot(table: State, kind: BetKind, number: number | null = null) {
  return table.spots.find((s) => s.spot.kind === kind && s.spot.number === number);
}

/** The request a tap makes, or null if tapping would do nothing. */
export function tap(
  view: SpotView | undefined,
  mode: Mode,
  chip: number,
  roll: number,
): Intent | null {
  if (!view) return null;
  if (mode === "switch") {
    const { number } = view.spot;
    if (view.working === null || number === null) return null;
    return { type: "working", number, working: !view.working, roll };
  }
  const amount = mode === "add" ? raised(view, chip) : lowered(view, chip);
  return amount === null ? null : { type: "bet", spot: view.spot, amount, roll };
}

/** Whether the Come bar is the Place on/off switch: on a come-out, with a Place bet up. */
export function canSwitch(table: State): boolean {
  return table.point === null && table.spots.some((s) => s.working !== null);
}

/** You, and whoever has the dice. */
export function players(table: State) {
  return {
    me: table.players.find((p) => p.seat === table.you),
    shooter: table.players.find((p) => p.shooter),
  };
}

export function hint(table: State, mode: Mode, held = false): string {
  if (mode === "switch") return "Tap a number to switch its Place bet on or off";
  if (mode === "take") return "Tap a bet to take chips off it";
  if (table.bankroll < 5 && table.can_refill) return "Low on chips? Refill from the top button";
  const { me, shooter } = players(table);
  if (shooter && me && shooter.seat !== me.seat) return `Tap to bet. ${shooter.name} is shooting`;
  if (held) return "Bets are going down…";
  const yours = table.players.length > 1 ? "Your dice! " : "";
  if (table.roll_blocked !== null) return `${yours}Tap PASS to start`;
  if (table.point === null) return `${yours}Roll to set the point`;
  const odds = findSpot(table, "pass_odds");
  if (odds && odds.amount === 0 && odds.low !== null) return "Back your Pass with odds, or roll";
  return `${yours}Tap to bet, then roll`;
}
