from fastapi import APIRouter, Depends, HTTPException
from aiosqlite import Connection
from datetime import datetime, timedelta

from app.database import get_db
from app.models import PinSetup, PinVerify, TokenResponse
from app.auth import hash_pin, verify_pin, create_session_token, require_parent

router = APIRouter()

LOCKOUT_MINUTES = 10
MAX_ATTEMPTS = 5


@router.post("/setup", summary="Nastavení PINu při prvním spuštění")
async def setup_pin(body: PinSetup, db: Connection = Depends(get_db)):
    """Spustí se pouze pokud parent_auth tabulka je prázdná."""
    async with db.execute("SELECT COUNT(*) FROM parent_auth") as cur:
        count = (await cur.fetchone())[0]
    if count > 0:
        raise HTTPException(status_code=400, detail="PIN již nastaven. Použijte /change-pin.")
    pin_hash = hash_pin(body.pin)
    await db.execute("INSERT INTO parent_auth (pin_hash) VALUES (?)", (pin_hash,))
    await db.execute("INSERT INTO audit_log (action, detail) VALUES ('pin_setup', 'Initial PIN set')")
    await db.commit()
    return {"status": "ok", "message": "PIN nastaven."}


@router.post("/verify", response_model=TokenResponse, summary="Přihlášení rodiče PINem")
async def verify(body: PinVerify, db: Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM parent_auth ORDER BY id LIMIT 1") as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="PIN není nastaven. Zavolejte /setup jako první.")

    # Lockout kontrola
    if row["locked_until"]:
        locked_until = datetime.fromisoformat(row["locked_until"])
        if datetime.utcnow() < locked_until:
            remaining = int((locked_until - datetime.utcnow()).total_seconds() / 60) + 1
            raise HTTPException(status_code=429, detail=f"Příliš mnoho pokusů. Zkuste za {remaining} minut.")

    if not verify_pin(body.pin, row["pin_hash"]):
        new_attempts = row["failed_attempts"] + 1
        locked_until = None
        if new_attempts >= MAX_ATTEMPTS:
            locked_until = (datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        await db.execute(
            "UPDATE parent_auth SET failed_attempts=?, locked_until=? WHERE id=?",
            (new_attempts, locked_until, row["id"])
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="Nesprávný PIN.")

    # Úspěch – reset failed attempts
    await db.execute(
        "UPDATE parent_auth SET failed_attempts=0, locked_until=NULL WHERE id=?",
        (row["id"],)
    )
    await db.execute("INSERT INTO audit_log (action, detail) VALUES ('parent_login', 'PIN verified')")
    await db.commit()
    token = create_session_token()
    from app.auth import SESSION_TTL
    return TokenResponse(access_token=token, expires_in_seconds=SESSION_TTL)


@router.post("/change-pin", summary="Změna PINu (vyžaduje platný token)")
async def change_pin(
    body: PinSetup,
    token: str = Depends(require_parent),
    db: Connection = Depends(get_db),
):
    new_hash = hash_pin(body.pin)
    await db.execute("UPDATE parent_auth SET pin_hash=?, updated_at=datetime('now') WHERE id=1")
    await db.execute("UPDATE parent_auth SET pin_hash=? WHERE id=1", (new_hash,))
    await db.execute("INSERT INTO audit_log (action, detail) VALUES ('pin_changed', 'PIN updated')")
    await db.commit()
    return {"status": "ok", "message": "PIN změněn."}
