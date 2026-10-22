"""Unit tests for the read-only Operation History query layer."""

from __future__ import annotations

from pathlib import Path

from fileforge.database.connection import DatabaseManager
from fileforge.database.journal import OperationJournal
from fileforge.services.history import (
    HistoryBatchStatus,
    HistoryFilters,
    HistoryOperationType,
    HistoryQueryService,
    escape_like,
)


def _db(tmp_path: Path) -> tuple[DatabaseManager, OperationJournal, HistoryQueryService]:
    manager = DatabaseManager(tmp_path / "history.db")
    manager.initialize()
    journal = OperationJournal(manager)
    return manager, journal, HistoryQueryService(manager)


def _seed_organize(journal: OperationJournal, *, status: str = "completed") -> str:
    batch_id = journal.begin_batch(
        operation_type="organize_move",
        summary="Organize test",
        source_root=r"C:\src",
        destination_root=r"C:\dst",
        mode="extension",
    )
    entry = journal.add_entry(
        batch_id,
        source_path=r"C:\src\a.txt",
        destination_path=r"C:\dst\txt\a.txt",
        operation_type="move",
    )
    journal.complete_entry(entry, status="success")
    if status != "pending":
        journal.complete_batch(batch_id, status=status, summary=f"done:{status}")
    return batch_id


def _seed_rename(
    journal: OperationJournal,
    *,
    status: str = "completed",
    fail: bool = False,
) -> str:
    batch_id = journal.begin_batch(
        operation_type="bulk_rename",
        summary="Rename test",
        source_root=r"C:\photos",
        destination_root=r"C:\photos",
        mode="prefix 'x_'",
    )
    entry = journal.add_entry(
        batch_id,
        source_path=r"C:\photos\IMG_001.JPG",
        destination_path=r"C:\photos\x_IMG_001.JPG",
        operation_type="rename",
    )
    if fail:
        journal.complete_entry(entry, status="failed", error_details="collision")
    else:
        journal.complete_entry(entry, status="success")
    journal.complete_batch(batch_id, status=status, summary=f"rename:{status}")
    return batch_id


def test_empty_database(tmp_path: Path) -> None:
    manager, _journal, service = _db(tmp_path)
    result = service.list_batches()
    assert result.error == ""
    assert result.batches == []
    assert result.totals.all_batches == 0
    manager.close()


def test_lists_organizer_and_renamer_batches(tmp_path: Path) -> None:
    manager, journal, service = _db(tmp_path)
    _seed_organize(journal)
    _seed_rename(journal)
    result = service.list_batches(HistoryFilters(newest_first=True))
    assert result.totals.all_batches == 2
    types = {b.operation_type for b in result.batches}
    assert types == {"organize_move", "bulk_rename"}
    manager.close()


def test_filter_by_operation_type(tmp_path: Path) -> None:
    manager, journal, service = _db(tmp_path)
    _seed_organize(journal)
    _seed_rename(journal)
    result = service.list_batches(
        HistoryFilters(operation_type=HistoryOperationType.BULK_RENAME)
    )
    assert result.totals.matching_batches == 1
    assert result.batches[0].operation_type == "bulk_rename"
    manager.close()


def test_filter_by_status(tmp_path: Path) -> None:
    manager, journal, service = _db(tmp_path)
    _seed_organize(journal, status="completed")
    _seed_rename(journal, status="failed", fail=True)
    _seed_organize(journal, status="cancelled")
    _seed_rename(journal, status="partial")

    failed = service.list_batches(
        HistoryFilters(batch_status=HistoryBatchStatus.FAILED)
    )
    assert failed.totals.matching_batches == 1
    assert failed.batches[0].status == "failed"

    partial = service.list_batches(
        HistoryFilters(batch_status=HistoryBatchStatus.PARTIAL)
    )
    assert partial.totals.matching_batches == 1
    manager.close()


def test_search_source_and_destination(tmp_path: Path) -> None:
    manager, journal, service = _db(tmp_path)
    _seed_organize(journal)
    _seed_rename(journal)
    by_src = service.list_batches(HistoryFilters(search="IMG_001"))
    assert by_src.totals.matching_batches == 1
    assert by_src.batches[0].operation_type == "bulk_rename"

    by_dst = service.list_batches(HistoryFilters(search=r"dst\txt"))
    assert by_dst.totals.matching_batches == 1
    assert by_dst.batches[0].operation_type == "organize_move"
    manager.close()


