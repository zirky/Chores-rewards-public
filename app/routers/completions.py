from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone

from app.database import get_db
from app.models import CompletionCreate, CompletionReview, CompletionResponse
from app.auth import require_parent
from app.coingecko import get_btc_czk_rate, czk_to_sats

router = APIRouter()


@router.post("", summary="Dítě nahlásí splnění úkolu")
async def submit_completion(
    body: CompletionCreate,
    db=Depends(get_db)
):
    """Bez autentizace – dítě jen klikne Hotovo!"""
    async with db.execute(
        "SELECT id FROM children WHERE id=? AND active=1", (body.child_id,)
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Dítě nenalezeno")

    async with db.execute(
        "SELECT id, daily_limit FROM tasks WHERE id=? AND active=1", (body.task_id,)
    ) as cur:
        task = await cur.fetchone()
    if not task:
        raise HTTPException(404, "Úkol nenalezen nebo není aktivní")

    # Kontrola denního limitu (daily_limit > 0 znamená omezení)
    daily_limit = task["daily_limit"] if task["daily_limit"] is not None else 1
    if daily_limit > 0:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        async with db.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM task_completions
            WHERE child_id = ? AND task_id = ?
              AND date(submitted_at) = ?
              AND status != 'rejected'
            """,
            (body.child_id, body.task_id, today)
        ) as cur:
            row = await cur.fetchone()
        if row["cnt"] >= daily_limit:
            limit_label = f"{daily_limit}×" if daily_limit > 1 else "jednou"
            raise HTTPException(
                429,
                f"Tento úkol lze dnes splnit nejvýše {limit_label}. Zkus to zítra!"
            )

    async with db.execute(
        "INSERT INTO task_completions (child_id, task_id, status) VALUES (?, ?, 'submitted')",
        (body.child_id, body.task_id)
    ) as cur:
        completion_id = cur.lastrowid
    await db.commit()
    return {"id": completion_id, "status": "submitted"}


@router.get("/pending", summary="Rodič: seznam čekajících na schválení",
            dependencies=[Depends(require_parent)])
async def get_pending(db=Depends(get_db)):
    async with db.execute(
        """
        SELECT tc.id, tc.child_id, tc.task_id, t.title AS task_title,
               c.name AS child_name,
               t.reward_czk, tc.status, tc.submitted_at,
               tc.reviewed_at, tc.review_note
        FROM task_completions tc
        JOIN tasks t ON t.id = tc.task_id
        JOIN children c ON c.id = tc.child_id
        WHERE tc.status = 'submitted'
        ORDER BY tc.submitted_at
        """
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/history/{child_id}", summary="Historie splněných úkolů dítěte (veřejné)")
async def get_history(child_id: int, db=Depends(get_db)):
    async with db.execute(
        "SELECT id FROM children WHERE id=?", (child_id,)
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Dítě nenalezeno")

    async with db.execute(
        """
        SELECT tc.id, tc.child_id, tc.task_id, t.title AS task_title,
               tc.status, tc.reward_czk, tc.reward_sats, tc.rate_czk_per_btc,
               tc.submitted_at, tc.reviewed_at, tc.review_note, tc.settled_at, tc.payout_id
        FROM task_completions tc
        JOIN tasks t ON t.id = tc.task_id
        WHERE tc.child_id = ?
        ORDER BY tc.submitted_at DESC
        """,
        (child_id,)
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.patch("/{completion_id}/approve", summary="Rodič: schválí úkol",
              dependencies=[Depends(require_parent)])
async def approve_completion(
    completion_id: int,
    body: CompletionReview,
    db=Depends(get_db)
):
    async with db.execute(
        """
        SELECT tc.id, tc.status, t.reward_czk
        FROM task_completions tc
        JOIN tasks t ON t.id = tc.task_id
        WHERE tc.id = ?
        """,
        (completion_id,)
    ) as cur:
        row = await cur.fetchone()

    if not row:
        raise HTTPException(404, "Completion nenalezeno")
    if row["status"] != "submitted":
        raise HTTPException(400, f"Nelze schválit – aktuální stav: {row['status']}")

    try:
        rate = await get_btc_czk_rate()
        reward_sats = czk_to_sats(row["reward_czk"], rate)
    except Exception as e:
        raise HTTPException(503, f"Nepodařilo se získat BTC kurz: {e}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
        """
        UPDATE task_completions
        SET status='approved', reviewed_at=?, review_note=?,
            reward_czk=?, rate_czk_per_btc=?, reward_sats=?
        WHERE id=?
        """,
        (now, body.note, row["reward_czk"], rate, reward_sats, completion_id)
    )
    await db.execute(
        "INSERT INTO audit_log (action, target_id, detail) VALUES ('approved', ?, ?)",
        (completion_id, f"rate={rate}, sats={reward_sats}")
    )
    await db.commit()
    return {
        "id": completion_id,
        "status": "approved",
        "reward_czk": row["reward_czk"],
        "rate_czk_per_btc": rate,
        "reward_sats": reward_sats
    }


@router.patch("/{completion_id}/reject", summary="Rodič: zamítne úkol",
              dependencies=[Depends(require_parent)])
async def reject_completion(
    completion_id: int,
    body: CompletionReview,
    db=Depends(get_db)
):
    async with db.execute(
        "SELECT id, status FROM task_completions WHERE id=?", (completion_id,)
    ) as cur:
        row = await cur.fetchone()

    if not row:
        raise HTTPException(404, "Completion nenalezeno")
    if row["status"] != "submitted":
        raise HTTPException(400, f"Nelze zamítnout – aktuální stav: {row['status']}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
        "UPDATE task_completions SET status='rejected', reviewed_at=?, review_note=? WHERE id=?",
        (now, body.note, completion_id)
    )
    await db.execute(
        "INSERT INTO audit_log (action, target_id, detail) VALUES ('rejected', ?, ?)",
        (completion_id, body.note or "")
    )
    await db.commit()
    return {"id": completion_id, "status": "rejected"}
