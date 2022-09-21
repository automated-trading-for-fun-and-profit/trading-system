import logging
import threading
import uuid
from datetime import datetime
from pprint import pprint
from typing import Dict, Optional

from .exchange_client import ExchangeClient
from .globals import COMPLETED_STATES, Side, State
from .iceberg_order import IcebergOrder

logger = logging.getLogger(__name__)


class StrategyManager:
    def __init__(self, client: ExchangeClient):
        self.orders = {}
        self.lock = threading.Lock()
        client.register_callbacks(
            self.on_create_resp,
            self.on_fill_resp,
            self.on_revise_resp,
            self.on_cancel_resp,
        )
        self.client = client

    def get_iceberg_order_parent(
        self, order_id: str, message_id: Optional[str] = None
    ) -> Optional[str]:
        for parent_id, order in self.orders.items():
            manager = order["iceberg_order"]
            if manager.slice_order_id == order_id or (
                message_id and manager.slice_message_id == message_id
            ):
                return parent_id
        logger.error(
            "Could not find parent for order ID %s and message ID %s",
            order_id,
            message_id,
        )
        return None

    def create_iceberg(
        self, side: Side, quantity: int, limit_price: float, slice_size: int
    ) -> None:
        parent_id = uuid.uuid4().hex
        self.orders[parent_id] = {
            "parent_id": parent_id,
            "side": side,
            "quantity": quantity,
            "filled_quantity": 0,
            "limit_price": limit_price,
            "state": State.Sent,
            "updated_at": datetime.now(),
            "iceberg_order": IcebergOrder(
                self.client, quantity, slice_size, side, limit_price
            ),
        }
        self.orders[parent_id]["iceberg_order"].submit()

    def on_create_resp(self, data: Dict) -> None:

        order_id = data["order_params"]["exch_order_id"]
        parent_id = self.get_iceberg_order_parent(order_id, data["client_msg_id"])
        if not parent_id:
            return

        if data["name"] == "FillOrderResponse":
            self.on_fill_resp(data)
        elif data["name"] == "OrderResponse":
            self.orders[parent_id]["iceberg_order"].slice_created(
                order_id,
                data["status"],
            )

            with self.lock:
                parent = self.orders[parent_id]
                parent["updated_at"] = datetime.now()
                parent["state"] = parent["iceberg_order"].parent_state
                self.orders[parent_id] = parent
        else:
            logger.warning("Received unexpected message %s", data)

    def on_fill_resp(self, data: Dict) -> None:
        logger.info("on_fill_resp: %s", data)
        order_id = data["order_params"]["exch_order_id"]
        parent_id = self.get_iceberg_order_parent(order_id)
        if not parent_id:
            return
        filled_quantity = self.orders[parent_id]["iceberg_order"].slice_fill(
            data["order_params"]["filled_quantity"],
            data["status"],
        )

        with self.lock:
            parent = self.orders[parent_id]
            parent["filled_quantity"] += filled_quantity
            parent["updated_at"] = datetime.now()
            parent["state"] = parent["iceberg_order"].parent_state
            self.orders[parent_id] = parent

    def revise(
        self, order_id: str, revised_quantity: int, revised_limit_price: float
    ) -> None:
        with self.lock:
            order = self.orders.get(order_id)
            if not order:
                logger.error("Could not find order with ID %s to revise it.", order_id)
                return

            order["iceberg_order"].revise(revised_quantity, revised_limit_price)
            order["quantity"] = revised_quantity
            order["limit_price"] = revised_limit_price
            order["state"] = order["iceberg_order"].parent_state
            order["updated_at"] = datetime.now()

            self.orders[order_id] = order

    def on_revise_resp(self, data: Dict) -> None:
        logger.info("on_revise_resp: %s", data)
        message_name = data["name"]
        if message_name == "FillOrderResponse":
            self.on_fill_resp(data)
            return

        if message_name != "OrderResponse":
            logger.error("Received unexpected message %s", data)
            return

        with self.lock:
            if not data["status"]:
                logger.warning("Received an error on revise response %s", data)
                return

            order_id = data["order_params"]["exch_order_id"]
            parent_id = self.get_iceberg_order_parent(order_id, data["client_msg_id"])
            if not parent_id:
                return

            parent = self.orders[parent_id]
            parent["iceberg_order"].revised(
                data["order_params"]["quantity"],
                data["order_params"]["limit_price"],
                data["status"],
            )
            parent["updated_at"] = datetime.now()
            parent["state"] = parent["iceberg_order"].parent_state
            self.orders[parent_id] = parent

    def cancel(self, order_id: str) -> None:
        parent = self.orders.get(order_id)
        if not parent:
            logger.error("Could not find parent for order ID %s.", order_id)
            return
        with self.lock:
            parent["iceberg_order"].cancel()
            parent["updated_at"] = datetime.now()
            parent["state"] = parent["iceberg_order"].parent_state
            self.orders[order_id] = parent

    def on_cancel_resp(self, data: Dict) -> None:
        order_id = data["order_params"]["exch_order_id"]
        parent_id = self.get_iceberg_order_parent(order_id, data["client_msg_id"])
        if not parent_id:
            return

        with self.lock:
            parent = self.orders[parent_id]
            parent["iceberg_order"].cancelled(data["status"])
            parent["updated_at"] = datetime.now()
            parent["state"] = parent["iceberg_order"].parent_state
            self.orders[parent_id] = parent

    def print_status(self, order_id=None) -> None:
        if order_id:
            print(self.orders.get(order_id, f"Order ID {order_id} not found"))
        filled = sorted(
            [
                value
                for value in self.orders.values()
                if value["state"] in COMPLETED_STATES
            ],
            key=lambda x: x["updated_at"],
            reverse=True,
        )
        pending = sorted(
            [
                value
                for value in self.orders.values()
                if value["state"] not in COMPLETED_STATES
            ],
            key=lambda x: x["updated_at"],
            reverse=True,
        )
        print("Completed orders:")
        pprint(filled)
        print("Pending orders:")
        pprint(pending)
