from crapless.engine import (
    PASS,
    Bet,
    Join,
    Outcome,
    Result,
    Roll,
    SetBet,
    Settings,
    Settlement,
    TableState,
    apply,
    new_table,
)

SHOOTER = "ana"
OTHER = "bo"


def dice(total: int) -> tuple[int, int]:
    return total // 2, total - total // 2


def table(*players: str, settings: Settings | None = None) -> TableState:
    state = new_table(settings)
    for player in players or (SHOOTER, OTHER):
        state = apply(state, Join(player)).state
    return state


def bet(state: TableState, what: Bet, amount: int, player: str = OTHER) -> TableState:
    return apply(state, SetBet(player, what, amount, state.roll_number)).state


def roll(state: TableState, total: int) -> Result:
    assert state.shooter is not None
    return apply(state, Roll(state.shooter, *dice(total), state.roll_number))


def come_out(state: TableState, total: int) -> Result:
    """Make sure the shooter has the Pass bet they need, then roll."""
    assert state.point is None and state.shooter is not None
    if not state.bet(state.shooter, PASS):
        state = bet(state, PASS, 30, state.shooter)
    return roll(state, total)


def with_point(state: TableState, point: int) -> TableState:
    return come_out(state, point).state


def bankroll(state: TableState, player: str = OTHER) -> int:
    seat = state.seat(player)
    assert seat is not None
    return seat.bankroll


def settled(result: Result, what: Bet, player: str = OTHER) -> Settlement | None:
    found = [s for s in result.settlements if s.player == player and s.bet == what]
    assert len(found) <= 1, "a bet was settled twice"
    return found[0] if found else None


def outcome(result: Result, what: Bet, player: str = OTHER) -> Outcome | None:
    settlement = settled(result, what, player)
    return settlement.outcome if settlement else None
