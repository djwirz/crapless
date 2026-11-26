import { describe, expect, it } from "vitest";
import { lowered, raised } from "./amounts";
import { settlementText } from "./labels";
import type { SpotView } from "./protocol.gen";

const spot = (change: Partial<SpotView>): SpotView => ({
  spot: { kind: "place", number: 6 },
  amount: 0,
  step: 6,
  low: 6,
  high: 498,
  removable: false,
  working: null,
  ...change,
});

describe("the + and − buttons", () => {
  it("round up to a multiple that pays evenly", () => {
    expect(raised(spot({}), 1)).toBe(6);
    expect(raised(spot({}), 25)).toBe(30);
    expect(raised(spot({ amount: 12 }), 5)).toBe(18);
  });

  it("stay inside the limits", () => {
    expect(raised(spot({ amount: 480 }), 100)).toBe(498);
    expect(raised(spot({ amount: 498 }), 5)).toBeNull();
    expect(raised(spot({ low: null, high: null }), 5)).toBeNull();
  });

  it("take a bet down when what is left would be too small", () => {
    expect(lowered(spot({ amount: 30, removable: true }), 5)).toBe(24);
    expect(lowered(spot({ amount: 6, removable: true }), 1)).toBe(0);
    expect(lowered(spot({ amount: 30 }), 5)).toBeNull();
  });
});

describe("settlements", () => {
  it("are said in words, not shown by color alone", () => {
    const base = { spot: { kind: "pass", number: null }, amount: 10, paid: 10 } as const;
    expect(settlementText({ ...base, outcome: "win", returned: 10 }, 7)).toBe("Pass: won 10");
    expect(settlementText({ ...base, outcome: "lose", paid: 0, returned: 0 }, 7)).toBe(
      "Pass: lost 10",
    );
  });
});
