import httpx
import logging
import aiosqlite
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

COINGECKO_URL    = "https://api.coingecko.com/api/v3/simple/price"
CACHE_TTL_MINUTES = 60
DB_PATH          = os.getenv("DB_PATH", "/app/data/chores.db")


async def get_btc_rates() -> tuple[float, float]:
    """
    Vrátí (rate_czk, rate_usd) pro BTC.
    Nejdříve zkusí cache v DB (platnou max 60 minut),
    při vypršení nebo chybě zavolá CoinGecko API.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=CACHE_TTL_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT rate_czk, rate_usd FROM btc_rate_cache WHERE fetched_at >= ? ORDER BY fetched_at DESC LIMIT 1",
            (cutoff,)
        ) as cur:
            row = await cur.fetchone()
        if row:
            logger.info(f"BTC kurz z cache: CZK={row['rate_czk']}, USD={row['rate_usd']}")
            return float(row["rate_czk"]), float(row["rate_usd"])

    # Cache vypršela nebo prázdná -- voláme CoinGecko
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                COINGECKO_URL,
                params={"ids": "bitcoin", "vs_currencies": "czk,usd"}
            )
            resp.raise_for_status()
            data = resp.json()
            rate_czk = float(data["bitcoin"]["czk"])
            rate_usd = float(data["bitcoin"]["usd"])

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO btc_rate_cache (rate_czk, rate_usd) VALUES (?, ?)",
                (rate_czk, rate_usd)
            )
            await db.commit()

        logger.info(f"BTC kurz z CoinGecko: CZK={rate_czk}, USD={rate_usd}")
        return rate_czk, rate_usd

    except Exception as e:
        logger.error(f"CoinGecko API chyba: {e}")
        # Fallback: použij poslední známý kurz i když vypršel
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT rate_czk, rate_usd FROM btc_rate_cache ORDER BY fetched_at DESC LIMIT 1"
            ) as cur:
                row = await cur.fetchone()
            if row:
                logger.warning(f"Fallback kurz: CZK={row['rate_czk']}, USD={row['rate_usd']}")
                return float(row["rate_czk"]), float(row["rate_usd"])
        raise RuntimeError("Nepodařilo se získat BTC kurz a cache je prázdná")


async def get_btc_czk_rate() -> float:
    """Zpětně kompatibilní wrapper – vrátí pouze CZK kurz."""
    czk, _ = await get_btc_rates()
    return czk


def czk_to_sats(czk_amount: float, rate_czk_per_btc: float) -> int:
    """
    Přepočítá CZK na satoshi.
    1 BTC = 100_000_000 sats
    """
    if rate_czk_per_btc <= 0:
        raise ValueError("Neplatný kurz BTC/CZK")
    sats = (czk_amount / rate_czk_per_btc) * 100_000_000
    return max(1, round(sats))
