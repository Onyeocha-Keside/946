import time
import uuid
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.config import Settings, get_settings
from src.schema import ExcelIngestionRequest, ExcelIngestionResponse, QueryRequest, QueryResponse, HealthCheckResponse, SystemMetricsResponse, DataSummaryResponse
from src.database import get_database_manager, get_policy_repository, get_audit_repository
from src.ingestion import InsuranceDataIngestionPipeline
from src.agent import get_insurance_rag_agent
from src.gemini_integration import get_gemini_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with component initialization."""
    # Startup
    logger.info("Starting Insurance RAG API with LangGraph workflows...")
    
    settings = get_settings()
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"LLM: Google Gemini {settings.gemini_model}")
    logger.info(f"Database: PostgreSQL")
    
    try:
        # Initialize database
        #db_manager = await get_database_manager()
        #logger.info("Database initialized")
        
        # Initialize Gemini
        gemini_manager = await get_gemini_manager()
        gemini_health = await gemini_manager.health_check()
        logger.info(f"Gemini status: {gemini_health.get('status')}")
        
        # Initialize agent
        agent = await get_insurance_rag_agent()
        logger.info("LangGraph agent initialized")
        
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise
    
    yield  # Application runs
    
    # Shutdown
    logger.info("Shutting down...")
    try:
        db_manager = await get_database_manager()
        await db_manager.close()
    except:
        pass


def create_app() -> FastAPI:
    """Create FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="Insurance Agentic RAG API",
        version="2.0.0",
        description="LangGraph-powered insurance data analysis with Google Gemini",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None
    )
    
    # Add middleware
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    @app.middleware("http")
    async def add_correlation_id(request: Request, call_next):
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
    
    # Add routes
    @app.post("/ingest-excel", response_model=ExcelIngestionResponse, tags=["Ingestion"])
    async def ingest_excel(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        validate_schema: bool = True,
        skip_duplicates: bool = True,
        batch_size: int = 1000
    ):
        """Excel file ingestion with schema transformation."""
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(400, "Only Excel files are supported")
        
        file_content = await file.read()
        if len(file_content) > settings.max_file_size_mb * 1024 * 1024:
            raise HTTPException(400, f"File too large. Max: {settings.max_file_size_mb}MB")
        
        try:
            pipeline = InsuranceDataIngestionPipeline(settings)
            request_obj = ExcelIngestionRequest(
                validate_schema=validate_schema,
                skip_duplicates=skip_duplicates,
                batch_size=batch_size
            )
            return await pipeline.ingest_excel_file(file_content, file.filename, request_obj)
        except Exception as e:
            raise HTTPException(500, f"Ingestion failed: {str(e)}")
    
    @app.post("/query", response_model=QueryResponse, tags=["Query"])
    async def query(request: QueryRequest):
        """Natural language query processing."""
        try:
            agent = await get_insurance_rag_agent()
            return await agent.process_query(request)
        except Exception as e:
            raise HTTPException(500, f"Query failed: {str(e)}")
    
    @app.get("/health", response_model=HealthCheckResponse, tags=["Health"])
    async def health():
        """System health check."""
        return HealthCheckResponse(status="healthy", version="2.0.0", components={})
    
    @app.get("/metrics", response_model=SystemMetricsResponse, tags=["Monitoring"])
    async def metrics():
        """System metrics."""
        try:
            agent = await get_insurance_rag_agent()
            status = await agent.get_system_status()
            return SystemMetricsResponse(
                database_metrics=status.get("components", {}).get("database", {}),
                api_metrics=status.get("usage_metrics", {}),
                query_metrics={},
                system_metrics={"uptime": time.time()}
            )
        except Exception as e:
            raise HTTPException(500, f"Metrics failed: {str(e)}")
    
    @app.get("/data-summary", response_model=DataSummaryResponse, tags=["Data"])
    async def data_summary():
        """Database statistics."""
        try:
            policy_repo = await get_policy_repository()
            financial = await policy_repo.get_financial_summary()
            date_range = await policy_repo.get_date_range_summary()
            
            return DataSummaryResponse(
                total_policies=financial.get("total_policies", 0),
                date_range={
                    "earliest_start": date_range.get("earliest_start_date"),
                    "latest_end": date_range.get("latest_end_date")
                },
                financial_summary=financial,
                policy_distribution={},
                recent_activity={}
            )
        except Exception as e:
            raise HTTPException(500, f"Data summary failed: {str(e)}")
    
    return app


app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=settings.is_development)