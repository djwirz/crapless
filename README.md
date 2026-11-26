# Crapless

A crapless craps table you can open on your phone and play with friends: join by link, take a seat, pass the dice. Play money only. Nothing is sold and nothing can be won.

**Status:** one player can play on a plain page; the table look and shared tables come next. Design: [docs/spec.md](docs/spec.md), [docs/protocol.md](docs/protocol.md) and [docs/adr/](docs/adr/).

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
