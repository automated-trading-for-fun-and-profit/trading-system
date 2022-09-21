from enum import Enum


class Side(Enum):
    Buy = "buy"
    Sell = "sell"


class OrderStatus(Enum):
    Ack = "ack"
    PartiallyFilled = "partially_filled"
    Filled = "filled"
    Cancelled = "cancelled"
