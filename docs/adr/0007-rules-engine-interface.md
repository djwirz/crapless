# 7. The rules engine is a pure function over immutable state

Date: 2026-11-26
Status: Accepted

## Context
ADR 0002 puts every decision on the server. The server, the protocol and the tests all build on how the engine is called, and phones send late and repeated messages.

## Options considered
1. **`apply(state, action)` returning a new state and settlements.**
2. **A mutable table object with methods:** familiar, but a rejected action can leave it half changed, and following every roll from a state (as the exact-math tests do) needs copying.
3. **An event log that state is rebuilt from:** a full history, which v1 has no use for.

## Decision
- `apply` takes an immutable table state and one action, and returns the new state and settlements, or raises a rejection carrying a reason and changes nothing.
- The engine does no I/O and has no randomness. A roll action carries the two dice.
- Betting, passing and rolling actions quote the roll number they were meant for. A stale one is rejected.
- A bet action sets the total on a spot rather than adding to it, so sending it twice changes nothing.
- The engine uses only the standard library.

## Why
Every case can be tested directly, and the late and duplicate messages in spec §5 are handled where the money is.

## Consequences
- The server holds the current state and applies one action at a time (ADR 0002), and supplies the dice.
- The engine's guard against repeats is not the whole answer. With two players, an old "pass the dice" message could act again if the dice came back before the next roll, so the protocol (slice 2) should also drop repeated message ids.
