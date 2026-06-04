from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import os, io, base64, logging, traceback
import httpx
import qrcode

from app.database import get_db
from app.models import PayoutResponse, RateResponse
from app.auth import require_parent
from app.coingecko import get_btc_czk_rate, czk_to_sats

router = APIRouter()
logger = logging.getLogger(__name__)

# Strip trailing slash aby nevznikalo double-slash v URL
LNBITS_URL       = os.getenv("LNBITS_URL", "https://legend.lnbits.com").rstrip("/")
LNBITS_ADMIN_KEY = os.getenv("LNBITS_ADMIN_KEY", "")


# ── Helpers ─────────────────────────────────────────────────────────────────────────────

async def _child_or_404(child_id: int, db):
    async with db.execute(
        "SELECT id, name, active, payout_method, ln_address FROM children WHERE id=?",
        (child_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Ýtě nenalezeno")
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


# ── Endpointy ───────────────────────────────────────────────────────────────────────────────────

@router.get("/rate", response_model=RateResponse, summary="Aktuální BTC/CZK kurz")
async def get_rate():
    """Veřejný endpoint – nevyadžuje auth."""
    try:
        rate = await get_btc_czk_rate()
    except Exception as e:
        raise HTTPException(503, f"Nelze načíst kurz: {e}")
    return {"rate_czk_per_btc": rate, "source": "coingecko"}


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
            await db.execute(
                "UPDATE payouts SET status='paid', paid_at=? WHERE id=?",
                (now, payout_id)
            )
            await db.commit()
            payout["status"] = "paid"
            payout["paid_at"] = now
        elif confirmed is False and payout["status"] == "paid":
            confirmed = True

        payout["lnbits_confirmed"] = confirmed
    else:
        payout["lnbits_confirmed"] = None

    return payout


@router.get(
    "/voucher-qr/{payout_id}",
    summary="LNURL-withdraw QR jako Base64 PNG (rodič)",
    dependencies=[Depends(require_parent)]
)
async def voucher_qr(payout_id: int, db=Depends(get_db)):
    async with db.execute(
        "SELECT id, status, payout_method, ln_payment_hash FROM payouts WHERE id=?",
        (payout_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Payout nenalezen")

    payout = dict(row)
    if payout["payout_method"] != "voucher":
        raise HTTPException(400, "Tento payout není voucher – použij payment_hash pro LN platbu")
    if not payout["ln_payment_hash"]:
        raise HTTPException(500, "Voucher ID chybí v DB")

    try:
        lnurl_str = await _get_lnurl_withdraw_string(payout["ln_payment_hash"])
    except Exception as e:
        raise HTTPException(502, f"Nelze načíst LNURL z LNbits: {e}")

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(lnurl_str.upper())
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "payout_id": payout_id,
        "lnurl": lnurl_str.upper(),
        "qr_png_base64": qr_b64,
    }


@router.get(
    "/history/{child_id}",
    summary="Historie výplat dítěte (rodič)",
    dependencies=[Depends(require_parent)]
)
async def payout_history(child_id: int, db=Depends(get_db)):
    await _child_or_404(child_id, db)
    async with db.execute(
        """
        SELECT id, child_id, total_sats, total_czk, status,
               payout_method, ln_payment_hash, created_at, paid_at
        FROM   payouts
        WHERE  child_id = ?
        ORDER  BY created_at DESC
        """,
        (child_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ── LNbits helpers ───────────────────────────────────────────────────────────────────────────────────────

def _lnbits_headers() -> dict:
    if not LNBITS_ADMIN_KEY:
        raise ValueError("LNBITS_ADMIN_KEY není nastaven v .env")
    return {"X-Api-Key": LNBITS_ADMIN_KEY, "Content-Type": "application/json"}


def _is_bitlifi(address: str) -> bool:
    """Vrátí True pro jakýkoli Bitlifi identifikátor (tel. č. nebo alias @bitlifi.com)."""
    return address.startswith("+") or address.endswith("@bitlifi.com")


def _bitlifi_identifier(address: str) -> str:
    """
    Vrátí identifier pro Bitlifi LNURL endpoint.
    Formáty: tel@bitlifi.com → tel, alias@bitlifi.com → alias, +tel → +tel
    """
    return address.split("@")[0]


async def _resolve_lnurl_pay(address: str) -> str:
    """
    Zjítí callback URL pro LNURL-pay.
    - Bitlifi adresa (tel. č. nebo @bitlifi.com alias) → přímý fetch z Bitlifi
    - ostatní Lightning Address → LNbits lnurlscan
    """
    async with httpx.AsyncClient(timeout=15) as client:
        if _is_bitlifi(address):
            identifier = _bitlifi_identifier(address)
            url = httpx.URL(f"https://www.bitlifi.com/.well-known/lnurlp/{identifier}")
            print(f"[_resolve_lnurl_pay] Bitlifi fetch: {url}", flush=True)
            r = await client.get(url, headers={"Accept": "application/json"})
            print(f"[_resolve_lnurl_pay] Bitlifi response {r.status_code}: {r.text[:300]}", flush=True)
            r.raise_for_status()
            return r.json()["callback"]
        else:
            h = _lnbits_headers()
            print(f"[_resolve_lnurl_pay] lnurlscan: {LNBITS_URL}/api/v1/lnurlscan/{address}", flush=True)
            r = await client.get(f"{LNBITS_URL}/api/v1/lnurlscan/{address}", headers=h)
            print(f"[_resolve_lnurl_pay] lnurlscan response {r.status_code}: {r.text[:300]}", flush=True)
            r.raise_for_status()
            return r.json()["callback"]


async def _pay_ln_address(ln_address: str, amount_sats: int, child_name: str = "") -> str:
    """Pošle platbu na Lightning adresu nebo Bitlifi. Vrátí payment_hash."""
    h = _lnbits_headers()
    async with httpx.AsyncClient(timeout=20) as client:
        callback = await _resolve_lnurl_pay(ln_address)
        print(f"[_pay_ln_address] callback={callback}, sats={amount_sats}", flush=True)

        r = await client.get(callback, params={
            "amount": amount_sats * 1000,
            "comment": f"Odměna za domácí práce: {amount_sats} sats"
        })
        print(f"[_pay_ln_address] invoice response {r.status_code}: {r.text[:300]}", flush=True)
        r.raise_for_status()
        bolt11 = r.json()["pr"]

        r = await client.post(
            f"{LNBITS_URL}/api/v1/payments",
            headers=h,
            json={"out": True, "bolt11": bolt11}
        )
        print(f"[_pay_ln_address] LNbits payment {r.status_code}: {r.text[:300]}", flush=True)
        r.raise_for_status()
        return r.json().get("payment_hash", "")


async def _create_lnurl_withdraw(amount_sats: int, child_name: str) -> str:
    """Vytvoří LNURL-withdraw voucher (1 použití). Vrátí withdraw link ID."""
    h = _lnbits_headers()
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{LNBITS_URL}/withdraw/api/v1/links",
            headers=h,
            json={
                "title":           f"Odmena {child_name}",
                "min_withdrawable": amount_sats,
                "max_withdrawable": amount_sats,
                "uses":            1,
                "wait_time":       1,
                "is_unique":       True,
            }
        )
        r.raise_for_status()
        return r.json()["id"]


async def _get_lnurl_withdraw_string(link_id: str) -> str:
    """Načte LNURL string pro zobrazení QR kódu."""
    h = _lnbits_headers()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{LNBITS_URL}/withdraw/api/v1/links/{link_id}",
            headers=h
        )
        r.raise_for_status()
        data = r.json()
        return data.get("lnurl") or data.get("lnurl_withdraw") or link_id


async def _check_lnbits_payment(payment_hash: str) -> bool:
    """Ověří zda byl payment_hash zaplacen. Vrátí True/False."""
    h = _lnbits_headers()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{LNBITS_URL}/api/v1/payments/{payment_hash}",
            headers=h
        )
        r.raise_for_status()
        return r.json().get("paid", False)
