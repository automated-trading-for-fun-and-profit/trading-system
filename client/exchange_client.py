import logging
import uuid
from enum import Enum
from typing import Callable, Dict

import socketio

from .globals import Side

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    Ack = "ack"
    PartiallyFilled = "partially_filled"
    Filled = "filled"
    Cancelled = "cancelled"


class ExchMsgType(Enum):
    CreateResp = "create_resp"
    ReviseResp = "revise_resp"
    CancelResp = "cancel_resp"


class ExchangeClient:
    def __init__(self, socketio_client: socketio.Client):
        self._sio = socketio_client
        self._response_handler = lambda: logging.warning(
            "Exchange Response Handler is not set"
        )
        self.client_id = uuid.uuid4().hex

    def connect(self, url: str = "http://127.0.0.1:5000") -> None:
        self._sio.connect(url)

    def disconnect(self) -> None:
        self._sio.disconnect()

    def register_callbacks(
        self,
        create_callback: Callable,
        fill_callback: Callable,
        revise_callback: Callable,
        cancel_callback: Callable,
    ):
        self._create_handler = create_callback
        self._fill_handler = fill_callback
        self._revise_handler = revise_callback
        self._cancel_handler = cancel_callback
        self._setup_handlers()

    def send_create_order_request(
        self,
        quantity: int,
        limit_price: float,
        side: Side,
    ) -> str:
        create_request = {
            "client_msg_id": uuid.uuid4().hex,
            "client_id": self.client_id,
            "quantity": quantity,
            "limit_price": limit_price,
            "side": side.value,
        }
        logger.info("Sending create order request: %s", create_request)
        self._sio.emit("create", create_request)
        return create_request["client_msg_id"]

    def send_revise_order_request(
        self,
        order_id: str,
        revised_qty: int,
        revised_price: float,
    ) -> str:
        revise_request = {
            "client_msg_id": uuid.uuid4().hex,
            "client_id": self.client_id,
            "order_id": order_id,
            "revised_quantity": revised_qty,
            "revised_price": revised_price,
        }
        logger.info("Sending revise order request: %s", revise_request)
        self._sio.emit("revise", revise_request)
        return revise_request["client_msg_id"]

    def send_cancel_order_request(
        self,
        order_id: str,
    ) -> str:
        cancel_request = {
            "client_msg_id": uuid.uuid4().hex,
            "client_id": self.client_id,
            "order_id": order_id,
        }
        logger.info("Sending cancel order request: %s", cancel_request)
        self._sio.emit("cancel", cancel_request)
        return cancel_request["client_msg_id"]

    def _setup_handlers(self):
        @self._sio.event
        def connect():
            logger.info("Connection established")

        @self._sio.event
        def disconnect():
            logger.error("Disconnected from the exchange")

        @self._sio.event
        def connect_error(data):
            logger.error("The connection to the exchange failed: %s", data)

        def pre_handle_response(event: str, data: Dict) -> bool:
            if data["client_id"] != self.client_id:
                logger.error(
                    "Current client ID: %s, received: %s",
                    self.client_id,
                    data["client_id"],
                )
                return False
            level = logging.INFO if data["status"] else logging.ERROR
            logger.log(level, f"Received {event} with {data}")
            return True

        @self._sio.on("create_resp")
        def on_created(data: Dict):
            if pre_handle_response("create", data):
                self._create_handler(data)

        @self._sio.on("fill_resp")
        def on_filled(data: Dict):
            if pre_handle_response("fill", data):
                self._fill_handler(data)

        @self._sio.on("revise_resp")
        def on_revised(data: Dict):
            if pre_handle_response("revise", data):
                self._revise_handler(data)

        @self._sio.on("cancel_resp")
        def on_cancelled(data: Dict):
            if pre_handle_response("cancel", data):
                self._cancel_handler(data)

        @self._sio.on("*")
        def catch_all(event, data: Dict):
            if pre_handle_response(event, data):
                logger.warning(f"Unknown event {event} with response: {data}")
