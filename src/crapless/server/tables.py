"""Tables held in memory (ADR 0002, ADR 0009). One seat each until slice 4."""

import json
import logging
import secrets
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

from crapless import engine
from crapless.server import messages

log = logging.getLogger("crapless")

SEAT = "p1"
REMEMBERED_IDS = 200

Dice = Callable[[], tuple[int, int]]


def secure_dice() -> tuple[int, int]:
    return secrets.randbelow(6) + 1, secrets.randbelow(6) + 1


def event(name: str, **fields: object) -> None:
    """One structured log line. Never pass a token."""
    log.info(json.dumps({"event": name, **fields}, separators=(",", ":")))


class TableFull(Exception):
    pass


@dataclass
class Table:
    id: str
    token: str
    state: engine.TableState
    last_seen: float
    last_roll: messages.LastRoll | None = None
    seen: OrderedDict[str, None] = field(default_factory=OrderedDict)
    connection: object | None = None
    """Whoever holds the seat now. A newer connection takes it over."""

    def handle(
        self,
        message: messages.PlaceBet | messages.Working | messages.RollDice | messages.Refill,
        dice: Dice,
    ) -> messages.State | messages.Refused:
        """Apply one message. This never awaits, so a table does one action at a time."""
        # A message sent twice changes nothing (spec §5, ADR 0007).
        if message.id in self.seen:
            return self.view(ack=message.id)
        self.seen[message.id] = None
        while len(self.seen) > REMEMBERED_IDS:
            self.seen.popitem(last=False)

        where = {"table": self.id, "seat": SEAT, "roll": self.state.roll_number}
        try:
            match message:
                case messages.PlaceBet():
                    bet = _bet(message.spot)
                    self._apply(engine.SetBet(SEAT, bet, message.amount, message.roll))
                    event(
                        "bet",
                        **where,
                        spot=message.spot.model_dump(mode="json"),
                        amount=message.amount,
                    )
                case messages.Working():
                    self._apply(
                        engine.SetWorking(SEAT, message.number, message.working, message.roll)
                    )
                    event("working", **where, number=message.number, working=message.working)
                case messages.RollDice():
                    self._roll(message.roll, dice)
                case messages.Refill():
                    self._apply(engine.Refill(SEAT))
                    event("refill", **where, bankroll=self.bankroll)
        except engine.Rejected as rejected:
            event("rejected", **where, code=rejected.code)
            return messages.Refused(
                type="rejected", id=message.id, code=rejected.code, reason=rejected.reason
            )
        return self.view(ack=message.id)

    def _apply(self, action: engine.Action) -> engine.Result:
        result = engine.apply(self.state, action)
        self.state = result.state
        return result

    def _roll(self, roll_number: int, dice: Dice) -> None:
        before = self.state
        die1, die2 = dice()
        result = self._apply(engine.Roll(SEAT, die1, die2, roll_number))
        settlements = [
            messages.SettlementView(
                spot=_spot(s.bet),
                outcome=s.outcome,
                amount=s.amount,
                paid=s.paid,
                returned=s.returned,
            )
            for s in result.settlements
        ]
        self.last_roll = messages.LastRoll(die1=die1, die2=die2, settlements=settlements)
        # Enough on one line to explain a disputed roll.
        event(
            "roll",
            table=self.id,
            seat=SEAT,
            roll=roll_number,
            dice=[die1, die2],
            point_before=before.point,
            point_after=self.state.point,
            bets_before=[
                {**asdict(bet), "amount": amount} for (_, bet), amount in before.bets.items()
            ],
            working=sorted(number for _, number in before.working),
            settlements=[s.model_dump(mode="json") for s in settlements],
            bankroll=self.bankroll,
        )

    @property
    def bankroll(self) -> int:
        seat = self.state.seat(SEAT)
        assert seat is not None
        return seat.bankroll

    def view(self, *, ack: str | None = None, reset: bool = False) -> messages.State:
        state = self.state
        held = [bet for _, bet in state.bets]
        offered = [
            engine.PASS,
            engine.PASS_ODDS,
            engine.COME,
            *(engine.place(n) for n in engine.POINT_NUMBERS),
        ]
        # Come bets that have moved to a number, and the odds spot behind each.
        for number in engine.POINT_NUMBERS:
            if engine.come(number) in held:
                offered += [engine.come(number), engine.come_odds(number)]

        spots = []
        for bet in offered:
            options = engine.spot_options(state, SEAT, bet)
            up = bet.kind is engine.BetKind.PLACE and options.amount > 0
            spots.append(
                messages.SpotView(
                    spot=_spot(bet),
                    amount=options.amount,
                    step=options.step,
                    low=options.low,
                    high=options.high,
                    removable=options.removable,
                    working=(SEAT, bet.number) in state.working if up else None,
                )
            )
        return messages.State(
            type="state",
            v=messages.VERSION,
            token=self.token,
            table=self.id,
            reset=reset,
            ack=ack,
            bankroll=self.bankroll,
            point=state.point,
            roll=state.roll_number,
            roll_blocked=_roll_blocked(state),
            can_refill=self.bankroll < state.settings.starting_bankroll,
            spots=spots,
            last_roll=self.last_roll,
        )


def _roll_blocked(state: engine.TableState) -> str | None:
    """Ask the engine, which is pure: try a roll and throw the result away."""
    try:
        engine.apply(state, engine.Roll(SEAT, 1, 1, state.roll_number))
    except engine.Rejected as rejected:
        return rejected.reason
    return None


def _bet(spot: messages.Spot) -> engine.Bet:
    try:
        return engine.Bet(spot.kind, spot.number)
    except ValueError:
        raise engine.Rejected(engine.Rejection.NOT_NOW, "There is no such spot.") from None


def _spot(bet: engine.Bet) -> messages.Spot:
    return messages.Spot(kind=bet.kind, number=bet.number)


class Tables:
    def __init__(
        self,
        *,
        limit: int = 500,
        idle_seconds: float = 12 * 60 * 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.idle_seconds = idle_seconds
        self.clock = clock
        self._by_token: dict[str, Table] = {}

    def __len__(self) -> int:
        return len(self._by_token)

    def find(self, token: str) -> Table | None:
        table = self._by_token.get(token)
        if table:
            table.last_seen = self.clock()
        return table

    def create(self) -> Table:
        self._make_room()
        state = engine.apply(engine.new_table(), engine.Join(SEAT)).state
        table = Table(
            id=secrets.token_urlsafe(6),
            token=secrets.token_urlsafe(32),
            state=state,
            last_seen=self.clock(),
        )
        self._by_token[table.token] = table
        event("table_created", table=table.id, tables=len(self))
        return table

    def _make_room(self) -> None:
        """Drop tables nobody has used for a long time, and if full, the longest unused."""
        now = self.clock()
        unused = sorted(
            (t for t in self._by_token.values() if t.connection is None),
            key=lambda t: t.last_seen,
        )
        for table in unused:
            if now - table.last_seen < self.idle_seconds and len(self) < self.limit:
                break
            del self._by_token[table.token]
            event("table_evicted", table=table.id)
        if len(self) >= self.limit:
            raise TableFull
