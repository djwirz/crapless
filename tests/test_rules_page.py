"""The How to play screen quotes pays and limits. They must be the engine's."""

import re
from fractions import Fraction
from pathlib import Path

from crapless.engine import DEFAULT_PLACE_PAYS, TRUE_ODDS, Settings

SOURCE = (Path(__file__).parent.parent / "web" / "src" / "rules.ts").read_text()

ROW = re.compile(
    r'numbers: \[(\d+), (\d+)\], odds: "(\d+) to (\d+)", place: "(\d+) to (\d+)", step: (\d+)'
)


def constant(name: str) -> int:
    found = re.search(rf"export const {name} = (\d+);", SOURCE)
    assert found, name
    return int(found[1])


def test_the_quoted_pays_are_the_engines() -> None:
    rows = [[int(v) for v in row] for row in ROW.findall(SOURCE)]
    quoted = []
    for one, other, odds_win, odds_per, place_win, place_per, step in rows:
        for number in (one, other):
            quoted.append(number)
            assert TRUE_ODDS[number] == Fraction(odds_win, odds_per)
            assert DEFAULT_PLACE_PAYS[number] == Fraction(place_win, place_per)
            assert DEFAULT_PLACE_PAYS[number].denominator == step
    assert sorted(quoted) == sorted(TRUE_ODDS)


def test_the_quoted_odds_multiples_are_the_engines() -> None:
    page = " ".join((Path(__file__).parent.parent / "web/src/HowToPlay.tsx").read_text().split())
    assert "Odds on 5 or 9 go in 2s, and on 6 or 8 in 5s." in page
    steps = {n: TRUE_ODDS[n].denominator for n in TRUE_ODDS}
    assert {n for n, step in steps.items() if step == 2} == {5, 9}
    assert {n for n, step in steps.items() if step == 5} == {6, 8}
    assert set(steps.values()) == {1, 2, 5}


def test_the_quoted_limits_are_the_defaults() -> None:
    settings = Settings()
    assert constant("MIN_BET") == settings.min_bet
    assert constant("MAX_BET") == settings.max_bet
    assert constant("PEDANTIC_MIN") == settings.pedantic_place_min
    assert constant("ODDS_MULTIPLE") == settings.odds_multiple
    assert not settings.come_odds_on_come_out  # the screen says they are off


def test_the_quoted_pedantic_numbers_are_the_ones_it_changes() -> None:
    page = " ".join((Path(__file__).parent.parent / "web/src/HowToPlay.tsx").read_text().split())
    assert "Place bets on 2, 3, 11 and 12 can then start at {PEDANTIC_MIN}." in page
    settings = Settings()
    changed = {
        number
        for number, pays in settings.place_pays.items()
        # The smallest multiple at or above each minimum.
        if -(-settings.pedantic_place_min // pays.denominator) * pays.denominator
        < -(-settings.min_bet // pays.denominator) * pays.denominator
    }
    assert changed == {2, 3, 11, 12}
