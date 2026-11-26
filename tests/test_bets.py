"""Every bet against every total, on and off the come-out (spec §8).

The expected pays are written out from the table in spec §4, not read from the engine.
"""

from fractions import Fraction

import pytest
from helpers import (
    OTHER,
    SHOOTER,
    bankroll,
    bet,
    come_out,
    outcome,
    roll,
    settled,
    table,
    with_point,
)

from crapless.engine import (
    COME,
    DEFAULT_PLACE_PAYS,
    PASS,
    PASS_ODDS,
    POINT_NUMBERS,
    Bet,
    Outcome,
    Refill,
    Rejected,
    Rejection,
    SetBet,
    SetPedantic,
    Settings,
    SetWorking,
    TableState,
    apply,
    come,
    come_odds,
    place,
    spot_options,
)

TOTALS = range(2, 13)
WIN, LOSE, MOVED, RETURNED = Outcome.WIN, Outcome.LOSE, Outcome.MOVED, Outcome.RETURNED

# number: (stake, winnings)
ODDS = {
    2: (10, 60),
    3: (10, 30),
    4: (10, 20),
    5: (10, 15),
    6: (10, 12),
    8: (10, 12),
    9: (10, 15),
    10: (10, 20),
    11: (10, 30),
    12: (10, 60),
}
PLACE = {
    2: (20, 110),
    3: (20, 55),
    4: (20, 36),
    5: (20, 28),
    6: (24, 28),
    8: (24, 28),
    9: (20, 28),
    10: (20, 36),
    11: (20, 55),
    12: (20, 110),
}


def another_point(number: int) -> int:
    return 8 if number == 6 else 6


@pytest.mark.parametrize("total", TOTALS)
def test_pass_on_the_come_out(total: int) -> None:
    state = bet(table(), PASS, 10)
    result = come_out(state, total)

    if total == 7:
        assert outcome(result, PASS) is WIN
        assert bankroll(result.state) == 1010
        assert result.state.bet(OTHER, PASS) == 0
        assert result.state.point is None
    else:
        assert outcome(result, PASS) is None
        assert result.state.bet(OTHER, PASS) == 10
        assert result.state.point == total


@pytest.mark.parametrize("point", POINT_NUMBERS)
@pytest.mark.parametrize("total", TOTALS)
def test_pass_with_a_point(point: int, total: int) -> None:
    state = with_point(bet(table(), PASS, 10), point)
    result = roll(state, total)

    expected = WIN if total == point else LOSE if total == 7 else None
    assert outcome(result, PASS) is expected
    assert bankroll(result.state) == (1010 if expected is WIN else 990)
    assert result.state.bet(OTHER, PASS) == (10 if expected is None else 0)
    assert result.state.point == (None if expected else point)


@pytest.mark.parametrize("point", POINT_NUMBERS)
@pytest.mark.parametrize("total", TOTALS)
def test_pass_odds(point: int, total: int) -> None:
    stake, winnings = ODDS[point]
    state = with_point(bet(table(), PASS, 10), point)
    state = bet(state, PASS_ODDS, stake)
    result = roll(state, total)

    expected = WIN if total == point else LOSE if total == 7 else None
    assert outcome(result, PASS_ODDS) is expected
    flat = {WIN: 20, LOSE: 0, None: 0}[expected]
    odds = {WIN: stake + winnings, LOSE: 0, None: 0}[expected]
    assert bankroll(result.state) == 1000 - 10 - stake + flat + odds


@pytest.mark.parametrize("point", [4, 6, 12])
@pytest.mark.parametrize("total", TOTALS)
def test_new_come_bet(point: int, total: int) -> None:
    state = bet(with_point(table(), point), COME, 10)
    result = roll(state, total)

    if total == 7:
        assert outcome(result, COME) is WIN
        assert bankroll(result.state) == 1010
    else:
        assert outcome(result, COME) is MOVED
        assert result.state.bet(OTHER, come(total)) == 10
        assert bankroll(result.state) == 990
    assert result.state.bet(OTHER, COME) == 0


def come_bet_on(number: int, *, odds: int = 0, settings: Settings | None = None) -> TableState:
    """A table with a Come bet on `number` while another point is on."""
    state = with_point(table(settings=settings), another_point(number))
    state = roll(bet(state, COME, 10), number).state
    if odds:
        state = bet(state, come_odds(number), odds)
    return state


