import asyncio
import os
from dotenv import load_dotenv
from eth_typing import ChecksumAddress, HexStr
from web3 import AsyncWeb3
from web3.providers.rpc.async_rpc import AsyncHTTPProvider
from web3.types import TxReceipt

# from examples.utils import show_all_orders
from gte_py.api.chain.utils import make_web3
from gte_py.clients import Client
from gte_py.api.chain.structs import Side, Settlement
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


async def get_order_status(client: Client, market: Market, order_id: int) -> None:
    """Get the status of an order."""

    try:
        order = await client.execution.get_order(market, order_id=order_id) # type: ignore

        print(f"Order ID: {order.order_id}")
        print(f"Market: {market.pair}")
        print(f"Side: {order.side.name}")
        print(f"Price: {order.price}")
        print(f"Amount: {order.amount}")
        print(f"Status: {order.status}")

    except Exception as e:
        print(f"Couldn't fetch on-chain order status: {str(e)}")


async def ensure_deposit(client: Client, market: Market, base_quantity: float, quote_quantity: float) -> None:
    """Approve and deposit base and quote tokens for trading."""
    base_amount = market.base.convert_quantity_to_amount(base_quantity)
    quote_amount = market.quote.convert_quantity_to_amount(quote_quantity)

    await client.account.ensure_deposit( # type: ignore
        token_address=market.base.address,
        amount=base_amount*2,
        gas=50 * 10**6
    )

    await client.account.ensure_deposit( # type: ignore
        token_address=market.quote.address,
        amount=quote_amount,
        gas=50 * 10**6
    )


async def main():
    web3 = await make_web3(TESTNET_CONFIG, WALLET_ADDRESS, WALLET_PRIVATE_KEY)
    client = Client(web3=web3, config=TESTNET_CONFIG, account=WALLET_ADDRESS)
    await client.init()

    market: Market = await client.info.get_market(MARKET_ADDRESS)
    snapshot: OrderBookSnapshot = await client.orderbook.get_order_book_snapshot(market, depth=10)

    best_bid_price = snapshot.bids[0][0] if snapshot.bids else 0
    base_quantity = 0.1
    quote_quantity = best_bid_price * base_quantity

    await ensure_deposit(client, market, base_quantity, quote_quantity)

    order = await client.execution.place_limit_order( # type: ignore
        market=market,
        side=Side.SELL,
        amount=market.base.convert_quantity_to_amount(base_quantity),
        price=market.quote.convert_quantity_to_amount(best_bid_price + 10),
        time_in_force=TimeInForce.GTC,
        gas=50 * 10**6
    )
    print(f"Order posted: {order}")
    if order:
        await get_order_status(client, market, order.order_id)
    

if __name__ == "__main__":
    asyncio.run(main())
