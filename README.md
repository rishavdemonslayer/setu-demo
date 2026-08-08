# Reconciliation Service API

A backend service built with FastAPI and SQLAlchemy to ingest financial transaction events, track payment states, generate daily reconciliation summaries, and detect data discrepancies across merchants.

## Overview
This microservice handles the ingestion of high-volume transaction lifecycle events (initiations, processing, failures, and settlements). It builds an internal source of truth for transaction states and provides clean endpoints for operational auditing and reconciliation.

## Architecture Overview
The application follows a simple microservice design focused on speed, efficiency, and reliability:

- **Framework**: FastAPI for high-performance async web handling and automatic schema validation using Pydantic.
- **ORM & Database**: SQLAlchemy ORM backed by SQLite for zero-config persistence and straightforward database management.
- **Security**: API Key authentication enforced via FastAPI dependencies using the `X-API-Key` request header.
- **Batch Processing Strategy**: The ingestion logic deduplicates incoming events in memory and processes database updates using batch operations. This approach prevents memory bloat and keeps execution times within a few seconds even for payloads containing thousands of events.

## Local Setup and Initialization
Here is how the project was set up and how you can run it locally on your machine.

### Prerequisites
- Python 3.11 or higher
- Git

### Step-by-Step Installation
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/rishavdemonslayer/setu-demo.git
    cd setu-demo
    ```
2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv

    # On macOS/Linux:
    source venv/bin/activate

    # On Windows (Command Prompt):
    venv\Scripts\activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Set the Environment Variable:**
    The API requires a secret key for authentication. You must export it before launching the app.
    ```bash
    # On macOS/Linux:
    export API_KEY="your-secret-api-key"

    # On Windows (Command Prompt):
    set API_KEY="your-secret-api-key"
    ```
5.  **Start the local server:**
    ```bash
    uvicorn main:app --reload
    ```
    The service will run locally at `http://127.0.0.1:8000`. You can access interactive documentation at `http://127.0.0.1:8000/docs`.

## Authentication
All endpoints require an API Key supplied in the HTTP request headers:

- **Header Key**: `X-API-Key`
- **Header Value**: `<your-configured-api-key>`

If the header is missing or incorrect, the server returns a `401 Unauthorized` status code.

## API Documentation and Examples
### 1. Event Ingestion
`POST /events`

Ingests financial events. This endpoint accepts either a single JSON object or a JSON array of multiple event objects.

**Request Example (Single Event)**
```bash
curl --location 'http://127.0.0.1:8000/events' \
--header 'Content-Type: application/json' \
--header 'X-API-Key: your-secret-api-key' \
--data '{
    "event_id": "d6e55673-3d91-4340-9a96-4530ebe6e3c1",
    "event_type": "settled",
    "transaction_id": "6c0926f8-089f-495c-afd6-6297688dd1f7",
    "merchant_id": "merchant_5",
    "merchant_name": "StyleHub",
    "amount": 45548.08,
    "currency": "INR",
    "timestamp": "2026-04-08T14:59:54.731227+00:00"
}'
```
**Response Example (Single Event)**
```json
{
  "message": "Event ingested successfully"
}
```
**Response Example (Bulk Array Input)**
```json
{
  "message": "Bulk ingestion complete",
  "processed": 1024,
  "duplicates_ignored": 12
}
```

### 2. List Transactions
`GET /transactions`

Retrieves a paginated list of transactions, sorted by creation date in descending order.

**Headers Required**
- `page-number`: Index starting at 0
- `page-size`: Must be strictly set to 100

**Request Example**
```bash
curl --location 'http://127.0.0.1:8000/transactions' \
--header 'page-number: 0' \
--header 'page-size: 100' \
--header 'X-API-Key: your-secret-api-key'
```
**Response Example**
```json
[
  {
    "id": "6c0926f8-089f-495c-afd6-6297688dd1f7",
    "merchant_id": "merchant_5",
    "amount": 45548.08,
    "currency": "INR",
    "status": "settled",
    "created_at": "2026-08-08T16:45:10",
    "events": []
  }
]
```

### 3. Get Single Transaction
`GET /transactions/{transaction_id}`

Fetches details for a specific transaction by its unique identifier.

**Response Example**
```json
{
  "id": "6c0926f8-089f-495c-afd6-6297688dd1f7",
  "merchant_id": "merchant_5",
  "amount": 45548.08,
  "currency": "INR",
  "status": "settled",
  "created_at": "2026-08-08T16:45:10",
  "events": []
}
```

### 4. Reconciliation Summary
`GET /reconciliation/summary`

Groups transactions across three dimensions: merchant ID, date, and status. It aggregates total transaction count and monetary sums directly inside the database.

**Request Example**
```bash
curl --location 'http://127.0.0.1:8000/reconciliation/summary' \
--header 'X-API-Key: your-secret-api-key'
```
**Response Example**
```json
[
  {
    "merchant_id": "merchant_1",
    "date": "2026-08-08",
    "status": "settled",
    "count": 45,
    "total_amount": 120500.5
  },
  {
    "merchant_id": "merchant_1",
    "date": "2026-08-08",
    "status": "payment_failed",
    "count": 3,
    "total_amount": 4500.0
  }
]
```

### 5. Reconciliation Discrepancies
`GET /reconciliation/discrepancies`

Scans transaction logs to locate broken state transitions or inconsistencies. Results are grouped by merchant for operational clarity.

It detects two main issues:
- **Settled with failures**: Transactions marked as settled despite having a recorded payment failure event.
- **Processed missing settlement**: Transactions stuck in `payment_processed` without reaching a terminal settlement state.

**Request Example**
```bash
curl --location 'http://127.0.0.1:8000/reconciliation/discrepancies' \
--header 'X-API-Key: your-secret-api-key'
```
**Response Example**
```json
{
  "settled_with_failures": [
    {
      "merchant_id": "merchant_4",
      "count": 2,
      "transaction_id": [
        "9bde585d-3ccc-458d-bec1-fe72d3290d5f",
        "fb0e988e-48fa-46f8-a869-b73c828b3ade"
      ]
    }
  ],
  "processed_missing_settlement": [
    {
      "merchant_id": "merchant_1",
      "count": 1,
      "transaction_id": [
        "5d4c4a6e-c24a-4d9b-aedc-59b2358fd7fd"
      ]
    }
  ]
}
```

## Deployment Details
The service is configured for cloud deployment on platforms like Render or Koyeb.

- **Environment Variable**: Set `API_KEY` in the hosting platform environment configuration settings.
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Assumptions and Tradeoffs
- **Storage Choice (SQLite vs PostgreSQL)**: SQLite was selected for simple local testing and immediate execution without external software dependencies. In a high-traffic production system, a managed database like PostgreSQL would be used to support concurrent write locks and scaling.
- **Ephemeral Disk Behavior**: Free cloud tiers wipe local files when containers restart. On cloud hosting, re-ingesting events populates the database cleanly for testing sessions.
- **Database Lookups vs Memory Overhead**: To optimize ingestion speed, the system queries existing IDs in bulk using SQL `.in_()` clauses rather than issuing single lookups per record. This approach keeps write speeds fast and prevents database connections from hanging.