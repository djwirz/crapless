"""What a roll does to each bet on the table (spec §4)."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import assert_never

from crapless.engine.model import Bet, BetKind, Outcome, Settlement, TableState, come
from crapless.engine.settings import TRUE_ODDS


def settle_roll(
    state: TableState, total: int
) -> tuple[tuple[Settlement, ...], Mapping[tuple[str, Bet], int]]:
    """Decide every bet once, against the table as it stood before the roll.

    Returns the settlements and the bets left on the table.
    """
    settlements: list[Settlement] = []
    remaining = dict(state.bets)
    moves: list[tuple[str, int, int]] = []

    for (player, bet), amount in state.bets.items():
        settlement = _decide(state, total, player, bet, amount)
        if settlement is None:
            continue
        settlements.append(settlement)
        if settlement.outcome is Outcome.MOVED:
            del remaining[player, bet]
            moves.append((player, total, amount))
        elif settlement.outcome is Outcome.LOSE or settlement.returned:
            del remaining[player, bet]

    # Moves land after every bet is decided: a Come bet already on this number has just won
    # and left, so the new one never merges with it.
    for player, number, amount in moves:
        remaining[player, come(number)] = amount

    return tuple(settlements), MappingProxyType(remaining)


def _decide(state: TableState, total: int, player: str, bet: Bet, amount: int) -> Settlement | None:
    """The settlement of one bet, or None if this roll leaves it alone."""
    come_out = state.point is None

    def lose() -> Settlement:
        return Settlement(player, bet, Outcome.LOSE, amount)

    def give_back() -> Settlement:
        return Settlement(player, bet, Outcome.RETURNED, amount, returned=amount)

    def win(numerator: int, denominator: int, *, stays_up: bool = False) -> Settlement:
        paid, remainder = divmod(amount * numerator, denominator)
        # Amounts are checked when bet, so a remainder would be a bug, never something to round.
        assert not remainder, f"{bet} of {amount} does not pay out evenly"
        returned = 0 if stays_up else amount
        return Settlement(player, bet, Outcome.WIN, amount, paid=paid, returned=returned)

    match bet.kind:
        case BetKind.PASS:
            if come_out:
                return win(1, 1) if total == 7 else None
            if total == state.point:
                return win(1, 1)
            return lose() if total == 7 else None

        case BetKind.PASS_ODDS:
            assert state.point is not None
            if total == state.point:
                return win(*TRUE_ODDS[state.point].as_integer_ratio())
            return lose() if total == 7 else None

        case BetKind.COME:
            if bet.number is None:
                if total == 7:
                    return win(1, 1)
                return Settlement(player, bet, Outcome.MOVED, amount)
            if total == bet.number:
                return win(1, 1)
            return lose() if total == 7 else None

        case BetKind.COME_ODDS:
            assert bet.number is not None
            if total not in (bet.number, 7):
                return None
            if come_out and not state.settings.come_odds_on_come_out:
                return give_back()
            if total == 7:
                return lose()
            return win(*TRUE_ODDS[bet.number].as_integer_ratio())

        case BetKind.PLACE:
            assert bet.number is not None
            if come_out and (player, bet.number) not in state.working:
                return None
            if total == bet.number:
                return win(*state.settings.place_pays[bet.number].as_integer_ratio(), stays_up=True)
            return lose() if total == 7 else None

        case _:
            assert_never(bet.kind)
