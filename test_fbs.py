import asyncio
from datetime import date
from app.services.fbs import fbs_client
fbs_client.connect()
candles = asyncio.run(fbs_client.fetch_candles("2330", "D",
    date(2026, 5, 1), date(2026, 5, 23)))
print(f"got {len(candles)} candles, first:", candles[0] if candles else "empty")