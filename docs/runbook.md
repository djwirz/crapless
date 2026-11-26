# Runbook

## A disputed roll
1. Ask for the **Table ref** and **last roll #**, shown at the bottom of the players panel. Neither lets anyone join the table.
2. In the Render dashboard, open the `crapless` service and its **Logs** page. Widen the time range (it starts at the last hour) and search for the ref.
3. Find the line with `"event":"roll"` and that `"roll"` number.

| Field | Meaning |
|---|---|
| `seat` | Who threw. Seats are `p1`, `p2` and so on, in the order people sat. |
| `dice` | The two faces. |
| `point_before`, `point_after` | `null` is a come-out. |
| `bets_before` | Every bet on the table when the dice landed. |
| `working` | Place bets turned on for a come-out. |
| `settlements` | What happened to each bet: `outcome`, `amount`, `paid`, `returned`. |
| `bankrolls` | Every seat's bankroll afterwards. |

Check `settlements` against the rules in [spec §4](spec.md#4-rules-v1). Earlier `bet`, `working`, `pedantic`, `refill`, `passed` and `rejected` lines with the same ref show how the table got there. A `rejected` line with `stale_roll` is a bet that arrived after the dice. A Place bet of 4 on 2, 3, 11 or 12 means that seat had pedantic mode on when it was made.

**Limits.** Render's [logging docs](https://render.com/docs/logging) (read November 2026) give seven days of retention on the free workspace, and drop lines above a few thousand a minute. They do not say whether logs survive a redeploy or a sleep. This procedure has been checked against the app's log lines, not yet tried in Render's dashboard.

## Is it healthy?
- `/healthz` answers `{"status":"ok"}`.
- `/stats` shows totals since the last restart. `Errors` should be 0; if it is not, search the logs for `error`.
- A `summary` line with the same totals is logged every five minutes while anyone is connected.
- The first visit after about fifteen quiet minutes takes about a minute while the server wakes.

## Releasing
Merging to `main` deploys once CI passes. A deploy restarts the server, so every table starts over.

## Privacy
Logs hold seat numbers and table refs. They never hold names, seat tokens or table codes. `/stats` holds totals only.
