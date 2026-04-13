"""
Inventory service — Reports API bulk snapshot sync.
"""

import csv
import io
import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.amazon_client import amazon_client
from app.config import settings
from app.models import InventoryCurrent, InventorySnapshot, SyncState

logger = logging.getLogger(__name__)

REPORT_TYPE = "GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA"

# Map report TSV columns → our model fields
# MINIMIZED: Only seller_sku, asin, afn_fulfillable_quantity
COLUMN_MAP = {
    "sku": "seller_sku",
    "asin": "asin",
    "afn-fulfillable-quantity": "afn_fulfillable_quantity",
}

INT_FIELDS = {
    "afn_fulfillable_quantity",
}


def _parse_report(content: str) -> list[dict]:
    """Parse tab-delimited report content into list of dicts."""
    reader = csv.DictReader(io.StringIO(content), delimiter="\t")
    rows = []
    for raw_row in reader:
        row = {}
        for report_col, model_field in COLUMN_MAP.items():
            value = raw_row.get(report_col, "")
            if model_field in INT_FIELDS:
                try:
                    value = int(value) if value else 0
                except ValueError:
                    value = 0
            row[model_field] = value
        rows.append(row)
    return rows


async def sync_inventory(db: AsyncSession) -> dict:
    """
    Full inventory sync via Reports API:
    1. Create report
    2. Poll until DONE
    3. Download & parse
    4. Bulk insert snapshots
    5. Rebuild inventory_current
    """
    start_time = time.time()
    marketplace = settings.SP_API_MARKETPLACE_ID
    snapshot_id = uuid.uuid4().hex[:16]
    now = datetime.now(timezone.utc)

    logger.info(f"Starting inventory sync — snapshot_id={snapshot_id}")

    # Step 1: Request report
    report_id = amazon_client.create_report(
        report_type=REPORT_TYPE,
        marketplace_ids=[marketplace],
    )
    logger.info(f"Report requested — reportId={report_id}")

    # Step 2: Poll for completion
    document_id = None
    wait_seconds = 30
    max_wait = 30 * 60  # 30 minutes max
    elapsed = 0

    while elapsed < max_wait:
        report_status = amazon_client.get_report(report_id)
        processing_status = report_status.get("processingStatus", "")

        if processing_status == "DONE":
            document_id = report_status.get("reportDocumentId")
            logger.info(f"Report DONE — documentId={document_id}")
            break
        elif processing_status in ("CANCELLED", "FATAL"):
            msg = f"Report failed with status: {processing_status}"
            logger.error(msg)
            return {"status": "error", "message": msg, "items_synced": 0, "snapshot_id": snapshot_id, "report_id": report_id, "duration_seconds": time.time() - start_time}

        logger.info(f"Report status: {processing_status} — waiting {wait_seconds}s (elapsed: {elapsed}s)")
        import asyncio
        await asyncio.sleep(wait_seconds)
        elapsed += wait_seconds
        wait_seconds = min(wait_seconds * 2, 300)  # Exponential backoff, max 5min

    if not document_id:
        msg = f"Report timed out after {max_wait}s"
        logger.error(msg)
        return {"status": "error", "message": msg, "items_synced": 0, "snapshot_id": snapshot_id, "report_id": report_id, "duration_seconds": time.time() - start_time}

    # Step 3: Download & parse
    content = amazon_client.get_report_document(document_id)
    rows = _parse_report(content)
    logger.info(f"Parsed {len(rows)} inventory items from report")

    if not rows:
        return {"status": "ok", "message": "Report was empty", "items_synced": 0, "snapshot_id": snapshot_id, "report_id": report_id, "duration_seconds": time.time() - start_time}

    # Step 4: Bulk insert into inventory_snapshots
    snapshot_records = [
        InventorySnapshot(
            snapshot_id=snapshot_id,
            report_id=report_id,
            marketplace_id=marketplace,
            snapshot_taken_at=now,
            **row,
        )
        for row in rows
    ]
    db.add_all(snapshot_records)

    # Step 5: Rebuild inventory_current (delete all, insert from snapshot)
    await db.execute(delete(InventoryCurrent))
    current_records = [
        InventoryCurrent(
            seller_sku=row["seller_sku"],
            asin=row["asin"],
            afn_fulfillable_quantity=row.get("afn_fulfillable_quantity", 0),
            marketplace_id=marketplace,
            last_snapshot_id=snapshot_id,
            last_synced_at=now,
        )
        for row in rows
    ]
    db.add_all(current_records)

    # Step 6: Update sync state
    stmt = select(SyncState).where(SyncState.job_name == "inventory_sync")
    result = await db.execute(stmt)
    sync_state = result.scalar_one_or_none()
    if sync_state:
        sync_state.last_checkpoint = now
        sync_state.last_report_id = report_id
        sync_state.last_snapshot_id = snapshot_id
    else:
        db.add(SyncState(
            job_name="inventory_sync",
            last_checkpoint=now,
            last_report_id=report_id,
            last_snapshot_id=snapshot_id,
        ))

    await db.commit()
    duration = time.time() - start_time
    logger.info(f"Inventory sync complete — {len(rows)} items, {duration:.1f}s")

    return {
        "status": "ok",
        "message": f"Synced {len(rows)} inventory items",
        "items_synced": len(rows),
        "snapshot_id": snapshot_id,
        "report_id": report_id,
        "duration_seconds": round(duration, 2),
    }


async def get_current_inventory(db: AsyncSession, sku: str | None = None) -> list[dict]:
    """Get current inventory, optionally filtered by SKU."""
    stmt = select(InventoryCurrent).order_by(InventoryCurrent.seller_sku)
    if sku:
        stmt = stmt.where(InventoryCurrent.seller_sku == sku)

    result = await db.execute(stmt)
    records = result.scalars().all()

    return [
        {
            "seller_sku": r.seller_sku,
            "asin": r.asin,
            "afn_fulfillable_quantity": r.afn_fulfillable_quantity,
            "marketplace_id": r.marketplace_id,
            "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
        }
        for r in records
    ]
