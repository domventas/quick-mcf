"""
Constants and Enums for the MCF Backend.
"""

# Map Amazon Outbound statuses to internal simplified statuses
FULFILLMENT_STATUS_MAP = {
    "New": "new",
    "Received": "received",
    "Planning": "planning",
    "Processing": "processing",
    "Cancelled": "cancelled",
    "Complete": "completed",
    "CompletePartialled": "completed_partial",
    "Unfulfillable": "unfulfillable",
    "Invalid": "failed",
}

def map_amazon_status(amazon_status: str) -> str:
    """Map Amazon status string to internal status."""
    return FULFILLMENT_STATUS_MAP.get(amazon_status, amazon_status.lower())
