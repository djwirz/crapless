"""Protocol version 3 (docs/protocol.md). These models are its one definition (ADR 0008).

The TypeScript types in `web/src/protocol.gen.ts` are generated from them.
No field has a default, so every field is required on both sides.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from crapless.engine import BetKind, Outcome

VERSION = 3

TableCode = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{12,32}$")]
Name = Annotated[
    str, Field(min_length=1, max_length=12, pattern=r"^[^\x00-\x1f\x7f]*\S[^\x00-\x1f\x7f]*$")
]

MessageId = Annotated[str, Field(min_length=1, max_length=64)]
Chips = Annotated[int, Field(ge=0, le=1_000_000_000)]
RollNumber = Annotated[int, Field(ge=0)]
Die = Annotated[int, Field(ge=1, le=6)]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Spot(Message):
    kind: BetKind
    number: int | None


# Client to server


class Hello(Message):
    """The first message on a connection."""

    type: Literal["hello"]
    v: int
    token: Annotated[str, Field(max_length=128)] | None
    """The seat token from last time, to resume that seat."""
    table: TableCode | None
    """The code from the invite link, or null to open a new table."""
    name: Name
    """What the others see. Never logged."""


class PlaceBet(Message):
    type: Literal["bet"]
    id: MessageId
    spot: Spot
    amount: Chips
    """The new total on the spot. 0 takes the bet down."""
    roll: RollNumber


class Working(Message):
    type: Literal["working"]
    id: MessageId
    number: int
    working: bool
    roll: RollNumber


class RollDice(Message):
    type: Literal["roll"]
    id: MessageId
    roll: RollNumber


class Pedantic(Message):
    """Switch pedantic mode on or off for your own seat."""

    type: Literal["pedantic"]
    id: MessageId
    on: bool


class Refill(Message):
    type: Literal["refill"]
    id: MessageId


class PassDice(Message):
    type: Literal["pass"]
    id: MessageId
    roll: RollNumber


class Leave(Message):
    type: Literal["leave"]
    id: MessageId


Request = PlaceBet | Working | RollDice | Pedantic | Refill | PassDice | Leave
"""Anything a seated player may ask for."""
ClientMessage = Annotated[Hello | Request, Field(discriminator="type")]
client_message: TypeAdapter[Hello | Request] = TypeAdapter(ClientMessage)


# Server to client


class SpotView(Message):
    spot: Spot
    amount: int
    step: int
    low: int | None
    high: int | None
    removable: bool
    working: bool | None
    """For a Place bet that is up: whether it is on for the come-out. Otherwise null."""


class SettlementView(Message):
    spot: Spot
    outcome: Outcome
    amount: int
    paid: int
    returned: int


class LastRoll(Message):
    die1: Die
    die2: Die
    settlements: list[SettlementView]


class PlayerView(Message):
    seat: str
    name: str
    color: int
    """0 to 7, one for each seat at a table."""
    bankroll: int
    away: bool
    shooter: bool
    pedantic: bool
    net: int | None
    """Winnings less losses on the last roll, or null if nothing of theirs was decided."""


class OthersOnSpot(Message):
    spot: Spot
    seats: list[str]


class State(Message):
    """One player's view of the whole table, sent after every change. Replace what you had."""

    type: Literal["state"]
    v: int
    token: str
    table: str
    """The code for the invite link. A secret."""
    ref: str
    """The table's id in the logs, for matching a complaint to a line. Lets nobody join."""
    you: str
    """Your seat id."""
    notice: str | None
    """Something to tell the player once, such as that the table started over."""
    announcement: str | None
    """News for the whole table, sent once. Show it for a few seconds."""
    ack: str | None
    """The id of the message this answers."""
    bankroll: int
    point: int | None
    roll: int
    roll_blocked: str | None
    """Why the dice cannot be rolled now, or null if they can."""
    wait_ms: int
    """How long the shooter's Roll is still held after someone else's bet."""
    can_refill: bool
    low_on_chips: bool
    """Too few for the smallest bet."""
    can_pass: bool
    leave_blocked: str | None
    players: list[PlayerView]
    """In seat order, which is the order the dice go round."""
    spots: list[SpotView]
    others: list[OthersOnSpot]
    last_roll: LastRoll | None
    """The dice, and what the roll did to your bets."""


class Refused(Message):
    type: Literal["rejected"]
    id: str | None
    code: str
    reason: str


ServerMessage = Annotated[State | Refused, Field(discriminator="type")]


class Protocol(Message):
    """Only for generating the schema: one of each direction."""

    client: ClientMessage
    server: ServerMessage
