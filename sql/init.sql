-- Chores & Rewards – init.sql
-- Spouští se při každém startu (CREATE IF NOT EXISTS = bezpečné)

PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS children (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL,
    active         INTEGER NOT NULL DEFAULT 1,
    payout_method  TEXT    NOT NULL DEFAULT 'voucher',
    ln_address     TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    reward_czk  REAL NOT NULL DEFAULT 0,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS task_completions (
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
);

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
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    action     TEXT NOT NULL,
    target_id  INTEGER,
    detail     TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
