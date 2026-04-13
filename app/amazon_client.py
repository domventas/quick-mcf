"""
Amazon SP-API client — single class handling all environments.

- production: real SP-API calls
- sandbox:    SP-API sandbox endpoints
- mock:       returns fake data, no network
"""

import json
import logging
from datetime import datetime

from sp_api.api import FulfillmentOutbound, Reports
from sp_api.base import Marketplaces

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Marketplace mapping
# ---------------------------------------------------------------------------

MARKETPLACE_MAP = {
    "ATVPDKIKX0DER": Marketplaces.US,
    "A2EUQ1WTGCTBG2": Marketplaces.CA,
    "A1AM78C64UM0Y8": Marketplaces.MX,
    "A1F83G8C2ARO7P": Marketplaces.UK,
    "A1PA6795UKMFR9": Marketplaces.DE,
    "A13V1IB3VIYZZH": Marketplaces.FR,
    "APJ6JRA9NG5V4":  Marketplaces.IT,
    "A1RKKUPIHCS9HS": Marketplaces.ES,
    "A21TJRUUN4KGV":  Marketplaces.IN,
}


def _get_marketplace():
    return MARKETPLACE_MAP.get(settings.SP_API_MARKETPLACE_ID, Marketplaces.US)


def _sp_credentials():
    """Build credentials dict for python-amazon-sp-api."""
    return dict(
        refresh_token=settings.SP_API_REFRESH_TOKEN,
        lwa_app_id=settings.SP_API_CLIENT_ID,
        lwa_client_secret=settings.SP_API_CLIENT_SECRET,
        aws_access_key=settings.SP_API_AWS_ACCESS_KEY,
        aws_secret_key=settings.SP_API_AWS_SECRET_KEY,
        role_arn=settings.SP_API_ROLE_ARN,
    )


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_FULFILLMENT_ORDERS = [
    {
        "sellerFulfillmentOrderId": "MOCK-ORDER-001",
        "displayableOrderId": "MOCK-DISPLAY-001",
        "fulfillmentOrderStatus": "Processing",
        "statusUpdatedDate": "2026-04-13T00:00:00Z",
        "shippingSpeedCategory": "Standard",
    },
    {
        "sellerFulfillmentOrderId": "MOCK-ORDER-002",
        "displayableOrderId": "MOCK-DISPLAY-002",
        "fulfillmentOrderStatus": "Complete",
        "statusUpdatedDate": "2026-04-12T00:00:00Z",
        "shippingSpeedCategory": "Expedited",
    },
]

MOCK_INVENTORY_REPORT = (
    "sku\tasin\tafn-fulfillable-quantity\n"
    "SKU-001\tB000TEST01\t100\n"
    "SKU-002\tB000TEST02\t50\n"
)


# ---------------------------------------------------------------------------
# Amazon Client
# ---------------------------------------------------------------------------

