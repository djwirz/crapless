"""The data the engine takes and returns. All of it is immutable."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from crapless.engine.settings import Settings

POINT_NUMBERS: tuple[int, ...] = (2, 3, 4, 5, 6, 8, 9, 10, 11, 12)
"""Every total but 7 (spec §4)."""


class BetKind(StrEnum):
    PASS = "pass"
    PASS_ODDS = "pass_odds"
    COME = "come"
    COME_ODDS = "come_odds"
    PLACE = "place"


@dataclass(frozen=True)
class Bet:
    """Which spot a player's chips are on. A player has at most one amount on each.

    `number` is None for Pass and Pass odds (their number is the table's point) and for a Come
    bet that has not yet moved to a number.
    """

    kind: BetKind
    number: int | None = None

    def __post_init__(self) -> None:
        match self.kind:
            case BetKind.PASS | BetKind.PASS_ODDS:
                valid = self.number is None
            case BetKind.COME:
                valid = self.number is None or self.number in POINT_NUMBERS
            case BetKind.COME_ODDS | BetKind.PLACE:
                valid = self.number in POINT_NUMBERS
        if not valid:
            raise ValueError(f"{self.kind} cannot be on {self.number}")


PASS = Bet(BetKind.PASS)
PASS_ODDS = Bet(BetKind.PASS_ODDS)
COME = Bet(BetKind.COME)


def come(number: int) -> Bet:
    return Bet(BetKind.COME, number)


def come_odds(number: int) -> Bet:
    return Bet(BetKind.COME_ODDS, number)


def place(number: int) -> Bet:
    return Bet(BetKind.PLACE, number)


@dataclass(frozen=True)
class Seat:
    player: str
    """An opaque id chosen by the caller. Display names are not the engine's business."""
    bankroll: int


@dataclass(frozen=True)
class TableState:
    settings: Settings
    seats: tuple[Seat, ...] = ()
    """In seat order. The player "to the left" is the next one, wrapping round."""
    shooter: str | None = None
    point: int | None = None
    """None means the next roll is a come-out roll."""
    roll_number: int = 0
    """How many rolls have been settled. Actions quote it so late ones are rejected."""
    bets: Mapping[tuple[str, Bet], int] = field(default_factory=lambda: MappingProxyType({}))
    working: frozenset[tuple[str, int]] = frozenset()
    """(player, number) of Place bets turned on for the come-out."""

    def seat(self, player: str) -> Seat | None:
        return next((s for s in self.seats if s.player == player), None)

    def bet(self, player: str, bet: Bet) -> int:
        return self.bets.get((player, bet), 0)


class Outcome(StrEnum):
    WIN = "win"
    LOSE = "lose"
    RETURNED = "returned"
    """Odds that were off when their bet was decided: the chips go back, nothing is won."""
    MOVED = "moved"
    """A Come bet moving to its number. No chips change hands."""


@dataclass(frozen=True)
class Settlement:
    """What one roll did to one bet."""

    player: str
    bet: Bet
    outcome: Outcome
    amount: int
    """The bet as it stood when the dice landed."""
    paid: int = 0
    """Winnings the house adds to the bankroll."""
    returned: int = 0
    """Chips moved from the table back to the bankroll."""

    @property
    def collected(self) -> int:
        """Chips the house takes off the table."""
        return self.amount if self.outcome is Outcome.LOSE else 0


@dataclass(frozen=True)
class Result:
    state: TableState
    settlements: tuple[Settlement, ...] = ()


class Rejection(StrEnum):
    NOT_SEATED = "not_seated"
    ALREADY_SEATED = "already_seated"
    STALE_ROLL = "stale_roll"
    NOT_SHOOTER = "not_shooter"
    NO_ONE_TO_PASS_TO = "no_one_to_pass_to"
    SHOOTER_NEEDS_PASS_BET = "shooter_needs_pass_bet"
    BAD_DICE = "bad_dice"
    BAD_AMOUNT = "bad_amount"
    NOT_NOW = "not_now"
    LOCKED = "locked"
    NO_FLAT_BET = "no_flat_bet"
    UNEVEN_AMOUNT = "uneven_amount"
    BELOW_MINIMUM = "below_minimum"
    ABOVE_MAXIMUM = "above_maximum"
    NOT_ENOUGH_CHIPS = "not_enough_chips"


class Rejected(Exception):
    """An action the rules do not allow. The state is unchanged; `reason` can be shown."""

    def __init__(self, code: Rejection, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason
