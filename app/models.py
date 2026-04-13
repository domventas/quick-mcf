"""
SQLAlchemy ORM models for MCF backend.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

class InventorySnapshot(Base):
    """One row per SKU per report snapshot. Keeps full history."""
    __tablename__ = "inventory_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), index=True)
    report_id: Mapped[str] = mapped_column(String(128))

    asin: Mapped[str] = mapped_column(String(20))
    seller_sku: Mapped[str] = mapped_column(String(128))
    fnsku: Mapped[str] = mapped_column(String(20), default="")
    product_name: Mapped[str] = mapped_column(String(512), default="")

    afn_fulfillable_quantity: Mapped[int] = mapped_column(Integer, default=0)
    afn_inbound_working_quantity: Mapped[int] = mapped_column(Integer, default=0)
    afn_inbound_shipped_quantity: Mapped[int] = mapped_column(Integer, default=0)
    afn_inbound_receiving_quantity: Mapped[int] = mapped_column(Integer, default=0)
    afn_reserved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    afn_unsellable_quantity: Mapped[int] = mapped_column(Integer, default=0)
    afn_researching_quantity: Mapped[int] = mapped_column(Integer, default=0)
    afn_total_quantity: Mapped[int] = mapped_column(Integer, default=0)

    condition: Mapped[str] = mapped_column(String(32), default="")
    marketplace_id: Mapped[str] = mapped_column(String(20), default="")
    snapshot_taken_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class InventoryCurrent(Base):
    """Latest inventory per SKU — rebuilt after each sync."""
    __tablename__ = "inventory_current"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_sku: Mapped[str] = mapped_column(String(128), index=True)
    asin: Mapped[str] = mapped_column(String(20))
    fnsku: Mapped[str] = mapped_column(String(20), default="")
    product_name: Mapped[str] = mapped_column(String(512), default="")

    afn_fulfillable_quantity: Mapped[int] = mapped_column(Integer, default=0)
    afn_reserved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    afn_unsellable_quantity: Mapped[int] = mapped_column(Integer, default=0)
    afn_total_quantity: Mapped[int] = mapped_column(Integer, default=0)

    marketplace_id: Mapped[str] = mapped_column(String(20), default="")
    last_snapshot_id: Mapped[str] = mapped_column(String(64), default="")
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# Fulfillment Orders
# ---------------------------------------------------------------------------

class FulfillmentOrderRecord(Base):
    """Current state of each MCF fulfillment order."""
    __tablename__ = "fulfillment_order_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_fulfillment_order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    marketplace_id: Mapped[str] = mapped_column(String(20), default="")

    # Status
    amazon_status: Mapped[str] = mapped_column(String(32), default="")
    internal_status: Mapped[str] = mapped_column(String(32), default="", index=True)
    previous_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Order details (stored as JSON strings for simplicity)
    displayable_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    shipping_speed_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    destination_address_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipments_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    order_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    amazon_last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_polled_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Quicklly sync
    quicklly_push_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    quicklly_pushed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    quicklly_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit
    request_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class FulfillmentStatusHistory(Base):
    """Append-only log of every status change."""
    __tablename__ = "fulfillment_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_fulfillment_order_id: Mapped[str] = mapped_column(String(64), index=True)
    old_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str] = mapped_column(String(32))
    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    full_response_json: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# Sync State
# ---------------------------------------------------------------------------

class SyncState(Base):
    """Tracks sync checkpoints for each job."""
    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_name: Mapped[str] = mapped_column(String(64), unique=True)
    last_checkpoint: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_report_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
