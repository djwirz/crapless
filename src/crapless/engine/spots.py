"""What may be put on a spot. `apply` validates with this, and callers can ask it up front."""

from dataclasses import dataclass
from typing import assert_never

from crapless.engine.model import (
    PASS,
    Bet,
    BetKind,
    Rejected,
    Rejection,
    TableState,
    come,
)
from crapless.engine.settings import TRUE_ODDS


@dataclass(frozen=True)
class SpotOptions:
    amount: int
    """The chips there now."""
    step: int
    """A bet here must be a multiple of this to pay out evenly."""
    low: int | None
    """The smallest total that can be set now. None if the spot cannot be bet."""
    high: int | None
    """The largest, allowing for the table limit and the player's bankroll."""
    removable: bool
    """Whether the chips there can be taken down."""


def spot_options(state: TableState, player: str, bet: Bet) -> SpotOptions:
    seat = state.seat(player)
    if seat is None:
        raise Rejected(Rejection.NOT_SEATED, "You are not at this table.")
    current = state.bet(player, bet)
    locked = bool(current) and is_locked(state, bet)
    step = step_of(state, bet)
    low: int | None = None
    high: int | None = None
    if not locked and is_open(state, player, bet):
        least, most = table_bounds(state, player, bet)
        first = -(-least // step) * step
        last = min(most, current + seat.bankroll) // step * step
        if first <= last:
            low, high = first, last
    return SpotOptions(current, step, low, high, removable=bool(current) and not locked)


def is_locked(state: TableState, bet: Bet) -> bool:
    """Pass and Come bets cannot be removed or reduced once they have a point (spec §4)."""
    if bet.kind is BetKind.PASS:
        return state.point is not None
    return bet.kind is BetKind.COME and bet.number is not None


def _number(bet: Bet) -> int:
    assert bet.number is not None
    return bet.number


def _flat_for(state: TableState, player: str, odds: Bet) -> int:
    flat = PASS if odds.kind is BetKind.PASS_ODDS else come(_number(odds))
    return state.bet(player, flat)


def step_of(state: TableState, bet: Bet) -> int:
    match bet.kind:
        case BetKind.PASS_ODDS:
            return TRUE_ODDS[state.point].denominator if state.point is not None else 1
        case BetKind.COME_ODDS:
            return TRUE_ODDS[_number(bet)].denominator
        case BetKind.PLACE:
            return state.settings.place_pays[_number(bet)].denominator
        case BetKind.PASS | BetKind.COME:
            return 1
        case _:
            assert_never(bet.kind)


def table_bounds(state: TableState, player: str, bet: Bet) -> tuple[int, int]:
    """The table's own limits for a spot that is open, before multiples and bankroll."""
    settings = state.settings
    if bet.kind in (BetKind.PASS_ODDS, BetKind.COME_ODDS):
        return 1, settings.odds_multiple * _flat_for(state, player, bet)
    if bet.kind is BetKind.PLACE:
        return smallest_bet(state, player), settings.max_bet
    return settings.min_bet, settings.max_bet


def smallest_bet(state: TableState, player: str) -> int:
    """The least this player may put anywhere, before multiples: it is lower in pedantic mode,
    and only for Place bets."""
    seat = state.seat(player)
    if seat is not None and seat.pedantic:
        return state.settings.pedantic_place_min
    return state.settings.min_bet


def is_open(state: TableState, player: str, bet: Bet) -> bool:
    try:
        check_open(state, player, bet)
    except Rejected:
        return False
    return True


def check_open(state: TableState, player: str, bet: Bet) -> None:
    """Whether chips may be put on this spot at this point in the hand."""
    match bet.kind:
        case BetKind.PASS:
            if state.point is not None:
                raise Rejected(Rejection.NOT_NOW, "Pass bets are made on the come-out.")
        case BetKind.COME:
            if bet.number is not None:
                raise Rejected(Rejection.NOT_NOW, "A Come bet moves to a number by being rolled.")
            if state.point is None:
                raise Rejected(Rejection.NOT_NOW, "Come bets wait until there is a point.")
        case BetKind.PASS_ODDS:
            if state.point is None:
                raise Rejected(Rejection.NOT_NOW, "Pass odds wait until there is a point.")
            if not _flat_for(state, player, bet):
                raise Rejected(Rejection.NO_FLAT_BET, "Odds need a Pass bet behind them.")
        case BetKind.COME_ODDS:
            if not _flat_for(state, player, bet):
                raise Rejected(Rejection.NO_FLAT_BET, "Odds need a Come bet on that number.")
        case BetKind.PLACE:
            pass
        case _:
            assert_never(bet.kind)


def check_amount(state: TableState, player: str, bet: Bet, amount: int) -> None:
    step = step_of(state, bet)
    # Never round (ADR 0006): a bet that cannot be paid exactly is refused.
    if amount % step:
        raise Rejected(Rejection.UNEVEN_AMOUNT, f"This bet goes in multiples of {step}.")
    least, most = table_bounds(state, player, bet)
    if bet.kind in (BetKind.PASS_ODDS, BetKind.COME_ODDS):
        if amount > most:
            raise Rejected(Rejection.ABOVE_MAXIMUM, f"The most odds here is {most}.")
    elif amount < least:
        raise Rejected(Rejection.BELOW_MINIMUM, f"The minimum bet is {least}.")
    elif amount > most:
        raise Rejected(Rejection.ABOVE_MAXIMUM, f"The maximum bet is {most}.")
