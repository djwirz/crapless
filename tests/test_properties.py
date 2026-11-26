"""Random sequences of actions keep invariants 2, 3 and 5 (spec §5 and §8)."""

from hypothesis import HealthCheck, event, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from crapless.engine import (
    COME,
    PASS,
    PASS_ODDS,
    POINT_NUMBERS,
    TRUE_ODDS,
    Action,
    Bet,
    Join,
    Leave,
    PassDice,
    Refill,
    Rejected,
    Result,
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
    spot_options,
)

PLAYERS = st.sampled_from(["ana", "bo", "cy", "dee"])
NUMBERS = st.sampled_from(POINT_NUMBERS)
SPOTS = st.one_of(
    st.sampled_from([PASS, PASS_ODDS, COME]),
    NUMBERS.map(place),
    NUMBERS.map(come),
    NUMBERS.map(come_odds),
)
# Mostly amounts some spot accepts, with a few that none does.
AMOUNTS = st.sampled_from([-1, 0, 1, 4, 5, 6, 8, 10, 12, 20, 30, 60, 498, 500, 600, 5000])
DIE = st.integers(1, 6)
OFFSET = st.sampled_from([0] * 9 + [-1, 1])
"""How far the quoted roll number is from the real one: nearly always right."""


def chips(state: TableState) -> int:
    return sum(s.bankroll for s in state.seats) + sum(state.bets.values())


