# 6. Whole-number chips, and no rounding

Date: 2026-11-26
Status: Accepted

## Context
Several bets pay fractions (7 to 6, 11 to 4, 3 to 2). Bankrolls, bets and settlements all need one unit, and the chips must always add up.

## Options considered
1. **Whole chips, and each bet a multiple that pays out evenly.**
2. **Whole chips with rounding:** any bet is allowed, but a bet no longer pays what the rules table says.
3. **Fractional chips** (decimals or hundredths): any bet pays exactly, but amounts get awkward to read on a phone and every client has to handle them.

## Decision
Chips are integers. A bet that would not pay out evenly is rejected with a reason, never rounded or adjusted. The multiple comes from the table's payout for that spot, so changing a payout changes the multiple with it.

## Why
Payouts stay exact, "chips add up" can be checked with plain equality, and it is how a real table expects Place 6 to be bet in sixes.

## Consequences
- Some amounts are refused, and the effective minimum on a spot can be above the table minimum (6 on Place 6, 8 on Place 3).
- The front end should offer amounts that fit.
- Moving to fractional chips would touch the engine, the protocol and any saved bankrolls.
