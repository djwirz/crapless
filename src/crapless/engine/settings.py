"""Table settings: limits and payouts (spec §4). Casinos differ, so these are not hard-coded."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from types import MappingProxyType

# Odds bets pay true odds, which is what makes them free of house edge. Not a setting.
TRUE_ODDS: Mapping[int, Fraction] = MappingProxyType(
    {
        2: Fraction(6, 1),
        3: Fraction(3, 1),
        4: Fraction(2, 1),
        5: Fraction(3, 2),
        6: Fraction(6, 5),
        8: Fraction(6, 5),
        9: Fraction(3, 2),
        10: Fraction(2, 1),
        11: Fraction(3, 1),
        12: Fraction(6, 1),
    }
)

DEFAULT_PLACE_PAYS: Mapping[int, Fraction] = MappingProxyType(
    {
        2: Fraction(11, 2),
        3: Fraction(11, 4),
        4: Fraction(9, 5),
        5: Fraction(7, 5),
        6: Fraction(7, 6),
        8: Fraction(7, 6),
        9: Fraction(7, 5),
        10: Fraction(9, 5),
        11: Fraction(11, 4),
        12: Fraction(11, 2),
    }
)


@dataclass(frozen=True)
class Settings:
    """Whole chips only (ADR 0006)."""

    min_bet: int = 5
    """Smallest Pass, Come or Place bet. Odds have no minimum beyond paying out evenly."""
    pedantic_place_min: int = 4
    """Smallest Place bet for a player in pedantic mode (ADR 0010). Multiples still apply."""
    max_bet: int = 500
    """Largest Pass, Come or Place bet. Odds are capped by the multiple instead."""
    odds_multiple: int = 3
    place_pays: Mapping[int, Fraction] = field(default_factory=lambda: DEFAULT_PLACE_PAYS)
    come_odds_on_come_out: bool = False
    starting_bankroll: int = 1000

    def __post_init__(self) -> None:
        if not 1 <= self.min_bet <= self.max_bet:
            raise ValueError("limits must satisfy 1 <= min_bet <= max_bet")
        if not 1 <= self.pedantic_place_min <= self.min_bet:
            raise ValueError("pedantic_place_min must satisfy 1 <= it <= min_bet")
        if self.odds_multiple < 0:
            raise ValueError("odds_multiple cannot be negative")
        if self.starting_bankroll < 1:
            raise ValueError("starting_bankroll must be at least 1")
        if set(self.place_pays) != set(TRUE_ODDS):
            raise ValueError("place_pays needs a ratio for each of the ten numbers")
        for number, pays in self.place_pays.items():
            if pays <= 0:
                raise ValueError(f"place pay for {number} must be positive")
            # The first multiple of the unit at or above the minimum must still be allowed.
            unit = pays.denominator
            if -(-self.min_bet // unit) * unit > self.max_bet:
                raise ValueError(f"no Place {number} bet fits the limits")
        # A private read-only copy, so a caller's dict cannot change the rules later.
        object.__setattr__(self, "place_pays", MappingProxyType(dict(self.place_pays)))
