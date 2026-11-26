# Crapless: spec

Status: Accepted in PR #1, updated by each slice · Date: 2026-11-26 · Owner: Dan

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

**Chips and limits** (the limits and payouts are table settings):
- Chips are whole numbers. A bet must be a multiple that pays out evenly (Place 6 or 8 in sixes), or it is rejected with a reason. Nothing is rounded (ADR 0006).
- Pass, Come and Place bets: minimum 5, maximum 500. Where 5 is not a valid multiple, the effective minimum is the next one up (6 on Place 6, 8 on Place 3).
- Odds: up to 3 times the flat bet, on every number.
- A seat starts with 1000 chips. A free refill tops the bankroll back up to that.
- Place pays default to the table above. Some casinos pay 2 and 12, or 3 and 11, differently. Odds always pay true odds.

**Table flow:**
- Place bets are off on the come-out unless the player turns them on.
- A Place bet turned on stays on until it is removed or lost. A winning Place bet is paid and stays up.
- Pass bets are made on the come-out. Come bets are made while there is a point.
- Pass and Come bets can't be removed or reduced once they have a point. Odds and Place bets can, before the roll.
- Come odds are off on a come-out roll unless the table setting turns them on. The Come bet itself still wins or loses, and odds that were off come back to the player. Neither rules page above says either way.
- The shooter needs a Pass bet to roll a come-out, and keeps the dice until a seven-out or chooses to pass them between rolls. The point and every bet stay. The dice go to the next player to the left.
- A player can leave unless they have a Pass or Come bet on a point. Their other bets leave with their bankroll.

**Next after v1:** field (2, 3, 4, 9, 10, 11, 12; 1 to 1, and 2 to 1 on 2 and 12) and hardways (4/10: 7 to 1; 6/8: 9 to 1), then buy bets.

## 5. Invariants and failure modes
1. **The server decides:** dice, bets and bankrolls change only on the server.
2. **Chips add up:** every chip is in a bankroll or on the table. The total changes only by what the house pays or collects on a roll, and by chips arriving with a new seat or a refill, or leaving with a player.
3. **Settled once:** each roll settles each bet at most once, even with retries and reconnects.
4. **Right pay:** every bet pays what §4 says.
5. **One shooter:** a table with players has exactly one shooter, and only the shooter rolls.

| Failure | What happens |
|---|---|
| A phone sleeps or loses signal | The seat and chips are held. On return the player gets the current table state. |
| The shooter disappears | After a short wait the dice pass to the left. |
| A message is sent twice | The second copy changes nothing. |
| A bet arrives after the roll | Rejected, with the reason shown. |
| The server restarts | Tables are held in memory only, so they start over, and the page says so (ADR 0009). |

## 6. Architecture
```
 phone browsers (TypeScript)
      │  WebSocket: intents up (join, bet, roll), events down (state, roll, settlements)
      ▼
 server (Python, FastAPI)
   tables and seats ─▶ rules engine (pure Python, no I/O)
   dice from the `secrets` module
```
- **Rules engine:** takes a table state and an action or a roll, returns the new state and the settlements. No I/O and no randomness inside it, so every case can be tested (ADR 0007).
- **Server:** one process holding tables in memory, one action at a time per table (ADR 0002).
- **Protocol:** versioned and written down in `docs/protocol.md`, so a native app can later be a second client.
- **Front end:** React and TypeScript built with Vite, with an SVG table from slice 3. It draws the state and sends intents. The server says what may be bet on each spot, so the page holds no rules, and the server checks everything again.
- **Host:** Render's free tier, deployed from `main` after CI passes (ADR 0009).

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
5. **Finish:** logs and counts, free chip refill polish, case-study notes.

A scripted browser hand (one player, fixed dice) runs in CI from slice 2 and records the README GIF. Slice 3 re-records it, and slice 4 grows it into the two-player end-to-end test.

A table of one is solo play, so there's no separate solo mode.

## 10. Acceptance criteria (v1 "done", depth 3)
1. A link opens the table on a current iPhone and Android phone with no install or sign-up.
2. Several players share a table, the dice rotate, and a dropped player can come back to their chips.
3. The exact-math and property tests run in CI.
4. Deployed from `main`, with logs that can explain a disputed roll.
5. ADRs for every expensive decision, and each PR says how AI was used and what it got wrong.

## 11. Open questions
Numbers are kept as questions are settled. Q1, Q2 and Q4 are settled in §4; Q3, Q5 and Q6 in §5 and §6.

- **Q7.** **Betting window** (before slice 4). Does the shooter roll whenever ready, or after a short timer or everyone's "ready"? Recommendation: the shooter rolls when ready, with a brief pause after the last bet.
- **Q8.** **Table size** (before slice 4). Recommendation: up to about eight.
