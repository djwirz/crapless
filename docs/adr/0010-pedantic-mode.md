# 10. Pedantic mode is a per-seat setting in the rules engine

Date: 2026-11-26
Status: Accepted

## Context
The smallest Place bet is 8 on 3 and 11 and 6 on 2 and 12, because the table minimum is 5 and every bet must pay out in whole chips (ADR 0006). A tester asked why. Dan asked for a switch each player can turn on to start those bets at 4, with the whole table told. The server decides what may be bet (ADR 0002).

## Options considered
1. **A flag on the seat in the engine, with its own action.** The engine already works out every limit, so offers and checks follow from one place, and the exact-math and property tests reach it.
2. **A check in the server, around the engine:** the engine would still refuse a bet of 4, so its minimum would have to be loosened for everyone and tightened again outside it.
3. **A setting kept by the page:** the server could not enforce it, which breaks spec §5.
4. **A lower minimum for the whole table:** simpler, but not what was asked.

## Decision
- Each seat in the engine has a `pedantic` flag, set by a `SetPedantic` action. It sets a value, so a repeat changes nothing.
- While it is on, that player's Place minimum is the table setting `pedantic_place_min` (4). One number for all Place bets is enough: multiples keep the minimum at 5 on 4, 5, 9 and 10 and at 6 on 6 and 8.
- Switching never moves chips. A bet below the usual minimum stays up after switching off; later changes follow the usual limits.
- The protocol goes to version 3: a `pedantic` request, a `pedantic` field for each player and a one-off `announcement`.

## Why
The limit lives where every other limit lives. Pays, multiples and settlement are untouched, so ADR 0006 holds.

## Consequences
- The setting lasts as long as the seat: through reconnects, but not leaving, a released seat or a restart (ADR 0009).
- A table can hold bets below its usual minimum, so nothing may assume that a bet on the table could be made again.
- An old open page is told to reload.
- Anyone can send news to the table by switching it often. Messages are rate limited, and the table is friends.
