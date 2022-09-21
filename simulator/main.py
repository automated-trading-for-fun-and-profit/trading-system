import logging

from flask import Flask, render_template
from flask_socketio import SocketIO, emit, join_room

from .order import Side
from .order_book import OrderBook

app = Flask(__name__)
socketio = SocketIO(app, async_mode=None, logger=True, engineio_logger=True)
order_book = OrderBook()
logger = logging.getLogger(__name__)


@app.route("/market", methods=["GET"])
def market():
    context = {"title": "Market Depth", "quotes": order_book.get_market_depth()}
    return render_template("market_depth.html", **context)


@socketio.on("create")
def handle_create(request):
    logging.info("Received Create Order request: %s", request)

    room_id = get_room_id(request)

    create_resp, fill_resp = order_book.create_order_request(
        side=Side(request["side"]),
        client_msg_id=request["client_msg_id"],
        quantity=request["quantity"],
        limit_price=request["limit_price"],
        client_id=request["client_id"],
    )

    for resp in create_resp:
        logging.info("Sending create_resp: %s", resp)
        send_response("create_resp", resp, room_id)
    for resp in fill_resp:
        logging.info("Sending fill_resp: %s", resp)
        send_response("fill_resp", resp, room_id)


@socketio.on("revise")
def handle_revise(request):
    logging.info("Received Revise Order request: %s", request)
    room_id = get_room_id(request)
    revise_resp = order_book.revise_order_request(
        client_msg_id=request.get("client_msg_id"),
        client_id=request["client_id"],
        order_id=request.get("order_id"),
        revised_quantity=request.get("revised_quantity"),
        revised_price=request.get("revised_price"),
    )
    for resp in revise_resp:
        logging.info("Sending revise_resp: %s", resp)
        send_response("revise_resp", resp, room_id)


@socketio.on("cancel")
def handle_cancel(request):
    logging.info("Received Cancel Order Request: %s", request)
    room_id = get_room_id(request)
    cancel_resp = order_book.cancel_order_request(
        client_msg_id=request.get("client_msg_id"),
        client_id=request["client_id"],
        order_id=request.get("order_id"),
    )
    for resp in cancel_resp:
        logging.info("Sending cancel_resp: %s", resp)
        send_response("cancel_resp", resp, room_id)


def get_room_id(request):
    room_id = request.get("client_id", None)
    join_room(room_id)
    return room_id


def send_response(msg, order_response, request_client_id):
    response_client_id = getattr(order_response, "client_id", None)

    if request_client_id == response_client_id:
        emit(msg, order_response.to_json(), to=response_client_id)


def initialize_order_book():
    quotes = [
        (Side.Sell, 10, 101.34),
        (Side.Sell, 19, 102.5),
        (Side.Sell, 21, 104.5),
        (Side.Sell, 15, 101.34),
        (Side.Buy, 10, 99.34),
        (Side.Buy, 2, 98.34),
        (Side.Buy, 7, 98.34),
    ]
    cntr = 0
    for side, quantity, limit_price in quotes:
        cntr = cntr + 1
        order_book.create_order_request(
            side=side,
            client_msg_id=f"init-order-{cntr}",
            client_id="12345",
            quantity=quantity,
            limit_price=limit_price,
        )


if __name__ == "__main__":
    logging.basicConfig(
        filename="exch_simulator.log",
        filemode="w",
        format="%(asctime)s:%(levelname)s:%(module)s:%(lineno)d:%(message)s",
        encoding="utf-8",
        level=logging.DEBUG,
    )
    initialize_order_book()
    socketio.run(app, host="127.0.0.1", port=5000, debug=True)
