"""
Simple SQLite database for the Wage Manager Bot.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

DB_PATH = Path(__file__).parent / "wage_bot.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS employees (
                telegram_id INTEGER PRIMARY KEY,
                name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
                balance     REAL NOT NULL DEFAULT 0.0,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS submissions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER NOT NULL,
                content_type    TEXT NOT NULL,          -- 'text' or 'photo'
                text_content    TEXT,
                photo_file_id   TEXT,
                status          TEXT NOT NULL DEFAULT 'pending',  -- pending / approved / rejected
                amount          REAL,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (telegram_id) REFERENCES employees(telegram_id)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER NOT NULL,
                amount          REAL NOT NULL,
                type            TEXT NOT NULL,          -- wage / bonus / fine
                note            TEXT,
                submission_id   INTEGER,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (telegram_id) REFERENCES employees(telegram_id),
                FOREIGN KEY (submission_id) REFERENCES submissions(id)
            );

            CREATE TABLE IF NOT EXISTS confirmations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER NOT NULL,
                amount          REAL NOT NULL,
                type            TEXT NOT NULL,          -- wage / bonus / fine
                note            TEXT,
                submission_id   INTEGER,
                status          TEXT NOT NULL DEFAULT 'pending',  -- pending / accepted / declined
                created_at      TEXT NOT NULL,
                FOREIGN KEY (telegram_id) REFERENCES employees(telegram_id),
                FOREIGN KEY (submission_id) REFERENCES submissions(id)
            );

            CREATE TABLE IF NOT EXISTS pending_registrations (
                telegram_id     INTEGER PRIMARY KEY,
                requested_name  TEXT NOT NULL,
                created_at      TEXT NOT NULL
            );
            """
        )


# ───────────────────────── Employees ─────────────────────────

def add_employee(telegram_id: int, name: str) -> bool:
    """Register a new employee. Returns False if name or ID already exists."""
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO employees (telegram_id, name, balance, created_at) VALUES (?, ?, 0.0, ?)",
                (telegram_id, name.strip(), datetime.utcnow().isoformat()),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def get_employee_by_id(telegram_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM employees WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()


def get_employee_by_name(name: str) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM employees WHERE name = ? COLLATE NOCASE", (name.strip(),)
        ).fetchone()


def list_employees() -> List[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM employees ORDER BY name COLLATE NOCASE"
        ).fetchall()


def update_balance(telegram_id: int, delta: float) -> float:
    """Add delta to balance and return the new balance."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE employees SET balance = balance + ? WHERE telegram_id = ?",
            (delta, telegram_id),
        )
        row = conn.execute(
            "SELECT balance FROM employees WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return row["balance"] if row else 0.0


# ───────────────────────── Submissions ─────────────────────────

def create_submission(
    telegram_id: int,
    content_type: str,
    text_content: Optional[str] = None,
    photo_file_id: Optional[str] = None,
) -> int:
    """Create a pending submission and return its ID."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO submissions
                (telegram_id, content_type, text_content, photo_file_id, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (
                telegram_id,
                content_type,
                text_content,
                photo_file_id,
                datetime.utcnow().isoformat(),
            ),
        )
        return cur.lastrowid


def get_submission(submission_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()


def approve_submission(submission_id: int, amount: float) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE submissions SET status = 'approved', amount = ? WHERE id = ?",
            (amount, submission_id),
        )


def reject_submission(submission_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE submissions SET status = 'rejected' WHERE id = ?",
            (submission_id,),
        )


# ───────────────────────── Transactions ─────────────────────────

def add_transaction(
    telegram_id: int,
    amount: float,
    type_: str,
    note: Optional[str] = None,
    submission_id: Optional[int] = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO transactions
                (telegram_id, amount, type, note, submission_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                telegram_id,
                amount,
                type_,
                note,
                submission_id,
                datetime.utcnow().isoformat(),
            ),
        )


def get_transactions(telegram_id: int, limit: int = 20) -> List[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM transactions
            WHERE telegram_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (telegram_id, limit),
        ).fetchall()


# ───────────────────────── Confirmations (mutual) ─────────────────────────

def create_confirmation(
    telegram_id: int,
    amount: float,
    type_: str,
    note: Optional[str] = None,
    submission_id: Optional[int] = None,
) -> int:
    """Create a pending confirmation that the employee must accept/decline."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO confirmations
                (telegram_id, amount, type, note, submission_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                telegram_id,
                amount,
                type_,
                note,
                submission_id,
                datetime.utcnow().isoformat(),
            ),
        )
        return cur.lastrowid


def get_confirmation(conf_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM confirmations WHERE id = ?", (conf_id,)
        ).fetchone()


def accept_confirmation(conf_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE confirmations SET status = 'accepted' WHERE id = ?",
            (conf_id,),
        )


def decline_confirmation(conf_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE confirmations SET status = 'declined' WHERE id = ?",
            (conf_id,),
        )


# ───────────────────────── Pending Registrations ─────────────────────────

def create_pending_registration(telegram_id: int, requested_name: str) -> bool:
    """Employee requests a name. Returns False if already pending or name taken."""
    try:
        with get_connection() as conn:
            # Check if name already used by registered employee
            exists = conn.execute(
                "SELECT 1 FROM employees WHERE name = ? COLLATE NOCASE",
                (requested_name.strip(),)
            ).fetchone()
            if exists:
                return False
            conn.execute(
                """
                INSERT OR REPLACE INTO pending_registrations
                    (telegram_id, requested_name, created_at)
                VALUES (?, ?, ?)
                """,
                (telegram_id, requested_name.strip(), datetime.utcnow().isoformat()),
            )
        return True
    except Exception:
        return False


def get_pending_registration(telegram_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM pending_registrations WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()


def delete_pending_registration(telegram_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM pending_registrations WHERE telegram_id = ?",
            (telegram_id,),
        )


def delete_employee(telegram_id: int) -> bool:
    """Delete an employee and all related data. Returns True if deleted."""
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM employees WHERE telegram_id = ?", (telegram_id,)
        )
        if cur.rowcount == 0:
            return False
        conn.execute("DELETE FROM submissions WHERE telegram_id = ?", (telegram_id,))
        conn.execute("DELETE FROM transactions WHERE telegram_id = ?", (telegram_id,))
        conn.execute("DELETE FROM confirmations WHERE telegram_id = ?", (telegram_id,))
        conn.execute("DELETE FROM pending_registrations WHERE telegram_id = ?", (telegram_id,))
        return True
