# Protocol, version 1

One WebSocket at `/ws`, carrying one JSON object per text message. The definition is the Pydantic models in `src/crapless/server/messages.py` (ADR 0008). `web/protocol.schema.json` and `web/src/protocol.gen.ts` are generated from them:

```bash
uv run python scripts/protocol_schema.py && npm run types --prefix web
```

Every field is always present (`null` where there is no value), and unknown fields are refused.

## A connection
1. The client sends `hello` with `v: 1` and the seat `token` it kept, or `null`.
2. The server answers with `state`. A token it does not know gets a new table, with `reset: true`.
3. The client sends one request at a time and waits for the answer.

A seat has one connection. A newer one takes it over and the older is closed.

## Client to server
| `type` | Fields | Meaning |
|---|---|---|
| `hello` | `v`, `token` | First message, once. |
| `bet` | `id`, `spot`, `amount`, `roll` | Make the chips on a spot total `amount`; 0 takes the bet down. |
| `working` | `id`, `number`, `working`, `roll` | Turn a Place bet on or off for the come-out. |
| `roll` | `id`, `roll` | Roll the dice. |
| `refill` | `id` | Top the bankroll back up. |

- `spot` is `{kind, number}`. `kind` is `pass`, `pass_odds`, `come`, `come_odds` or `place`.
- `id` is chosen by the client, up to 64 characters, and unique per request. The server remembers the most recent ones for each seat: a repeat is answered with the current `state` and does nothing.
- `roll` is the roll number from the latest `state`. A request meant for an earlier roll is rejected.

## Server to client
**`state`** is the whole table. Replace what you had.

| Field | Meaning |
|---|---|
| `token` | Keep this to come back to the seat. It is a secret. |
| `table` | Table id, as it appears in logs. |
| `reset` | The token sent was not known. |
| `ack` | The `id` this answers, or `null`. |
| `bankroll`, `point`, `roll` | `point` is `null` on a come-out. |
| `roll_blocked` | Why the dice cannot be rolled now, or `null`. |
| `can_refill` | Whether a refill would add chips. |
| `spots` | For each spot: `amount`, `step`, `low` and `high` (the smallest and largest total allowed now, or `null`), `removable`, and `working` for a Place bet that is up. The client needs no rules of its own. |
| `last_roll` | `die1`, `die2` and `settlements` (`spot`, `outcome`, `amount`, `paid`, `returned`), or `null`. |

**`rejected`** has `id`, `code` and `reason`. Nothing changed. `reason` is for showing to the player.

## Close codes
| Code | Meaning | What the client does |
|---|---|---|
| 1003, 1008, 1009 | Not a protocol message, too big, too many, or no `hello` in time | Reconnect with backoff |
| 1013 | Server busy or no tables free | Reconnect with backoff |
| 4000 | Protocol version not supported | Ask for a reload |
| 4001 | The seat was opened somewhere else | Stay closed |
