import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "leads.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS leads (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Identity
                name                TEXT NOT NULL,
                title               TEXT,
                company             TEXT,
                linkedin_url        TEXT,
                industry            TEXT,
                seniority           TEXT,

                -- Discovery
                signals             TEXT,   -- JSON array of signal strings
                discovery_source    TEXT DEFAULT 'linkedin_mock',

                -- Qualification
                status              TEXT DEFAULT 'discovered',
                    -- discovered | qualified | blocked | skipped
                score               INTEGER,        -- 0-100, null until qualified
                qualification_notes TEXT,

                created_at          TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id     INTEGER NOT NULL REFERENCES leads(id),

                type        TEXT NOT NULL,  -- linkedin_invite | followup_email
                content     TEXT NOT NULL,  -- full message text
                approach    TEXT,           -- acquisition_uncertainty | performance_cost | migration_simplicity | vendor_independence

                -- Evaluation
                eval_score  INTEGER,        -- 0-100
                eval_notes  TEXT,
                eval_status TEXT,           -- APPROVED | REJECTED
                retry_count INTEGER DEFAULT 0,

                -- Always a dry run
                dry_run     INTEGER DEFAULT 1,

                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS message_feedback (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id    INTEGER NOT NULL REFERENCES messages(id),

                -- Response captured from CRM / webhook / manual entry (ingest_feedback.py)
                response_type TEXT NOT NULL,
                    -- replied | accepted | ignored | rejected

                -- Optional free-text note (e.g. "Lead asked for a demo")
                notes         TEXT,

                -- Whether this record has been ingested into ChromaDB yet
                ingested      INTEGER DEFAULT 0,

                created_at    TEXT DEFAULT (datetime('now'))
            );
        """)

        # Migrations — safe to run repeatedly (ALTER TABLE is a no-op if column exists)
        _add_column_if_missing(conn, "messages", "approach",  "TEXT")
        _add_column_if_missing(conn, "leads",    "industry",  "TEXT")
        _add_column_if_missing(conn, "leads",    "seniority", "TEXT")


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    """Add a column to an existing table if it doesn't already exist."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


if __name__ == "__main__":
    init_db()
    print(f"Database initialised at {DB_PATH}")
