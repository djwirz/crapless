"""Tables held in memory (ADR 0002, ADR 0009): up to eight seats, joined by a link.

Nothing here awaits, so a table does one thing at a time. Whoever calls sends each connected
player their view afterwards.
"""

import json
import logging
import secrets
import time
from collections import Counter, OrderedDict
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field

from crapless import engine
from crapless.server import messages

log = logging.getLogger("crapless")

SEATS = 8
REMEMBERED_IDS = 200
BET_PAUSE = 2.0
"""After someone else's bet, how long before the shooter may roll (spec §4)."""
SHOOTER_AWAY = 30.0
"""How long the dice wait for a shooter who has gone."""
SEAT_HELD = 600.0
"""How long a seat is kept for a player who has gone."""

Dice = Callable[[], tuple[int, int]]
Clock = Callable[[], float]


def secure_dice() -> tuple[int, int]:
    return secrets.randbelow(6) + 1, secrets.randbelow(6) + 1


def event(name: str, **fields: object) -> None:
    """One structured log line. Never pass a token, a table code or a player's name."""
    log.info(json.dumps({"event": name, **fields}, separators=(",", ":")))


class TableFull(Exception):
    """The table has no seat left."""


class Busy(Exception):
    """The server cannot take another table or player just now."""


class Bucket:
    """A token bucket."""

    def __init__(self, burst: int, per_second: float, clock: Clock = time.monotonic) -> None:
        self.burst = burst
        self.per_second = per_second
        self.clock = clock
        self.allowance = float(burst)
        self.then = clock()

    def allow(self) -> bool:
        now = self.clock()
        self.allowance = min(self.burst, self.allowance + (now - self.then) * self.per_second)
        self.then = now
        if self.allowance < 1:
            return False
        self.allowance -= 1
        return True


COUNTED = ("tables_created", "joined", "rolls", "rejected", "disconnects", "errors")
"""Counted since the server started (spec §7). They are lost with everything else on restart."""


@dataclass
class Player:
    seat: str
    name: str
    token: str
    color: int
    connection: object | None = None
    """Whoever holds the seat now. A newer connection takes it over."""
    away_since: float | None = None
    seen: OrderedDict[str, None] = field(default_factory=OrderedDict)
    net: int | None = None
    settlements: list[messages.SettlementView] = field(default_factory=list)


