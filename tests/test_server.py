"""One table over a real WebSocket, with fixed dice (spec §8)."""

import json
from collections.abc import Iterator
from itertools import count
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from crapless.server import app as server
from crapless.server.tables import REMEMBERED_IDS, TableFull, Tables, secure_dice

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


class Player:
    ids = count()

    def __init__(self, socket: WebSocketTestSession, token: str | None = None) -> None:
        self.socket = socket
        self.send(type="hello", v=1, token=token)
        self.state = self.receive()

    def send(self, **message: Any) -> None:
        self.socket.send_text(json.dumps(message))

    def receive(self) -> dict[str, Any]:
        reply: dict[str, Any] = self.socket.receive_json()
        if reply["type"] == "state":
            self.state = reply
        return reply

    def ask(self, **message: Any) -> dict[str, Any]:
        message.setdefault("id", f"m{next(self.ids)}")
        if message["type"] != "refill":
            message.setdefault("roll", self.state["roll"])
        self.send(**message)
        return self.receive()

    def bet(self, where: dict[str, Any], amount: int) -> dict[str, Any]:
        return self.ask(type="bet", spot=where, amount=amount)

    def amount(self, where: dict[str, Any]) -> int:
        return next((s["amount"] for s in self.state["spots"] if s["spot"] == where), 0)


@pytest.fixture
def dice() -> Dice:
    return Dice()


@pytest.fixture
def tables() -> Tables:
    return Tables()


@pytest.fixture
def client(dice: Dice, tables: Tables, tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(server.create_app(dice=dice, tables=tables, static=tmp_path / "none")) as c:
        yield c


def closed_with(socket: WebSocketTestSession) -> int:
    with pytest.raises(WebSocketDisconnect) as closed:
        socket.receive_text()
    return closed.value.code


def test_a_full_turn_to_the_seven_out(client: TestClient, dice: Dice) -> None:
    dice.next = [(3, 3), (4, 5), (4, 4), (4, 5), (3, 4)]
    with client.websocket_connect("/ws") as socket:
        player = Player(socket)
        assert player.state["bankroll"] == 1000
        assert player.state["roll_blocked"]
        assert not player.state["reset"]

        player.bet(PASS, 10)
        assert player.state["roll_blocked"] is None
        player.ask(type="roll")  # 6 is the point
        assert player.state["point"] == 6

        player.bet(PASS_ODDS, 25)
        player.bet(COME, 10)
        player.bet(spot("place", 8), 12)
        player.ask(type="roll")  # 9: the Come bet moves there
        assert player.amount(spot("come", 9)) == 10

        player.bet(spot("come_odds", 9), 20)
        player.ask(type="roll")  # 8: Place 8 pays 14
        assert player.state["last_roll"]["settlements"] == [
            {"spot": spot("place", 8), "outcome": "win", "amount": 12, "paid": 14, "returned": 0}
        ]
        player.ask(type="roll")  # 9: Come and its odds win
        player.ask(type="roll")  # seven-out

        assert player.state["point"] is None
        assert player.state["roll"] == 5
        assert all(s["amount"] == 0 for s in player.state["spots"])
        # 1000 + 14 (Place) + 10 + 30 (Come) - 10 - 25 (Pass) - 12 (Place)
        assert player.state["bankroll"] == 1007


def test_a_message_sent_twice_changes_nothing(client: TestClient, dice: Dice) -> None:
    dice.next = [(3, 3)]
    with client.websocket_connect("/ws") as socket:
        player = Player(socket)
        player.bet(PASS, 10)
        first = player.ask(type="roll", id="once", roll=0)
        again = player.ask(type="roll", id="once", roll=0)

        assert again == first
        assert not dice.next


def test_a_late_message_is_rejected_with_the_reason(client: TestClient, dice: Dice) -> None:
    dice.next = [(3, 3)]
    with client.websocket_connect("/ws") as socket:
        player = Player(socket)
        player.bet(PASS, 10)
        player.ask(type="roll")
        late = player.ask(type="bet", spot=spot("place", 8), amount=12, roll=0)

        assert late["type"] == "rejected"
        assert late["code"] == "stale_roll"
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
    with client.websocket_connect("/ws") as socket:
        reply = Player(socket).bet(where, amount)
        assert (reply["type"], reply["code"]) == ("rejected", code)


def test_working_and_refill(client: TestClient, dice: Dice) -> None:
    dice.next = [(3, 4)]
    with client.websocket_connect("/ws") as socket:
        player = Player(socket)
        player.bet(spot("place", 6), 12)
        player.ask(type="working", number=6, working=True)
        up = next(s for s in player.state["spots"] if s["spot"] == spot("place", 6))
        assert up["working"] is True

        player.bet(PASS, 10)
        player.ask(type="roll")  # come-out 7 takes the working Place bet
        assert player.state["bankroll"] == 998
        assert player.state["can_refill"]
        player.ask(type="refill")
        assert player.state["bankroll"] == 1000


def test_coming_back_finds_the_same_seat(client: TestClient, dice: Dice) -> None:
    dice.next = [(3, 3)]
    with client.websocket_connect("/ws") as socket:
        player = Player(socket)
        player.bet(PASS, 10)
        player.ask(type="roll")
        before = player.state
    with client.websocket_connect("/ws") as socket:
        after = Player(socket, before["token"]).state

    same = ("table", "bankroll", "point", "roll", "spots", "last_roll")
    assert {k: after[k] for k in same} == {k: before[k] for k in same}
    assert not after["reset"]


def test_an_unknown_token_gets_a_new_table_and_says_so(client: TestClient) -> None:
    with client.websocket_connect("/ws") as socket:
        state = Player(socket, "from-before-the-restart").state
    assert state["reset"]
    assert state["bankroll"] == 1000


def test_each_browser_has_its_own_table(client: TestClient) -> None:
    with client.websocket_connect("/ws") as one, client.websocket_connect("/ws") as two:
        first, second = Player(one), Player(two)
        first.bet(PASS, 10)
        second.bet(PASS, 25)
        assert (first.state["table"] != second.state["table"], first.amount(PASS)) == (True, 10)


def test_a_newer_connection_takes_over_the_seat(client: TestClient) -> None:
    with client.websocket_connect("/ws") as old:
        token = Player(old).state["token"]
        with client.websocket_connect("/ws") as new:
            player = Player(new, token)
            assert closed_with(old) == server.TAKEN_OVER
            assert player.bet(PASS, 10)["type"] == "state"


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("not json", server.POLICY),
        ('{"type":"roll","id":"a","roll":0,"dice":[3,4]}', server.POLICY),
        (
            '{"type":"bet","id":"a","spot":{"kind":"pass","number":null},"amount":"10","roll":0}',
            server.POLICY,
        ),
        (
            '{"type":"bet","id":"a","spot":{"kind":"field","number":null},"amount":10,"roll":0}',
            server.POLICY,
        ),
        ('{"type":"hello","v":1,"token":null}', server.POLICY),
        ("x" * (server.MAX_MESSAGE + 1), server.TOO_BIG),
    ],
)
def test_messages_outside_the_protocol_close_the_connection(
    client: TestClient, text: str, code: int
) -> None:
    with client.websocket_connect("/ws") as socket:
        Player(socket)
        socket.send_text(text)
        assert closed_with(socket) == code


