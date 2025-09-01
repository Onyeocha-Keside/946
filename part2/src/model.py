from datetime import datetime

from uuid import uuid4

from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID



# SQLAlchemy Base
Base = declarative_base()


class InsurancePolicy(Base):
    """
    Insurance policy database model matching exact schema requirements.
    Exact field mapping as specified in requirements
    with proper PostgreSQL types and indexing.
    """
    __tablename__ = "insurance_policies"
    
    # Primary key
    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Exact schema fields as specified in requirements
    policy_number = Column(String(50), nullable=False, unique=True, index=True)
    insured_name = Column(String(200), nullable=False, index=True)
    sum_insured = Column(Float, nullable=False)
    premium = Column(Float, nullable=False)
    own_retention_ppn = Column(Float, nullable=False)
    own_retention_sum_insured = Column(Float, nullable=False)
    own_retention_premium = Column(Float, nullable=False)
    treaty_ppn = Column(Float, nullable=False)
    treaty_sum_insured = Column(Float, nullable=False)
    treaty_premium = Column(Float, nullable=False)
    insurance_period_start_date = Column(Date, nullable=False, index=True)
    insurance_period_end_date = Column(Date, nullable=False, index=True)
    
    # Metadata fields for tracking
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_policy_period', 'insurance_period_start_date', 'insurance_period_end_date'),
        Index('ix_policy_amounts', 'sum_insured', 'premium'),
        Index('ix_treaty_info', 'treaty_ppn', 'treaty_sum_insured', 'treaty_premium'),
    )


class DataIngestionLog(Base):
    """
    Track data ingestion operations for audit and monitoring.
    Comprehensive audit trail for data operations.
    """
    __tablename__ = "data_ingestion_logs"
    
    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    filename = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    rows_processed = Column(Integer, nullable=False, default=0)
    rows_successful = Column(Integer, nullable=False, default=0)
    rows_failed = Column(Integer, nullable=False, default=0)
    processing_time_ms = Column(Float, nullable=False)
    status = Column(String(20), nullable=False)  # success, failed, partial
    error_details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class QueryLog(Base):
    """
    Track API queries for monitoring and analytics.
    Query performance and usage tracking.
    """
    __tablename__ = "query_logs"
    
    id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    query_text = Column(Text, nullable=False)
    query_type = Column(String(50), nullable=True)
    processing_time_ms = Column(Float, nullable=False)
    langgraph_steps = Column(Integer, nullable=False, default=0)
    tokens_used = Column(Integer, nullable=False, default=0)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

