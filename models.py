from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import datetime
from database import Base

class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(String, primary_key=True, index=True)
    name = Column(String)

    # Relationship to easily fetch all transactions for a specific merchant
    transactions = relationship("Transaction", back_populates="merchant")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)
    merchant_id = Column(String, ForeignKey("merchants.id"))
    amount = Column(Float)
    currency = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    merchant = relationship("Merchant", back_populates="transactions")
    events = relationship("Event", back_populates="transaction")

class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"))
    event_type = Column(String)
    timestamp = Column(DateTime)
    transaction = relationship("Transaction", back_populates="events")
