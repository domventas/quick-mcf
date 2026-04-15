# MCF Backend

A streamlined Amazon Multi-Channel Fulfillment (MCF) backend service built with FastAPI and SQLite. This service handles inventory synchronization, order creation, and status tracking via the Amazon Selling Partner API (SP-API).

## 🚀 Getting Started

1.  **Installation**:
    ```bash
    uv pip install -r pyproject.toml
    ```
2.  **Configuration**:
    Copy `.env.example` to `.env` and fill in your Amazon SP-API credentials.
3.  **Run the App**:
    ```bash
    uv run fastapi dev app/main.py
    ```

---

## 🔐 Authentication

All API endpoints are protected via an API Key authentication system.

*   **Header Required**: `X-API-Key: <your_api_key>`
*   **Master Key**: A `MASTER_API_KEY` can be configured in `.env` (default `dev_master_key`) for bootstrapping and admin tasks.
*   **Admin Route**: Use `POST /api/v1/admin/keys` (authorized with the Master Key) to generate individual client keys.

---

## 🛠️ Core Features

The backend implements the following prioritized features:

### 1. Fulfillment Order Push
Create a new fulfillment order at Amazon.
*   **Endpoint**: `POST /api/v1/fulfillment/orders`
*   **Action**: Validates the payload and submits the order to Amazon FBA.
*   **Note**: Respects `DRY_RUN=True` in `.env` to avoid real Amazon calls during testing.

### 2. Inventory Sync (Reports API)
Sync your FBA inventory levels to a local database.
*   **Automatic**: Runs every 3 hours (configurable via `INVENTORY_SYNC_INTERVAL_HOURS`).
*   **Manual Trigger**: `POST /api/v1/inventory/sync`
*   **Stored Fields**: Strictly tracks `seller_sku`, `asin`, and `afn_fulfillable_quantity`.

### 3. Order Status Polling
Tracks the lifecycle of your MCF orders.
*   **Automatic**: Runs every 60 minutes (configurable via `ORDER_POLL_INTERVAL_MINUTES`).
*   **Manual Trigger**: `POST /api/v1/orders/sync`
*   **Auto-discovery**: Automatically discovers and tracks any fulfillment order processed by Amazon (e.g., from Seller Central) that isn't yet in the local DB.
*   **Features**: Safely captures all updates, including `fulfillmentShipmentStatus`, meaning tracking numbers and shipping statuses are reliably recorded in the local history.

### 4. Background Job Monitoring
Verify the status of APScheduler background jobs.
*   **Endpoint**: `GET /api/v1/jobs`
*   **Returns**: Real-time exact next-run datetimes and active status directly from the global scheduler instance.

---

## 📦 Project Structure

- `app/services/`: Core business logic for Amazon integrations and API key validation.
- `app/routers/`: Modularized API endpoint definitions (Fulfillment, Orders, Inventory, Admin, Jobs).
- `app/models/`: SQLite database schema, including API Keys and Sync states.
- `app/jobs.py`: Global APScheduler instance and background task wrappers.
- `app/amazon_client.py`: Unified SP-API client supporting mock, sandbox, and production environments.
