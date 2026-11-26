# Crapless

A crapless craps table you can open on your phone and play with friends: join by link, take a seat, pass the dice. Play money only. Nothing is sold and nothing can be won.

![A craps table on a phone screen: a Pass bet sets the point at 6, odds, Come and Place bets go up, the dice tumble, the Come bet moves to 9 and wins, and the point is made](docs/demo.gif)

One hand on a phone-sized screen, played by a script against the real server. The dice are fixed for the recording; in play the server rolls them. Re-recorded by `npm run demo:gif --prefix web`.

**Play it:** https://crapless.onrender.com. The first visit after a quiet spell can take about a minute while the server wakes, and your table starts over.

**Status:** one player can play at the table; shared tables come next. Design: [docs/spec.md](docs/spec.md), [docs/protocol.md](docs/protocol.md) and [docs/adr/](docs/adr/).

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

The browser test plays one hand with fixed dice. It needs a browser once:

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
