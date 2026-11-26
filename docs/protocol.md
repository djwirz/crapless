# Protocol, version 3

One WebSocket at `/ws`, carrying one JSON object per text message. The definition is the Pydantic models in `src/crapless/server/messages.py` (ADR 0008). `web/protocol.schema.json` and `web/src/protocol.gen.ts` are generated from them:

```bash
uv run python scripts/protocol_schema.py && npm run types --prefix web
```

Every field is always present (`null` where there is no value), and unknown fields are refused.

Version 3 added the `pedantic` request, `announcement` and each player's `pedantic`.

## A connection
1. The client sends `hello`: `v: 3`, a display `name` (1 to 12 characters), the `table` code from the link (or `null` for a new table) and the seat `token` it kept for that table (or `null`).
2. The server answers with `state`. A code it does not know opens a table under that code. A token it does not know gets a new seat, with a `notice` saying why.
3. The client sends one request at a time and waits for the answer.
4. The server sends each seated player a new `state` whenever anything at the table changes.

A seat has one connection. A newer one takes it over and the older is closed. A table has eight seats.

## Client to server
| `type` | Fields | Meaning |
|---|---|---|
| `hello` | `v`, `name`, `table`, `token` | First message, once. |
| `bet` | `id`, `spot`, `amount`, `roll` | Make the chips on a spot total `amount`; 0 takes the bet down. |
| `working` | `id`, `number`, `working`, `roll` | Turn a Place bet on or off for the come-out. |
| `roll` | `id`, `roll` | Roll the dice. Shooter only. |
| `pass` | `id`, `roll` | Pass the dice to the left. Shooter only. |
| `pedantic` | `id`, `on` | Switch pedantic mode on or off for your own seat (ADR 0010). |
| `refill` | `id` | Top the bankroll back up. |
| `leave` | `id` | Give up the seat. The server closes with 4002. |

- `spot` is `{kind, number}`. `kind` is `pass`, `pass_odds`, `come`, `come_odds` or `place`.
- `id` is chosen by the client, up to 64 characters, and unique per request. The server remembers the most recent ones for each seat: a repeat does nothing and is answered with the current `state`.
- `roll` is the roll number from the latest `state`. A request meant for an earlier roll is rejected.
- A `roll` within about two seconds of someone else's bet is rejected with `still_betting`.

## Server to client
**`state`** is the whole table as one player sees it. Replace what you had.

| Field | Meaning |
|---|---|
| `token` | Keep this to come back to the seat. It is a secret. |
| `table` | The code for the invite link. Also a secret. |
| `ref` | The table's id in the server's logs, for reporting a problem. It lets nobody join. |
| `you` | Your seat id. |
| `notice` | Something to show once, or `null`. |
| `announcement` | News for the whole table, or `null`: for now, that a player switched pedantic mode. Sent once, to those connected. Show it for a few seconds. |
| `ack` | The `id` this answers, or `null` when someone else changed the table. |
| `bankroll`, `point`, `roll` | `point` is `null` on a come-out. |
| `roll_blocked` | Why you cannot roll now, or `null`. |
| `wait_ms` | For the shooter, how long Roll is still held after another's bet. |
| `can_refill`, `can_pass` | Whether those would do anything. |
| `low_on_chips` | Too few for your smallest bet. |
| `leave_blocked` | Why you cannot leave now, or `null`. |
| `players` | In the order the dice go round: `seat`, `name`, `color` (0 to 7), `bankroll`, `away`, `shooter`, `pedantic`, and `net` for the last roll. |
| `spots` | Your spots: `amount`, `step`, `low` and `high` (the smallest and largest total allowed now, or `null`), `removable`, and `working` for a Place bet that is up. The client needs no rules of its own. |
| `others` | Where other players have bets: `spot` and `seats`. No amounts. |
| `last_roll` | `die1`, `die2` and your `settlements` (`spot`, `outcome`, `amount`, `paid`, `returned`), or `null`. |

**`rejected`** has `id`, `code` and `reason`. Nothing changed. `reason` is for showing to the player.

Show a roll being thrown only when `roll` is one more than in the previous `state` on the same connection.

## Close codes
| Code | Meaning | What the client does |
|---|---|---|
| 1003, 1008, 1009 | Not a protocol message, too big, too many, or no `hello` in time | Reconnect with backoff |
| 1013 | Server busy, or the connection fell too far behind | Reconnect with backoff |
| 4000 | `hello` not understood, such as an older version | Ask for a reload |
| 4001 | The seat was opened somewhere else | Stay closed |
| 4002 | You left the table | Forget the seat |
| 4003 | The table is full | Stay closed |
