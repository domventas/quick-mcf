"""
Quicklly push client — sends fulfillment status updates to Quicklly.
"""

import logging
from datetime import datetime, timezone

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class QuickllyClient:
    """Simple HTTP client for pushing status updates to Quicklly."""

    def __init__(self):
        self.api_url = settings.QUICKLLY_API_URL
        self.api_key = settings.QUICKLLY_API_KEY
        self.enabled = settings.QUICKLLY_PUSH_ENABLED

    async def push_status_update(self, order_data: dict) -> dict:
        """
        Push a fulfillment status update to Quicklly.

        Returns: {"status": "pushed"/"skipped"/"failed", "error": "..."}
        """
        if not self.enabled:
            return {"status": "skipped", "error": None}

        if not self.api_url:
            logger.warning("Quicklly push enabled but QUICKLLY_API_URL is empty")
            return {"status": "failed", "error": "QUICKLLY_API_URL not configured"}

        payload = {
            "order_id": order_data.get("seller_fulfillment_order_id"),
            "status": order_data.get("internal_status"),
            "amazon_status": order_data.get("amazon_status"),
            "tracking": order_data.get("shipments"),
            "updated_at": order_data.get("status_changed_at"),
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.api_url.rstrip('/')}/fulfillment/status",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                logger.info(f"Quicklly push OK for order {payload['order_id']}")
                return {"status": "pushed", "error": None}

        except httpx.HTTPStatusError as e:
            error_msg = f"Quicklly HTTP {e.response.status_code}: {e.response.text[:200]}"
            logger.error(error_msg)
            return {"status": "failed", "error": error_msg}
        except Exception as e:
            error_msg = f"Quicklly push error: {str(e)}"
            logger.error(error_msg)
            return {"status": "failed", "error": error_msg}


# Module-level singleton
quicklly_client = QuickllyClient()
