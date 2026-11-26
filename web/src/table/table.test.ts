import { describe, expect, it } from "vitest";
import type { PlayerView, SettlementView, SpotView, State } from "../protocol.gen";
import { canSwitch, hint, tap } from "./model";
import { isThrow, outcome } from "./outcome";

const spot = (change: Partial<SpotView> = {}): SpotView => ({
  spot: { kind: "place", number: 6 },
  amount: 0,
  step: 6,
  low: 6,
  high: 498,
  removable: false,
  working: null,
  ...change,
});

const seat = (change: Partial<PlayerView> = {}): PlayerView => ({
  seat: "p1",
  name: "Ana",
  color: 0,
  bankroll: 1000,
  away: false,
  shooter: true,
  net: null,
  ...change,
});

const state = (change: Partial<State> = {}): State => ({
  type: "state",
  v: 2,
  token: "s",
  table: "t",
  you: "p1",
  notice: null,
  ack: "a",
  bankroll: 1000,
  point: null,
  roll: 0,
  roll_blocked: null,
  wait_ms: 0,
  can_refill: false,
  can_pass: false,
  leave_blocked: null,
  players: [seat()],
  spots: [],
  others: [],
  last_roll: null,
  ...change,
});

const settled = (change: Partial<SettlementView>): SettlementView => ({
  spot: { kind: "pass", number: null },
  outcome: "win",
  amount: 10,
  paid: 0,
  returned: 0,
  ...change,
});

describe("a tap", () => {
  it("adds, takes off or switches, as the mode says", () => {
    expect(tap(spot(), "add", 5, 3)).toMatchObject({ type: "bet", amount: 6, roll: 3 });
    expect(tap(spot({ amount: 12, removable: true }), "take", 5, 3)).toMatchObject({ amount: 6 });
    expect(tap(spot({ amount: 6, working: false }), "switch", 5, 3)).toEqual({
      type: "working",
      number: 6,
      working: true,
      roll: 3,
    });
  });

  it("does nothing where nothing can be done", () => {
    expect(tap(undefined, "add", 5, 0)).toBeNull();
    expect(tap(spot({ low: null, high: null }), "add", 5, 0)).toBeNull();
    expect(tap(spot(), "take", 5, 0)).toBeNull();
    expect(tap(spot(), "switch", 5, 0)).toBeNull();
  });

  it("offers the Place switch only on a come-out with a Place bet up", () => {
    const up = state({ spots: [spot({ amount: 6, working: false })] });
    expect(canSwitch(up)).toBe(true);
    expect(canSwitch({ ...up, point: 6 })).toBe(false);
    expect(canSwitch(state({ spots: [spot()] }))).toBe(false);
  });

  it("tells watchers who is shooting, and a shooter to wait", () => {
    const two = [seat({ shooter: false }), seat({ seat: "p2", name: "Bo" })];
    expect(hint(state({ players: two }), "add")).toBe("Tap to bet. Bo is shooting");
    expect(hint(state(), "add", true)).toBe("Bets are going down…");
  });

  it("is prompted by a hint", () => {
    expect(hint(state({ roll_blocked: "x" }), "add")).toBe("Tap PASS to start");
    expect(hint(state(), "add")).toBe("Roll to set the point");
    expect(hint(state(), "take")).toContain("take chips off");
  });
});

describe("a throw", () => {
  const rolled = state({ roll: 1, last_roll: { die1: 3, die2: 3, settlements: [] } });

  it("is seen only for the next roll, on the same connection", () => {
    expect(isThrow(state(), rolled, true)).toBe(true);
    expect(isThrow(state(), { ...rolled, ack: null }, true)).toBe(true); // someone else's
    expect(isThrow(state(), rolled, false)).toBe(false); // a reconnect
    expect(isThrow(null, rolled, true)).toBe(false);
    expect(isThrow(state(), { ...rolled, table: "other" }, true)).toBe(false);
    expect(isThrow(state(), { ...rolled, roll: 5 }, true)).toBe(false);
    expect(isThrow(rolled, rolled, true)).toBe(false);
  });

  it.each([
    [null, 6, [3, 3], "The point is 6"],
    [null, null, [3, 4], "Seven! Pass wins"],
    [6, null, [3, 3], "Point 6 made!"],
    [6, null, [3, 4], "Seven out"],
    [6, 6, [4, 4], ""],
  ] as const)("from point %s to %s says what happened", (before, after, [die1, die2], banner) => {
    const next = { ...rolled, point: after, last_roll: { die1, die2, settlements: [] } };
    expect(outcome(state({ point: before }), next).banner).toBe(banner);
  });

  it("marks each place once, in signs and words", () => {
    const settlements = [
      settled({ spot: { kind: "come", number: 9 }, paid: 10 }),
      settled({ spot: { kind: "come_odds", number: 9 }, paid: 39 }),
      settled({ spot: { kind: "place", number: 8 }, outcome: "lose", amount: 12 }),
      settled({ spot: { kind: "come_odds", number: 4 }, outcome: "returned", returned: 5, amount: 5 }),
      settled({ spot: { kind: "come", number: null }, outcome: "moved" }),
    ];
    const next = { ...rolled, last_roll: { die1: 5, die2: 4, settlements } };
    const result = outcome(state({ point: 6 }), next);

    expect(result.net).toBe(37);
    expect(result.marks.map((m) => m.text).sort()).toEqual(["+49", "5 back", "to 9", "−12"]);
  });
});
