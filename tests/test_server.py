"""Tables over real WebSockets, with fixed dice and a clock the test controls (spec §8)."""

import json
import runpy
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from itertools import count
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from crapless.server import app as server
from crapless.server import messages
from crapless.server.tables import (
    BET_PAUSE,
    REMEMBERED_IDS,
    SEAT_HELD,
    SEATS,
    SHOOTER_AWAY,
    Bucket,
    Busy,
    Tables,
    secure_dice,
)

PASS = {"kind": "pass", "number": None}
PASS_ODDS = {"kind": "pass_odds", "number": None}
COME = {"kind": "come", "number": None}


def spot(kind: str, number: int) -> dict[str, Any]:
    return {"kind": kind, "number": number}


class Dice:
    def __init__(self) -> None:
        self.next: list[tuple[int, int]] = []

    def __call__(self) -> tuple[int, int]:
        return self.next.pop(0)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class Player:
    ids = count()

    def __init__(
        self,
        socket: WebSocketTestSession,
        name: str = "Ana",
        table: str | None = None,
        token: str | None = None,
    ) -> None:
        self.socket = socket
        self.send(type="hello", v=2, name=name, table=table, token=token)
        self.state = self.receive()

    def send(self, **message: Any) -> None:
        self.socket.send_text(json.dumps(message))

    def receive(self) -> dict[str, Any]:
        reply: dict[str, Any] = self.socket.receive_json()
        if reply["type"] == "state":
            self.state = reply
        return reply

    def see(self, wanted: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        """Read what the server sends until the table looks like this."""
        while not wanted(self.state):
            self.receive()
        return self.state

    def ask(self, **message: Any) -> dict[str, Any]:
        message.setdefault("id", f"m{next(self.ids)}")
        if message["type"] not in ("refill", "leave"):
            message.setdefault("roll", self.state["roll"])
        self.send(**message)
        while True:
            reply = self.receive()
            if reply.get("ack") == message["id"] or reply.get("id") == message["id"]:
                return reply

    def bet(self, where: dict[str, Any], amount: int) -> dict[str, Any]:
        return self.ask(type="bet", spot=where, amount=amount)

    def amount(self, where: dict[str, Any]) -> int:
        return next((s["amount"] for s in self.state["spots"] if s["spot"] == where), 0)

    def at_table(self, name: str) -> dict[str, Any]:
        found: dict[str, Any] = next(p for p in self.state["players"] if p["name"] == name)
        return found


@pytest.fixture
def dice() -> Dice:
    return Dice()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def tables(clock: Clock) -> Tables:
    return Tables(clock=clock)


@pytest.fixture
def client(dice: Dice, tables: Tables, tmp_path: Path) -> Iterator[TestClient]:
    app = server.create_app(dice=dice, tables=tables, static=tmp_path / "none", tick_seconds=0.01)
    with TestClient(app) as c:
        yield c


@contextmanager
def seated(client: TestClient, *names: str) -> Iterator[list[Player]]:
    """Players at one table, each having seen all the others arrive."""
    sockets = [client.websocket_connect("/ws") for _ in names]
    try:
        players: list[Player] = []
        for socket, name in zip(sockets, names, strict=True):
            code = players[0].state["table"] if players else None
            players.append(Player(socket.__enter__(), name, code))
        for player in players:
            player.see(lambda s: len(s["players"]) == len(names))
        yield players
    finally:
        for socket in reversed(sockets):
            socket.__exit__(None, None, None)


def closed_with(socket: WebSocketTestSession) -> int:
    with pytest.raises(WebSocketDisconnect) as closed:
        while True:
            socket.receive_text()
    return closed.value.code


def test_a_full_turn_to_the_seven_out(client: TestClient, dice: Dice) -> None:
    dice.next = [(3, 3), (4, 5), (4, 4), (4, 5), (3, 4)]
    with seated(client, "Ana") as [player]:
        assert player.state["bankroll"] == 1000
        assert player.state["roll_blocked"]
        assert player.state["notice"] is None

        player.bet(PASS, 10)
        assert player.state["roll_blocked"] is None
        player.ask(type="roll")
        assert player.state["point"] == 6

        player.bet(PASS_ODDS, 25)
        player.bet(COME, 10)
        player.bet(spot("place", 8), 12)
        player.ask(type="roll")
        assert player.amount(spot("come", 9)) == 10

        player.bet(spot("come_odds", 9), 20)
        player.ask(type="roll")
        assert player.state["last_roll"]["settlements"] == [
            {"spot": spot("place", 8), "outcome": "win", "amount": 12, "paid": 14, "returned": 0}
        ]
        player.ask(type="roll")
        player.ask(type="roll")

        assert (player.state["point"], player.state["roll"]) == (None, 5)
        assert all(s["amount"] == 0 for s in player.state["spots"])
        assert player.state["bankroll"] == 1007


def test_friends_join_by_the_code_and_see_each_other(client: TestClient) -> None:
    with seated(client, "Ana", "Bo") as [ana, bo]:
        assert ana.state["table"] == bo.state["table"]
        assert [p["name"] for p in ana.state["players"]] == ["Ana", "Bo"]
        assert ana.at_table("Ana")["shooter"]
        assert ana.at_table("Ana")["color"] != ana.at_table("Bo")["color"]
        assert bo.state["roll_blocked"] == "Ana has the dice."
        assert (ana.state["can_pass"], bo.state["can_pass"]) == (True, False)


def test_others_see_where_you_bet_but_not_your_token(client: TestClient) -> None:
    with seated(client, "Ana", "Bo") as [ana, bo]:
        bo.bet(spot("place", 6), 12)
        ana.see(lambda s: s["others"] != [])
        assert ana.state["others"] == [{"spot": spot("place", 6), "seats": [bo.state["you"]]}]
        assert ana.amount(spot("place", 6)) == 0
        assert bo.state["token"] not in json.dumps(ana.state)


def test_everyone_sees_the_roll_and_the_dice_go_left_on_a_seven_out(
    client: TestClient, dice: Dice
) -> None:
    dice.next = [(3, 3), (3, 4)]
    with seated(client, "Ana", "Bo") as [ana, bo]:
        ana.bet(PASS, 10)
        ana.ask(type="roll")
        bo.see(lambda s: s["roll"] == 1)
        assert (bo.state["point"], bo.state["ack"]) == (6, None)
        assert bo.state["last_roll"]["die1"] == 3

        ana.ask(type="roll")
        bo.see(lambda s: s["roll"] == 2)
        assert bo.at_table("Bo")["shooter"]
        assert bo.at_table("Ana")["net"] == -10
        assert bo.at_table("Bo")["net"] is None
        assert bo.state["last_roll"]["settlements"] == []
        assert bo.state["roll_blocked"] == "Make a Pass bet to come out."


def test_only_the_shooter_rolls_or_passes(client: TestClient) -> None:
    with seated(client, "Ana", "Bo") as [ana, bo]:
        ana.bet(PASS, 10)
        bo.see(lambda s: s["others"] != [])
        assert bo.ask(type="roll")["code"] == "not_shooter"
        assert bo.ask(type="pass")["code"] == "not_shooter"
        ana.ask(type="pass")
        bo.see(lambda s: s["can_pass"])
        assert bo.at_table("Bo")["shooter"]


def test_the_roll_waits_after_someone_else_bets(
    client: TestClient, dice: Dice, clock: Clock
) -> None:
    dice.next = [(3, 3)]
    with seated(client, "Ana", "Bo") as [ana, bo]:
        ana.bet(PASS, 10)
        assert ana.state["wait_ms"] == 0  # your own bet does not hold you
        bo.bet(PASS, 10)
        ana.see(lambda s: s["wait_ms"] > 0)
        assert ana.state["wait_ms"] == BET_PAUSE * 1000
        assert ana.ask(type="roll")["code"] == "still_betting"

        clock.now += BET_PAUSE
        assert ana.ask(type="roll")["type"] == "state"
        assert not dice.next


def test_a_bet_that_changes_nothing_does_not_hold_the_roll(
    client: TestClient, clock: Clock
) -> None:
    with seated(client, "Ana", "Bo") as [ana, bo]:
        bo.bet(PASS, 10)
        ana.see(lambda s: s["wait_ms"] > 0)
        clock.now += BET_PAUSE
        bo.bet(PASS, 10)
        ana.see(lambda s: s["wait_ms"] == 0)


def test_a_ninth_player_is_told_the_table_is_full(client: TestClient) -> None:
    with seated(client, *[f"p{i}" for i in range(SEATS)]) as players:
        code = players[0].state["table"]
        with client.websocket_connect("/ws") as socket:
            socket.send_text(
                json.dumps({"type": "hello", "v": 2, "name": "x", "table": code, "token": None})
            )
            assert closed_with(socket) == server.TABLE_FULL


def test_a_dropped_player_comes_back_to_their_chips(client: TestClient, dice: Dice) -> None:
    dice.next = [(3, 3)]
    with seated(client, "Ana") as [ana]:
        code = ana.state["table"]
        with client.websocket_connect("/ws") as socket:
            bo = Player(socket, "Bo", code)
            bo.bet(spot("place", 8), 12)
            token = bo.state["token"]
        ana.see(lambda s: any(p["away"] for p in s["players"]))
        ana.bet(PASS, 10)
        ana.ask(type="roll", id="r1")
        with client.websocket_connect("/ws") as socket:
            back = Player(socket, "Bo", code, token)
            assert back.state["bankroll"] == 988
            assert back.amount(spot("place", 8)) == 12
            assert back.state["notice"] is None
            ana.see(lambda s: not any(p["away"] for p in s["players"]))


def test_a_message_sent_twice_changes_nothing(client: TestClient, dice: Dice) -> None:
    dice.next = [(3, 3)]
    with seated(client, "Ana") as [ana]:
        ana.bet(PASS, 10)
        first = ana.ask(type="roll", id="once", roll=0)
        again = ana.ask(type="roll", id="once", roll=0)
        assert again == first
        assert not dice.next


def test_a_late_message_is_rejected_with_the_reason(client: TestClient, dice: Dice) -> None:
    dice.next = [(3, 3)]
    with seated(client, "Ana") as [ana]:
        ana.bet(PASS, 10)
        ana.ask(type="roll")
        late = ana.ask(type="bet", spot=spot("place", 8), amount=12, roll=0)
        assert (late["type"], late["code"]) == ("rejected", "stale_roll")
        assert late["reason"]


@pytest.mark.parametrize(
    ("where", "amount", "code"),
    [
        (spot("place", 6), 7, "uneven_amount"),
        (spot("place", 7), 10, "not_now"),
        ({"kind": "pass", "number": 4}, 10, "not_now"),
        (PASS, 5000, "above_maximum"),
    ],
)
def test_bets_the_rules_refuse(
    client: TestClient, where: dict[str, Any], amount: int, code: str
) -> None:
    with seated(client, "Ana") as [ana]:
        reply = ana.bet(where, amount)
        assert (reply["type"], reply["code"]) == ("rejected", code)


def test_working_and_refill(client: TestClient, dice: Dice) -> None:
    dice.next = [(3, 4)]
    with seated(client, "Ana") as [ana]:
        ana.bet(spot("place", 6), 12)
        ana.ask(type="working", number=6, working=True)
        up = next(s for s in ana.state["spots"] if s["spot"] == spot("place", 6))
        assert up["working"] is True

        ana.bet(PASS, 10)
        ana.ask(type="roll")
        assert (ana.state["bankroll"], ana.state["can_refill"]) == (998, True)
        ana.ask(type="refill")
        assert ana.state["bankroll"] == 1000


def test_a_shooter_who_is_gone_loses_the_dice_after_a_wait(
    client: TestClient, clock: Clock
) -> None:
    with seated(client, "Ana") as [ana]:
        code = ana.state["table"]
        with client.websocket_connect("/ws") as socket:
            bo = Player(socket, "Bo", code)
        with client.websocket_connect("/ws") as socket:
            cy = Player(socket, "Cy", code)
            ana.see(lambda s: len(s["players"]) == 3)
            ana.ask(type="pass")  # the dice are with Bo, who has gone
            cy.see(lambda s: s["players"][1]["shooter"])
            assert bo.state

            clock.now += SHOOTER_AWAY
            cy.see(lambda s: s["players"][2]["shooter"])
            assert cy.at_table("Bo")["away"]


def test_a_seat_is_given_up_after_a_long_absence_once_nothing_is_locked(
    client: TestClient, clock: Clock, dice: Dice
) -> None:
    dice.next = [(3, 3), (3, 4)]
    with seated(client, "Ana") as [ana]:
        code = ana.state["table"]
        ana.bet(PASS, 10)
        with client.websocket_connect("/ws") as socket:
            bo = Player(socket, "Bo", code)
            bo.bet(PASS, 10)
            token = bo.state["token"]
        ana.see(lambda s: any(p["away"] for p in s["players"]))
        clock.now += BET_PAUSE
        ana.ask(type="roll")

        clock.now += SEAT_HELD
        ana.bet(spot("place", 8), 12)
        assert len(ana.state["players"]) == 2  # Bo's Pass bet has still to be decided

        ana.ask(type="roll")  # seven out decides it
        ana.see(lambda s: len(s["players"]) == 1)
        with client.websocket_connect("/ws") as socket:
            back = Player(socket, "Bo", code, token)
            assert "given up" in back.state["notice"]
            assert back.state["bankroll"] == 1000


def test_leaving(client: TestClient, dice: Dice) -> None:
    dice.next = [(3, 3)]
    with seated(client, "Ana", "Bo") as [ana, bo]:
        ana.bet(PASS, 10)
        bo.bet(PASS, 10)
        ana.see(lambda s: s["wait_ms"] > 0)
        bo.see(lambda s: len(s["others"]) == 1)
        assert bo.state["leave_blocked"] is None
        bo.send(type="leave", id="bye")
        assert closed_with(bo.socket) == server.LEFT
        ana.see(lambda s: len(s["players"]) == 1)
        assert ana.state["others"] == []


def test_leaving_is_refused_with_a_locked_bet(client: TestClient, dice: Dice) -> None:
    dice.next = [(3, 3)]
    with seated(client, "Ana") as [ana]:
        ana.bet(PASS, 10)
        ana.ask(type="roll")
        assert ana.state["leave_blocked"]
        assert ana.ask(type="leave")["code"] == "locked"


def test_an_old_link_starts_the_table_again_after_a_restart(client: TestClient) -> None:
    code = "from-before-the-restart"
    with client.websocket_connect("/ws") as one, client.websocket_connect("/ws") as two:
        ana = Player(one, "Ana", code, "old-token")
        bo = Player(two, "Bo", code, "another-old-token")
        assert "restarted" in ana.state["notice"]
        assert ana.state["table"] == bo.state["table"] == code
        assert [p["name"] for p in bo.state["players"]] == ["Ana", "Bo"]


def test_a_newer_connection_takes_over_the_seat(client: TestClient) -> None:
    with seated(client, "Ana") as [ana], client.websocket_connect("/ws") as new:
        again = Player(new, "Ana", ana.state["table"], ana.state["token"])
        assert closed_with(ana.socket) == server.TAKEN_OVER
        assert len(again.state["players"]) == 1
        assert again.bet(PASS, 10)["type"] == "state"


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("not json", server.POLICY),
        ('{"type":"roll","id":"a","roll":0,"dice":[3,4]}', server.POLICY),
        (
            '{"type":"bet","id":"a","spot":{"kind":"pass","number":null},"amount":"10","roll":0}',
            server.POLICY,
        ),
        ("x" * (server.MAX_MESSAGE + 1), server.TOO_BIG),
    ],
)
def test_messages_outside_the_protocol_close_the_connection(
    client: TestClient, text: str, code: int
) -> None:
    with seated(client, "Ana") as [ana]:
        ana.socket.send_text(text)
        assert closed_with(ana.socket) == code


