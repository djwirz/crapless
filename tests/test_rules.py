"""What the table refuses, and how the dice move."""

from fractions import Fraction

import pytest
from helpers import OTHER, SHOOTER, bankroll, bet, come_out, dice, roll, table, with_point

from crapless.engine import (
    COME,
    DEFAULT_PLACE_PAYS,
    PASS,
    PASS_ODDS,
    Action,
    Bet,
    BetKind,
    Join,
    Leave,
    PassDice,
    Refill,
    Rejected,
    Rejection,
    Roll,
    SetBet,
    Settings,
    SetWorking,
    TableState,
    apply,
    come,
    come_odds,
    new_table,
    place,
)


def refused(state: TableState, action: Action) -> Rejection:
    with pytest.raises(Rejected) as error:
        apply(state, action)
    assert error.value.reason
    return error.value.code


def try_bet(state: TableState, what: Bet, amount: int, player: str = OTHER) -> Rejection:
    return refused(state, SetBet(player, what, amount, state.roll_number))


@pytest.mark.parametrize(
    ("number", "unit", "lowest", "highest"),
    [(2, 2, 6, 500), (3, 4, 8, 500), (4, 5, 5, 500), (5, 5, 5, 500), (6, 6, 6, 498)],
)
def test_place_limits_round_to_the_next_even_multiple(
    number: int, unit: int, lowest: int, highest: int
) -> None:
    state = table()
    bet(state, place(number), lowest)
    bet(state, place(number), highest)

    assert try_bet(state, place(number), lowest + 1) is Rejection.UNEVEN_AMOUNT
    below = (lowest - 1) // unit * unit
    if below:  # otherwise the next multiple down is 0, which takes the bet down
        assert try_bet(state, place(number), below) is Rejection.BELOW_MINIMUM
    assert try_bet(state, place(number), highest + unit) is Rejection.ABOVE_MAXIMUM


def test_flat_limits() -> None:
    state = table()
    bet(state, PASS, 5)
    bet(state, PASS, 500)
    assert try_bet(state, PASS, 4) is Rejection.BELOW_MINIMUM
    assert try_bet(state, PASS, 501) is Rejection.ABOVE_MAXIMUM


@pytest.mark.parametrize(("number", "unit"), [(2, 1), (3, 1), (4, 1), (5, 2), (6, 5)])
def test_odds_are_three_times_the_flat_bet_in_even_multiples(number: int, unit: int) -> None:
    state = with_point(bet(table(), PASS, 10), number)
    bet(state, PASS_ODDS, unit)
    bet(state, PASS_ODDS, 30)

    assert try_bet(state, PASS_ODDS, 30 + unit) is Rejection.ABOVE_MAXIMUM
    if unit > 1:
        assert try_bet(state, PASS_ODDS, unit + 1) is Rejection.UNEVEN_AMOUNT


@pytest.mark.parametrize("amount", [-5, 5.0, True])
def test_chips_are_whole_and_not_negative(amount: object) -> None:
    assert try_bet(table(), PASS, amount) is Rejection.BAD_AMOUNT  # type: ignore[arg-type]


def test_cannot_bet_more_than_the_bankroll() -> None:
    state = table(settings=Settings(starting_bankroll=20))
    assert try_bet(state, PASS, 25) is Rejection.NOT_ENOUGH_CHIPS
    state = bet(state, PASS, 15)
    # Only the increase has to be covered.
    assert bankroll(bet(state, PASS, 20)) == 0


def test_setting_the_same_total_again_changes_nothing() -> None:
    state = bet(table(), PASS, 10)
    assert bet(state, PASS, 10) == state


def test_removable_bets_can_be_reduced() -> None:
    state = bet(table(), PASS, 20)
    assert bankroll(bet(state, PASS, 5)) == 995
    assert bankroll(bet(state, PASS, 0)) == 1000

    state = bet(with_point(state, 6), PASS_ODDS, 30)
    assert bankroll(bet(state, PASS_ODDS, 0)) == 980

    state = bet(state, COME, 10)
    assert bankroll(bet(state, COME, 0)) == bankroll(state) + 10


@pytest.mark.parametrize("amount", [0, 5, 50])
def test_pass_and_come_bets_are_locked_once_they_have_a_point(amount: int) -> None:
    state = bet(table(), PASS, 10)
    state = roll(bet(with_point(state, 6), COME, 10), 9).state

    assert try_bet(state, PASS, amount) is Rejection.LOCKED
    assert try_bet(state, come(9), amount) is Rejection.LOCKED


def test_when_each_bet_may_be_made() -> None:
    off = table()
    assert try_bet(off, COME, 10) is Rejection.NOT_NOW
    assert try_bet(off, PASS_ODDS, 10) is Rejection.NOT_NOW
    assert try_bet(off, come(6), 10) is Rejection.NOT_NOW
    assert try_bet(off, come_odds(6), 10) is Rejection.NO_FLAT_BET

    on = with_point(off, 6)
    assert try_bet(on, PASS, 10) is Rejection.NOT_NOW
    assert try_bet(on, PASS_ODDS, 10) is Rejection.NO_FLAT_BET
    assert try_bet(on, come(6), 10) is Rejection.NOT_NOW


@pytest.mark.parametrize(
    ("kind", "number"),
    [(BetKind.PASS, 6), (BetKind.PLACE, 7), (BetKind.PLACE, None), (BetKind.COME, 13)],
)
def test_spots_that_do_not_exist(kind: BetKind, number: int | None) -> None:
    with pytest.raises(ValueError):
        Bet(kind, number)


