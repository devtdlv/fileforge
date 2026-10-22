"""Read-only SQLite queries for Operation History."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fileforge.database.connection import DatabaseError, DatabaseManager
from fileforge.services.history.models import (
    BatchListResult,
    BatchSummary,
    EntrySummary,
    HistoryBatchStatus,
    HistoryFilters,
    HistoryOperationType,
    HistoryTotals,
)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def escape_like(term: str) -> str:
    """Escape ``%``, ``_``, and ``\\`` for use with ``LIKE ... ESCAPE '\\'``."""
    return (
        term.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


class HistoryQueryService:
    """Query operation_batches / operation_entries without modifying them."""

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @classmethod
    def open(cls, database_path: Path | str) -> tuple[HistoryQueryService, DatabaseManager]:
        """Open a short-lived database connection for background queries."""
        manager = DatabaseManager(database_path)
        manager.initialize()
        return cls(manager), manager

    @property
    def _connection(self) -> sqlite3.Connection:
        return self._database.connection

    def list_batches(self, filters: HistoryFilters | None = None) -> BatchListResult:
        """Return a paginated batch list with aggregate counts."""
        filters = filters or HistoryFilters()
        limit = max(1, min(int(filters.limit), MAX_PAGE_SIZE))
        offset = max(0, int(filters.offset))

        try:
            where_sql, params = self._batch_where(filters)
            order = "DESC" if filters.newest_first else "ASC"

            totals = self._compute_totals(where_sql, params)

            rows = self._connection.execute(
                f"""
                SELECT
                    b.id AS batch_id,
                    b.operation_type,
                    b.status,
                    COALESCE(b.summary, '') AS summary,
                    COALESCE(b.source_root, '') AS source_root,
                    COALESCE(b.destination_root, '') AS destination_root,
                    COALESCE(b.mode, '') AS mode,
                    COALESCE(b.created_at, '') AS created_at,
                    COALESCE(b.completed_at, '') AS completed_at,
                    COUNT(e.id) AS entry_total,
                    COALESCE(SUM(CASE WHEN e.status = 'success' THEN 1 ELSE 0 END), 0)
                        AS entry_success,
                    COALESCE(SUM(CASE WHEN e.status = 'failed' THEN 1 ELSE 0 END), 0)
                        AS entry_failed,
                    COALESCE(SUM(CASE WHEN e.status = 'pending' THEN 1 ELSE 0 END), 0)
                        AS entry_pending
                FROM operation_batches AS b
                LEFT JOIN operation_entries AS e ON e.batch_id = b.id
                {where_sql}
                GROUP BY b.id
                ORDER BY b.created_at {order}, b.rowid {order}
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()

            batches = [
                BatchSummary(
                    batch_id=str(row["batch_id"] or ""),
                    operation_type=str(row["operation_type"] or ""),
                    status=str(row["status"] or ""),
                    summary=str(row["summary"] or ""),
                    source_root=str(row["source_root"] or ""),
                    destination_root=str(row["destination_root"] or ""),
                    mode=str(row["mode"] or ""),
                    created_at=str(row["created_at"] or ""),
                    completed_at=str(row["completed_at"] or ""),
                    entry_total=int(row["entry_total"] or 0),
                    entry_success=int(row["entry_success"] or 0),
                    entry_failed=int(row["entry_failed"] or 0),
                    entry_pending=int(row["entry_pending"] or 0),
                )
                for row in rows
            ]

            message = (
                f"Showing {len(batches)} of {totals.matching_batches} matching batch(es)."
                if totals.matching_batches
                else "No matching operation batches."
            )
            return BatchListResult(
                batches=batches,
                totals=totals,
                filters=HistoryFilters(
                    operation_type=filters.operation_type,
                    batch_status=filters.batch_status,
                    search=filters.search,
                    newest_first=filters.newest_first,
                    limit=limit,
                    offset=offset,
                ),
                message=message,
            )
        except (sqlite3.Error, DatabaseError) as exc:
            return BatchListResult(
                filters=filters,
                error=f"Unable to read operation history: {exc}",
                message="Database error while loading history.",
            )

    def get_batch(self, batch_id: str) -> BatchSummary | None:
        """Return one batch with entry aggregates, or None."""
        try:
            row = self._connection.execute(
                """
                SELECT
                    b.id AS batch_id,
                    b.operation_type,
                    b.status,
                    COALESCE(b.summary, '') AS summary,
                    COALESCE(b.source_root, '') AS source_root,
                    COALESCE(b.destination_root, '') AS destination_root,
                    COALESCE(b.mode, '') AS mode,
                    COALESCE(b.created_at, '') AS created_at,
                    COALESCE(b.completed_at, '') AS completed_at,
                    COUNT(e.id) AS entry_total,
                    COALESCE(SUM(CASE WHEN e.status = 'success' THEN 1 ELSE 0 END), 0)
                        AS entry_success,
                    COALESCE(SUM(CASE WHEN e.status = 'failed' THEN 1 ELSE 0 END), 0)
                        AS entry_failed,
                    COALESCE(SUM(CASE WHEN e.status = 'pending' THEN 1 ELSE 0 END), 0)
                        AS entry_pending
                FROM operation_batches AS b
                LEFT JOIN operation_entries AS e ON e.batch_id = b.id
                WHERE b.id = ?
                GROUP BY b.id
                """,
                (batch_id,),
            ).fetchone()
        except (sqlite3.Error, DatabaseError):
            return None
        if row is None:
            return None
        return BatchSummary(
            batch_id=str(row["batch_id"] or ""),
            operation_type=str(row["operation_type"] or ""),
            status=str(row["status"] or ""),
            summary=str(row["summary"] or ""),
            source_root=str(row["source_root"] or ""),
            destination_root=str(row["destination_root"] or ""),
            mode=str(row["mode"] or ""),
            created_at=str(row["created_at"] or ""),
            completed_at=str(row["completed_at"] or ""),
            entry_total=int(row["entry_total"] or 0),
            entry_success=int(row["entry_success"] or 0),
            entry_failed=int(row["entry_failed"] or 0),
            entry_pending=int(row["entry_pending"] or 0),
        )

    def list_entries(
        self,
        batch_id: str,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> list[EntrySummary]:
        """Return journal entries for *batch_id* (paginated)."""
        limit = max(1, min(int(limit), 2000))
        offset = max(0, int(offset))
        try:
            rows = self._connection.execute(
                """
                SELECT
                    id,
                    batch_id,
                    COALESCE(operation_type, '') AS operation_type,
                    COALESCE(source_path, '') AS source_path,
                    COALESCE(destination_path, '') AS destination_path,
                    COALESCE(status, '') AS status,
                    COALESCE(error_details, '') AS error_details,
                    COALESCE(created_at, '') AS created_at,
                    COALESCE(completed_at, '') AS completed_at
                FROM operation_entries
                WHERE batch_id = ?
                ORDER BY id ASC
                LIMIT ? OFFSET ?
                """,
                (batch_id, limit, offset),
            ).fetchall()
        except (sqlite3.Error, DatabaseError):
            return []
        return [
            EntrySummary(
                entry_id=int(row["id"]),
                batch_id=str(row["batch_id"] or ""),
                operation_type=str(row["operation_type"] or ""),
                source_path=str(row["source_path"] or ""),
                destination_path=str(row["destination_path"] or ""),
                status=str(row["status"] or ""),
                error_details=str(row["error_details"] or ""),
                created_at=str(row["created_at"] or ""),
                completed_at=str(row["completed_at"] or ""),
            )
            for row in rows
        ]

    def _batch_where(self, filters: HistoryFilters) -> tuple[str, list[object]]:
        clauses: list[str] = ["1=1"]
        params: list[object] = []

        if filters.operation_type is not HistoryOperationType.ALL:
            clauses.append("b.operation_type = ?")
            params.append(filters.operation_type.value)

        if filters.batch_status is not HistoryBatchStatus.ALL:
            clauses.append("b.status = ?")
            params.append(filters.batch_status.value)

        search = (filters.search or "").strip()
        if search:
            pattern = f"%{escape_like(search)}%"
            clauses.append(
                """
                (
                    b.source_root LIKE ? ESCAPE '\\'
                    OR b.destination_root LIKE ? ESCAPE '\\'
                    OR b.summary LIKE ? ESCAPE '\\'
                    OR b.mode LIKE ? ESCAPE '\\'
                    OR EXISTS (
                        SELECT 1 FROM operation_entries AS se
                        WHERE se.batch_id = b.id
                          AND (
                              se.source_path LIKE ? ESCAPE '\\'
                              OR se.destination_path LIKE ? ESCAPE '\\'
                              OR se.error_details LIKE ? ESCAPE '\\'
                          )
                    )
                )
                """
            )
            params.extend([pattern] * 7)

        return "WHERE " + " AND ".join(clauses), params

    def _compute_totals(self, where_sql: str, params: list[object]) -> HistoryTotals:
        matching = self._connection.execute(
            f"""
            SELECT
                COUNT(*) AS matching_batches,
                COALESCE(SUM(CASE WHEN b.status = 'completed' THEN 1 ELSE 0 END), 0)
                    AS completed,
                COALESCE(SUM(CASE WHEN b.status = 'failed' THEN 1 ELSE 0 END), 0)
                    AS failed,
                COALESCE(SUM(CASE WHEN b.status = 'cancelled' THEN 1 ELSE 0 END), 0)
                    AS cancelled,
                COALESCE(SUM(CASE WHEN b.status = 'partial' THEN 1 ELSE 0 END), 0)
                    AS partial,
                COALESCE(SUM(CASE WHEN b.status = 'pending' THEN 1 ELSE 0 END), 0)
                    AS pending
            FROM operation_batches AS b
            {where_sql}
            """,
            params,
        ).fetchone()

        overall = self._connection.execute(
            """
            SELECT
                COUNT(*) AS all_batches,
                COALESCE(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END), 0)
                    AS all_completed,
                COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0)
                    AS all_failed,
                COALESCE(SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END), 0)
                    AS all_cancelled,
                COALESCE(SUM(CASE WHEN status = 'partial' THEN 1 ELSE 0 END), 0)
                    AS all_partial
            FROM operation_batches
            """
        ).fetchone()

        return HistoryTotals(
            matching_batches=int(matching["matching_batches"] or 0) if matching else 0,
            completed=int(matching["completed"] or 0) if matching else 0,
            failed=int(matching["failed"] or 0) if matching else 0,
            cancelled=int(matching["cancelled"] or 0) if matching else 0,
            partial=int(matching["partial"] or 0) if matching else 0,
            pending=int(matching["pending"] or 0) if matching else 0,
            all_batches=int(overall["all_batches"] or 0) if overall else 0,
            all_completed=int(overall["all_completed"] or 0) if overall else 0,
            all_failed=int(overall["all_failed"] or 0) if overall else 0,
            all_cancelled=int(overall["all_cancelled"] or 0) if overall else 0,
            all_partial=int(overall["all_partial"] or 0) if overall else 0,
        )