def test_search_is_parameterized_like_escape(tmp_path: Path) -> None:
    manager, journal, service = _db(tmp_path)
    batch_id = journal.begin_batch(
        operation_type="bulk_rename",
        summary="percent_test",
        source_root=r"C:\data",
        destination_root=r"C:\data",
        mode="x",
    )
    journal.add_entry(
        batch_id,
        source_path=r"C:\data\100%_done.txt",
        destination_path=r"C:\data\ok.txt",
        operation_type="rename",
        status="success",
    )
    journal.complete_batch(batch_id, status="completed", summary="ok")

    # Literal % should not match every row; escape_like makes it literal.
    assert "%" in escape_like("%")
    matched = service.list_batches(HistoryFilters(search="100%_done"))
    assert matched.totals.matching_batches == 1
    # A bare wildcard-looking search for something absent returns empty.
    missing = service.list_batches(HistoryFilters(search="no_such_%_file"))
    assert missing.totals.matching_batches == 0
    manager.close()


def test_combined_filters(tmp_path: Path) -> None:
    manager, journal, service = _db(tmp_path)
    _seed_organize(journal, status="completed")
    _seed_rename(journal, status="completed")
    _seed_rename(journal, status="failed", fail=True)
    result = service.list_batches(
        HistoryFilters(
            operation_type=HistoryOperationType.BULK_RENAME,
            batch_status=HistoryBatchStatus.COMPLETED,
            search="photos",
        )
    )
    assert result.totals.matching_batches == 1
    assert result.batches[0].status == "completed"
    manager.close()


def test_timestamp_sort_and_secondary_id(tmp_path: Path) -> None:
    manager, journal, service = _db(tmp_path)
    first = _seed_organize(journal)
    second = _seed_rename(journal)
    newest = service.list_batches(HistoryFilters(newest_first=True))
    oldest = service.list_batches(HistoryFilters(newest_first=False))
    # Same-second timestamps fall back to SQLite rowid (insertion order).
    assert newest.batches[0].batch_id == second
    assert newest.batches[1].batch_id == first
    assert oldest.batches[0].batch_id == first
    assert oldest.batches[1].batch_id == second
    manager.close()


def test_pagination(tmp_path: Path) -> None:
    manager, journal, service = _db(tmp_path)
    for _ in range(5):
        _seed_organize(journal)
    page1 = service.list_batches(HistoryFilters(limit=2, offset=0))
    page2 = service.list_batches(HistoryFilters(limit=2, offset=2))
    assert len(page1.batches) == 2
    assert len(page2.batches) == 2
    assert page1.totals.matching_batches == 5
    ids1 = {b.batch_id for b in page1.batches}
    ids2 = {b.batch_id for b in page2.batches}
    assert ids1.isdisjoint(ids2)
    manager.close()


def test_list_entries_and_failed_error(tmp_path: Path) -> None:
    manager, journal, service = _db(tmp_path)
    batch_id = _seed_rename(journal, status="failed", fail=True)
    entries = service.list_entries(batch_id)
    assert len(entries) == 1
    assert entries[0].status == "failed"
    assert entries[0].error_details == "collision"
    assert entries[0].operation_type == "rename"
    manager.close()


def test_multiple_entries_per_batch(tmp_path: Path) -> None:
    manager, journal, service = _db(tmp_path)
    batch_id = journal.begin_batch(
        operation_type="organize_move",
        summary="multi",
        source_root=r"C:\s",
        destination_root=r"C:\d",
        mode="category",
    )
    for name in ("a.txt", "b.txt", "c.txt"):
        eid = journal.add_entry(
            batch_id,
            source_path=rf"C:\s\{name}",
            destination_path=rf"C:\d\{name}",
            operation_type="move",
        )
        journal.complete_entry(eid, status="success")
    journal.complete_batch(batch_id, status="completed", summary="3 moved")
    batch = service.get_batch(batch_id)
    assert batch is not None
    assert batch.entry_total == 3
    assert batch.entry_success == 3
    assert len(service.list_entries(batch_id)) == 3
    manager.close()


def test_missing_fields_tolerate_nulls(tmp_path: Path) -> None:
    manager, _journal, service = _db(tmp_path)
    manager.connection.execute(
        """
        INSERT INTO operation_batches (
            id, operation_type, status, summary, source_root, destination_root,
            mode, created_at, details_json
        ) VALUES ('legacy-1', 'organize_move', 'completed', '', '', '', '',
                  '2020-01-01T00:00:00+00:00', '{}')
        """
    )
    manager.connection.commit()
    result = service.list_batches()
    assert result.totals.all_batches == 1
    assert result.batches[0].source_root == ""
    assert result.batches[0].entry_total == 0
    manager.close()


def test_totals_not_double_counted(tmp_path: Path) -> None:
    manager, journal, service = _db(tmp_path)
    _seed_organize(journal, status="completed")
    _seed_rename(journal, status="failed", fail=True)
    result = service.list_batches()
    totals = result.totals
    assert totals.all_batches == 2
    assert totals.all_completed == 1
    assert totals.all_failed == 1
    assert totals.all_completed + totals.all_failed == totals.all_batches
    manager.close()
