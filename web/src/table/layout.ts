/**
 * Everything is drawn in one 360 × 590 box that is scaled to fit the screen. On the smallest
 * phone aimed for it shrinks a little, so no target is under 48 units (about 44 px).
 */
import type { Spot } from "../protocol.gen";

export const WIDTH = 360;
export const HEIGHT = 590;

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

const box = (x: number, y: number, width: number, height: number): Box => ({
  x,
  y,
  width,
  height,
});

export const ROWS = [
  [2, 3, 4, 5, 6],
  [8, 9, 10, 11, 12],
] as const;

const NUMBER_WIDTH = 68.8;
const NUMBER_TOP = 56;
const NUMBER_HEIGHT = 100;
/** The top of a number box, where a Come bet sits. */
export const COME_ZONE = 48;

export function numberBox(number: number): Box {
  const row = number < 7 ? 0 : 1;
  const column = ROWS[row].indexOf(number as never);
  return box(
    8 + column * NUMBER_WIDTH,
    NUMBER_TOP + row * (NUMBER_HEIGHT + 2),
    NUMBER_WIDTH,
    NUMBER_HEIGHT,
  );
}

export const DICE = box(8, 260, 344, 80);
export const COME = box(8, 344, 344, 50);
export const PASS = box(8, 398, 228, 54);
export const ODDS = box(240, 398, 112, 54);
export const HINT_Y = 468;
export const RAIL = box(8, 478, 344, 50);
export const ROLL = box(8, 532, 344, 52);

/** Where a spot's result is written. */
export function anchor(spot: Spot): { x: number; y: number } {
  const { kind, number } = spot;
  if (kind === "pass") return { x: PASS.x + PASS.width - 34, y: PASS.y + 16 };
  if (kind === "pass_odds") return { x: ODDS.x + ODDS.width - 28, y: ODDS.y + 14 };
  if (number === null) return { x: COME.x + COME.width - 34, y: COME.y + 16 };
  const at = numberBox(number);
  const y = kind === "place" ? at.y + at.height - 8 : at.y + 14;
  return { x: at.x + at.width / 2, y };
}

/** Where the dots for other players' bets on a spot start. Come bets and their odds share. */
export function dots(spot: Spot): { key: string; x: number; y: number } {
  const { kind, number } = spot;
  if (kind === "pass") return { key: "pass", x: PASS.x + 50, y: PASS.y + 9 };
  if (kind === "pass_odds") return { key: "odds", x: ODDS.x + 50, y: ODDS.y + 9 };
  if (number === null) return { key: "come", x: COME.x + 70, y: COME.y + 9 };
  const at = numberBox(number);
  const low = kind === "place";
  return { key: `${low ? "place" : "come"}:${number}`, x: at.x + 7, y: at.y + (low ? 93 : 50) };
}
