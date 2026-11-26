"""What a caller can ask the engine to do (ADR 0007).

Actions that depend on the state of the hand quote `roll_number`, so one that arrives after
the roll it was meant for is rejected.
"""

from dataclasses import dataclass

from crapless.engine.model import Bet


@dataclass(frozen=True)
class Join:
    player: str


@dataclass(frozen=True)
class Leave:
    player: str


@dataclass(frozen=True)
class Refill:
    """Top the bankroll back up to the starting bankroll. Does nothing if it is there already."""

    player: str


@dataclass(frozen=True)
class SetPedantic:
    """Switch pedantic mode on or off. A value, not a flip, so a repeat changes nothing."""

    player: str
    on: bool


@dataclass(frozen=True)
class SetBet:
    """Make the chips on one spot total `amount`. 0 takes the bet down.

    A total, not an addition, so a repeated message changes nothing.
    """

    player: str
    bet: Bet
    amount: int
    roll_number: int


@dataclass(frozen=True)
class SetWorking:
    """Turn a Place bet on (or back off) for come-out rolls."""

    player: str
    number: int
    working: bool
    roll_number: int


@dataclass(frozen=True)
class PassDice:
    player: str
    roll_number: int


@dataclass(frozen=True)
class Roll:
    player: str
    die1: int
    die2: int
    roll_number: int


Action = Join | Leave | Refill | SetPedantic | SetBet | SetWorking | PassDice | Roll
