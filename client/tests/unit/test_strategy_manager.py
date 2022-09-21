import logging
from unittest import mock

import pytest

from client.globals import State
from client.strategy_manager import StrategyManager
from message.message import Side

logger = logging.getLogger(__name__)


DEFAULT_PRICE = 100.00
DEFAULT_QTY = 10
DEFAULT_SIDE = Side.Buy
DEFAULT_MSG_ID = "Test_Strategy"
DEFAULT_FILLED_QTY = 0
DEFAULT_SLICE_SIZE = 10
DEFAULT_REVISED_QTY = 20
DEFAULT_REVISED_PRICE = 150.00
DEFAULT_ORDER_ID = "1234"


@pytest.fixture
def strategy_manager():
    return StrategyManager(mock.Mock())


@pytest.fixture
def order_id(strategy_manager):
    strategy_manager.create_iceberg(
        side=DEFAULT_SIDE,
        quantity=DEFAULT_QTY,
        limit_price=DEFAULT_PRICE,
        slice_size=DEFAULT_SLICE_SIZE,
    )

    return next(iter(strategy_manager.orders.keys()))


@pytest.fixture
def given_acked_order(exchange_create_response):
    strategy_manager.on_create_resp(exchange_create_response)


@pytest.fixture
def fill_order_id(strategy_manager, order_id):
    slice = strategy_manager.orders[order_id]["iceberg_order"]
    strategy_manager.orders[order_id]["state"] = State.Filled
    strategy_manager.orders[order_id]["filled_quantity"] = 10
    slice.last_slice_state = State.Filled
    slice.parent_slice_state = State.Filled
    slice.slice_order_id = DEFAULT_ORDER_ID
    slice.slice_filled_quantity = 10
    slice.filled_quantity = 10
    strategy_manager.orders[order_id]["iceberg_order"] = slice

    return next(iter(strategy_manager.orders.keys()))


@pytest.fixture
def exchange_create_response(strategy_manager, order_id):
    slice = strategy_manager.orders[order_id]["iceberg_order"]
    return {
        "name": "OrderResponse",
        "client_msg_id": slice.slice_message_id,
        "client_id": "ceaba6cb06ee4e5ba39e84af4d01a55c",
        "order_params": {
            "limit_price": DEFAULT_PRICE,
            "quantity": DEFAULT_SLICE_SIZE,
            "side": "buy",
            "symbol": "AUTOTRAD Equity",
            "filled_quantity": 0,
            "exch_order_id": DEFAULT_ORDER_ID,
            "status": "ack",
        },
        "status": True,
        "status_msg": "Successful order creation",
    }


@pytest.fixture
def exchange_revise_response(strategy_manager, order_id):
    slice = strategy_manager.orders[order_id]["iceberg_order"]
    return {
        "name": "OrderResponse",
        "client_msg_id": slice.slice_message_id,
        "client_id": "369ceee4969c4b50bef16fb2d6652ab2",
        "order_params": {
            "limit_price": 100,
            "quantity": 5,
            "side": "buy",
            "symbol": "AUTOTRAD Equity",
            "filled_quantity": 0,
            "exch_order_id": DEFAULT_ORDER_ID,
            "status": "ack",
        },
        "status": True,
        "status_msg": "Revise order successful",
    }


@pytest.fixture
def exchange_cancel_response(strategy_manager, order_id):
    slice = strategy_manager.orders[order_id]["iceberg_order"]
    return {
        "name": "OrderResponse",
        "client_msg_id": slice.slice_message_id,
        "client_id": "9a440016815e415e9f8fa474af383703",
        "order_params": {
            "limit_price": DEFAULT_PRICE,
            "quantity": DEFAULT_SLICE_SIZE,
            "side": "buy",
            "symbol": "AUTOTRAD Equity",
            "filled_quantity": 0,
            "exch_order_id": DEFAULT_ORDER_ID,
            "status": "cancelled",
        },
        "status": True,
        "status_msg": "Order cancellation is successful",
    }


@pytest.fixture
def given_order_is_filled(strategy_manager, order_id):
    mock_response = {
        {
            "name": "FillOrderResponse",
            "order_params": {
                "limit_price": 100,
                "quantity": 10,
                "side": "buy",
                "symbol": "AUTOTRAD Equity",
                "filled_quantity": 10,
                "exch_order_id": DEFAULT_ORDER_ID,
                "status": "filled",
            },
            "client_id": "2285deab75cb448ebf7d784482550861",
            "trade": {
                "quantity": 10,
                "limit_price": 100,
                "symbol": "AUTOTRAD Equity",
                "exch_order_id": DEFAULT_ORDER_ID,
                "trade_id": "FillId-1663719822.706924",
                "fill_type": "Complete Fill",
                "side": "buy",
            },
            "status": True,
            "status_msg": "Order filled successfully",
        }
    }
    strategy_manager.on_fill_response(mock_response)
    parent_order_id = next(iter(strategy_manager.orders.keys()))
    return parent_order_id


def test_ordercreation(strategy_manager, order_id):
    # then
    assert strategy_manager.orders[order_id]["state"] == State.Sent
    assert strategy_manager.orders[order_id]["iceberg_order"]
    assert strategy_manager.orders[order_id]["limit_price"] == DEFAULT_PRICE
    assert strategy_manager.orders[order_id]["side"] == DEFAULT_SIDE
    assert strategy_manager.orders[order_id]["quantity"] == DEFAULT_QTY
    assert strategy_manager.orders[order_id]["filled_quantity"] == DEFAULT_FILLED_QTY


def test_on_create_resp(exchange_create_response, order_id, strategy_manager):
    # When
    strategy_manager.on_create_resp(exchange_create_response)

    # Then
    assert (
        strategy_manager.orders[order_id]["state"]
        == strategy_manager.orders[order_id]["iceberg_order"].last_slice_state
    )


def test_revise_pass(exchange_create_response, order_id, strategy_manager):
    # Given
    strategy_manager.on_create_resp(exchange_create_response)

    # When
    print(strategy_manager.orders)
    strategy_manager.revise(
        order_id=order_id,
        revised_quantity=DEFAULT_REVISED_QTY,
        revised_limit_price=DEFAULT_REVISED_PRICE,
    )

    # Then
    assert strategy_manager.orders[order_id]["quantity"] == DEFAULT_REVISED_QTY
    assert strategy_manager.orders[order_id]["limit_price"] == DEFAULT_REVISED_PRICE


def test_revise_fail(order_id, strategy_manager, caplog, exchange_create_response):

    # When
    strategy_manager.revise(
        order_id=order_id,
        revised_quantity=DEFAULT_REVISED_QTY,
        revised_limit_price=DEFAULT_PRICE,
    )

    # Then
    assert "is of State.Sent state and can not be revised" in caplog.text


def test_revise_order_qty_less_order_filled_fail(
    exchange_create_response, strategy_manager, fill_order_id, caplog
):
    # Given
    strategy_manager.on_create_resp(exchange_create_response)

    strategy_manager.revise(
        order_id=fill_order_id, revised_quantity=5, revised_limit_price=DEFAULT_PRICE
    )
    # Then
    assert "Can not update quantity to 5, already filled 10" in caplog.text


def test_cancel(
    order_id, strategy_manager, exchange_create_response, exchange_cancel_response
):
    strategy_manager.on_create_resp(exchange_create_response)

    # When
    strategy_manager.cancel(order_id)

    # Then
    assert strategy_manager.orders[order_id]["state"] == State.CancelSent

    strategy_manager.on_cancel_resp(exchange_cancel_response)

    assert strategy_manager.orders[order_id]["state"] == State.Cancelled
