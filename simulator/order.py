import logging
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from functools import total_ordering
from typing import Dict, List, Optional

from message.message import OrderStatus, Side

DEFAULT_SYMBOL = "AUTTRAD Equity"
ORDER_CREATION_SUCCESS_MSG = "Successful order creation"
ORDER_FILL_SUCCESS_MSG = "Order filled successfully"
ORDER_CANCEL_SUCCESS_MSG = "Order cancellation is successful"
logger = logging.getLogger(__name__)


class TradeFillType(Enum):
    CompleteFill = "Complete Fill"
    PartialFill = "Partial Fill"


@dataclass
class Trade:
    quantity: int
    limit_price: float
    symbol: str
    exch_order_id: str
    trade_id: str
    fill_type: TradeFillType
    side: Side

    @classmethod
    def from_json(cls, json_msg: Dict):
        return cls(
            quantity=json_msg["quantity"],
            limit_price=json_msg["limit_price"],
            symbol=json_msg["symbol"],
            exch_order_id=json_msg["exch_order_id"],
            trade_id=json_msg["trade_id"],
            fill_type=TradeFillType["fill_type"],
            side=Side(json_msg["side"]),
        )

    def to_json(self):
        return {
            "quantity": self.quantity,
            "limit_price": self.limit_price,
            "symbol": self.symbol,
            "exch_order_id": self.exch_order_id,
            "trade_id": self.trade_id,
            "fill_type": self.fill_type.value,
            "side": self.side.value,
        }


@dataclass
class OrderParams:
    limit_price: float
    quantity: int
    side: Side
    symbol: str
    exch_order_id: str
    status: OrderStatus
    filled_quantity: int = 0

    def __str__(self):
        return (
            f"limit_price: {self.limit_price}, quantity: {self.quantity}, side: {self.side}, "
            f"symbol: {self.symbol}, filled_quantity: {self.filled_quantity}, "
            f"exch_order_id: {self.exch_order_id}, "
            f"status: {self.status.value if self.status else None}"
        )

    def to_json(self):
        return {
            "limit_price": self.limit_price,
            "quantity": self.quantity,
            "side": self.side.value,
            "symbol": self.symbol,
            "filled_quantity": self.filled_quantity,
            "exch_order_id": self.exch_order_id,
            "status": self.status.value,
        }

    @classmethod
    def from_json(cls, json_msg: Dict):
        return OrderParams(
            limit_price=json_msg["limit_price"],
            quantity=json_msg["quantity"],
            side=Side(json_msg["side"]),
            symbol=json_msg["symbol"],
            filled_quantity=json_msg["filled_quantity"],
            exch_order_id=json_msg["exch_order_id"],
            status=OrderStatus(json_msg["status"]),
        )


@dataclass
class Response:
    client_id: str
    order_params: Optional[OrderParams]
    status: bool
    status_msg: str


@dataclass
class OrderResponse(Response):
    client_msg_id: str
    name: str = "OrderResponse"

    def to_json(self):
        return {
            "name": self.name,
            "client_msg_id": self.client_msg_id,
            "client_id": self.client_id,
            "order_params": self.order_params.to_json() if self.order_params else None,
            "status": self.status,
            "status_msg": self.status_msg,
        }

    @classmethod
    def from_json(cls, json_msg: Dict):
        return cls(
            name=json_msg["name"],
            client_msg_id=json_msg["client_msg_id"],
            client_id=json_msg["client_id"],
            order_params=(
                OrderParams.from_json(json_msg["order_params"])
                if json_msg.get("order_params")
                else None
            ),
            status=json_msg["status"],
            status_msg=json_msg["status_msg"],
        )


@dataclass
class FillOrderResponse(Response):
    trade: Trade
    name: str = "FillOrderResponse"

    def to_json(self):
        return {
            "name": self.name,
            "order_params": self.order_params.to_json() if self.order_params else None,
            "client_id": self.client_id,
            "trade": self.trade.to_json(),
            "status": self.status,
            "status_msg": self.status_msg,
        }

    @classmethod
    def from_json(cls, json_msg: Dict):
        return cls(
            order_params=OrderParams.from_json(json_msg["order_params"]),
            client_id=json_msg["client_id"],
            trade=Trade.from_json(json_msg["trade"]),
            status=json_msg["status"],
            status_msg=json_msg["status_msg"],
        )


