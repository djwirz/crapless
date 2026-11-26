"""Each bet's house edge, computed exactly by driving the engine with all 36 dice results.

A bet is followed from the moment it is made until it is first decided. The rolls that leave
it undecided lead to other table states, which gives a small system of linear equations,
solved with fractions.
"""

from collections.abc import Hashable
from dataclasses import replace
from fractions import Fraction

import pytest
from helpers import OTHER, bet, dice, with_point

from crapless.engine import (
    COME,
    PASS,
    PASS_ODDS,
    POINT_NUMBERS,
    Bet,
    Join,
    Outcome,
    Roll,
    SetBet,
    SetPedantic,
    Settings,
    SetWorking,
    TableState,
    apply,
    come,
    come_odds,
    new_table,
    place,
)

ALL_DICE = [(a, b) for a in range(1, 7) for b in range(1, 7)]
STAKE = 60  # pays out evenly on every spot


def seated(**settings: object) -> TableState:
    state = new_table(Settings(max_bet=1000, starting_bankroll=10_000, **settings))  # type: ignore[arg-type]
    for player in ("ana", OTHER):
        state = apply(state, Join(player)).state
    return state


def ready(state: TableState) -> TableState:
    """Level out what does not affect the bet being followed, so the states repeat."""
    state = replace(
        state,
        seats=tuple(replace(s, bankroll=10_000) for s in state.seats),
        shooter="ana",
        roll_number=0,
    )
    if state.point is None and not state.bet("ana", PASS):
        state = apply(state, SetBet("ana", PASS, STAKE, 0)).state
    return state


def key(state: TableState, followed: Bet) -> Hashable:
    return followed, state.point, frozenset(state.bets.items()), state.working


def expected_net(start: TableState, followed: Bet) -> Fraction:
    """The follower's expected win or loss, in chips, when the bet is first decided."""
    start = ready(start)
    todo = [(start, followed)]
    seen = {key(start, followed)}
    equations: dict[Hashable, tuple[Fraction, dict[Hashable, Fraction]]] = {}

    while todo:
        state, spot = todo.pop()
        constant = Fraction(0)
        onward: dict[Hashable, Fraction] = {}
        for faces in ALL_DICE:
            result = apply(state, Roll("ana", *faces, 0))
            mine = [s for s in result.settlements if s.player == OTHER and s.bet == spot]
            next_spot = spot
            if mine and mine[0].outcome is not Outcome.MOVED:
                constant += Fraction(mine[0].paid - mine[0].collected, len(ALL_DICE))
                continue
            if mine:
                next_spot = come(sum(faces))
            after = ready(result.state)
            node = key(after, next_spot)
            onward[node] = onward.get(node, Fraction(0)) + Fraction(1, len(ALL_DICE))
            if node not in seen:
                seen.add(node)
                todo.append((after, next_spot))
        equations[key(state, spot)] = constant, onward

    return solve(equations, key(start, followed))


def solve(
    equations: dict[Hashable, tuple[Fraction, dict[Hashable, Fraction]]], start: Hashable
) -> Fraction:
    """Gaussian elimination for x[i] = constant[i] + sum(p[i][j] * x[j])."""
    nodes = list(equations)
    index = {node: i for i, node in enumerate(nodes)}
    rows: list[list[Fraction]] = []
    for i, node in enumerate(nodes):
        constant, onward = equations[node]
        row = [Fraction(0)] * len(nodes) + [constant]
        row[i] += 1
        for other, p in onward.items():
            row[index[other]] -= p
        rows.append(row)

    for column in range(len(nodes)):
        pivot = next(r for r in range(column, len(nodes)) if rows[r][column])
        rows[column], rows[pivot] = rows[pivot], rows[column]
        rows[column] = [value / rows[column][column] for value in rows[column]]
        for r in range(len(nodes)):
            factor = rows[r][column]
            if r != column and factor:
                rows[r] = [a - factor * b for a, b in zip(rows[r], rows[column], strict=True)]
    return rows[index[start]][-1]


def edge(state: TableState, spot: Bet, amount: int = STAKE) -> Fraction:
    return -expected_net(state, spot) / amount


# Spec §4, as exact fractions.
PLACE_EDGE = {
    2: Fraction(1, 14),
    3: Fraction(1, 16),
    4: Fraction(1, 15),
    5: Fraction(1, 25),
    6: Fraction(1, 66),
}
PLACE_EDGE |= {14 - n: e for n, e in PLACE_EDGE.items()}
PASS_EDGE = Fraction(373, 6930)


def test_pass() -> None:
    assert edge(bet(seated(), PASS, STAKE), PASS) == PASS_EDGE
    assert float(PASS_EDGE) == pytest.approx(0.054, abs=0.0005)


@pytest.mark.parametrize("point", POINT_NUMBERS)
def test_come_is_the_same_math_as_pass(point: int) -> None:
    state = bet(with_point(seated(), point), COME, STAKE)
    assert edge(state, COME) == PASS_EDGE


@pytest.mark.parametrize("number", POINT_NUMBERS)
@pytest.mark.parametrize("turned_on", [False, True])
def test_place(number: int, turned_on: bool) -> None:
    table = bet(seated(), place(number), STAKE)
    if turned_on:
        table = apply(table, SetWorking(OTHER, number, True, 0)).state
    assert edge(table, place(number)) == PLACE_EDGE[number]


@pytest.mark.parametrize("point", POINT_NUMBERS)
def test_pass_odds_have_no_edge(point: int) -> None:
    state = with_point(bet(seated(), PASS, STAKE), point)
    state = bet(state, PASS_ODDS, STAKE)
    assert edge(state, PASS_ODDS) == 0


@pytest.mark.parametrize("working", [False, True])
@pytest.mark.parametrize("number", POINT_NUMBERS)
def test_come_odds_have_no_edge(number: int, working: bool) -> None:
    point = 8 if number == 6 else 6
    state = with_point(seated(come_odds_on_come_out=working), point)
    state = apply(bet(state, COME, STAKE), Roll("ana", *dice(number), 1)).state
    state = bet(state, come_odds(number), STAKE)
    assert edge(state, come_odds(number)) == 0


@pytest.mark.parametrize("number", [2, 3, 11, 12])
def test_the_smallest_pedantic_bet_has_the_same_edge(number: int) -> None:
    state = apply(seated(), SetPedantic(OTHER, True)).state
    assert edge(bet(state, place(number), 4), place(number), 4) == PLACE_EDGE[number]


def test_the_method_notices_a_wrong_payout() -> None:
    pays = {**Settings().place_pays, 6: Fraction(6, 5)}
    state = bet(seated(place_pays=pays), place(6), STAKE)
    assert edge(state, place(6)) != PLACE_EDGE[6]
