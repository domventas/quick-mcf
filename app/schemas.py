"""
Pydantic schemas for API request/response models.
"""

from datetime import datetime
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Fulfillment
# ---------------------------------------------------------------------------

class AddressSchema(BaseModel):
    name: str
    line1: str
    line2: str = ""
    line3: str = ""
    city: str
    state_or_region: str
    postal_code: str
    country_code: str = "US"
    phone: str = ""


class FulfillmentItemSchema(BaseModel):
    seller_sku: str
    quantity: int
    seller_fulfillment_order_item_id: str = ""  # Auto-generated if empty


class CreateFulfillmentRequest(BaseModel):
    seller_fulfillment_order_id: str = ""  # Auto-generated if empty
    displayable_order_id: str
    displayable_order_date: datetime | None = None
    displayable_order_comment: str = "Thank you for your order"
    shipping_speed_category: str = "Standard"  # Standard, Expedited, Priority
    destination_address: AddressSchema
    items: list[FulfillmentItemSchema]
    marketplace_id: str = ""  # Uses config default if empty


class FulfillmentPreviewRequest(BaseModel):
    address: AddressSchema
    items: list[FulfillmentItemSchema]
    shipping_speed_categories: list[str] = Field(default_factory=lambda: ["Standard", "Expedited", "Priority"])
    marketplace_id: str = ""



class FulfillmentOrderResponse(BaseModel):
    seller_fulfillment_order_id: str
    amazon_status: str
    internal_status: str
    dry_run: bool = False
    details: dict | None = None
    message: str = ""

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

class InventoryItemResponse(BaseModel):
    seller_sku: str
    asin: str
    afn_fulfillable_quantity: int
    marketplace_id: str
    last_synced_at: datetime | None = None

    class Config:
        from_attributes = True


class InventorySyncResponse(BaseModel):
    status: str
    message: str
    items_synced: int = 0
    snapshot_id: str = ""
    report_id: str = ""
    duration_seconds: float = 0


# ---------------------------------------------------------------------------
# Orders / Fulfillment Status
# ---------------------------------------------------------------------------

class OrderStatusResponse(BaseModel):
    seller_fulfillment_order_id: str
    amazon_status: str
    internal_status: str
    shipment_status: str | None = None
    displayable_order_id: str | None = None
    shipping_speed_category: str | None = None
    order_created_at: datetime | None = None
    status_changed_at: datetime | None = None
    last_polled_at: datetime | None = None

    class Config:
        from_attributes = True


class StatusHistoryEntry(BaseModel):
    old_status: str | None
    new_status: str
    shipment_status: str | None = None
    changed_at: datetime

    class Config:
        from_attributes = True


class OrderPollResponse(BaseModel):
    status: str
    message: str
    total_polled: int = 0
    changed: int = 0
    failures: int = 0


# ---------------------------------------------------------------------------
# Health / Jobs
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    environment: str
    dry_run: bool
    marketplace_id: str


class JobStatusResponse(BaseModel):
    job_name: str
    last_run: datetime | None = None
    next_run: datetime | None = None
    status: str = "scheduled"