def test_binary_frames_are_refused(client: TestClient) -> None:
    with client.websocket_connect("/ws") as socket:
        socket.send_bytes(b"{}")
        assert closed_with(socket) == server.UNSUPPORTED_DATA


def hello(**change: Any) -> str:
    return json.dumps(
        {"type": "hello", "v": 2, "name": "Ana", "table": None, "token": None} | change
    )


@pytest.mark.parametrize(
    ("first", "code"),
    [
        ('{"type":"refill","id":"a"}', server.POLICY),
        ('{"type":"hello","v":1,"token":null}', server.WRONG_VERSION),  # last version's page
        (hello(v=3), server.WRONG_VERSION),
        (hello(name="   "), server.WRONG_VERSION),
        (hello(name="x" * 13), server.WRONG_VERSION),
        (hello(table="short"), server.WRONG_VERSION),
    ],
)
def test_a_connection_must_start_with_a_hello_it_understands(
    client: TestClient, first: str, code: int
) -> None:
    with client.websocket_connect("/ws") as socket:
        socket.send_text(first)
        assert closed_with(socket) == code


def test_a_silent_connection_is_dropped(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server, "HELLO_SECONDS", 0.05)
    with client.websocket_connect("/ws") as socket:
        assert closed_with(socket) == server.POLICY


