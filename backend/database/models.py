from sqlalchemy import Column, Integer, String, Float, Text, DateTime
import datetime
from database.connection import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    balance = Column(Float, default=0.0)
    data_remaining = Column(String, default="0 GB")
    minutes_remaining = Column(Integer, default=0)

class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String, unique=True, index=True, nullable=False) # e.g., CMP-2026-001
    customer_id = Column(String, nullable=False)
    issue_type = Column(String, nullable=False)   # Network, Billing, Package
    priority = Column(String, nullable=False)     # Low, Medium, High
    description = Column(Text, nullable=False)
    status = Column(String, default="Open")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)