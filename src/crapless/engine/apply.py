"""Apply one action to a table: validate it, then return the new state."""

from collections.abc import Mapping
from dataclasses import replace
from types import MappingProxyType
from typing import assert_never

from crapless.engine.actions import (
    Action,
    Join,
    Leave,
    PassDice,
    Refill,
    Roll,
    SetBet,
    SetWorking,
)
from crapless.engine.model import (
    PASS,
    Bet,
    BetKind,
    Rejected,
    Rejection,
    Result,
    Seat,
    TableState,
    place,
)
from crapless.engine.settings import TRUE_ODDS, Settings
from crapless.engine.settle import settle_roll
from crapless.engine.spots import check_amount, check_open, is_locked


def new_table(settings: Settings | None = None) -> TableState:
    return TableState(settings=settings or Settings())


def apply(state: TableState, action: Action) -> Result:
    """Return the new state and any settlements, or raise `Rejected` and change nothing."""
    match action:
        case Join():
            return Result(_join(state, action))
        case Leave():
            return Result(_leave(state, action))
        case Refill():
            return Result(_refill(state, action))
        case SetBet():
            return Result(_set_bet(state, action))
        case SetWorking():
            return Result(_set_working(state, action))
        case PassDice():
            return Result(_pass_dice(state, action))
        case Roll():
            return _roll(state, action)
        case _:
            assert_never(action)


def _seated(state: TableState, player: str) -> Seat:
    seat = state.seat(player)
    if seat is None:
        raise Rejected(Rejection.NOT_SEATED, "You are not at this table.")
    return seat


def _current(state: TableState, roll_number: int) -> None:
    if roll_number != state.roll_number:
        raise Rejected(Rejection.STALE_ROLL, "The dice have already been rolled.")


def _with_bankroll(seats: tuple[Seat, ...], player: str, bankroll: int) -> tuple[Seat, ...]:
    return tuple(Seat(player, bankroll) if s.player == player else s for s in seats)


def left_of(seats: tuple[Seat, ...], player: str) -> str:
    """The next player in seat order, wrapping round."""
    index = next(i for i, s in enumerate(seats) if s.player == player)
    return seats[(index + 1) % len(seats)].player


def _join(state: TableState, action: Join) -> TableState:
    if state.seat(action.player) is not None:
        raise Rejected(Rejection.ALREADY_SEATED, "You already have a seat.")
    seat = Seat(action.player, state.settings.starting_bankroll)
    return replace(state, seats=(*state.seats, seat), shooter=state.shooter or action.player)


def _leave(state: TableState, action: Leave) -> TableState:
    _seated(state, action.player)
    mine = [bet for player, bet in state.bets if player == action.player]
    if any(is_locked(state, bet) for bet in mine):
        raise Rejected(Rejection.LOCKED, "Your Pass or Come bet has to be decided first.")

    # Bets that can be removed leave with the player, as their bankroll does.
    seats = tuple(s for s in state.seats if s.player != action.player)
    shooter = state.shooter
    if shooter == action.player:
        shooter = left_of(state.seats, action.player) if seats else None
    return replace(
        state,
        seats=seats,
        shooter=shooter,
        point=state.point if seats else None,
        bets=MappingProxyType({k: v for k, v in state.bets.items() if k[0] != action.player}),
        working=frozenset(w for w in state.working if w[0] != action.player),
    )


def _refill(state: TableState, action: Refill) -> TableState:
    seat = _seated(state, action.player)
    bankroll = max(seat.bankroll, state.settings.starting_bankroll)
    return replace(state, seats=_with_bankroll(state.seats, action.player, bankroll))


def _set_bet(state: TableState, action: SetBet) -> TableState:
    seat = _seated(state, action.player)
    _current(state, action.roll_number)
    player, bet, amount = action.player, action.bet, action.amount
    if type(amount) is not int or amount < 0:
        raise Rejected(Rejection.BAD_AMOUNT, "A bet is a whole number of chips.")

    current = state.bet(player, bet)
    if amount == current:
        return state
    if current and is_locked(state, bet):
        raise Rejected(Rejection.LOCKED, "That bet cannot be changed once it has a point.")
    if amount > 0:
        check_open(state, player, bet)
        check_amount(state, player, bet, amount)
    if amount - current > seat.bankroll:
        raise Rejected(Rejection.NOT_ENOUGH_CHIPS, "You do not have that many chips.")

    bets = dict(state.bets)
    working = state.working
    if amount:
        bets[player, bet] = amount
    else:
        del bets[player, bet]
        if bet.kind is BetKind.PLACE:
            working = working - {(player, _number(bet))}
    return replace(
        state,
        seats=_with_bankroll(state.seats, player, seat.bankroll - (amount - current)),
        bets=MappingProxyType(bets),
        working=working,
    )


def _number(bet: Bet) -> int:
    assert bet.number is not None
    return bet.number


def _set_working(state: TableState, action: SetWorking) -> TableState:
    _seated(state, action.player)
    _current(state, action.roll_number)
    if action.number not in TRUE_ODDS or not state.bet(action.player, place(action.number)):
        raise Rejected(Rejection.NO_FLAT_BET, "You have no Place bet on that number.")
    entry = {(action.player, action.number)}
    working = state.working | entry if action.working else state.working - entry
    return replace(state, working=working)


def _pass_dice(state: TableState, action: PassDice) -> TableState:
    _seated(state, action.player)
    _current(state, action.roll_number)
    if state.shooter != action.player:
        raise Rejected(Rejection.NOT_SHOOTER, "You do not have the dice.")
    if len(state.seats) < 2:
        raise Rejected(Rejection.NO_ONE_TO_PASS_TO, "There is no one to pass the dice to.")
    return replace(state, shooter=left_of(state.seats, action.player))


def _roll(state: TableState, action: Roll) -> Result:
    _seated(state, action.player)
    _current(state, action.roll_number)
    if state.shooter != action.player:
        raise Rejected(Rejection.NOT_SHOOTER, "Only the shooter rolls.")
    if any(type(die) is not int or not 1 <= die <= 6 for die in (action.die1, action.die2)):
        raise Rejected(Rejection.BAD_DICE, "Each die shows 1 to 6.")
    if state.point is None and not state.bet(action.player, PASS):
        raise Rejected(Rejection.SHOOTER_NEEDS_PASS_BET, "Make a Pass bet to come out.")

    total = action.die1 + action.die2
    settlements, bets = settle_roll(state, total)

    returns: dict[str, int] = {}
    for s in settlements:
        returns[s.player] = returns.get(s.player, 0) + s.paid + s.returned
    seats = tuple(Seat(s.player, s.bankroll + returns.get(s.player, 0)) for s in state.seats)

    seven_out = state.point is not None and total == 7
    if state.point is None:
        point = None if total == 7 else total
    else:
        point = None if total in (7, state.point) else state.point

    return Result(
        replace(
            state,
            seats=seats,
            shooter=left_of(state.seats, action.player) if seven_out else state.shooter,
            point=point,
            roll_number=state.roll_number + 1,
            bets=bets,
            working=_still_up(state.working, bets),
        ),
        settlements,
    )


def _still_up(
    working: frozenset[tuple[str, int]], bets: Mapping[tuple[str, Bet], int]
) -> frozenset[tuple[str, int]]:
    return frozenset((player, n) for player, n in working if (player, place(n)) in bets)
