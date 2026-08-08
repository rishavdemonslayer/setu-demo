import os
from fastapi import FastAPI, Depends, HTTPException, Query, status, Header
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import models
import schemas
from database import engine, get_db
from sqlalchemy import func
from typing import List, Union

models.Base.metadata.create_all(bind=engine)
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise ValueError("FATAL ERROR: API_KEY is not set. Please configure it before starting the server.")

api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )

app = FastAPI(
    title="Reconciliation Service",
    dependencies=[Depends(verify_api_key)]
)

@app.post("/events", status_code=202)
def ingest_event(payload: Union[List[schemas.EventCreate], schemas.EventCreate], db: Session = Depends(get_db)):
    is_bulk = isinstance(payload, list)
    events = payload if is_bulk else [payload]

    unique_events = {}
    for e in events:
        if e.event_id not in unique_events:
            unique_events[e.event_id] = e

    incoming_ids = list(unique_events.keys())
    existing_events = db.query(models.Event.id).filter(models.Event.id.in_(incoming_ids)).all()
    existing_ids = {e.id for e in existing_events}
    new_events_data = [e for e in unique_events.values() if e.event_id not in existing_ids]

    if not new_events_data:
        if is_bulk:
            return {
                "message": "Bulk ingestion complete",
                "processed": 0,
                "duplicates_ignored": len(events)
            }
        else:
            return {"message": "Event already processed"}

    merchant_ids = {e.merchant_id for e in new_events_data}
    transaction_ids = {e.transaction_id for e in new_events_data}

    existing_merchants = {
        m.id: m for m in db.query(models.Merchant).filter(models.Merchant.id.in_(merchant_ids)).all()
    }
    existing_txs = {
        t.id: t for t in db.query(models.Transaction).filter(models.Transaction.id.in_(transaction_ids)).all()
    }

    new_merchants = {}
    new_transactions = {}
    new_event_objs = []

    for event in new_events_data:
        if event.merchant_id not in existing_merchants and event.merchant_id not in new_merchants:
            new_m = models.Merchant(id=event.merchant_id, name=event.merchant_name)
            new_merchants[event.merchant_id] = new_m

        if event.transaction_id not in existing_txs:
            if event.transaction_id not in new_transactions:
                new_tx = models.Transaction(
                    id=event.transaction_id,
                    merchant_id=event.merchant_id,
                    amount=event.amount,
                    currency=event.currency,
                    status=event.event_type
                )
                new_transactions[event.transaction_id] = new_tx
            else:
                new_transactions[event.transaction_id].status = event.event_type
        else:
            existing_txs[event.transaction_id].status = event.event_type

        new_event_obj = models.Event(
            id=event.event_id,
            transaction_id=event.transaction_id,
            event_type=event.event_type,
            timestamp=event.timestamp
        )
        new_event_objs.append(new_event_obj)

    if new_merchants:
        db.add_all(list(new_merchants.values()))
    if new_transactions:
        db.add_all(list(new_transactions.values()))
    if new_event_objs:
        db.add_all(new_event_objs)

    db.commit()

    if is_bulk:
        return {
            "message": "Bulk ingestion complete",
            "processed": len(new_events_data),
            "duplicates_ignored": len(events) - len(new_events_data)
        }
    else:
        return {"message": "Event ingested successfully"}


@app.get("/transactions", response_model=list[schemas.TransactionResponse])
def list_transactions(
    merchant_id: str = None,
    status: str = None,
    page_number: int = Header(default=0, description="Page index starting at 0"),
    page_size: int = Header(default=100, description="Strictly fixed to 100 items per page"),
    db: Session = Depends(get_db)
):
    if page_size != 100:
        raise HTTPException(status_code=400, detail="The page-size header must be exactly 100")
    skip = page_number * page_size

    query = db.query(models.Transaction)
    if merchant_id:
        query = query.filter(models.Transaction.merchant_id == merchant_id)
    if status:
        query = query.filter(models.Transaction.status == status)
    return query.order_by(models.Transaction.created_at.desc()).offset(skip).limit(page_size).all()


@app.get("/transactions/{transaction_id}", response_model=schemas.TransactionResponse)
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    tx = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()

    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@app.get("/reconciliation/summary")
def get_reconciliation_summary(db: Session = Depends(get_db)):
    summary_query = db.query(
        models.Transaction.merchant_id,
        func.date(models.Transaction.created_at).label('date'),
        models.Transaction.status,
        func.count(models.Transaction.id).label('count'),
        func.sum(models.Transaction.amount).label('total_amount')
    ).group_by(
        models.Transaction.merchant_id,
        func.date(models.Transaction.created_at),
        models.Transaction.status
    ).all()
    result = []
    for row in summary_query:
        result.append({
            "merchant_id": row.merchant_id,
            "date": row.date,
            "status": row.status,
            "count": row.count,
            "total_amount": round(row.total_amount, 2) if row.total_amount else 0.0
        })
    return result


@app.get("/reconciliation/discrepancies")
def get_discrepancies(db: Session = Depends(get_db)):
    settled_but_failed = db.query(models.Transaction).join(models.Event).filter(
        models.Transaction.status == "settled",
        models.Event.event_type == "payment_failed"
    ).all()

    processed_not_settled = db.query(models.Transaction).filter(
        models.Transaction.status == "payment_processed"
    ).all()

    def format_grouped_discrepancies(transactions):
        grouped_data = {}
        for tx in transactions:
            if tx.merchant_id not in grouped_data:
                grouped_data[tx.merchant_id] = []
            grouped_data[tx.merchant_id].append(tx.id)
        return [
            {
                "merchant_id": m_id,
                "count": len(tx_ids),
                "transaction_id": tx_ids
            }
            for m_id, tx_ids in grouped_data.items()
        ]

    return {
        "settled_with_failures": format_grouped_discrepancies(settled_but_failed),
        "processed_missing_settlement": format_grouped_discrepancies(processed_not_settled)
    }
