from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models import ChildCreate, ChildResponse
from app.auth import require_parent

router = APIRouter()


@router.get("/public",
            summary="Seznam aktivních dětí – jména a ID (veřejné, bez auth)",
            response_model=list[dict])
async def list_children_public(db=Depends(get_db)):
    async with db.execute(
        "SELECT id, name FROM children WHERE active=1 ORDER BY id"
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/", response_model=list[ChildResponse],
            summary="Seznam dětí (rodič)",
            dependencies=[Depends(require_parent)])
async def list_children(db=Depends(get_db)):
    async with db.execute(
        "SELECT id, name, active, payout_method, ln_address FROM children ORDER BY id"
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/", response_model=ChildResponse,
             summary="Přidej dítě (rodič)",
             dependencies=[Depends(require_parent)])
async def create_child(body: ChildCreate, db=Depends(get_db)):
    async with db.execute(
        "INSERT INTO children (name, payout_method, ln_address) VALUES (?, ?, ?) RETURNING id, name, active, payout_method, ln_address",
        (body.name, body.payout_method, body.ln_address)
    ) as cur:
        row = await cur.fetchone()
    await db.commit()
    return dict(row)


@router.patch("/{child_id}", response_model=ChildResponse,
              summary="Uprav dítě (rodič)",
              dependencies=[Depends(require_parent)])
async def update_child(child_id: int, body: ChildCreate, db=Depends(get_db)):
    async with db.execute(
        "SELECT id FROM children WHERE id=?", (child_id,)
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Dítě nenalezeno")

    await db.execute(
        "UPDATE children SET name=?, payout_method=?, ln_address=? WHERE id=?",
        (body.name, body.payout_method, body.ln_address, child_id)
    )
    await db.commit()

    async with db.execute(
        "SELECT id, name, active, payout_method, ln_address FROM children WHERE id=?",
        (child_id,)
    ) as cur:
        row = await cur.fetchone()
    return dict(row)


@router.patch("/{child_id}/deactivate",
              summary="Deaktivuj dítě – soft delete (rodič)",
              dependencies=[Depends(require_parent)])
async def deactivate_child(child_id: int, db=Depends(get_db)):
    async with db.execute(
        "SELECT id, active FROM children WHERE id=?", (child_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Dítě nenalezeno")
    if not row["active"]:
        raise HTTPException(400, "Dítě je již deaktivováno")

    await db.execute("UPDATE children SET active=0 WHERE id=?", (child_id,))
    await db.execute(
        "INSERT INTO audit_log (action, target_id, detail) VALUES ('child_deactivated', ?, ?)",
        (child_id, f"child_id={child_id}")
    )
    await db.commit()
    return {"id": child_id, "active": False}


@router.delete("/{child_id}",
               summary="Trvale vymaž dítě z DB (jen neaktivní, rodič)",
               dependencies=[Depends(require_parent)])
async def delete_child(child_id: int, db=Depends(get_db)):
    """
    Trvale odstraňuje dítě a všechna jeho data (tasks, completions, payouts).
    Povolen pouze pro neaktivní děti (active=0) jako bezpečrestní pojistka.
    """
    async with db.execute(
        "SELECT id, name, active FROM children WHERE id=?", (child_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Dítě nenalezeno")
    if row["active"]:
        raise HTTPException(400, "Nejdřív deaktivuj dítě, pak ho můžeš vymazat.")

    name = row["name"]
    # Smaz všechna data dítěte (ON DELETE CASCADE není garantováno v každé verzi SQLite)
    await db.execute("DELETE FROM task_completions WHERE child_id=?", (child_id,))
    await db.execute("DELETE FROM payouts WHERE child_id=?", (child_id,))
    # Tasks přiřazené pouze tomuto dítěti smaz tež
    await db.execute(
        "DELETE FROM tasks WHERE id NOT IN (SELECT DISTINCT task_id FROM task_completions WHERE task_id IS NOT NULL)"
        " AND id IN (SELECT task_id FROM tasks WHERE 1=0)"  # placeholder – tasks nejsou vázány na child, nemazat
    )
    await db.execute("DELETE FROM children WHERE id=?", (child_id,))
    await db.execute(
        "INSERT INTO audit_log (action, target_id, detail) VALUES ('child_deleted', ?, ?)",
        (child_id, f"child_id={child_id}, name={name}")
    )
    await db.commit()
    return {"status": "deleted", "id": child_id, "name": name}