@dataclass
class Table:
    code: str
    id: str
    """For logs. Not the code, which would let a reader of the logs join."""
    clock: Clock
    last_seen: float
    counts: Counter[str] = field(default_factory=Counter)
    """Shared by every table on the server."""
    state: engine.TableState = field(default_factory=engine.new_table)
    players: dict[str, Player] = field(default_factory=dict)
    dice: tuple[int, int] | None = None
    bet_at: dict[str, float] = field(default_factory=dict)
    seats_given: int = 0
    news: str | None = None
    """An announcement waiting for the next broadcast."""

    # Seats

    def join(self, name: str) -> Player:
        if len(self.players) >= SEATS:
            raise TableFull
        self.seats_given += 1
        seat = f"p{self.seats_given}"
        color = min(set(range(SEATS)) - {p.color for p in self.players.values()})
        player = Player(seat, name.strip(), secrets.token_urlsafe(32), color)
        self._apply(engine.Join(seat))
        self.players[seat] = player
        self.counts["joined"] += 1
        event("joined", table=self.id, seat=seat, seats=len(self.players))
        return player

    def by_token(self, token: str) -> Player | None:
        # compare_digest, so the time taken says nothing about how close a guess was.
        return next(
            (p for p in self.players.values() if secrets.compare_digest(p.token, token)), None
        )

    def connect(self, player: Player, connection: object) -> object | None:
        """Give the seat to a connection. Returns the one it replaces."""
        previous, player.connection = player.connection, connection
        player.away_since = None
        return previous

    def disconnect(self, player: Player, connection: object) -> bool:
        if player.connection is not connection:
            return False
        player.connection = None
        player.away_since = self.clock()
        self.last_seen = self.clock()
        return True

    @property
    def empty_handed(self) -> bool:
        """Nobody is connected."""
        return all(p.connection is None for p in self.players.values())

    def tick(self) -> bool:
        """Act on players who have gone. True if the table changed."""
        now = self.clock()
        changed = False
        for player in list(self.players.values()):
            if player.away_since is None or now - player.away_since < SEAT_HELD:
                continue
            try:
                self._apply(engine.Leave(player.seat))
            except engine.Rejected:
                continue  # A Pass or Come bet is still to be decided. Try again later.
            del self.players[player.seat]
            event("seat_released", table=self.id, seat=player.seat)
            changed = True
        return self._move_dice(now) or changed

    def _move_dice(self, now: float) -> bool:
        shooter = self.players.get(self.state.shooter or "")
        if shooter is None or shooter.away_since is None:
            return False
        if now - shooter.away_since < SHOOTER_AWAY or self.empty_handed:
            return False
        # Pass to the left until the dice reach someone who is here.
        while (holder := self.players[self.state.shooter or ""]).connection is None:
            self._apply(engine.PassDice(holder.seat, self.state.roll_number))
        event("dice_moved_on", table=self.id, seat=self.state.shooter)
        return True

    # Requests

    def handle(
        self, player: Player, message: messages.Request, dice: Dice
    ) -> messages.Refused | None:
        """Apply one request. None means it was accepted, or had already been dealt with."""
        # A message sent twice changes nothing (spec §5, ADR 0007).
        if message.id in player.seen:
            return None
        player.seen[message.id] = None
        while len(player.seen) > REMEMBERED_IDS:
            player.seen.popitem(last=False)

        seat = player.seat
        where = {"table": self.id, "seat": seat, "roll": self.state.roll_number}
        before = self.state
        try:
            match message:
                case messages.PlaceBet():
                    bet = _bet(message.spot)
                    self._apply(engine.SetBet(seat, bet, message.amount, message.roll))
                    spot = message.spot.model_dump(mode="json")
                    event("bet", **where, spot=spot, amount=message.amount)
                case messages.Working():
                    self._apply(
                        engine.SetWorking(seat, message.number, message.working, message.roll)
                    )
                    event("working", **where, number=message.number, working=message.working)
                case messages.RollDice():
                    self._roll(player, message.roll, dice)
                case messages.Pedantic():
                    self._apply(engine.SetPedantic(seat, message.on))
                    # Said once, and only if something changed. The name is never logged.
                    if self.state != before:
                        word = "enabled" if message.on else "disabled"
                        self.news = f"Pedantic mode {word} for {player.name}"
                        event("pedantic", **where, on=message.on)
                case messages.Refill():
                    self._apply(engine.Refill(seat))
                    event("refill", **where)
                case messages.PassDice():
                    self._apply(engine.PassDice(seat, message.roll))
                    event("passed", **where)
                case messages.Leave():
                    self._apply(engine.Leave(seat))
                    del self.players[seat]
                    event("left", **where)
        except engine.Rejected as rejected:
            self.counts["rejected"] += 1
            event("rejected", **where, code=rejected.code)
            return messages.Refused(
                type="rejected", id=message.id, code=rejected.code, reason=rejected.reason
            )
        except _StillBetting:
            self.counts["rejected"] += 1
            event("rejected", **where, code="still_betting")
            return messages.Refused(
                type="rejected",
                id=message.id,
                code="still_betting",
                reason="Bets are still going down.",
            )
        # Only chips that actually moved or switched hold the shooter back.
        if isinstance(message, messages.PlaceBet | messages.Working) and self.state != before:
            self.bet_at[seat] = self.clock()
        return None

    def _apply(self, action: engine.Action) -> engine.Result:
        result = engine.apply(self.state, action)
        self.state = result.state
        return result

    def take_news(self) -> str | None:
        news, self.news = self.news, None
        return news

    def pause_left(self) -> float:
        """Seconds the shooter must still wait because someone else just bet."""
        others = [at for seat, at in self.bet_at.items() if seat != self.state.shooter]
        return max(0.0, max(others) + BET_PAUSE - self.clock()) if others else 0.0

    def _roll(self, player: Player, roll_number: int, dice: Dice) -> None:
        before = self.state
        action_for = player.seat
        # Refuse for the usual reasons first, and only then for the pause.
        engine.apply(before, engine.Roll(action_for, 1, 1, roll_number))
        if self.pause_left() > 0:
            raise _StillBetting
        die1, die2 = dice()
        result = self._apply(engine.Roll(action_for, die1, die2, roll_number))
        self.dice = die1, die2
        self.bet_at.clear()
        self.counts["rolls"] += 1
        for other in self.players.values():
            mine = [s for s in result.settlements if s.player == other.seat]
            other.settlements = [
                messages.SettlementView(
                    spot=_spot(s.bet),
                    outcome=s.outcome,
                    amount=s.amount,
                    paid=s.paid,
                    returned=s.returned,
                )
                for s in mine
            ]
            decided = [s for s in mine if s.outcome is not engine.Outcome.MOVED]
            other.net = sum(s.paid - s.collected for s in decided) if decided else None
        # Enough on one line to explain a disputed roll.
        event(
            "roll",
            table=self.id,
            seat=action_for,
            roll=roll_number,
            dice=[die1, die2],
            point_before=before.point,
            point_after=self.state.point,
            bets_before=[
                {"seat": seat, **asdict(bet), "amount": amount}
                for (seat, bet), amount in before.bets.items()
            ],
            working=sorted(before.working),
            settlements=[
                {
                    "seat": s.player,
                    **asdict(s.bet),
                    "outcome": s.outcome,
                    "amount": s.amount,
                    "paid": s.paid,
                    "returned": s.returned,
                }
                for s in result.settlements
            ],
            bankrolls={s.player: s.bankroll for s in self.state.seats},
        )

    # Views

    def view(
        self,
        player: Player,
        *,
        ack: str | None = None,
        notice: str | None = None,
        announcement: str | None = None,
    ) -> messages.State:
        state, seat = self.state, player.seat
        mine = state.seat(seat)
        assert mine is not None
        held = [bet for owner, bet in state.bets if owner == seat]
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
            options = engine.spot_options(state, seat, bet)
            up = bet.kind is engine.BetKind.PLACE and options.amount > 0
            spots.append(
                messages.SpotView(
                    spot=_spot(bet),
                    amount=options.amount,
                    step=options.step,
                    low=options.low,
                    high=options.high,
                    removable=options.removable,
                    working=(seat, bet.number) in state.working if up else None,
                )
            )

        others: dict[engine.Bet, list[str]] = {}
        for owner, bet in state.bets:
            if owner != seat:
                others.setdefault(bet, []).append(owner)

        shooter = state.shooter == seat
        last_roll = None
        if self.dice:
            die1, die2 = self.dice
            last_roll = messages.LastRoll(die1=die1, die2=die2, settlements=player.settlements)

        return messages.State(
            type="state",
            v=messages.VERSION,
            token=player.token,
            table=self.code,
            ref=self.id,
            you=seat,
            notice=notice,
            announcement=announcement,
            ack=ack,
            bankroll=mine.bankroll,
            point=state.point,
            roll=state.roll_number,
            roll_blocked=self._roll_blocked(seat),
            wait_ms=round(self.pause_left() * 1000) if shooter else 0,
            can_refill=mine.bankroll < state.settings.starting_bankroll,
            low_on_chips=mine.bankroll < engine.smallest_bet(state, seat),
            can_pass=shooter and len(state.seats) > 1,
            leave_blocked=_refusal(state, engine.Leave(seat)),
            players=[self._player_view(self.players[s.player], s) for s in state.seats],
            spots=spots,
            others=[
                messages.OthersOnSpot(spot=_spot(bet), seats=seats) for bet, seats in others.items()
            ],
            last_roll=last_roll,
        )

    def _player_view(self, player: Player, seat: engine.Seat) -> messages.PlayerView:
        return messages.PlayerView(
            seat=player.seat,
            name=player.name,
            color=player.color,
            bankroll=seat.bankroll,
            away=player.connection is None,
            shooter=self.state.shooter == player.seat,
            pedantic=seat.pedantic,
            net=player.net,
        )

    def _roll_blocked(self, seat: str) -> str | None:
        shooter = self.state.shooter
        if shooter is not None and shooter != seat:
            return f"{self.players[shooter].name} has the dice."
        # Ask the engine, which is pure: try a roll and throw the result away.
        return _refusal(self.state, engine.Roll(seat, 1, 1, self.state.roll_number))


