# Crapless

A crapless craps table you can open on your phone and play with friends: join by link, take a seat, pass the dice. Play money only. Nothing is sold and nothing can be won.

![A craps table on a phone screen shared by two players: one sets a point of 6 and bets odds, Come and Place, sevens out, and the dice move to the other player](docs/demo.gif)

One of two phones at a table, played by a script against the real server. The dice are fixed for the recording; in play the server rolls them. Re-recorded by `npm run demo:gif --prefix web`.

**Play it:** https://crapless.onrender.com. The first visit after a quiet spell can take about a minute while the server wakes, and the table starts over.

**Status:** up to eight players share a table by link. Logs, counts and polish come next. Design: [docs/spec.md](docs/spec.md), [docs/protocol.md](docs/protocol.md) and [docs/adr/](docs/adr/).

## Development
Needs [uv](https://docs.astral.sh/uv/) and Node 22.

Build the page, then run the server and open http://localhost:8000:

```bash
npm ci --prefix web && npm run build --prefix web
```

```bash
uv run uvicorn crapless.server.app:create_app --factory --port 8000
```

While working on the page, `npm run dev --prefix web` reloads it and passes `/ws` to that server.

Tests:

```bash
uv run pytest
```

```bash
npm test --prefix web
```

The browser test seats two players and gives each a turn with fixed dice. It needs a browser once:

```bash
cd web && npx playwright install chromium
```

```bash
npm run e2e --prefix web
```

To re-record the GIF after the page changes (needs Docker):

```bash
npm run demo:gif --prefix web
```
