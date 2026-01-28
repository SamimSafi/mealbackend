"""In-memory runtime store for sync progress. All transports (WebSocket, SSE, polling) read from here first; ETL updates it during sync."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from models import SyncLog

_store: Dict[int, dict] = {}


def get(sync_id: int) -> Optional[dict]:
    return _store.get(sync_id)


def set(sync_id: int, data: dict) -> None:
    _store[sync_id] = {**data, "sync_id": sync_id}


def from_sync_log(sync_log: "SyncLog") -> dict:
    """Build a progress dict from a SyncLog ORM. Used by ETL and main to push into the store."""
    status = getattr(sync_log, "status", None) or "running"
    total_forms = getattr(sync_log, "total_forms", None) or 0
    total_submissions = getattr(sync_log, "total_submissions", None) or 0
    current_form_index = getattr(sync_log, "current_form_index", None) or 0
    current_submission_index = getattr(sync_log, "current_submission_index", None) or 0

    message = None
    if status == "running":
        if total_forms and total_forms > 1:
            message = f"Syncing form {current_form_index + 1} of {total_forms}"
            if getattr(sync_log, "current_form_title", None):
                message += f": {sync_log.current_form_title}"
        elif total_submissions and total_submissions > 0:
            message = f"Processing submission {current_submission_index} of {total_submissions}"
    elif status == "success":
        message = "Sync completed successfully"
    elif status == "error":
        message = f"Sync failed: {getattr(sync_log, 'error_message', None) or ''}"

    return {
        "sync_id": getattr(sync_log, "id", None),
        "status": status,
        "current_form_index": current_form_index,
        "total_forms": total_forms,
        "current_form_id": getattr(sync_log, "current_form_id", None),
        "current_form_title": getattr(sync_log, "current_form_title", None),
        "current_submission_index": current_submission_index,
        "total_submissions": total_submissions,
        "progress_percentage": float(getattr(sync_log, "progress_percentage", None) or 0),
        "records_added": getattr(sync_log, "records_added", None) or 0,
        "records_updated": getattr(sync_log, "records_updated", None) or 0,
        "records_processed": getattr(sync_log, "records_processed", None) or 0,
        "started_at": (sync_log.started_at.isoformat() if getattr(sync_log, "started_at", None) else None),
        "completed_at": (sync_log.completed_at.isoformat() if getattr(sync_log, "completed_at", None) else None),
        "error_message": getattr(sync_log, "error_message", None),
        "message": message,
    }
