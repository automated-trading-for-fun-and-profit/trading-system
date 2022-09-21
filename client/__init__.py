import logging

from .globals import Side
from .trading_app import (cancel, connect, create_iceberg, disconnect, revise,
                          status)

logging.basicConfig(
    filename="trading_app.log",
    filemode="w",
    format="%(asctime)s:%(levelname)s:%(module)s:%(lineno)d:%(message)s",
    encoding="utf-8",
    level=logging.INFO,
)

__all__ = [
    "Side",
    "cancel",
    "connect",
    "create_iceberg",
    "disconnect",
    "revise",
    "status",
]
