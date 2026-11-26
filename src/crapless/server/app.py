"""The FastAPI app: one WebSocket, a health check and the built page."""

import asyncio
import logging
import os
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from crapless.server import messages
from crapless.server.tables import (
    Dice,
    Table,
    TableFull,
    Tables,
    event,
    log,
    secure_dice,
)

MAX_MESSAGE = 1024
HELLO_SECONDS = 10.0
MAX_CONNECTIONS = 100
BURST = 30
PER_SECOND = 10.0

# WebSocket close codes. 4000 and up are ours; docs/protocol.md lists them.
UNSUPPORTED_DATA = 1003
POLICY = 1008
TOO_BIG = 1009
TRY_LATER = 1013
WRONG_VERSION = 4000
TAKEN_OVER = 4001


class Close(Exception):
    def __init__(self, code: int, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


class RateLimit:
    """A token bucket for one connection."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.allowance = float(BURST)
        self.then = clock()

    def allow(self) -> bool:
        now = self.clock()
        self.allowance = min(BURST, self.allowance + (now - self.then) * PER_SECOND)
        self.then = now
        if self.allowance < 1:
            return False
        self.allowance -= 1
        return True


async def _receive(
    socket: WebSocket,
) -> messages.Hello | messages.PlaceBet | messages.Working | messages.RollDice | messages.Refill:
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
    *, dice: Dice = secure_dice, tables: Tables | None = None, static: Path | None = None
) -> FastAPI:
    _log_to_stdout()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    registry = tables if tables is not None else Tables()
    open_sockets: set[WebSocket] = set()

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    async def send(socket: WebSocket, message: messages.State | messages.Refused) -> None:
        await socket.send_text(message.model_dump_json())

    async def sit_down(socket: WebSocket) -> Table:
        try:
            hello = await asyncio.wait_for(_receive(socket), HELLO_SECONDS)
        except TimeoutError:
            raise Close(POLICY, "no hello") from None
        if not isinstance(hello, messages.Hello):
            raise Close(POLICY, "hello comes first")
        if hello.v != messages.VERSION:
            raise Close(WRONG_VERSION, "protocol version not supported")

        table = registry.find(hello.token) if hello.token else None
        reset = table is None and hello.token is not None
        if table is None:
            try:
                table = registry.create()
            except TableFull:
                raise Close(TRY_LATER, "no tables free") from None

        # One connection per seat. Take the seat first, then tell the old one to go.
        previous, table.connection = table.connection, socket
        if isinstance(previous, WebSocket):
            with suppress(RuntimeError, WebSocketDisconnect):
                await previous.close(TAKEN_OVER, "opened somewhere else")
        event("connected", table=table.id)
        await send(socket, table.view(reset=reset))
        return table

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        if len(open_sockets) >= MAX_CONNECTIONS:
            await socket.close(TRY_LATER, "server busy")
            return
        open_sockets.add(socket)
        table: Table | None = None
        limit = RateLimit()
        try:
            table = await sit_down(socket)
            while True:
                message = await _receive(socket)
                if not limit.allow():
                    raise Close(POLICY, "too many messages")
                if isinstance(message, messages.Hello):
                    raise Close(POLICY, "already said hello")
                if table.connection is not socket:
                    raise Close(TAKEN_OVER, "opened somewhere else")
                table.last_seen = registry.clock()
                await send(socket, table.handle(message, dice))
        except Close as close:
            event("closed", table=table and table.id, code=close.code, why=close.reason)
            with suppress(RuntimeError, WebSocketDisconnect):
                await socket.close(close.code, close.reason)
        except WebSocketDisconnect:
            event("disconnected", table=table and table.id)
        except Exception:
            log.exception("error on table %s", table and table.id)
            raise
        finally:
            open_sockets.discard(socket)
            if table is not None and table.connection is socket:
                table.connection = None
                table.last_seen = registry.clock()

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