def test_flooding_closes_the_connection(client: TestClient) -> None:
    with seated(client, "Ana") as [ana]:
        with pytest.raises(WebSocketDisconnect) as closed:
            for _ in range(server.BURST * 3):
                ana.ask(type="refill")
        assert closed.value.code == server.POLICY


def test_buckets_refill(clock: Clock) -> None:
    bucket = Bucket(3, 1.0, clock)
    assert all(bucket.allow() for _ in range(3))
    assert not bucket.allow()
    clock.now += 1
    assert bucket.allow()


def test_busy_server(client: TestClient, tables: Tables, monkeypatch: pytest.MonkeyPatch) -> None:
    tables.limit = 1
    with seated(client, "Ana"), client.websocket_connect("/ws") as socket:
        socket.send_text(hello())
        assert closed_with(socket) == server.TRY_LATER
    tables.joins.allowance = 0
    with client.websocket_connect("/ws") as socket:
        socket.send_text(hello())
        assert closed_with(socket) == server.TRY_LATER
    monkeypatch.setattr(server, "MAX_CONNECTIONS", 0)
    with client.websocket_connect("/ws") as socket:
        assert closed_with(socket) == server.TRY_LATER


def test_unused_tables_are_dropped(clock: Clock) -> None:
    tables = Tables(limit=2, idle_seconds=100, clock=clock)
    old, _, _ = tables.sit(None, None, "a")
    clock.now += 50
    newer, player, _ = tables.sit(None, None, "b")
    newer.connect(player, object())
    tables.sit(None, None, "c")  # full, so the longest unused goes
    assert len(tables) == 2 and old not in list(tables)
    with pytest.raises(Busy):
        for table in tables:
            for p in table.players.values():
                table.connect(p, object())
        tables.sit(None, None, "d")


