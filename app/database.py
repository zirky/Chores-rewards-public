import aiosqlite
import os

DB_PATH     = os.getenv("DB_PATH",     "/app/data/chores.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "sql", "init.sql")

MIGRATIONS = [
    # v0.2
    "ALTER TABLE task_completions ADD COLUMN payout_id INTEGER REFERENCES payouts(id)",
    """
    CREATE TABLE IF NOT EXISTS payouts (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        child_id         INTEGER NOT NULL REFERENCES children(id),
        total_sats       INTEGER NOT NULL,
        total_czk        REAL    NOT NULL DEFAULT 0,
        status           TEXT    NOT NULL DEFAULT 'open',
        payout_method    TEXT    NOT NULL DEFAULT 'ln_address',
        ln_address       TEXT,
        ln_payment_hash  TEXT,
        created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
        paid_at          TEXT
    )
    """,
    # v0.3
    """
    CREATE TABLE IF NOT EXISTS task_completions_new (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        child_id         INTEGER NOT NULL REFERENCES children(id),
        task_id          INTEGER NOT NULL REFERENCES tasks(id),
        status           TEXT    NOT NULL DEFAULT 'submitted',
        week_key         TEXT,
        reward_czk       REAL,
        reward_sats      INTEGER,
        rate_czk_per_btc REAL,
        submitted_at     TEXT    NOT NULL DEFAULT (datetime('now')),
        reviewed_at      TEXT,
        review_note      TEXT,
        settled_at       TEXT,
        payout_id        INTEGER REFERENCES payouts(id)
    )
    """,
    """
    INSERT OR IGNORE INTO task_completions_new
        (id, child_id, task_id, status, week_key, reward_czk, reward_sats,
         rate_czk_per_btc, submitted_at, reviewed_at, review_note, settled_at, payout_id)
    SELECT id, child_id, task_id, status, week_key, reward_czk, reward_sats,
           rate_czk_per_btc, submitted_at, reviewed_at, review_note, settled_at, payout_id
    FROM task_completions
    """,
    "DROP TABLE IF EXISTS task_completions_old",
    "ALTER TABLE task_completions RENAME TO task_completions_old",
    "ALTER TABLE task_completions_new RENAME TO task_completions",
    "DROP TABLE IF EXISTS task_completions_old",
    # v0.4 – daily_limit na tasks
    "ALTER TABLE tasks ADD COLUMN daily_limit INTEGER NOT NULL DEFAULT 1",
    # v0.5 – btc_rate_cache
    """
    CREATE TABLE IF NOT EXISTS btc_rate_cache (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        rate_czk   REAL NOT NULL,
        fetched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
    )
    """,
    # v0.6 – přidat rate_usd do btc_rate_cache
    "ALTER TABLE btc_rate_cache ADD COLUMN rate_usd REAL NOT NULL DEFAULT 0",
]


async def get_db() -> aiosqlite.Connection:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        yield db


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema = f.read()
        await db.executescript(schema)

        for sql in MIGRATIONS:
            try:
                await db.execute(sql.strip())
                await db.commit()
            except Exception:
                pass

        await db.commit()
