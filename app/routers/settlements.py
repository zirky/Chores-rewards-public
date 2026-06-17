from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import os, io, base64, logging, traceback
import httpx
import qrcode

from app.database import get_db
from app.models import PayoutResponse, RateResponse
from app.auth import require_parent
from app.coingecko import get_btc_rates, czk_to_sats

router = APIRouter()
logger = logging.getLogger(__name__)

# Strip trailing slash aby nevznikalo double-slash v URL
LNBITS_URL       = os.getenv("LNBITS_URL", "https://legend.lnbits.com").rstrip("/")
LNBITS_ADMIN_KEY = os.getenv("LNBITS_ADMIN_KEY", "")


# ── Helpers ──────────────────────────────────────────────────────────────────────────────────

async def _child_or_404(child_id: int, db):
    async with db.execute(
        "SELECT id, name, active, payout_method, ln_address FROM children WHERE id=?",
        (child_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Dítě nenalezeno")
    return row


async def _approved_unpaid(child_id: int, db) -> list[dict]:
    """Schválené, dosud nevyplacené completions."""
    async with db.execute(
        """
        SELECT tc.id, tc.reward_czk, tc.reward_sats
        FROM   task_completions tc
        WHERE  tc.child_id  = ?
          AND  tc.status    = 'approved'
          AND  tc.payout_id IS NULL
        """,
        (child_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ── Endpointy ───────────────────────────────────────────────────────────────────────────────────────

@router.get("/rate", response_model=RateResponse, summary="Aktuální BTC kurz (CZK + USD)")
async def get_rate():
    """Veřejný endpoint – nevyadžuje auth."""
    try:
        rate_czk, rate_usd = await get_btc_rates()
    except Exception as e:
        raise HTTPException(503, f"Nelze načíst kurz: {e}")
    return {"rate_czk_per_btc": rate_czk, "rate_usd_per_btc": rate_usd, "source": "coingecko"}


@router.get(
    "/balance/{child_id}",
    response_model=PayoutResponse,
    summary="Nevyplacený zůstatek dítěte (rodič)",
    dependencies=[Depends(require_parent)]
)
async def get_balance(child_id: int, db=Depends(get_db)):
    await _child_or_404(child_id, db)
    rows = await _approved_unpaid(child_id, db)
    return PayoutResponse(
        id=None,
        child_id=child_id,
        total_sats=sum(r["reward_sats"] or 0 for r in rows),
        total_czk=round(sum(r["reward_czk"] or 0 for r in rows), 2),
        pending_count=len(rows),
        status="open",
    )


@router.post(
    "/pay/{child_id}",
    response_model=PayoutResponse,
    summary="Vyplť dítěti nevyplacený zůstatek (rodič)",
    dependencies=[Depends(require_parent)]
)
async def pay_child(child_id: int, db=Depends(get_db)):
    child = await _child_or_404(child_id, db)
    rows  = await _approved_unpaid(child_id, db)

    if not rows:
        raise HTTPException(400, "Žádné schválené nevyplacené odměny")

    total_sats    = sum(r["reward_sats"] or 0 for r in rows)
    total_czk     = round(sum(r["reward_czk"] or 0 for r in rows), 2)
    ln_address    = child["ln_address"]
    payout_method = child["payout_method"] or "ln_address"
    now           = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    print(f"[pay_child] child_id={child_id}, ln_address={ln_address!r}, method={payout_method}, sats={total_sats}", flush=True)

    if ln_address and payout_method == "ln_address":
        try:
            payment_hash = await _pay_ln_address(ln_address, total_sats, child["name"])
        except Exception as e:
            print(f"[pay_child ERROR] {e}\n{traceback.format_exc()}", flush=True)
            raise HTTPException(502, f"LNbits platba selhala: {e}")
    else:
        try:
            payment_hash  = await _create_lnurl_withdraw(total_sats, child["name"])
            payout_method = "voucher"
        except Exception as e:
            print(f"[pay_child ERROR voucher] {e}\n{traceback.format_exc()}", flush=True)
            raise HTTPException(502, f"Voucher generování selhalo: {e}")

    async with db.execute(
        """
        INSERT INTO payouts
            (child_id, total_sats, total_czk, status, payout_method,
             ln_address, ln_payment_hash, paid_at)
        VALUES (?, ?, ?, 'paid', ?, ?, ?, ?)
        RETURNING id
        """,
        (child_id, total_sats, total_czk, payout_method, ln_address, payment_hash, now)
    ) as cur:
        payout_id = (await cur.fetchone())["id"]

    ids_ph = ",".join(["?"] * len(rows))
    await db.execute(
        f"UPDATE task_completions SET status='settled', settled_at=?, payout_id=? WHERE id IN ({ids_ph})",
        [now, payout_id] + [r["id"] for r in rows]
    )
    await db.execute(
        "INSERT INTO audit_log (action, target_id, detail) VALUES ('payout', ?, ?)",
        (payout_id, f"child={child_id}, sats={total_sats}, method={payout_method}")
    )
    await db.commit()

    return PayoutResponse(
        id=payout_id,
        child_id=child_id,
        total_sats=total_sats,
        total_czk=total_czk,
        pending_count=0,
        status="paid",
        ln_payment_hash=payment_hash,
        paid_at=now,
    )


@router.get(
    "/status/{payout_id}",
    summary="Ověření stavu platby v LNbits (rodič)",
    dependencies=[Depends(require_parent)]
)
async def check_payment_status(payout_id: int, db=Depends(get_db)):
    async with db.execute(
        "SELECT id, status, payout_method, ln_payment_hash, paid_at FROM payouts WHERE id=?",
        (payout_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Payout nenalezen")

    payout = dict(row)

    if payout["payout_method"] == "ln_address" and payout["ln_payment_hash"]:
        try:
            confirmed = await _check_lnbits_payment(payout["ln_payment_hash"])
        except Exception:
            confirmed = None

        if confirmed is True and payout["status"] != "paid":
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            async with db.execute(
                "UPDATE payouts SET status='paid', paid_at=? WHERE id=?",
                (now, payout_id)
            ):
                pass
            await db.commit()
            payout["status"] = "paid"
            payout["paid_at"] = now

    return {**payout, "lnbits_confirmed": confirmed if payout["payout_method"] == "ln_address" else None}


# ── LNbits helpers ──────────────────────────────────────────────────────────────────────────────

async def _pay_ln_address(ln_address: str, amount_sats: int, description: str) -> str:
    """Odešle platbu na Lightning adresu přes LNbits a vrátí payment_hash."""
    # 1. Resolve LNURL
    local, domain = ln_address.split("@")
    lnurl_endpoint = f"https://{domain}/.well-known/lnurlp/{local}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(lnurl_endpoint)
        r.raise_for_status()
        lnurl_data = r.json()

        min_sendable = lnurl_data.get("minSendable", 1000)   # msat
        max_sendable = lnurl_data.get("maxSendable", 10**12)  # msat
        callback     = lnurl_data["callback"]

        amount_msat = amount_sats * 1000
        if not (min_sendable <= amount_msat <= max_sendable):
            raise ValueError(
                f"Částka {amount_sats} sats je mimo povolený rozsah "
                f"({min_sendable//1000}–{max_sendable//1000} sats)"
            )

        # 2. Získej invoice
        cb_r = await client.get(callback, params={"amount": amount_msat, "comment": description[:144]})
        cb_r.raise_for_status()
        invoice_data = cb_r.json()
        payment_request = invoice_data["pr"]

        # 3. Zaplať přes LNbits
        pay_r = await client.post(
            f"{LNBITS_URL}/api/v1/payments",
            headers={"X-Api-Key": LNBITS_ADMIN_KEY, "Content-Type": "application/json"},
            json={"out": True, "bolt11": payment_request},
            timeout=30.0
        )
        pay_r.raise_for_status()
        return pay_r.json().get("payment_hash", "")


async def _create_lnurl_withdraw(amount_sats: int, label: str) -> str:
    """Vytvoří LNURL-withdraw voucher v LNbits a vrátí jeho jedinečný hash."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{LNBITS_URL}/withdraw/api/v1/links",
            headers={"X-Api-Key": LNBITS_ADMIN_KEY, "Content-Type": "application/json"},
            json={
                "title":       label,
                "min_withdrawable": amount_sats,
                "max_withdrawable": amount_sats,
                "uses":        1,
                "wait_time":   1,
                "is_unique":   True,
            }
        )
        r.raise_for_status()
        data = r.json()
        return data.get("id", "")


async def _check_lnbits_payment(payment_hash: str) -> bool:
    """Ověří stav platby v LNbits. Vrátí True/False nebo vyhodí výjimku."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            f"{LNBITS_URL}/api/v1/payments/{payment_hash}",
            headers={"X-Api-Key": LNBITS_ADMIN_KEY},
        )
        r.raise_for_status()
        return r.json().get("paid", False)


@router.get(
    "/voucher/{payout_id}/qr",
    summary="QR kód pro LNURL-withdraw voucher (rodič)",
    dependencies=[Depends(require_parent)]
)
async def get_voucher_qr(payout_id: int, db=Depends(get_db)):
    async with db.execute(
        "SELECT id, payout_method, ln_payment_hash FROM payouts WHERE id=?",
        (payout_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Payout nenalezen")
    if row["payout_method"] != "voucher":
        raise HTTPException(400, "Tento payout není voucher")

    withdraw_id = row["ln_payment_hash"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            f"{LNBITS_URL}/withdraw/api/v1/links/{withdraw_id}",
            headers={"X-Api-Key": LNBITS_ADMIN_KEY},
        )
        r.raise_for_status()
        link_data = r.json()

    lnurl = link_data.get("lnurl", "")
    if not lnurl:
        raise HTTPException(502, "LNbits nevrátil LNURL")

    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(lnurl.upper())
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return {"lnurl": lnurl, "qr_png_base64": qr_b64}