@pytest.mark.parametrize("number", POINT_NUMBERS)
@pytest.mark.parametrize("total", TOTALS)
def test_come_bet_and_odds_with_a_point_on(number: int, total: int) -> None:
    stake, winnings = ODDS[number]
    result = roll(come_bet_on(number, odds=stake), total)

    expected = WIN if total == number else LOSE if total == 7 else None
    assert outcome(result, come(number)) is expected
    assert outcome(result, come_odds(number)) is expected
    back = 20 + stake + winnings if expected is WIN else 0
    assert bankroll(result.state) == 1000 - 10 - stake + back


@pytest.mark.parametrize("working", [False, True])
@pytest.mark.parametrize("number", POINT_NUMBERS)
@pytest.mark.parametrize("total", TOTALS)
def test_come_bet_and_odds_on_the_come_out(number: int, total: int, working: bool) -> None:
    stake, winnings = ODDS[number]
    settings = Settings(come_odds_on_come_out=working)
    state = come_bet_on(number, odds=stake, settings=settings)
    point = state.point
    assert point is not None
    state = roll(state, point).state  # the point is made, so the next roll is a come-out
    assert state.point is None
    before = bankroll(state)

    result = come_out(state, total)

    if total not in (number, 7):
        assert outcome(result, come(number)) is None
        assert outcome(result, come_odds(number)) is None
        assert result.state.bet(OTHER, come_odds(number)) == stake
        return
    flat = WIN if total == number else LOSE
    assert outcome(result, come(number)) is flat
    assert outcome(result, come_odds(number)) is (flat if working else RETURNED)
    back = 20 if flat is WIN else 0
    if not working:
        back += stake
    elif flat is WIN:
        back += stake + winnings
    assert bankroll(result.state) == before + back
    assert result.state.bet(OTHER, come_odds(number)) == 0


def test_a_come_bet_moving_onto_an_occupied_number_pays_the_old_one() -> None:
    state = bet(come_bet_on(8), come_odds(8), 10)
    state = bet(state, COME, 15)
    result = roll(state, 8)

    assert outcome(result, come(8)) is WIN
    assert outcome(result, come_odds(8)) is WIN
    assert outcome(result, COME) is MOVED
    assert result.state.bet(OTHER, come(8)) == 15
    assert result.state.bet(OTHER, come_odds(8)) == 0


@pytest.mark.parametrize("number", POINT_NUMBERS)
@pytest.mark.parametrize("total", TOTALS)
def test_place_with_a_point(number: int, total: int) -> None:
    stake, winnings = PLACE[number]
    state = bet(with_point(table(), another_point(number)), place(number), stake)
    result = roll(state, total)

    expected = WIN if total == number else LOSE if total == 7 else None
    assert outcome(result, place(number)) is expected
    assert bankroll(result.state) == 1000 - stake + (winnings if expected is WIN else 0)
    # A winning Place bet stays up.
    assert result.state.bet(OTHER, place(number)) == (0 if expected is LOSE else stake)


@pytest.mark.parametrize("turned_on", [False, True])
@pytest.mark.parametrize("number", POINT_NUMBERS)
@pytest.mark.parametrize("total", TOTALS)
def test_place_on_the_come_out(number: int, total: int, turned_on: bool) -> None:
    stake, winnings = PLACE[number]
    state = bet(table(), place(number), stake)
    if turned_on:
        state = apply(state, SetWorking(OTHER, number, True, state.roll_number)).state
    result = come_out(state, total)

    expected = None
    if turned_on:
        expected = WIN if total == number else LOSE if total == 7 else None
    assert outcome(result, place(number)) is expected
    assert bankroll(result.state) == 1000 - stake + (winnings if expected is WIN else 0)
    assert result.state.bet(OTHER, place(number)) == (0 if expected is LOSE else stake)


@pytest.mark.parametrize("number", POINT_NUMBERS)
def test_alternative_place_pays_are_a_setting(number: int) -> None:
    pays = {**DEFAULT_PLACE_PAYS, number: Fraction(25, 5)}
    state = table(settings=Settings(place_pays=pays))
    state = bet(with_point(state, another_point(number)), place(number), 7)
    result = roll(state, number)

    settlement = settled(result, place(number))
    assert settlement is not None and settlement.paid == 35


