import asyncio
import os

from dotenv import load_dotenv
from eth_typing import ChecksumAddress, HexStr
from web3 import AsyncWeb3
from gte_py.api.chain.utils import make_web3
from gte_py.clients import Client
from gte_py.api.chain.structs import Side
from gte_py.configs import TESTNET_CONFIG
from gte_py.models import OrderBookSnapshot, Market, TimeInForce

load_dotenv()

WALLET_ADDRESS_RAW = os.getenv("WALLET_ADDRESS")
WALLET_PRIVATE_KEY_RAW = os.getenv("WALLET_PRIVATE_KEY")
MARKET_ADDRESS: ChecksumAddress = AsyncWeb3.to_checksum_address("0x0F3642714B9516e3d17a936bAced4de47A6FFa5F")

if not WALLET_ADDRESS_RAW or not WALLET_PRIVATE_KEY_RAW:
    raise ValueError("Missing wallet credentials")

WALLET_ADDRESS: ChecksumAddress = AsyncWeb3.to_checksum_address(WALLET_ADDRESS_RAW)
WALLET_PRIVATE_KEY: HexStr = HexStr(WALLET_PRIVATE_KEY_RAW)


async def initialize_client() -> Client:
    web3 = await make_web3(TESTNET_CONFIG, WALLET_ADDRESS, WALLET_PRIVATE_KEY)
    client = Client(web3=web3, config=TESTNET_CONFIG, account=WALLET_ADDRESS)
    await client.init()
    return client


async def fetch_market_snapshot(client: Client, market_address: ChecksumAddress) -> tuple[Market, OrderBookSnapshot]:
    market = await client.info.get_market(market_address)
    snapshot = await client.orderbook.get_order_book_snapshot(market, depth=10)
    return market, snapshot


async def prepare_deposits(client: Client, market: Market, base_qty: float, best_bid_price: float) -> None:
    quote_qty = best_bid_price * base_qty
    await ensure_deposit(client, market, base_qty, quote_qty)


async def ensure_deposit(client: Client, market: Market, base_qty: float, quote_qty: float) -> None:
    base_amt = market.base.convert_quantity_to_amount(base_qty)
    quote_amt = market.quote.convert_quantity_to_amount(quote_qty)

    await client.account.ensure_deposit(
        token_address=market.base.address,
        amount=base_amt * 2,
        gas=50_000_000
    )
    await client.account.ensure_deposit(
        token_address=market.quote.address,
        amount=quote_amt,
        gas=50_000_000
    )


async def place_sell_order(client: Client, market: Market, base_qty: float, price: float):
    return await client.execution.place_limit_order(
        market=market,
        side=Side.SELL,
        amount=market.base.convert_quantity_to_amount(base_qty),
        price=market.quote.convert_quantity_to_amount(price),
        time_in_force=TimeInForce.GTC,
        gas=50_000_000
    )


async def get_order_status(client: Client, market: Market, order_id: int) -> None:
    try:
        order = await client.execution.get_order(market, order_id=order_id)
        print(f"Order ID: {order.order_id}")
        print(f"Market: {market.pair}")
        print(f"Side: {order.side.name}")
        print(f"Price: {order.price}")
        print(f"Amount: {order.amount}")
        print(f"Status: {order.status}")
    except Exception as e:
        print(f"Couldn't fetch on-chain order status: {e}")


async def main():
    client = await initialize_client()
    market, snapshot = await fetch_market_snapshot(client, MARKET_ADDRESS)

    base_qty = 0.1
    best_bid_price = snapshot.bids[0][0] if snapshot.bids else 0
    post_price = best_bid_price + 10

    await prepare_deposits(client, market, base_qty, best_bid_price)

    order = await place_sell_order(client, market, base_qty, post_price)
    print(f"Order posted: {order}")

    if order:
        await get_order_status(client, market, order.order_id)


if __name__ == "__main__":
    asyncio.run(main())