class Table(RuleBasedStateMachine):
    state: TableState
    issued: int
    """Chips brought in by joining and refilling, less those taken away by leaving."""
    house: int
    """What the house has paid out, less what it has collected."""

    @initialize(working=st.booleans(), bankroll=st.sampled_from([40, 1000]))
    def open_table(self, working: bool, bankroll: int) -> None:
        self.state = new_table(Settings(come_odds_on_come_out=working, starting_bankroll=bankroll))
        self.issued = 0
        self.house = 0
        self.do(Join("ana"))
        self.do(Join("bo"))

    def do(self, action: Action) -> Result | None:
        before = self.state
        try:
            result = apply(before, action)
        except Rejected as rejected:
            event(f"rejected: {rejected.code}")
            return None
        self.state = result.state
        self.check_settlements(before, action, result)
        self.check_repeat(action, result.state)
        return result

    def check_settlements(self, before: TableState, action: Action, result: Result) -> None:
        match action:
            case Roll():
                spots = [(s.player, s.bet) for s in result.settlements]
                # Settled once: no bet twice, and only bets that were on the table.
                assert len(spots) == len(set(spots))
                for s in result.settlements:
                    assert before.bets[s.player, s.bet] == s.amount
                    self.house += s.paid - s.collected
                    event(f"{s.bet.kind}: {s.outcome}")
                assert result.state.roll_number == before.roll_number + 1
                return
            case Join():
                self.issued += before.settings.starting_bankroll
            case Refill(player):
                old, new = before.seat(player), result.state.seat(player)
                assert old and new
                self.issued += new.bankroll - old.bankroll
            case Leave(player):
                seat = before.seat(player)
                assert seat
                on_table = sum(v for (p, _), v in before.bets.items() if p == player)
                self.issued -= seat.bankroll + on_table
        assert result.settlements == ()
        assert result.state.roll_number == before.roll_number

    def check_repeat(self, action: Action, after: TableState) -> None:
        """The same message again either changes nothing or is refused."""
        try:
            again = apply(after, action)
        except Rejected:
            # Setting a total or a switch, or refilling, is never refused the second time.
            assert not isinstance(action, SetBet | SetWorking | Refill)
            return
        assert not isinstance(action, Roll), "a roll was settled twice"
        assert again.state == after
        assert again.settlements == ()

    @rule(player=PLAYERS)
    def join(self, player: str) -> None:
        self.do(Join(player))

    @rule(player=PLAYERS)
    def leave(self, player: str) -> None:
        self.do(Leave(player))

    @rule(player=PLAYERS)
    def refill(self, player: str) -> None:
        self.do(Refill(player))

    @rule(player=PLAYERS, spot=SPOTS, amount=AMOUNTS, offset=OFFSET)
    def set_any_bet(self, player: str, spot: Bet, amount: int, offset: int) -> None:
        self.do(SetBet(player, spot, amount, self.state.roll_number + offset))

    @rule(data=st.data(), number=NUMBERS, size=st.integers(1, 3), working=st.booleans())
    def make_a_place_bet(self, data: st.DataObject, number: int, size: int, working: bool) -> None:
        """Random spots, players and amounts are mostly refused, so also bet properly."""
        if not self.state.seats:
            return
        player = data.draw(st.sampled_from([s.player for s in self.state.seats]))
        amount = self.state.settings.place_pays[number].denominator * 3 * size
        self.do(SetBet(player, place(number), amount, self.state.roll_number))
        self.do(SetWorking(player, number, working, self.state.roll_number))

    @rule(data=st.data(), size=st.integers(1, 3))
    def make_a_come_bet(self, data: st.DataObject, size: int) -> None:
        if not self.state.seats or self.state.point is None:
            return
        player = data.draw(st.sampled_from([s.player for s in self.state.seats]))
        self.do(SetBet(player, COME, 5 * size, self.state.roll_number))

    @rule(data=st.data(), size=st.integers(1, 3))
    def back_a_flat_bet_with_odds(self, data: st.DataObject, size: int) -> None:
        """Random spots rarely hit a bet that can take odds, so aim for one."""
        flats = sorted(
            (player, bet.number or 0)
            for player, bet in self.state.bets
            if (bet == PASS and self.state.point) or (bet.kind == COME.kind and bet.number)
        )
        if not flats:
            return
        player, number = data.draw(st.sampled_from(flats))
        target = number or self.state.point
        assert target
        amount = TRUE_ODDS[target].denominator * 5 * size
        spot = come_odds(number) if number else PASS_ODDS
        self.do(SetBet(player, spot, amount, self.state.roll_number))

    @rule(player=PLAYERS, number=NUMBERS, working=st.booleans(), offset=OFFSET)
    def set_working(self, player: str, number: int, working: bool, offset: int) -> None:
        self.do(SetWorking(player, number, working, self.state.roll_number + offset))

    @rule(player=PLAYERS, offset=OFFSET)
    def pass_dice(self, player: str, offset: int) -> None:
        self.do(PassDice(player, self.state.roll_number + offset))

    @rule(player=PLAYERS, die1=DIE, die2=DIE, offset=OFFSET)
    def anyone_rolls(self, player: str, die1: int, die2: int, offset: int) -> None:
        shooter = self.state.shooter
        result = self.do(Roll(player, die1, die2, self.state.roll_number + offset))
        assert result is None or player == shooter

    @rule(die1=DIE, die2=DIE)
    def shooter_rolls(self, die1: int, die2: int) -> None:
        shooter = self.state.shooter
        if shooter is None:
            return
        if self.state.point is None and not self.state.bet(shooter, PASS):
            self.do(SetBet(shooter, PASS, 5, self.state.roll_number))
        self.do(Roll(shooter, die1, die2, self.state.roll_number))

    @invariant()
    def chips_add_up(self) -> None:
        assert chips(self.state) == self.issued + self.house
        assert all(s.bankroll >= 0 for s in self.state.seats)
        assert all(amount > 0 for amount in self.state.bets.values())

    @invariant()
    def one_shooter(self) -> None:
        players = [s.player for s in self.state.seats]
        assert len(players) == len(set(players))
        if players:
            assert self.state.shooter in players
        else:
            assert self.state.shooter is None

    @invariant()
    def offered_amounts_are_the_accepted_ones(self) -> None:
        """`spot_options` and `apply` agree, at both ends of each range and just outside."""
        state = self.state
        for seat in state.seats:
            held = [b for p, b in state.bets if p == seat.player]
            for spot in {PASS, PASS_ODDS, COME, place(3), place(6), come(8), come_odds(8), *held}:
                options = spot_options(state, seat.player, spot)
                low, high, step = options.low, options.high, options.step

                def accepted(amount: int, spot: Bet = spot, player: str = seat.player) -> bool:
                    try:
                        apply(state, SetBet(player, spot, amount, state.roll_number))
                    except Rejected:
                        return False
                    return True

                if options.amount:
                    assert accepted(0) is options.removable
                if low is None or high is None:
                    for amount in (step, step * 5, 600):
                        assert amount == options.amount or not accepted(amount)
                    continue
                assert accepted(low) and accepted(high)
                for outside in (low - step, high + step):
                    assert outside <= 0 or outside == options.amount or not accepted(outside)
                if step > 1:
                    assert low + 1 == options.amount or not accepted(low + 1)

    @invariant()
    def bets_make_sense(self) -> None:
        state = self.state
        for player, bet in state.bets:
            assert state.seat(player)
            if bet == PASS_ODDS:
                assert state.point and state.bet(player, PASS)
            if bet.kind == come_odds(6).kind:
                assert bet.number and state.bet(player, come(bet.number))
            if bet == COME:
                assert state.point, "a Come bet cannot still be waiting on a come-out"
        for player, number in state.working:
            assert state.bet(player, place(number))


TestTable = Table.TestCase
TestTable.settings = settings(
    max_examples=300,
    stateful_step_count=60,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
