from message.message import Side

from .exchange_client import ExchangeClient
from .globals import State


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
        self.state = State.Pending
        self.parent_state = State.Pending

    def __repr__(self) -> str:
        return str(
            {
                "state": self.state,
                "message_id": self.slice_message_id,
                "order_id": self.slice_order_id,
                "side": self.side,
                "limit_price": self.limit_price,
                "slice_size": self.slice_size,
                "slice_filled_quantity": self.slice_filled_quantity,
            }
        )

    def submit(self) -> None:
        """Create a slice for the order and send it to the exchange.
        Interact with the exchange simulator through self.client and keep track of the order
        by its message ID.
        """
        pass

    def slice_created(self, order_id: str, status: bool) -> None:
        """Callback of a slice that has been created."""
        pass

    def slice_fill(self, filled_quantity: int, status: bool) -> int:
        """Callback for a slice getting filled partially or fully."""
        pass

    def revise(self, revised_quantity: int, revised_price: float) -> None:
        """Revise a parent order by updating its iceberg slice.
        The slice should be updated accordingly to what we need for the parent, may need to do
        nothing, cancel the last slice or revise the last slice.
        Note: Not all states of a slice can be updated. ACTIVE_STATES are good to update.
        """
        pass

    def revised(
        self, revised_quantity: int, revised_price: float, status: bool
    ) -> None:
        """Callback of a slice that has been revised."""
        pass

    def cancel(self) -> None:
        """Cancel a slice if possible.
        Note: Not all states of a slice can be updated. ACTIVE_STATES are good to update.
        """
        pass

    def cancelled(self, status: bool) -> None:
        """Callback of a slice that has been cancelled."""
        pass