@total_ordering
class Order:
    def __init__(
        self,
        limit_price: float,
        quantity: int,
        side: Side,
        client_msg_id: str,
        client_id: str,
        symbol: str = DEFAULT_SYMBOL,
    ):
        self._order_params = OrderParams(
            limit_price=limit_price,
            quantity=quantity,
            side=side,
            symbol=symbol,
            filled_quantity=0,
            exch_order_id=uuid.uuid4().hex,
            status=OrderStatus.Ack,
        )
        self._timestamp = time.time()

        self._client_id: str = client_id
        self._client_msg_id: str = client_msg_id
        self._trades: List[Trade] = []

    def __str__(self):
        return (
            f"client_msg_id: {self._client_msg_id}, timestamp: {self._timestamp}, "
            f"order_params: {self._order_params}, client_id: {self._client_id}"
        )

    def __hash__(self):
        return self.exch_order_id

    def __eq__(self, other):
        return self.exch_order_id == other.exch_order_id

    def __lt__(self, other):
        # Buy order(Bids) should be sorted in descending order
        if self.side == Side.Buy and self.limit_price > other.limit_price:
            return True

        if self.side == Side.Sell and self.limit_price < other.limit_price:
            return True

        if self.limit_price == other.limit_price:
            return self._timestamp < other._timestamp
        return False

    def open_quantity(self):
        return self.quantity - self.filled_quantity

    def revise(
        self,
        client_msg_id: str,
        client_id: str,
        revised_qty: Optional[int] = None,
        revised_price: Optional[float] = None,
    ) -> Response:
        if revised_qty:
            if self.filled_quantity > revised_qty:
                status_msg = (
                    f"Revise quantity {revised_qty} should not be less than filled quantity "
                    f"{self.filled_quantity}"
                )
                return OrderResponse(
                    client_msg_id=client_msg_id,
                    client_id=client_id,
                    order_params=self._order_params,
                    status=False,
                    status_msg=status_msg,
                )

            self._order_params.quantity = revised_qty

        if self.open_quantity() == 0:
            self._order_params.status = OrderStatus.Filled

        if revised_price:
            if self.status == OrderStatus.Filled:
                status_msg = "Order price cannot be revised after revised quantity filled the order"
                return OrderResponse(
                    client_msg_id=client_msg_id,
                    client_id=client_id,
                    order_params=self._order_params,
                    status=False,
                    status_msg=status_msg,
                )
            self._order_params.limit_price = revised_price

        self._timestamp = time.time()
        status_msg = "Revise order successful"
        return OrderResponse(
            client_msg_id=client_msg_id,
            client_id=client_id,
            order_params=self._order_params,
            status=True,
            status_msg=status_msg,
        )

    def cancel(self, client_msg_id: str, client_id: str) -> OrderResponse:
        if self.status == OrderStatus.Filled:
            status_msg = "Filled order cannot be cancelled"
            return OrderResponse(
                client_msg_id=client_msg_id,
                client_id=client_id,
                order_params=self._order_params,
                status=False,
                status_msg=status_msg,
            )

        self._order_params.status = OrderStatus.Cancelled
        status_msg = "Order cancellation is successful"
        return OrderResponse(
            client_msg_id=client_msg_id,
            client_id=client_id,
            order_params=self._order_params,
            status=True,
            status_msg=status_msg,
        )

    def fill(self, quantity: int, price: float, trade_id: str) -> FillOrderResponse:
        if quantity > self.open_quantity():
            raise ValueError(
                f"Fill quantity {quantity} cannot be more than the open quantity "
                f"{self.open_quantity()}"
            )

        self._order_params.filled_quantity = (
            self._order_params.filled_quantity + quantity
        )
        if self.open_quantity() == 0:
            fill_type = TradeFillType.CompleteFill
            self._order_params.status = OrderStatus.Filled
            logger.info("Order: %s is filled", self._order_params)
        else:
            fill_type = TradeFillType.PartialFill
            self._order_params.status = OrderStatus.PartiallyFilled

        trade = Trade(
            quantity=quantity,
            limit_price=price,
            exch_order_id=self.exch_order_id,
            trade_id=trade_id,
            fill_type=fill_type,
            symbol=self.symbol,
            side=self.side,
        )
        self._trades.append(trade)
        return FillOrderResponse(
            order_params=self._order_params,
            client_id=self._client_id,
            status=True,
            status_msg="Order filled successfully",
            trade=trade,
        )

    @property
    def client_id(self):
        return self._client_id

    @property
    def order_params(self):
        return self._order_params

    @property
    def filled_quantity(self):
        return self._order_params.filled_quantity

    @property
    def quantity(self):
        return self._order_params.quantity

    @property
    def exch_order_id(self):
        return self._order_params.exch_order_id

    @property
    def limit_price(self):
        return self._order_params.limit_price

    @property
    def status(self):
        return self._order_params.status

    @property
    def side(self):
        return self._order_params.side

    @property
    def symbol(self):
        return self._order_params.symbol


def ack_response(client_msg_id: str, client_id: str, order: Order):
    return OrderResponse(
        client_msg_id=client_msg_id,
        client_id=client_id,
        order_params=order.order_params,
        status=True,
        status_msg="Successful order creation",
    )
