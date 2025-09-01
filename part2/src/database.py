import logging
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, and_, or_, text, inspect
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
#import asyncpg
#from alembic import command
#from alembic.config import Config

from src.model import Base, InsurancePolicy, DataIngestionLog, QueryLog
from src.schema import InsurancePolicyCreate
from src.config import Settings, get_settings


logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Database manager with connection pooling and async operations.
    Comprehensive database management with proper
    lifecycle handling, connection pooling, and error recovery.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = None
        self.async_session_factory = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize database connection and create tables."""
        if self._initialized:
            return
        
        try:
            # Create async engine with connection pooling
            self.engine = create_async_engine(
                self.settings.database_url,
                echo=self.settings.database_config["echo"],
                pool_size=self.settings.database_config["pool_size"],
                max_overflow=self.settings.database_config["max_overflow"],
                pool_timeout=self.settings.database_config["pool_timeout"],
                pool_pre_ping=True,  # Verify connections before use
                pool_recycle=3600,   # Recycle connections every hour
            )
            
            # Create session factory
            self.async_session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables if they don't exist
            await self.create_tables()
            
            self._initialized = True
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise
    
    async def create_tables(self):
        """Create database tables if they don't exist."""
        try:
            async with self.engine.begin() as conn:
                # Create tables
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Database tables created/verified")
        except Exception as e:
            logger.error(f"Error creating tables: {str(e)}")
            raise
    
    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")
    
    @asynccontextmanager
    async def get_session(self):
        """
        Get database session with proper error handling.
        Context manager ensures proper session lifecycle
        with automatic cleanup and error handling.
        """
        if not self._initialized:
            await self.initialize()
        
        async with self.async_session_factory() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {str(e)}")
                raise
            finally:
                await session.close()
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform database health check."""
        try:
            async with self.get_session() as session:
                # Test basic connectivity
                result = await session.execute(text("SELECT 1 as health_check"))
                health_result = result.scalar()
                
                # Get connection pool info
                pool_info = {
                    "pool_size": self.engine.pool.size(),
                    "checked_in": self.engine.pool.checkedin(),
                    "checked_out": self.engine.pool.checkedout(),
                    "overflow": self.engine.pool.overflow(),
                    "invalid": self.engine.pool.invalid(),
                }
                
                return {
                    "status": "healthy" if health_result == 1 else "unhealthy",
                    "pool_info": pool_info,
                    "database_url": self.settings.database_url.split('@')[1] if '@' in self.settings.database_url else "hidden"
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "database_url": "connection_failed"
            }


class InsurancePolicyRepository:
    """
    Repository for insurance policy CRUD operations.
    Repository pattern with comprehensive query methods,
    performance optimization, and business logic encapsulation.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    async def create_policy(self, policy_data: InsurancePolicyCreate) -> InsurancePolicy:
        """Create a new insurance policy."""
        try:
            async with self.db_manager.get_session() as session:
                # Check for duplicate policy number
                existing = await session.execute(
                    select(InsurancePolicy).where(
                        InsurancePolicy.policy_number == policy_data.policy_number
                    )
                )
                if existing.scalar_one_or_none():
                    raise ValueError(f"Policy number {policy_data.policy_number} already exists")
                
                # Create new policy
                db_policy = InsurancePolicy(**policy_data.dict())
                session.add(db_policy)
                await session.commit()
                await session.refresh(db_policy)
                
                logger.info(f"Created policy: {policy_data.policy_number}")
                return db_policy
                
        except IntegrityError as e:
            logger.error(f"Integrity error creating policy: {str(e)}")
            raise ValueError(f"Policy creation failed: duplicate or invalid data")
        except Exception as e:
            logger.error(f"Error creating policy: {str(e)}")
            raise
    
    async def bulk_create_policies(
        self, 
        policies_data: List[InsurancePolicyCreate],
        batch_size: int = 1000
    ) -> Tuple[int, int, List[str]]:
        """
        Bulk create insurance policies with batch processing.
        
        Returns: (successful_count, failed_count, error_messages)
        Efficient bulk operations with error handling.
        """
        successful_count = 0
        failed_count = 0
        error_messages = []
        
        # Process in batches for memory efficiency
        for i in range(0, len(policies_data), batch_size):
            batch = policies_data[i:i + batch_size]
            
            try:
                async with self.db_manager.get_session() as session:
                    # Convert to database models
                    db_policies = []
                    for policy_data in batch:
                        try:
                            # Validate individual policy
                            db_policy = InsurancePolicy(**policy_data.dict())
                            db_policies.append(db_policy)
                        except Exception as e:
                            failed_count += 1
                            error_messages.append(f"Policy {policy_data.policy_number}: {str(e)}")
                    
                    if db_policies:
                        # Bulk insert
                        session.add_all(db_policies)
                        await session.commit()
                        successful_count += len(db_policies)
                        
                        logger.info(f"Bulk inserted {len(db_policies)} policies")
            
            except Exception as e:
                failed_count += len(batch)
                error_messages.append(f"Batch {i//batch_size + 1}: {str(e)}")
                logger.error(f"Bulk insert error: {str(e)}")
        
        return successful_count, failed_count, error_messages
    
    async def get_policy_by_number(self, policy_number: str) -> Optional[InsurancePolicy]:
        """Get policy by policy number."""
        try:
            async with self.db_manager.get_session() as session:
                result = await session.execute(
                    select(InsurancePolicy).where(
                        InsurancePolicy.policy_number == policy_number
                    )
                )
                return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching policy {policy_number}: {str(e)}")
            return None
    
    async def get_policies_by_criteria(
        self,
        insured_name: Optional[str] = None,
        min_sum_insured: Optional[float] = None,
        max_sum_insured: Optional[float] = None,
        start_date_from: Optional[date] = None,
        start_date_to: Optional[date] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[InsurancePolicy]:
        """
        Get policies by various criteria.
        Flexible query builder with performance optimization.
        """
        try:
            async with self.db_manager.get_session() as session:
                query = select(InsurancePolicy)
                
                # Build WHERE conditions
                conditions = []
                
                if insured_name:
                    conditions.append(
                        InsurancePolicy.insured_name.ilike(f"%{insured_name}%")
                    )
                
                if min_sum_insured is not None:
                    conditions.append(InsurancePolicy.sum_insured >= min_sum_insured)
                
                if max_sum_insured is not None:
                    conditions.append(InsurancePolicy.sum_insured <= max_sum_insured)
                
                if start_date_from:
                    conditions.append(InsurancePolicy.insurance_period_start_date >= start_date_from)
                
                if start_date_to:
                    conditions.append(InsurancePolicy.insurance_period_start_date <= start_date_to)
                
                if conditions:
                    query = query.where(and_(*conditions))
                
                # Add pagination
                query = query.offset(offset).limit(limit)
                
                # Order by creation date (most recent first)
                query = query.order_by(InsurancePolicy.created_at.desc())
                
                result = await session.execute(query)
                return result.scalars().all()
                
        except Exception as e:
            logger.error(f"Error querying policies: {str(e)}")
            return []
    
    async def get_financial_summary(self) -> Dict[str, float]:
        """Get financial summary statistics."""
        try:
            async with self.db_manager.get_session() as session:
                # Aggregate queries for financial data
                summary_query = select(
                    func.count(InsurancePolicy.id).label('total_policies'),
                    func.sum(InsurancePolicy.sum_insured).label('total_sum_insured'),
                    func.sum(InsurancePolicy.premium).label('total_premium'),
                    func.avg(InsurancePolicy.sum_insured).label('avg_sum_insured'),
                    func.avg(InsurancePolicy.premium).label('avg_premium'),
                    func.sum(InsurancePolicy.treaty_sum_insured).label('total_treaty_sum'),
                    func.sum(InsurancePolicy.own_retention_sum_insured).label('total_retention_sum')
                )
                
                result = await session.execute(summary_query)
                row = result.first()
                
                return {
                    "total_policies": int(row.total_policies or 0),
                    "total_sum_insured": float(row.total_sum_insured or 0),
                    "total_premium": float(row.total_premium or 0),
                    "avg_sum_insured": float(row.avg_sum_insured or 0),
                    "avg_premium": float(row.avg_premium or 0),
                    "total_treaty_sum": float(row.total_treaty_sum or 0),
                    "total_retention_sum": float(row.total_retention_sum or 0)
                }
                
        except Exception as e:
            logger.error(f"Error getting financial summary: {str(e)}")
            return {}
    
    async def get_date_range_summary(self) -> Dict[str, Any]:
        """Get insurance period date range summary."""
        try:
            async with self.db_manager.get_session() as session:
                date_query = select(
                    func.min(InsurancePolicy.insurance_period_start_date).label('earliest_start'),
                    func.max(InsurancePolicy.insurance_period_end_date).label('latest_end'),
                    func.count(InsurancePolicy.id).label('total_policies')
                )
                
                result = await session.execute(date_query)
                row = result.first()
                
                return {
                    "earliest_start_date": row.earliest_start,
                    "latest_end_date": row.latest_end,
                    "total_policies": int(row.total_policies or 0),
                    "date_range_days": (row.latest_end - row.earliest_start).days if row.earliest_start and row.latest_end else 0
                }
                
        except Exception as e:
            logger.error(f"Error getting date range summary: {str(e)}")
            return {}
    
    async def execute_custom_query(self, query_text: str, params: Dict[str, Any] = None) -> List[Dict]:
        """
        Execute custom SQL query safely.
        Safe custom query execution with parameter binding.
        """
        try:
            async with self.db_manager.get_session() as session:
                # Execute with parameters to prevent SQL injection
                result = await session.execute(text(query_text), params or {})
                
                # Convert to list of dictionaries
                columns = result.keys()
                rows = []
                for row in result.fetchall():
                    rows.append(dict(zip(columns, row)))
                
                return rows
                
        except Exception as e:
            logger.error(f"Error executing custom query: {str(e)}")
            raise


class AuditRepository:
    """
    Repository for audit and logging operations.
    Separate audit concerns with performance considerations.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    async def log_data_ingestion(
        self,
        filename: str,
        file_size_bytes: int,
        rows_processed: int,
        rows_successful: int,
        rows_failed: int,
        processing_time_ms: float,
        status: str,
        error_details: Optional[str] = None
    ) -> DataIngestionLog:
        """Log data ingestion operation."""
        try:
            async with self.db_manager.get_session() as session:
                log_entry = DataIngestionLog(
                    filename=filename,
                    file_size_bytes=file_size_bytes,
                    rows_processed=rows_processed,
                    rows_successful=rows_successful,
                    rows_failed=rows_failed,
                    processing_time_ms=processing_time_ms,
                    status=status,
                    error_details=error_details
                )
                
                session.add(log_entry)
                await session.commit()
                await session.refresh(log_entry)
                
                return log_entry
                
        except Exception as e:
            logger.error(f"Error logging ingestion: {str(e)}")
            raise
    
    async def log_query_execution(
        self,
        query_text: str,
        query_type: Optional[str],
        processing_time_ms: float,
        langgraph_steps: int,
        tokens_used: int,
        success: bool,
        error_message: Optional[str] = None
    ) -> QueryLog:
        """Log query execution for monitoring."""
        try:
            async with self.db_manager.get_session() as session:
                log_entry = QueryLog(
                    query_text=query_text,
                    query_type=query_type,
                    processing_time_ms=processing_time_ms,
                    langgraph_steps=langgraph_steps,
                    tokens_used=tokens_used,
                    success=success,
                    error_message=error_message
                )
                
                session.add(log_entry)
                await session.commit()
                await session.refresh(log_entry)
                
                return log_entry
                
        except Exception as e:
            logger.error(f"Error logging query: {str(e)}")
            # Don't raise - logging failures shouldn't break queries
            return None
    
    async def get_ingestion_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get ingestion statistics for the last N days."""
        try:
            async with self.db_manager.get_session() as session:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                
                stats_query = select(
                    func.count(DataIngestionLog.id).label('total_ingestions'),
                    func.sum(DataIngestionLog.rows_processed).label('total_rows_processed'),
                    func.sum(DataIngestionLog.rows_successful).label('total_rows_successful'),
                    func.sum(DataIngestionLog.rows_failed).label('total_rows_failed'),
                    func.avg(DataIngestionLog.processing_time_ms).label('avg_processing_time')
                ).where(DataIngestionLog.created_at >= cutoff_date)
                
                result = await session.execute(stats_query)
                row = result.first()
                
                return {
                    "period_days": days,
                    "total_ingestions": int(row.total_ingestions or 0),
                    "total_rows_processed": int(row.total_rows_processed or 0),
                    "total_rows_successful": int(row.total_rows_successful or 0),
                    "total_rows_failed": int(row.total_rows_failed or 0),
                    "avg_processing_time_ms": float(row.avg_processing_time or 0),
                    "success_rate": (row.total_rows_successful / row.total_rows_processed * 100) if row.total_rows_processed else 0
                }
                
        except Exception as e:
            logger.error(f"Error getting ingestion stats: {str(e)}")
            return {}


# Global database manager instance
db_manager = None


async def get_database_manager() -> DatabaseManager:
    """Get or create database manager instance."""
    global db_manager
    if db_manager is None:
        settings = get_settings()
        db_manager = DatabaseManager(settings)
        await db_manager.initialize()
    return db_manager


async def get_policy_repository() -> InsurancePolicyRepository:
    """Get policy repository instance."""
    db_mgr = await get_database_manager()
    return InsurancePolicyRepository(db_mgr)


async def get_audit_repository() -> AuditRepository:
    """Get audit repository instance."""
    db_mgr = await get_database_manager()
    return AuditRepository(db_mgr)