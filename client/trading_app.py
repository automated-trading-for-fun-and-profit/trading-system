import logging

import socketio

from message.message import Side

from .exchange_client import ExchangeClient
from .globals import ORDER_SIDES
from .strategy_manager import StrategyManager

client = ExchangeClient(socketio.Client())
strategy_manager = StrategyManager(client)
client.connect()
logger = logging.getLogger(__name__)


def status(order_id=None) -> None:
    strategy_manager.print_status(order_id)


def create_iceberg(
    side: Side, quantity: int, limit_price: float, slice_size: int
) -> None:
    if side not in ORDER_SIDES:
        logger.error("Order can only be of types %s, got %s", ORDER_SIDES, side)
        return

    strategy_manager.create_iceberg(side, quantity, limit_price, slice_size)


def revise(order_id: str, revised_quantity: int, revised_price: float) -> None:
    strategy_manager.revise(order_id, revised_quantity, revised_price)


def cancel(order_id: str) -> None:
    strategy_manager.cancel(order_id)


def connect() -> None:
    client.connect()


def disconnect() -> None:
    client.disconnect()