def test_binary_frames_are_refused(client: TestClient) -> None:
    with client.websocket_connect("/ws") as socket:
        socket.send_bytes(b"{}")
        assert closed_with(socket) == server.UNSUPPORTED_DATA


@pytest.mark.parametrize(
    ("hello", "code"),
    [
        ({"type": "refill", "id": "a"}, server.POLICY),
        ({"type": "hello", "v": 2, "token": None}, server.WRONG_VERSION),
    ],
)
def test_a_connection_must_start_with_a_hello_it_understands(
    client: TestClient, hello: dict[str, Any], code: int
) -> None:
    with client.websocket_connect("/ws") as socket:
        socket.send_text(json.dumps(hello))
        assert closed_with(socket) == code


def test_a_silent_connection_is_dropped(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server, "HELLO_SECONDS", 0.05)
    with client.websocket_connect("/ws") as socket:
        assert closed_with(socket) == server.POLICY


def test_flooding_closes_the_connection(client: TestClient) -> None:
    with client.websocket_connect("/ws") as socket:
        player = Player(socket)
        with pytest.raises(WebSocketDisconnect) as closed:
            for _ in range(server.BURST * 3):
                player.ask(type="refill")
        assert closed.value.code == server.POLICY


def test_the_rate_limit_recovers() -> None:
    now = [0.0]
    limit = server.RateLimit(clock=lambda: now[0])
    assert all(limit.allow() for _ in range(server.BURST))
    assert not limit.allow()
    now[0] += 1
    assert limit.allow()


def test_busy_server_and_full_tables(
    client: TestClient, tables: Tables, monkeypatch: pytest.MonkeyPatch
) -> None:
    tables.limit = 1
    with client.websocket_connect("/ws") as one:
        Player(one)
        with client.websocket_connect("/ws") as two:
            two.send_text('{"type":"hello","v":1,"token":null}')
            assert closed_with(two) == server.TRY_LATER
    monkeypatch.setattr(server, "MAX_CONNECTIONS", 0)
    with client.websocket_connect("/ws") as socket:
        assert closed_with(socket) == server.TRY_LATER


def test_unused_tables_are_dropped() -> None:
    now = [0.0]
    tables = Tables(limit=2, idle_seconds=100, clock=lambda: now[0])
    old = tables.create()
    now[0] = 50
    newer = tables.create()
    tables.create()  # full, so the longest unused goes
    assert tables.find(old.token) is None and tables.find(newer.token) is newer

    now[0] = 500
    tables.create()
    assert len(tables) == 1

    held = Tables(limit=1)
    held.create().connection = object()
    with pytest.raises(TableFull):
        held.create()


def test_only_recent_message_ids_are_remembered(client: TestClient, tables: Tables) -> None:
    table = tables.create()
    from crapless.server import messages

    for i in range(REMEMBERED_IDS + 5):
        table.handle(messages.Refill(type="refill", id=str(i)), secure_dice)
    assert len(table.seen) == REMEMBERED_IDS


def test_logs_explain_a_roll_and_never_hold_the_token(
    client: TestClient, dice: Dice, caplog: pytest.LogCaptureFixture
) -> None:
    dice.next = [(3, 4)]
    with caplog.at_level("INFO", logger="crapless"), client.websocket_connect("/ws") as socket:
        player = Player(socket)
        player.bet(PASS, 10)
        player.ask(type="roll")
        token = player.state["token"]

    lines = [json.loads(r.message) for r in caplog.records if r.name == "crapless"]
    roll = next(line for line in lines if line["event"] == "roll")
    assert roll["table"] == player.state["table"]
    assert (roll["seat"], roll["roll"], roll["dice"]) == ("p1", 0, [3, 4])
    assert roll["bets_before"] == [{"kind": "pass", "number": None, "amount": 10}]
    assert roll["settlements"][0]["paid"] == 10
    assert token not in caplog.text


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
    import runpy

    script = runpy.run_path(str(Path(__file__).parent.parent / "scripts" / "protocol_schema.py"))
    assert script["SCHEMA"].read_text() == script["schema_text"]()