def test_working_needs_a_place_bet() -> None:
    state = table()
    assert refused(state, SetWorking(OTHER, 6, True, 0)) is Rejection.NO_FLAT_BET
    assert refused(state, SetWorking(OTHER, 7, True, 0)) is Rejection.NO_FLAT_BET


def test_a_bet_that_arrives_after_the_roll_is_rejected() -> None:
    state = with_point(table(), 6)
    late = state.roll_number - 1

    assert refused(state, SetBet(OTHER, place(8), 12, late)) is Rejection.STALE_ROLL
    assert refused(state, SetWorking(OTHER, 8, True, late)) is Rejection.STALE_ROLL
    assert refused(state, PassDice(SHOOTER, late)) is Rejection.STALE_ROLL
    assert refused(state, Roll(SHOOTER, 3, 3, late)) is Rejection.STALE_ROLL


def test_only_the_shooter_rolls_or_passes() -> None:
    state = bet(table(), PASS, 10, OTHER)
    assert refused(state, Roll(OTHER, 3, 4, 0)) is Rejection.NOT_SHOOTER
    assert refused(state, PassDice(OTHER, 0)) is Rejection.NOT_SHOOTER
    assert refused(state, Roll("nobody", 3, 4, 0)) is Rejection.NOT_SEATED


def test_the_shooter_needs_a_pass_bet_to_come_out() -> None:
    assert refused(table(), Roll(SHOOTER, 3, 4, 0)) is Rejection.SHOOTER_NEEDS_PASS_BET


@pytest.mark.parametrize("faces", [(0, 3), (3, 7), (3, 3.0), (True, 3)])
def test_dice_show_one_to_six(faces: tuple[int, int]) -> None:
    state = bet(table(), PASS, 10, SHOOTER)
    assert refused(state, Roll(SHOOTER, *faces, 0)) is Rejection.BAD_DICE


def test_the_dice_move_left_on_a_seven_out_only() -> None:
    state = table("ana", "bo", "cy")
    assert state.shooter == "ana"
    state = come_out(state, 7).state
    assert state.shooter == "ana"
    state = with_point(state, 5)
    assert roll(state, 5).state.shooter == "ana"

    for expected in ("bo", "cy", "ana"):
        state = roll(state, 7).state
        assert state.shooter == expected
        state = with_point(state, 5)


def test_passing_the_dice_keeps_the_point_and_bets() -> None:
    state = bet(with_point(table(), 9), place(6), 12)
    passed = apply(state, PassDice(SHOOTER, state.roll_number)).state

    assert passed.shooter == OTHER
    assert (passed.point, passed.bets) == (state.point, state.bets)
    # The new shooter finishes the hand without needing a Pass bet.
    assert (
        passed.roll_number + 1
        == apply(passed, Roll(OTHER, *dice(4), passed.roll_number)).state.roll_number
    )


def test_a_lone_player_cannot_pass_the_dice() -> None:
    assert refused(table(SHOOTER), PassDice(SHOOTER, 0)) is Rejection.NO_ONE_TO_PASS_TO


def test_joining_and_leaving() -> None:
    state = new_table()
    assert state.shooter is None
    state = apply(state, Join("ana")).state
    state = apply(state, Join("bo")).state
    state = apply(state, Join("cy")).state
    assert refused(state, Join("bo")) is Rejection.ALREADY_SEATED

    state = bet(state, place(6), 12, "ana")
    state = apply(state, Leave("ana")).state
    assert state.shooter == "bo"
    assert not state.bets
    assert refused(state, Leave("ana")) is Rejection.NOT_SEATED

    state = apply(apply(state, Leave("cy")).state, Leave("bo")).state
    assert (state.seats, state.shooter) == ((), None)


def test_cannot_leave_with_a_locked_bet() -> None:
    state = with_point(bet(table(), PASS, 10), 6)
    assert refused(state, Leave(OTHER)) is Rejection.LOCKED

    state = roll(bet(with_point(table(), 6), COME, 10), 9).state
    assert refused(state, Leave(OTHER)) is Rejection.LOCKED


def test_refill_tops_up_and_never_takes_away() -> None:
    state = bet(table(), place(6), 12)
    state = apply(state, Refill(OTHER)).state
    assert bankroll(state) == 1000
    assert apply(state, Refill(OTHER)).state == state

    rich = roll(bet(with_point(table(), 8), place(6), 12), 6).state
    rich = apply(rich, SetBet(OTHER, place(6), 0, rich.roll_number)).state
    assert bankroll(apply(rich, Refill(OTHER)).state) == 1014


@pytest.mark.parametrize(
    "bad",
    [
        {"min_bet": 0},
        {"min_bet": 10, "max_bet": 5},
        {"odds_multiple": -1},
        {"starting_bankroll": 0},
        {"place_pays": {6: Fraction(7, 6)}},
        {"place_pays": {**DEFAULT_PLACE_PAYS, 6: Fraction(0)}},
        {"min_bet": 5, "max_bet": 5},
    ],
)
def test_settings_that_make_no_sense_are_refused(bad: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        Settings(**bad)  # type: ignore[arg-type]


def test_settings_cannot_be_changed_from_outside() -> None:
    pays = dict(DEFAULT_PLACE_PAYS)
    settings = Settings(place_pays=pays)
    pays[6] = Fraction(100)
    assert settings.place_pays[6] == Fraction(7, 6)


def test_the_state_given_is_never_changed() -> None:
    state = bet(table(), PASS, 10, SHOOTER)
    before = (state.seats, dict(state.bets), state.point, state.roll_number)
    apply(state, Roll(SHOOTER, 3, 4, 0))
    assert before == (state.seats, dict(state.bets), state.point, state.roll_number)
    with pytest.raises(TypeError):
        state.bets[SHOOTER, PASS] = 500  # type: ignore[index]
