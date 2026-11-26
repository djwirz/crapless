"""Protocol version 1 (docs/protocol.md). These models are its one definition (ADR 0008).

The TypeScript types in `web/src/protocol.gen.ts` are generated from them.
No field has a default, so every field is required on both sides.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from crapless.engine import BetKind, Outcome

VERSION = 1

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


class Refill(Message):
    type: Literal["refill"]
    id: MessageId


ClientMessage = Annotated[
    Hello | PlaceBet | Working | RollDice | Refill, Field(discriminator="type")
]
client_message: TypeAdapter[Hello | PlaceBet | Working | RollDice | Refill] = TypeAdapter(
    ClientMessage
)


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


class State(Message):
    """The whole table, sent after every change. Clients replace what they had."""

    type: Literal["state"]
    v: int
    token: str
    table: str
    reset: bool
    """True when the token sent was not known, so this is a new table."""
    ack: str | None
    """The id of the message this answers."""
    bankroll: int
    point: int | None
    roll: int
    roll_blocked: str | None
    """Why the dice cannot be rolled now, or null if they can."""
    can_refill: bool
    spots: list[SpotView]
    last_roll: LastRoll | None


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
