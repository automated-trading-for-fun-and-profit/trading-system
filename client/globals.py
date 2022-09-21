from enum import Enum

from message.message import Side


class State(Enum):
    Rejected = "Rejected"
    Pending = "Pending"
    Working = "Working"
    Sent = "Sent"
    ReviseSent = "ReviseSent"
    CancelSent = "CancelSent"
    Cancelled = "Cancelled"
    PartiallyFilled = "PartiallyFilled"
    Filled = "Filled"
    Suspended = "Suspended"


ORDER_SIDES = [side for side in Side]
ACTIVE_STATES = [
    State.Pending,
    State.Working,
    State.PartiallyFilled,
]
TRANSIENT_STATES = [State.Sent, State.ReviseSent, State.CancelSent]
COMPLETED_STATES = [State.Rejected, State.Cancelled, State.Filled]
