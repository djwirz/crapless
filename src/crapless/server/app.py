"""The FastAPI app: one WebSocket, a health check and the built page."""

import asyncio
import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from crapless.server import messages
from crapless.server.stats import page as stats_page
from crapless.server.tables import (
    Bucket,
    Busy,
    Dice,
    Player,
    Table,
    TableFull,
    Tables,
    event,
    log,
    secure_dice,
)

MAX_MESSAGE = 1024
HELLO_SECONDS = 10.0
MAX_CONNECTIONS = 200
BURST = 30
PER_SECOND = 10.0
QUEUE = 64
SUMMARY_SECONDS = 300.0

# WebSocket close codes. 4000 and up are ours; docs/protocol.md lists them.
UNSUPPORTED_DATA = 1003
POLICY = 1008
TOO_BIG = 1009
TRY_LATER = 1013
WRONG_VERSION = 4000
TAKEN_OVER = 4001
LEFT = 4002
TABLE_FULL = 4003


class Close(Exception):
    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


class Connection:
    """One socket's outbox. A slow phone fills its own queue and holds nobody else up."""

    def __init__(self, socket: WebSocket) -> None:
        self.socket = socket
        self.outbox: asyncio.Queue[str | Close] = asyncio.Queue(QUEUE)
        self.closing = False

    def send(self, message: messages.State | messages.Refused) -> None:
        self._put(message.model_dump_json())

    def close(self, code: int, reason: str) -> None:
        self._put(Close(code, reason))
        self.closing = True

    def _put(self, item: str | Close) -> None:
        if self.closing:
            return
        try:
            self.outbox.put_nowait(item)
        except asyncio.QueueFull:
            # Too far behind to catch up. Drop what is waiting and let it reconnect.
            while not self.outbox.empty():
                self.outbox.get_nowait()
            self.outbox.put_nowait(Close(TRY_LATER, "fell behind"))
            self.closing = True

    async def write(self) -> None:
        with suppress(RuntimeError, WebSocketDisconnect):
            while True:
                item = await self.outbox.get()
                if isinstance(item, Close):
                    await self.socket.close(item.code, item.reason)
                    return
                await self.socket.send_text(item)


def broadcast(table: Table, *, asker: Player | None = None, ack: str | None = None) -> None:
    """Send each connected player their own view."""
    for player in table.players.values():
        if isinstance(player.connection, Connection):
            player.connection.send(table.view(player, ack=ack if player is asker else None))


async def _receive(socket: WebSocket) -> messages.Hello | messages.Request:
    frame = await socket.receive()
    if frame["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(frame.get("code", 1000))
    text = frame.get("text")
    if text is None:
        raise Close(UNSUPPORTED_DATA, "text messages only")
    if len(text) > MAX_MESSAGE:
        raise Close(TOO_BIG, "message too big")
    try:
        return messages.client_message.validate_json(text)
    except ValidationError:
        raise Close(POLICY, "not a protocol message") from None


def create_app(
    *,
    dice: Dice = secure_dice,
    tables: Tables | None = None,
    static: Path | None = None,
    tick_seconds: float = 1.0,
    summary_seconds: float = SUMMARY_SECONDS,
) -> FastAPI:
    _log_to_stdout()
    registry = tables if tables is not None else Tables()
    open_sockets: set[WebSocket] = set()

    async def tick() -> None:
        summarised = registry.clock()
        while True:
            await asyncio.sleep(tick_seconds)
            try:
                for table in registry.tick():
                    broadcast(table)
                if registry.clock() - summarised >= summary_seconds:
                    summarised = registry.clock()
                    stats = registry.stats()
                    # Quiet while nobody is here, so an idle server says nothing.
                    if stats["players_connected"]:
                        event("summary", **stats)
            except Exception:
                # Keep ticking: one bad table must not stop the dice moving at the others.
                registry.counts["errors"] += 1
                log.exception("error while ticking")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(tick())
        yield
        task.cancel()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.get("/stats", response_class=HTMLResponse)
    async def stats() -> str:
        return stats_page(registry.stats())

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    async def hello(socket: WebSocket) -> messages.Hello:
        try:
            first = await asyncio.wait_for(_receive(socket), HELLO_SECONDS)
        except TimeoutError:
            raise Close(POLICY, "no hello") from None
        except Close as close:
            # An old page's hello lacks fields we now need; tell it to reload.
            if close.code == POLICY:
                raise Close(WRONG_VERSION, "protocol version not supported") from None
            raise
        if not isinstance(first, messages.Hello):
            raise Close(POLICY, "hello comes first")
        if first.v != messages.VERSION:
            raise Close(WRONG_VERSION, "protocol version not supported")
        return first

    async def play(socket: WebSocket, connection: Connection, table: Table, player: Player) -> None:
        limit = Bucket(BURST, PER_SECOND)
        while True:
            message = await _receive(socket)
            if not limit.allow():
                raise Close(POLICY, "too many messages")
            if isinstance(message, messages.Hello):
                raise Close(POLICY, "already said hello")
            if player.connection is not connection:
                raise Close(TAKEN_OVER, "opened somewhere else")
            table.last_seen = registry.clock()
            refused = table.handle(player, message, dice)
            if refused:
                connection.send(refused)
            elif player.seat not in table.players:
                broadcast(table)
                raise Close(LEFT, "you left the table")
            else:
                broadcast(table, asker=player, ack=message.id)

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        if len(open_sockets) >= MAX_CONNECTIONS:
            await socket.close(TRY_LATER, "server busy")
            return
        open_sockets.add(socket)
        connection = Connection(socket)
        writer: asyncio.Task[None] | None = None
        table: Table | None = None
        player: Player | None = None
        try:
            first = await hello(socket)
            try:
                table, player, notice = registry.sit(first.table, first.token, first.name)
            except TableFull:
                raise Close(TABLE_FULL, "the table is full") from None
            except Busy:
                raise Close(TRY_LATER, "no room just now") from None

            # One connection per seat. Take the seat first, then tell the old one to go.
            previous = table.connect(player, connection)
            if isinstance(previous, Connection):
                previous.close(TAKEN_OVER, "opened somewhere else")
            writer = asyncio.create_task(connection.write())
            event("connected", table=table.id, seat=player.seat)
            connection.send(table.view(player, notice=notice))
            for other in table.players.values():
                if other is not player and isinstance(other.connection, Connection):
                    other.connection.send(table.view(other))
            await play(socket, connection, table, player)
        except Close as close:
            event("closed", table=table and table.id, code=close.code, why=close.reason)
            if writer:
                connection.close(close.code, close.reason)
                await writer
            else:
                with suppress(RuntimeError, WebSocketDisconnect):
                    await socket.close(close.code, close.reason)
        except WebSocketDisconnect:
            if player:
                registry.counts["disconnects"] += 1
            event("disconnected", table=table and table.id, seat=player and player.seat)
        except Exception:
            registry.counts["errors"] += 1
            log.exception("error on table %s", table and table.id)
            raise
        finally:
            open_sockets.discard(socket)
            if writer:
                writer.cancel()
            gone = table and player and table.disconnect(player, connection)
            if table and player and gone and player.seat in table.players:
                broadcast(table)

    page = static or Path(os.environ.get("CRAPLESS_STATIC", "web/dist"))
    if page.is_dir():
        app.mount("/", StaticFiles(directory=page, html=True), name="page")
    return app


def _log_to_stdout() -> None:
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