class _StillBetting(Exception):
    pass


def _refusal(state: engine.TableState, action: engine.Action) -> str | None:
    try:
        engine.apply(state, action)
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
        limit: int = 200,
        idle_seconds: float = 12 * 60 * 60,
        clock: Clock = time.monotonic,
    ) -> None:
        self.limit = limit
        self.idle_seconds = idle_seconds
        self.clock = clock
        self._by_code: dict[str, Table] = {}
        self.counts: Counter[str] = Counter()
        self.started = clock()
        # Across everyone: new seats are limited, since each takes memory.
        self.joins = Bucket(burst=40, per_second=0.5, clock=clock)

    def __len__(self) -> int:
        return len(self._by_code)

    def __iter__(self) -> Iterator[Table]:
        return iter(list(self._by_code.values()))

    def sit(
        self, code: str | None, token: str | None, name: str
    ) -> tuple[Table, Player, str | None]:
        """Find or make the table and the seat. Returns a notice for the player, if any."""
        table = self._by_code.get(code) if code else None
        if table is not None:
            table.last_seen = self.clock()
            player = table.by_token(token) if token else None
            if player is not None:
                player.name = name.strip()
                return table, player, None
        if not self.joins.allow():
            raise Busy
        notice = None
        if table is None:
            # A link to a table that is gone starts it again under the same code, so everyone
            # who has the link still meets.
            if token:
                notice = "The server restarted, so the table has started over."
            table = self._create(code or secrets.token_urlsafe(12))
        elif token:
            notice = "Your old seat was given up while you were away."
        return table, table.join(name), notice

    def _create(self, code: str) -> Table:
        self._make_room()
        table = Table(
            code=code,
            id=secrets.token_urlsafe(6),
            clock=self.clock,
            last_seen=self.clock(),
            counts=self.counts,
        )
        self._by_code[code] = table
        self.counts["tables_created"] += 1
        event("table_created", table=table.id, tables=len(self))
        return table

    def stats(self) -> dict[str, int]:
        """Totals only: nothing about any one table or player."""
        return {
            "uptime_seconds": int(self.clock() - self.started),
            "tables_open": len(self),
            "players_connected": sum(
                p.connection is not None for table in self for p in table.players.values()
            ),
            **{name: self.counts[name] for name in COUNTED},
        }

    def tick(self) -> list[Table]:
        """Let every table act on absent players. Returns those that changed."""
        changed = [table for table in self if table.tick()]
        for table in changed:
            if not table.players:
                self._drop(table)
        return changed

    def _drop(self, table: Table) -> None:
        if self._by_code.pop(table.code, None):
            event("table_closed", table=table.id)

    def _make_room(self) -> None:
        """Drop tables nobody has used for a long time, and if full, the longest unused."""
        now = self.clock()
        unused = sorted((t for t in self if t.empty_handed), key=lambda t: t.last_seen)
        for table in unused:
            if now - table.last_seen < self.idle_seconds and len(self) < self.limit:
                break
            self._drop(table)
        if len(self) >= self.limit:
            raise Busy