class AmazonClient:
    """
    Unified Amazon SP-API client.
    Respects settings.ENVIRONMENT for endpoint routing.
    """

    def __init__(self):
        self.is_mock = settings.ENVIRONMENT == "mock"
        self.is_sandbox = settings.ENVIRONMENT == "sandbox"
        logger.info(f"AmazonClient initialized: environment={settings.ENVIRONMENT}")

    # --- Internal helpers ---

    def _fulfillment_api(self) -> FulfillmentOutbound:
        creds = _sp_credentials()
        return FulfillmentOutbound(
            marketplace=_get_marketplace(),
            credentials=creds,
        )

    def _reports_api(self) -> Reports:
        creds = _sp_credentials()
        return Reports(
            marketplace=_get_marketplace(),
            credentials=creds,
        )

    # -----------------------------------------------------------------------
    # Fulfillment Outbound
    # -----------------------------------------------------------------------

    def get_fulfillment_preview(self, body: dict) -> dict:
        """Get fulfillment preview — validates items & address."""
        if self.is_mock:
            logger.info("MOCK: get_fulfillment_preview")
            return {
                "fulfillmentPreviews": [{
                    "shippingSpeedCategory": "Standard",
                    "isFulfillable": True,
                    "estimatedShippingWeight": {"unit": "pounds", "value": "2.0"},
                    "estimatedFees": [{"name": "FBAPerUnitFulfillmentFee", "amount": {"value": "3.99", "currencyCode": "USD"}}],
                }]
            }
        res = self._fulfillment_api().get_fulfillment_preview(**body)
        return res.payload

    def create_fulfillment_order(self, body: dict) -> dict:
        """Create a new MCF fulfillment order."""
        if self.is_mock:
            logger.info(f"MOCK: create_fulfillment_order — {body.get('sellerFulfillmentOrderId', 'N/A')}")
            return {"status": "created", "mock": True}

        res = self._fulfillment_api().create_fulfillment_order(**body)
        return res.payload or {"status": "created"}

    def get_fulfillment_order(self, order_id: str) -> dict:
        """Get full details of a specific fulfillment order."""
        if self.is_mock:
            logger.info(f"MOCK: get_fulfillment_order — {order_id}")
            return {
                "fulfillmentOrder": {
                    "sellerFulfillmentOrderId": order_id,
                    "displayableOrderId": f"DISPLAY-{order_id}",
                    "fulfillmentOrderStatus": "Processing",
                    "statusUpdatedDate": datetime.utcnow().isoformat() + "Z",
                    "shippingSpeedCategory": "Standard",
                    "destinationAddress": {"name": "Mock Customer", "city": "Seattle", "stateOrRegion": "WA"},
                },
                "fulfillmentOrderItems": [
                    {"sellerSku": "SKU-001", "quantity": 1, "sellerFulfillmentOrderItemId": "item-1"}
                ],
                "fulfillmentShipments": [],
            }
        res = self._fulfillment_api().get_fulfillment_order(sellerFulfillmentOrderId=order_id)
        return res.payload

    def list_all_fulfillment_orders(self, query_start_date: datetime) -> list[dict]:
        """List fulfillment orders updated since query_start_date. Handles pagination."""
        if self.is_mock:
            logger.info(f"MOCK: list_all_fulfillment_orders since {query_start_date}")
            return MOCK_FULFILLMENT_ORDERS

        all_orders = []
        next_token = None
        while True:
            kwargs = {}
            if next_token:
                kwargs["nextToken"] = next_token
            else:
                kwargs["queryStartDate"] = query_start_date.isoformat()

            res = self._fulfillment_api().list_all_fulfillment_orders(**kwargs)
            payload = res.payload or {}
            orders = payload.get("fulfillmentOrders", [])
            all_orders.extend(orders)

            next_token = payload.get("nextToken")
            if not next_token:
                break

        return all_orders

    def cancel_fulfillment_order(self, order_id: str) -> dict:
        """Cancel a fulfillment order (only if Received/Planning)."""
        if self.is_mock:
            logger.info(f"MOCK: cancel_fulfillment_order — {order_id}")
            return {"status": "cancelled", "mock": True}

        res = self._fulfillment_api().cancel_fulfillment_order(sellerFulfillmentOrderId=order_id)
        return res.payload or {"status": "cancelled"}

    # -----------------------------------------------------------------------
    # Reports API (for Inventory)
    # -----------------------------------------------------------------------

    def create_report(self, report_type: str, marketplace_ids: list[str]) -> str:
        """Request a report. Returns reportId."""
        if self.is_mock:
            logger.info(f"MOCK: create_report — {report_type}")
            return "MOCK-REPORT-001"

        res = self._reports_api().create_report(
            reportType=report_type,
            marketplaceIds=marketplace_ids,
        )
        return res.payload.get("reportId", "")

    def get_report(self, report_id: str) -> dict:
        """Check report generation status."""
        if self.is_mock:
            logger.info(f"MOCK: get_report — {report_id}")
            return {
                "reportId": report_id,
                "processingStatus": "DONE",
                "reportDocumentId": "MOCK-DOC-001",
            }

        res = self._reports_api().get_report(report_id)
        return res.payload

    def get_report_document(self, document_id: str) -> str:
        """Download report document content as string."""
        if self.is_mock:
            logger.info(f"MOCK: get_report_document — {document_id}")
            return MOCK_INVENTORY_REPORT

        res = self._reports_api().get_report_document(document_id, download=True)
        # python-amazon-sp-api returns the document content in payload
        payload = res.payload
        if isinstance(payload, dict):
            return payload.get("document", "")
        return str(payload)


# Module-level singleton
amazon_client = AmazonClient()
