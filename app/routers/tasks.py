from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.models import TaskCreate, TaskUpdate, TaskResponse
from app.auth import require_parent

router = APIRouter()


@router.get("/", response_model=list[TaskResponse], summary="Seznam aktivních úkolů (dítě)")
async def list_tasks(db=Depends(get_db)):
    async with db.execute(
        "SELECT id, title, reward_czk, active, sort_order, daily_limit FROM tasks WHERE active=1 ORDER BY sort_order, id"
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/all", response_model=list[TaskResponse],
            summary="Všechny úkoly včetně neaktivních (rodič)",
            dependencies=[Depends(require_parent)])
async def list_all_tasks(db=Depends(get_db)):
    async with db.execute(
        "SELECT id, title, reward_czk, active, sort_order, daily_limit FROM tasks ORDER BY sort_order, id"
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/", response_model=TaskResponse,
             summary="Vytvoř nový úkol (rodič)",
             dependencies=[Depends(require_parent)])
async def create_task(body: TaskCreate, db=Depends(get_db)):
    async with db.execute(
        "INSERT INTO tasks (title, reward_czk, sort_order, daily_limit) VALUES (?, ?, ?, ?) RETURNING id, title, reward_czk, active, sort_order, daily_limit",
        (body.title, body.reward_czk, body.sort_order, body.daily_limit)
    ) as cur:
        row = await cur.fetchone()
    await db.execute(
        "INSERT INTO audit_log (action, target_id, detail) VALUES ('task_created', ?, ?)",
        (row["id"], f"{body.title} / {body.reward_czk} CZK / limit={body.daily_limit}")
    )
    await db.commit()
    return dict(row)


@router.patch("/{task_id}", response_model=TaskResponse,
              summary="Uprav úkol (rodič)",
              dependencies=[Depends(require_parent)])
async def update_task(task_id: int, body: TaskUpdate, db=Depends(get_db)):
    async with db.execute(
        "SELECT id, title, reward_czk, active, sort_order, daily_limit FROM tasks WHERE id=?", (task_id,)
    ) as cur:
        existing = await cur.fetchone()

    if not existing:
        raise HTTPException(404, "Úkol nenalezen")

    title       = body.title       if body.title       is not None else existing["title"]
    reward_czk  = body.reward_czk  if body.reward_czk  is not None else existing["reward_czk"]
    active      = body.active      if body.active      is not None else bool(existing["active"])
    sort_order  = body.sort_order  if body.sort_order  is not None else existing["sort_order"]
    daily_limit = body.daily_limit if body.daily_limit is not None else existing["daily_limit"]

    await db.execute(
        "UPDATE tasks SET title=?, reward_czk=?, active=?, sort_order=?, daily_limit=? WHERE id=?",
        (title, reward_czk, int(active), sort_order, daily_limit, task_id)
    )
    await db.execute(
        "INSERT INTO audit_log (action, target_id, detail) VALUES ('task_updated', ?, ?)",
        (task_id, f"{title} / {reward_czk} CZK / limit={daily_limit}")
    )
    await db.commit()

    return {
        "id": task_id,
        "title": title,
        "reward_czk": reward_czk,
        "active": active,
        "sort_order": sort_order,
        "daily_limit": daily_limit,
    }


@router.delete("/{task_id}",
               summary="Smaž úkol (rodič) – pouze pokud nemá žádné splnění",
               dependencies=[Depends(require_parent)])
async def delete_task(task_id: int, db=Depends(get_db)):
    async with db.execute(
        "SELECT id FROM tasks WHERE id=?", (task_id,)
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Úkol nenalezen")

    async with db.execute(
        "SELECT COUNT(*) AS cnt FROM task_completions WHERE task_id=?", (task_id,)
    ) as cur:
        row = await cur.fetchone()
    if row["cnt"] > 0:
        # Bezpečnější: pouze deaktivovat, ne mazat (zachová historii)
        await db.execute("UPDATE tasks SET active=0 WHERE id=?", (task_id,))
        await db.execute(
            "INSERT INTO audit_log (action, target_id, detail) VALUES ('task_deactivated', ?, 'má splnění – deaktivováno místo smazání')",
            (task_id,)
        )
        await db.commit()
        return {"detail": "Úkol má historii splnění – byl deaktivován (ne smazán)."}

    await db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    await db.execute(
        "INSERT INTO audit_log (action, target_id, detail) VALUES ('task_deleted', ?, '')",
        (task_id,)
    )
    await db.commit()
    return {"detail": "Smazáno"}
