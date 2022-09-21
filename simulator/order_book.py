import copy
import logging
import time
from dataclasses import dataclass
from itertools import zip_longest
from typing import Iterable, List, Optional, Tuple, TypedDict

from sortedcontainers import SortedList

from .order import (Order, OrderResponse, OrderStatus, Response, Side,
                    ack_response)

logger = logging.getLogger(__name__)

DEFAULT_ORDER_BOOK_SYMBOL = "AUTOTRAD Equity"


class OrderMap(TypedDict):
    exch_ord_id: str
    order: Order


@dataclass
class PriceLevel:
    price: float
    order_ids: List[str]


@dataclass
class OrderBook:
    def __init__(self, symbol: str = DEFAULT_ORDER_BOOK_SYMBOL):
        self.order_book_dict = {
            "asks": SortedList([]),
            "bids": SortedList([]),
            "completed_orders": {},
            "symbol": symbol,
        }

    def create_order_request(
        self,
        side: Side,
        client_msg_id: str,
        client_id: str,
        quantity: int,
        limit_price: float,
    ) -> Tuple[List, List]:
        order = Order(
            limit_price=limit_price,
            quantity=quantity,
            side=side,
            symbol=self.order_book_dict["symbol"],
            client_msg_id=client_msg_id,
            client_id=client_id,
        )
        create_responses: List[OrderResponse] = [
            copy.deepcopy(ack_response(client_msg_id, client_id, order))
        ]
        fill_responses: List[Response] = self._evaluate_order_match(order)
        return create_responses, fill_responses

    def revise_order_request(
        self,
        client_msg_id: str,
        client_id: str,
        order_id: str,
        revised_quantity: Optional[int] = None,
        revised_price: Optional[float] = None,
    ) -> List[Response]:
        try:
            order = self._validated_order(order_id)
            revise_resp = order.revise(
                client_msg_id=client_msg_id,
                client_id=client_id,
                revised_qty=revised_quantity,
                revised_price=revised_price,
            )
            fill_resp = self._evaluate_order_match(order)
            fill_resp.insert(0, revise_resp)
            return fill_resp
        except ValueError as err:
            return [
                OrderResponse(
                    client_msg_id=client_msg_id,
                    client_id=client_id,
                    order_params=None,
                    status=False,
                    status_msg=str(err),
                )
            ]

    def cancel_order_request(
        self, client_msg_id: str, client_id: str, order_id: str
    ) -> Iterable[OrderResponse]:
        try:
            order = self._validated_order(order_id)
            cancel_msg = order.cancel(client_msg_id=client_msg_id, client_id=client_id)
            self._update_order_book(order, [], [])
            return [cancel_msg]

        except ValueError as err:
            return [
                OrderResponse(
                    client_msg_id=client_msg_id,
                    client_id=client_id,
                    order_params=None,
                    status=False,
                    status_msg=str(err),
                )
            ]

    def reset(self) -> None:
        pass

    def get_market_depth(self) -> List:
        bid_market_depth = []
        ask_market_depth = []
        market_depth = []
        bids = self.order_book_dict.get("bids", SortedList([]))
        for bid in bids:
            bid_market_depth = OrderBook._build_market_depth(
                order=bid, market_depth=bid_market_depth
            )

        asks = self.order_book_dict.get("asks", SortedList([]))
        for ask in asks:
            ask_market_depth = OrderBook._build_market_depth(
                order=ask, market_depth=ask_market_depth
            )

        for bid_depth, ask_depth in zip_longest(bid_market_depth, ask_market_depth):
            market_depth_elem = {
                "bid": "",
                "bid_volume": "",
                "ask": "",
                "ask_volume": "",
            }
            if bid_depth:
                market_depth_elem.update(bid_depth)
            if ask_depth:
                market_depth_elem.update(ask_depth)
            if market_depth_elem["bid"] != "" or market_depth_elem["ask"] != "":
                market_depth.append(market_depth_elem)
        return market_depth

    @staticmethod
    def _build_market_depth(order: Order, market_depth: List):
        key = "bid" if order.side == Side.Buy else "ask"
        key_volume = f"{key}_volume"
        prev_elem = market_depth[-1] if len(market_depth) > 0 else None
        if prev_elem and order.limit_price == prev_elem[key]:
            prev_elem[key_volume] = prev_elem[key_volume] + order.open_quantity()
        else:
            market_depth_row = {
                key: order.limit_price,
                key_volume: order.open_quantity(),
            }
            market_depth.append(market_depth_row)
        return market_depth

    def _evaluate_order_match(self, order: Order) -> List[Response]:
        responses: List[Response] = []

        cross_quotes = self._cross_quote_list(order)
        completed_quote_list = []
        for quote in cross_quotes:
            if order.status == OrderStatus.Filled:
                break
            price_matched = (
                quote.limit_price >= order.limit_price
                if order.side == Side.Sell
                else quote.limit_price <= order.limit_price
            )
            logger.info(
                "Order: %s Quote: %s Price matched %s", order, quote, price_matched
            )

            if price_matched:
                fill_qty = (
                    order.open_quantity()
                    if quote.open_quantity() >= order.open_quantity()
                    else quote.open_quantity()
                )
                trade_id = f"FillId-{time.time()}"
                trade_price = order.limit_price
                try:
                    fill_response = copy.deepcopy(
                        order.fill(fill_qty, trade_price, trade_id)
                    )
                    responses.append(fill_response)
                    cross_fill_response = quote.fill(fill_qty, trade_price, trade_id)
                    responses.append(cross_fill_response)
                except ValueError as err:
                    logger.warning(str(err))
                if quote.status == OrderStatus.Filled:
                    completed_quote_list.append(quote)
            else:
                break
        self._update_order_book(order, completed_quote_list, cross_quotes)
        return responses

    def _update_order_book(
        self,
        order: Order,
        completed_cross_quotes: List[Order],
        cross_quotes: SortedList[Order],
    ) -> None:
        for cross_quote in completed_cross_quotes:
            cross_quotes.remove(cross_quote)
            self.order_book_dict["completed_orders"][
                cross_quote.exch_order_id
            ] = cross_quote

        for cross_quote in cross_quotes:
            logger.info("Updated cross quote list %s", cross_quote)
        quote_list = self._quotes_list(order)

        if order.status == OrderStatus.Filled or order.status == OrderStatus.Cancelled:
            self.order_book_dict["completed_orders"][order.exch_order_id] = order
            quote_list.discard(order)
        else:
            # Remove if same element existed already and insert again
            quote_list.discard(order)
            quote_list.add(order)

    def _quotes_list(self, order: Order) -> SortedList[Order]:
        return (
            self.order_book_dict.get("bids", SortedList([]))
            if order.side == Side.Buy
            else self.order_book_dict.get("asks", SortedList([]))
        )

    def _cross_quote_list(self, order: Order) -> SortedList[Order]:
        return (
            self.order_book_dict.get("asks", SortedList([]))
            if order.side == Side.Buy
            else self.order_book_dict.get("bids", SortedList([]))
        )

    def _validated_order(self, order_id: str):

        completed_order = self.order_book_dict.get("completed_orders", {}).get(
            order_id, None
        )

        if completed_order:
            raise ValueError(f"Completed Order id: {order_id} cannot be updated")

        order = self._get_order(order_id)
        if not order:
            raise ValueError(f"Order id: {order_id} does not exist in the order book")
        return order

    def _all_quotes(self) -> List:
        all_quotes = []
        all_quotes.extend(self.order_book_dict.get("asks", SortedList([])))
        all_quotes.extend(self.order_book_dict.get("bids", SortedList([])))
        return all_quotes

    def _get_order(self, order_id: str) -> Optional[Order]:
        all_quotes = self._all_quotes()
        for quote in all_quotes:
            if order_id == quote.exch_order_id:
                return quote
        return None