def test_a_table_everyone_has_gone_from_is_closed(clock: Clock) -> None:
    tables = Tables(clock=clock)
    table, player, _ = tables.sit(None, None, "a")
    connection = object()
    table.connect(player, connection)
    table.disconnect(player, connection)
    clock.now += SEAT_HELD
    tables.tick()
    assert len(tables) == 0


def test_a_slow_connection_is_let_go_without_holding_others() -> None:
    connection = server.Connection(None)  # type: ignore[arg-type]
    refused = messages.Refused(type="rejected", id=None, code="x", reason="y")
    for _ in range(server.QUEUE + 5):
        connection.send(refused)
    assert connection.outbox.qsize() == 1
    assert isinstance(connection.outbox.get_nowait(), server.Close)


def test_only_recent_message_ids_are_remembered(tables: Tables) -> None:
    table, player, _ = tables.sit(None, None, "a")
    for i in range(REMEMBERED_IDS + 5):
        table.handle(player, messages.Refill(type="refill", id=str(i)), secure_dice)
    assert len(player.seen) == REMEMBERED_IDS


def test_logs_explain_a_roll_and_never_hold_secrets_or_names(
    client: TestClient, dice: Dice, caplog: pytest.LogCaptureFixture
) -> None:
    dice.next = [(3, 4)]
    with caplog.at_level("INFO", logger="crapless"), seated(client, "Zebedee") as [player]:
        player.bet(PASS, 10)
        player.ask(type="roll")
        token, code = player.state["token"], player.state["table"]

    lines = [json.loads(r.message) for r in caplog.records if r.name == "crapless"]
    roll = next(line for line in lines if line["event"] == "roll")
    assert (roll["seat"], roll["roll"], roll["dice"]) == ("p1", 0, [3, 4])
    assert roll["bets_before"] == [{"seat": "p1", "kind": "pass", "number": None, "amount": 10}]
    assert roll["settlements"][0]["paid"] == 10
    assert roll["bankrolls"] == {"p1": 1010}
    for secret in (token, code, "Zebedee"):
        assert secret not in caplog.text


def test_dice_are_fair_enough_to_show_every_face() -> None:
    faces = [die for _ in range(600) for die in secure_dice()]
    assert set(faces) == {1, 2, 3, 4, 5, 6}


def test_health_and_the_built_page(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<p>table</p>")
    with TestClient(server.create_app(static=tmp_path)) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert "table" in client.get("/").text
        assert client.get("/docs").status_code == 404


def test_the_generated_protocol_files_are_current() -> None:
    """The TypeScript side is checked in CI; this catches a stale schema early."""
    script = runpy.run_path(str(Path(__file__).parent.parent / "scripts" / "protocol_schema.py"))
    assert script["SCHEMA"].read_text() == script["schema_text"]()
