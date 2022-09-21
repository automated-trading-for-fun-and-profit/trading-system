import logging
from xmlrpc.client import boolean

from message.message import Side

from .exchange_client import ExchangeClient
from .globals import ACTIVE_STATES, State

logger = logging.getLogger(__name__)


class IcebergOrder:
    def __init__(
        self,
        client: ExchangeClient,
        total_quantity: int,
        slice_size: int,
        side: Side,
        limit_price: float,
    ):
        self.client = client
        self.total_quantity = total_quantity
        self.side = side
        self.limit_price = limit_price
        self.filled_quantity = 0
        self.slice_size = slice_size
        self.slice_filled_quantity = 0
        self.slice_message_id = None
        self.slice_order_id = None
        self.last_slice_state = State.Pending
        self.parent_state = State.Pending

    def __repr__(self) -> str:
        return str(
            {
                "state": self.last_slice_state,
                "message_id": self.slice_message_id,
                "order_id": self.slice_order_id,
                "side": self.side,
                "limit_price": self.limit_price,
                "slice_size": self.slice_size,
                "slice_filled_quantity": self.slice_filled_quantity,
            }
        )

    def submit(self) -> None:
        self.slice_filled_quantity = 0
        self.slice_order_id = None
        self.slice_message_id = self.client.send_create_order_request(
            self.slice_size, self.limit_price, self.side
        )
        self.last_slice_state = State.Sent
        if self.parent_state != State.PartiallyFilled:
            self.parent_state = State.Sent

    def evaluate_and_slice(self):
        if self.slice_filled_quantity == self.slice_size:
            self.last_slice_state = State.Filled
        elif self.slice_filled_quantity > 0:
            self.last_slice_state = State.PartiallyFilled
        else:
            self.last_slice_state = State.Working

        if self.filled_quantity == self.total_quantity:
            self.parent_state = State.Filled
        elif self.filled_quantity > 0:
            self.parent_state = State.PartiallyFilled
        else:
            self.parent_state = State.Working

        if (
            self.last_slice_state == State.Filled
            and self.filled_quantity < self.total_quantity
        ):
            # Filled slice, slice some more
            self.submit()

    def slice_created(self, order_id: str, status: bool) -> None:
        if not status:
            logger.warning("Order slice  %s creation rejected", order_id)
            self.last_slice_state = State.Rejected
            self.parent_state = State.Rejected
            return
        self.slice_order_id = order_id
        self.last_slice_state = State.Working
        self.parent_state = State.Working

    def slice_fill(self, filled_quantity: int, status: bool) -> int:
        if not status:
            logger.warning("Received Unsuccesful fill %s ", self.slice_order_id)
            return 0
        new_filled_quantity = filled_quantity - self.slice_filled_quantity
        self.slice_filled_quantity = filled_quantity
        self.filled_quantity += new_filled_quantity
        self.evaluate_and_slice()

        return new_filled_quantity

    def revise(self, revised_quantity: int, revised_price: float) -> None:
        logger.info(
            "Received revise request, revised_quantity: %s and revised_price: %s",
            revised_quantity,
            revised_price,
        )
        if self.parent_state not in ACTIVE_STATES or not self.slice_order_id:
            logger.error(
                "Order is of %s state and can not be revised",
                self.parent_state,
            )
            return

        if revised_quantity <= self.filled_quantity:
            logger.error(
                "Can not update quantity to %s, already filled %s",
                revised_quantity,
                self.filled_quantity,
            )
            return

        revised_open_quantity = revised_quantity - self.filled_quantity
        slice_open_quantity = self.slice_size - self.slice_filled_quantity
        if revised_open_quantity == 0:
            logger.info(
                "Cancelling outstanding slice as the revised quantity is already filled"
            )
            self.client.send_cancel_order_request(self.slice_order_id)
            self.last_slice_state = State.CancelSent
            self.parent_state = State.CancelSent
            return
        elif slice_open_quantity > revised_open_quantity:
            logger.info(
                "Revising down outstanding slice size to %s", slice_open_quantity
            )
            self.client.send_revise_order_request(
                self.slice_order_id,
                slice_open_quantity,
                revised_price,
            )
            self.last_slice_state = State.ReviseSent
            self.parent_state = State.ReviseSent
            return
        elif self.limit_price != revised_price:
            logger.info("Sending revise price request")
            self.client.send_revise_order_request(
                self.slice_order_id, self.slice_size, revised_price
            )
            self.last_slice_state = State.ReviseSent
            self.parent_state = State.ReviseSent
            return
        self.total_quantity = revised_quantity
        self.limit_price = revised_price
        logger.info("Updated hidden quantity and price: %s", self)

    def revised(
        self, revised_quantity: int, revised_price: float, status: boolean
    ) -> None:
        if self.last_slice_state != State.ReviseSent:
            logger.info("Slice already moved on, no awaiting revise.")
            return

        if not status:
            self.last_slice_state = State.Working
            self.parent_state = State.Working
            return

        self.slice_size = revised_quantity
        self.limit_price = revised_price

        self.evaluate_and_slice()

    def cancel(self) -> None:
        if self.last_slice_state not in ACTIVE_STATES or not self.slice_order_id:
            logger.warning("Your order is in Transient State and cannot be modified")
            return

        self.client.send_cancel_order_request(self.slice_order_id)
        self.last_slice_state = State.CancelSent
        self.parent_state = State.CancelSent

    def cancelled(self, status: boolean) -> None:
        if self.last_slice_state != State.CancelSent:
            logger.info("Slice already moved on, no awaiting cancel.")
            return

        if not status:
            self.last_slice_state = State.Working
            self.parent_state = State.Working
            return

        self.last_slice_state = State.Cancelled
        self.parent_state = State.Cancelled
