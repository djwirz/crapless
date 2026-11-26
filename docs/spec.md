# Crapless: spec

Status: Draft for PR #1 · Date: 2026-11-26 · Owner: Dan

## 1. Problem
Crapless craps is a craps variant with few games to play it in. This one is a table for a handful of friends: open a link on a phone, take a seat, bet, and take your turn with the dice. It should feel like playing craps without copying a whole casino.

## 2. Non-goals (v1)
- Real money, purchases, prizes or anything of value (ADR 0003).
- Accounts, saved history, a public lobby, chat or voice.
- Native iOS or Android apps, and installable-PWA extras (ADR 0005).
- Proposition, hop, fire and bonus bets.
- AI features.

## 3. Appetite
- **Time:** about two to four days of focused sessions.
- **Money:** free tiers.
- **If time runs short, cut in this order:** the end-to-end test's second scenario, sound, animation polish, metrics beyond logs. **Never cut:** correct payouts, server-side dice, the shared table with shooter rotation, reconnecting to your seat.

## 4. Rules (v1)
Sources: [Maryland standard rules for crapless craps, v1.1](https://www.mdgaming.com/wp-content/uploads/2026/04/Crapless-Craps-Standard-Rules-Version-1.1-accessible.pdf) and [Wizard of Odds](https://wizardofodds.com/games/crapless-craps/). Casinos differ, so payouts and limits are table settings.

**Come-out:** 7 wins the Pass bet. Every other total (2, 3, 4, 5, 6, 8, 9, 10, 11, 12) becomes the point. There is no don't pass or don't come.

| Bet | Wins when | Pays | House edge |
|---|---|---|---|
| Pass | 7 on the come-out, or the point repeats before a 7 | 1 to 1 | about 5.4% |
| Come | the same, starting from the next roll | 1 to 1 | same math as Pass |
| Odds on Pass or Come | with its flat bet | 2/12: 6 to 1; 3/11: 3 to 1; 4/10: 2 to 1; 5/9: 3 to 2; 6/8: 6 to 5 | none |
| Place 2 or 12 | the number before a 7 | 11 to 2 | about 7.1% |
| Place 3 or 11 | the number before a 7 | 11 to 4 | 6.25% |
| Place 4 or 10 | the number before a 7 | 9 to 5 | about 6.7% |
| Place 5 or 9 | the number before a 7 | 7 to 5 | 4% |
| Place 6 or 8 | the number before a 7 | 7 to 6 | about 1.5% |

**Table flow:**
- Place bets are off on the come-out unless the player turns them on.
- Pass and Come bets can't be removed or reduced once they have a point. Odds and Place bets can, before the roll.
- The shooter makes a Pass bet and keeps the dice until a seven-out, or chooses to pass them. The dice go to the next player to the left.

**Next after v1:** field (2, 3, 4, 9, 10, 11, 12; 1 to 1, and 2 to 1 on 2 and 12) and hardways (4/10: 7 to 1; 6/8: 9 to 1), then buy bets.

## 5. Invariants and failure modes
1. **The server decides:** dice, bets and bankrolls change only on the server.
2. **Chips add up:** every chip is in a bankroll or on the table, except what the house pays or collects on a roll.
3. **Settled once:** each roll settles each bet at most once, even with retries and reconnects.
4. **Right pay:** every bet pays what §4 says.
5. **One shooter:** a table with players has exactly one shooter, and only the shooter rolls.

| Failure | What happens |
|---|---|
| A phone sleeps or loses signal | The seat and chips are held. On return the player gets the current table state. |
| The shooter disappears | After a short wait the dice pass to the left. |
| A message is sent twice | The second copy changes nothing. |
| A bet arrives after the roll | Rejected, with the reason shown. |
| The server restarts | See §11 Q3. |

## 6. Architecture
```
 phone browsers (TypeScript)
      │  WebSocket: intents up (join, bet, roll), events down (state, roll, settlements)
      ▼
 server (Python, FastAPI)
   tables and seats ─▶ rules engine (pure Python, no I/O)
   dice from the `secrets` module
```
- **Rules engine:** takes a table state and an action or a roll, returns the new state and the settlements. No I/O and no randomness inside it, so every case can be tested.
- **Server:** one process holding tables in memory, one action at a time per table (ADR 0002).
- **Protocol:** versioned and written down in `docs/protocol.md`, so a native app can later be a second client.
- **Front end:** draws the state and sends intents. It holds no rules beyond what it needs to grey out illegal bets, and the server checks everything again.

## 7. Observability
Structured logs with table, seat and roll ids. Counts of open tables, rolls, rejected messages, disconnects and errors. No names in logs above debug level.

## 8. Testing and CI
- **Unit:** every bet, every total, on and off the come-out.
- **Exact math:** each bet's house edge, computed by enumerating the dice through the engine, matches §4.
- **Property:** random sequences of actions keep invariants 2, 3 and 5.
- **Integration:** a table over WebSockets with several clients, including disconnects and duplicate messages.
- **End to end:** two browser players, one full shooter turn each.
- **CI on every PR:** ruff, mypy, tests, front-end build and type check, gitleaks.

## 9. Slice plan (one PR each, after this spec)
1. **Rules engine:** the uv project, CI with gitleaks, the engine and its unit, property and exact-math tests.
2. **One player on a phone:** FastAPI and the protocol, a plain page that can play a full turn, deployed.
3. **Look and feel:** the table layout, chips, the dice throw and clear win and loss feedback, judged on a real phone.
4. **Shared table:** join by link, seats, shooter rotation, reconnects, the end-to-end test.
5. **Finish:** logs and counts, free chip refill polish, README GIF and case-study notes.

A table of one is solo play, so there's no separate solo mode.

## 10. Acceptance criteria (v1 "done", depth 3)
1. A link opens the table on a current iPhone and Android phone with no install or sign-up.
2. Several players share a table, the dice rotate, and a dropped player can come back to their chips.
3. The exact-math and property tests run in CI.
4. Deployed from `main`, with logs that can explain a disputed roll.
5. ADRs for every expensive decision, and each PR says how AI was used and what it got wrong.

## 11. Open questions
1. **Chip units and rounding** (before slice 1). Several pays are fractions. Recommendation: whole-number chips, with each bet required to be a multiple that pays out evenly (Place 6 in sixes).
2. **Table limits** (before slice 1). Minimum bet, maximum, and the odds multiple. Recommendation: one modest odds multiple on every number.
3. **State across restarts** (before slice 2). Memory only, or saved? Recommendation: save bankrolls and table state to SQLite after each roll if the host keeps a disk; otherwise accept the loss for v1 and say so.
4. **Come odds on a come-out roll** (before slice 1). On or off by default? Not found in the rules pages read. Check, then make it a setting.
5. **Front-end approach** (before slice 2). React, Svelte or plain TypeScript, and DOM, SVG or canvas for the table. Recommendation: React with SVG, unless a quick spike shows the dice throw needs canvas.
6. **Host** (before slice 2). One small instance that supports WebSockets. Check current free limits.
7. **Betting window** (before slice 4). Does the shooter roll whenever ready, or after a short timer or everyone's "ready"? Recommendation: the shooter rolls when ready, with a brief pause after the last bet.
8. **Table size** (before slice 4). Recommendation: up to about eight.