def test_a_removed_place_bet_comes_back_and_is_switched_off() -> None:
    state = bet(table(), place(6), 12)
    state = apply(state, SetWorking(OTHER, 6, True, state.roll_number)).state
    state = apply(state, SetBet(OTHER, place(6), 0, state.roll_number)).state

    assert bankroll(state) == 1000
    assert not state.working


def test_a_lost_place_bet_is_switched_off() -> None:
    state = bet(table(), place(6), 12)
    state = apply(state, SetWorking(OTHER, 6, True, state.roll_number)).state

    assert not come_out(state, 7).state.working


def pedantic(state: TableState, on: bool = True, player: str = OTHER) -> TableState:
    return apply(state, SetPedantic(player, on)).state


def refused(state: TableState, what: Bet, amount: int, player: str = OTHER) -> Rejection:
    with pytest.raises(Rejected) as rejected:
        bet(state, what, amount, player)
    return rejected.value.code


# number: smallest Place bet, as usual and in pedantic mode
SMALLEST = {
    2: (6, 4),
    3: (8, 4),
    4: (5, 5),
    5: (5, 5),
    6: (6, 6),
    8: (6, 6),
    9: (5, 5),
    10: (5, 5),
    11: (8, 4),
    12: (6, 4),
}


@pytest.mark.parametrize("number", POINT_NUMBERS)
def test_pedantic_mode_lowers_the_smallest_place_bet(number: int) -> None:
    usual, low = SMALLEST[number]
    for state, least in ((table(), usual), (pedantic(table()), low)):
        assert spot_options(state, OTHER, place(number)).low == least
        assert bet(state, place(number), least).bet(OTHER, place(number)) == least


@pytest.mark.parametrize("number", [2, 3, 11, 12])
def test_pedantic_bets_still_go_in_even_multiples(number: int) -> None:
    state = pedantic(table())
    step = DEFAULT_PLACE_PAYS[number].denominator
    assert refused(state, place(number), 5) is Rejection.UNEVEN_AMOUNT
    assert bet(state, place(number), 4 + step).bet(OTHER, place(number)) == 4 + step


def test_pedantic_mode_leaves_pass_come_and_other_players_alone() -> None:
    state = pedantic(table())
    assert spot_options(state, SHOOTER, place(3)).low == 8
    assert refused(state, place(3), 4, SHOOTER) is Rejection.BELOW_MINIMUM
    assert spot_options(state, OTHER, PASS).low == 5
    assert refused(state, PASS, 4) is Rejection.BELOW_MINIMUM
    assert refused(with_point(state, 6), COME, 4) is Rejection.BELOW_MINIMUM


def test_pedantic_mode_lasts_through_bets_rolls_and_refills() -> None:
    state = bet(pedantic(table()), place(3), 4)
    state = apply(state, SetWorking(OTHER, 3, True, state.roll_number)).state
    state = come_out(state, 3).state
    state = apply(state, Refill(OTHER)).state
    seat = state.seat(OTHER)
    assert seat is not None and seat.pedantic


def test_a_small_bet_stays_and_pays_after_pedantic_mode_is_off() -> None:
    state = pedantic(bet(pedantic(table()), place(3), 4), on=False)
    assert state.bet(OTHER, place(3)) == 4

    options = spot_options(state, OTHER, place(3))
    assert (options.amount, options.low, options.removable) == (4, 8, True)
    assert bet(state, place(3), 4) == state  # saying the same again changes nothing
    assert bet(state, place(3), 8).bet(OTHER, place(3)) == 8
    assert bet(state, place(3), 0).bet(OTHER, place(3)) == 0

    result = roll(with_point(state, 6), 3)
    settlement = settled(result, place(3))
    assert settlement is not None and settlement.paid == 11
    assert result.state.bet(OTHER, place(3)) == 4


def test_a_bigger_bet_cannot_be_lowered_below_the_usual_minimum_once_off() -> None:
    state = pedantic(bet(pedantic(table()), place(11), 12), on=False)
    assert refused(state, place(11), 4) is Rejection.BELOW_MINIMUM


def test_pedantic_mode_needs_a_seat_and_the_minimum_must_make_sense() -> None:
    with pytest.raises(Rejected):
        apply(table(), SetPedantic("nobody", True))
    for wrong in (0, 6):
        with pytest.raises(ValueError):
            Settings(pedantic_place_min=wrong)
