import pytest

from simulator.order import (DEFAULT_SYMBOL, Order, OrderStatus, Side, Trade,
                             TradeFillType)

DEFAULT_PRICE = 100.10
DEFAULT_QTY = 5
DEFAULT_SIDE = Side.Buy
DEFAULT_MSG_ID = "MsgId"
DEFAULT_CLIENT_ID = "TestClient"


@pytest.fixture
def order() -> Order:
    return Order(
        limit_price=DEFAULT_PRICE,
        quantity=DEFAULT_QTY,
        side=DEFAULT_SIDE,
        client_msg_id=DEFAULT_MSG_ID,
        client_id=DEFAULT_CLIENT_ID,
    )


def test_order_creation(order):
    assert order.exch_order_id
    assert order.quantity == DEFAULT_QTY
    assert order.open_quantity() == DEFAULT_QTY
    assert order.limit_price == DEFAULT_PRICE
    assert order.side == Side.Buy
    assert order.symbol == DEFAULT_SYMBOL
    assert order._trades == []
    assert order.status == OrderStatus.Ack


def test_complete_fill_success(order):
    # Given
    expected_qty = DEFAULT_QTY
    expected_price = DEFAULT_PRICE
    expected_trade_id = "test_id_xxx"
    expected_trade = Trade(
        quantity=expected_qty,
        limit_price=expected_price,
        exch_order_id=order.exch_order_id,
        trade_id=expected_trade_id,
        fill_type=TradeFillType.CompleteFill,
        symbol=DEFAULT_SYMBOL,
        side=DEFAULT_SIDE,
    )

    # When
    fill_response = order.fill(
        quantity=expected_qty,
        price=expected_price,
        trade_id=expected_trade_id,
    )

    # Then
    assert order.open_quantity() == 0
    assert order.status == OrderStatus.Filled
    assert len(order._trades) == 1
    assert order._trades[0].to_json() == expected_trade.to_json()
    assert fill_response.status
    assert fill_response.status_msg == "Order filled successfully"
    assert fill_response.trade.to_json() == expected_trade.to_json()


def test_fill_qty_cannot_be_more_than_open_qty(order):
    # Given
    fill_qty = DEFAULT_QTY + 2
    expected_msg = (
        f"Fill quantity {fill_qty} cannot be more than the open quantity "
        f"{DEFAULT_QTY}"
    )

    # When
    with pytest.raises(ValueError) as error:
        order.fill(
            quantity=fill_qty,
            price=100.0,
            trade_id="test_trade_id",
        )
    assert expected_msg in str(error)


def test_partial_fill_status(order):
    # Given
    fill_qty = DEFAULT_QTY - 2
    expected_trade_id = "XXYYZZ"
    expected_trade = Trade(
        quantity=fill_qty,
        limit_price=DEFAULT_PRICE,
        exch_order_id=order.exch_order_id,
        trade_id=expected_trade_id,
        fill_type=TradeFillType.PartialFill,
        symbol=DEFAULT_SYMBOL,
        side=DEFAULT_SIDE,
    )

    # When
    fill_response = order.fill(
        quantity=fill_qty,
        price=DEFAULT_PRICE,
        trade_id=expected_trade_id,
    )

    # Then
    assert fill_response.status
    assert fill_response.status_msg == "Order filled successfully"
    assert fill_response.trade.to_json() == expected_trade.to_json()

    assert order.open_quantity() == 2
    assert len(order._trades) == 1
    assert order._trades[0].to_json() == expected_trade.to_json()
    assert order.status == OrderStatus.PartiallyFilled
    assert order.quantity == DEFAULT_QTY
    assert order.client_id == DEFAULT_CLIENT_ID


def test_order_cancel_success(order):
    # Given
    client_id = "test_client_xx"

    # When
    response = order.cancel(client_msg_id="test-cancel-req", client_id=client_id)

    # Then
    assert order.status == OrderStatus.Cancelled
    assert response.status
    assert response.status_msg == "Order cancellation is successful"
    assert response.client_id == client_id


def test_filled_order_cannot_be_cancelled(order):
    # When
    fill_response = order.fill(
        quantity=DEFAULT_QTY,
        price=DEFAULT_PRICE,
        trade_id="test_trade_id",
    )

    # Then
    assert fill_response.status
    assert order.status == OrderStatus.Filled

    # When
    cancel_response = order.cancel(
        client_msg_id="Test-cancel-req", client_id="test_client_xx"
    )

    # Then
    assert not cancel_response.status
    assert cancel_response.status_msg == "Filled order cannot be cancelled"
