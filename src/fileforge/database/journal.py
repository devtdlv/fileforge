"""Operation journal helpers for organization batches and entries."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

from fileforge.database.connection import DatabaseManager


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


class OperationJournal:
    """Persist organization batches and per-file move outcomes."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _connection(self) -> sqlite3.Connection:
        return self._database.connection

    def begin_batch(
        self,
        *,
        operation_type: str,
        summary: str,
        source_root: str,
        destination_root: str,
        mode: str,
        details: dict[str, Any] | None = None,
    ) -> str:
        """Create a pending batch and matching legacy journal row. Returns batch id."""
        batch_id = str(uuid.uuid4())
        now = _utc_now()
        payload = json.dumps(details or {}, ensure_ascii=True)
        try:
            self._connection.execute(
                """
                INSERT INTO operation_batches (
                    id, operation_type, status, summary,
                    source_root, destination_root, mode,
                    created_at, details_json
                ) VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    operation_type,
                    summary,
                    source_root,
                    destination_root,
                    mode,
                    now,
                    payload,
                ),
            )
            self._connection.execute(
                """
                INSERT INTO operation_journal (
                    operation_type, status, summary, details_json, created_at
                ) VALUES (?, 'pending', ?, ?, ?)
                """,
                (
                    operation_type,
                    summary,
                    json.dumps({"batch_id": batch_id, **(details or {})}, ensure_ascii=True),
                    now,
                ),
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            self._connection.rollback()
            raise RuntimeError(f"Unable to create operation journal batch: {exc}") from exc
        return batch_id

    def add_entry(
        self,
        batch_id: str,
        *,
        source_path: str,
        destination_path: str,
        operation_type: str = "move",
        status: str = "pending",
        error_details: str = "",
    ) -> int:
        """Insert a per-file journal entry and return its id."""
        now = _utc_now()
        try:
            cursor = self._connection.execute(
                """
                INSERT INTO operation_entries (
                    batch_id, operation_type, source_path, destination_path,
                    status, error_details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    operation_type,
                    source_path,
                    destination_path,
                    status,
                    error_details,
                    now,
                ),
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            self._connection.rollback()
            raise RuntimeError(f"Unable to journal operation entry: {exc}") from exc
        return int(cursor.lastrowid)

    def complete_entry(
        self,
        entry_id: int,
        *,
        status: str,
        error_details: str = "",
    ) -> None:
        """Update an entry after the filesystem outcome is known."""
        now = _utc_now()
        try:
            self._connection.execute(
                """
                UPDATE operation_entries
                SET status = ?, error_details = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, error_details, now, entry_id),
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            self._connection.rollback()
            raise RuntimeError(f"Unable to update journal entry: {exc}") from exc

    def complete_batch(
        self,
        batch_id: str,
        *,
        status: str,
        summary: str,
    ) -> None:
        """Mark a batch finished and sync the legacy journal summary row."""
        now = _utc_now()
        try:
            self._connection.execute(
                """
                UPDATE operation_batches
                SET status = ?, summary = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, summary, now, batch_id),
            )
            self._connection.execute(
                """
                UPDATE operation_journal
                SET status = ?, summary = ?, completed_at = ?
                WHERE id = (
                    SELECT id FROM operation_journal
                    WHERE details_json LIKE ?
                    ORDER BY id DESC
                    LIMIT 1
                )
                """,
                (status, summary, now, f'%\"batch_id\": \"{batch_id}\"%'),
            )
            self._connection.commit()
        except sqlite3.Error as exc:
            self._connection.rollback()
            raise RuntimeError(f"Unable to complete journal batch: {exc}") from exc

    def list_batch_entries(self, batch_id: str) -> list[sqlite3.Row]:
        rows = self._connection.execute(
            """
            SELECT * FROM operation_entries
            WHERE batch_id = ?
            ORDER BY id ASC
            """,
            (batch_id,),
        ).fetchall()
        return list(rows)

    def get_batch(self, batch_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM operation_batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
