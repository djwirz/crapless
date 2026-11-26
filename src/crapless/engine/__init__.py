"""The crapless craps rules engine: pure functions over immutable table state.

No I/O and no randomness live here (spec §6). The caller rolls the dice and passes them in.
"""

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
from crapless.engine.apply import apply, new_table
from crapless.engine.model import (
    COME,
    PASS,
    PASS_ODDS,
    POINT_NUMBERS,
    Bet,
    BetKind,
    Outcome,
    Rejected,
    Rejection,
    Result,
    Seat,
    Settlement,
    TableState,
    come,
    come_odds,
    place,
)
from crapless.engine.settings import DEFAULT_PLACE_PAYS, TRUE_ODDS, Settings
from crapless.engine.spots import SpotOptions, spot_options

__all__ = [
    "COME",
    "DEFAULT_PLACE_PAYS",
    "PASS",
    "PASS_ODDS",
    "POINT_NUMBERS",
    "TRUE_ODDS",
    "Action",
    "Bet",
    "BetKind",
    "Join",
    "Leave",
    "Outcome",
    "PassDice",
    "Refill",
    "Rejected",
    "Rejection",
    "Result",
    "Roll",
    "Seat",
    "SetBet",
    "SetWorking",
    "Settings",
    "Settlement",
    "SpotOptions",
    "TableState",
    "apply",
    "come",
    "come_odds",
    "new_table",
    "place",
    "spot_options",
]
