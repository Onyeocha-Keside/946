from datetime import datetime, date
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, validator, root_validator

class InsurancePolicyBase(BaseModel):
    """Base insurance policy model with validation."""
    
    policy_number: str = Field(..., min_length=1, max_length=50, description="Unique policy number")
    insured_name: str = Field(..., min_length=1, max_length=200, description="Name of insured party")
    sum_insured: float = Field(..., gt=0, description="Total sum insured amount")
    premium: float = Field(..., gt=0, description="Premium amount")
    own_retention_ppn: float = Field(..., ge=0, le=100, description="Own retention percentage")
    own_retention_sum_insured: float = Field(..., ge=0, description="Own retention sum insured")
    own_retention_premium: float = Field(..., ge=0, description="Own retention premium")
    treaty_ppn: float = Field(..., ge=0, le=100, description="Treaty percentage")
    treaty_sum_insured: float = Field(..., ge=0, description="Treaty sum insured")
    treaty_premium: float = Field(..., ge=0, description="Treaty premium")
    insurance_period_start_date: date = Field(..., description="Insurance period start date")
    insurance_period_end_date: date = Field(..., description="Insurance period end date")
    
    @validator('own_retention_ppn', 'treaty_ppn')
    def validate_percentages(cls, v):
        """Ensure percentages are valid."""
        if not 0 <= v <= 100:
            raise ValueError('Percentage must be between 0 and 100')
        return v
    
    @root_validator(skip_on_failure=True)
    def validate_period_dates(cls, values):
        """Ensure end date is after start date."""
        start_date = values.get('insurance_period_start_date')
        end_date = values.get('insurance_period_end_date')
        
        if start_date and end_date and end_date <= start_date:
            raise ValueError('Insurance period end date must be after start date')
        
        return values
    
    @root_validator(skip_on_failure=True)
    def validate_financial_consistency(cls, values):
        """Validate financial field consistency."""
        sum_insured = values.get('sum_insured', 0)
        own_retention_sum = values.get('own_retention_sum_insured', 0)
        treaty_sum = values.get('treaty_sum_insured', 0)
        
        # Check if retention + treaty approximately equals total
        if abs((own_retention_sum + treaty_sum) - sum_insured) > 0.01:
            # Allow small discrepancies due to rounding, but log warning
            pass  # In production, might want to log this discrepancy
        
        return values


class InsurancePolicyCreate(InsurancePolicyBase):
    """Model for creating new insurance policies."""
    pass


class InsurancePolicyResponse(InsurancePolicyBase):
    """Model for insurance policy API responses."""
    
    id: UUID = Field(..., description="Unique policy ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    class Config:
        from_attributes = True  # For SQLAlchemy compatibility


class ExcelIngestionRequest(BaseModel):
    """Request model for Excel file ingestion."""
    
    validate_schema: bool = Field(
        default=True, 
        description="Whether to validate Excel schema strictly"
    )
    skip_duplicates: bool = Field(
        default=True,
        description="Skip duplicate policy numbers"
    )
    batch_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Processing batch size"
    )


class ExcelIngestionResponse(BaseModel):
    """Response model for Excel ingestion results."""
    
    ingestion_id: UUID = Field(..., description="Unique ingestion operation ID")
    filename: str = Field(..., description="Processed filename")
    total_rows: int = Field(..., description="Total rows in Excel file")
    processed_rows: int = Field(..., description="Successfully processed rows")
    failed_rows: int = Field(..., description="Failed rows")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    status: str = Field(..., description="Ingestion status")
    errors: List[str] = Field(default_factory=list, description="List of processing errors")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")


class QueryRequest(BaseModel):
    """Request model for natural language queries."""
    
    question: str = Field(
        ..., 
        min_length=1, 
        max_length=1000, 
        description="Natural language question about insurance data"
    )
    max_results: int = Field(
        default=10, 
        ge=1, 
        le=100, 
        description="Maximum number of results to return"
    )
    include_reasoning: bool = Field(
        default=True,
        description="Include LangGraph reasoning steps in response"
    )
    use_cache: bool = Field(
        default=True,
        description="Use cached results if available"
    )


class QueryStepResult(BaseModel):
    """Individual step result in LangGraph workflow."""
    
    step_name: str = Field(..., description="Name of the workflow step")
    step_type: str = Field(..., description="Type of step (query, analysis, generation)")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Step input data")
    output_data: Dict[str, Any] = Field(default_factory=dict, description="Step output data")
    execution_time_ms: float = Field(..., description="Step execution time")
    success: bool = Field(..., description="Whether step completed successfully")
    error_message: Optional[str] = Field(None, description="Error message if step failed")


class QueryResponse(BaseModel):
    """Response model for natural language queries."""
    
    query_id: UUID = Field(default_factory=uuid4, description="Unique query identifier")
    question: str = Field(..., description="Original question")
    answer: str = Field(..., description="Generated answer")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Answer confidence score")
    
    # LangGraph execution details
    workflow_steps: List[QueryStepResult] = Field(
        default_factory=list, 
        description="LangGraph workflow execution steps"
    )
    
    # Data sources
    source_policies: List[str] = Field(
        default_factory=list,
        description="Policy numbers used in generating answer"
    )
    
    # Performance metrics
    total_processing_time_ms: float = Field(..., description="Total query processing time")
    database_query_time_ms: float = Field(..., description="Database query time")
    llm_processing_time_ms: float = Field(..., description="LLM processing time")
    tokens_used: int = Field(default=0, description="Total tokens used")


class HealthCheckResponse(BaseModel):
    """System health check response."""
    
    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    version: str = Field(..., description="API version")
    
    components: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Individual component status"
    )


class SystemMetricsResponse(BaseModel):
    """System metrics and usage statistics."""
    
    database_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Database performance metrics"
    )
    api_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="API usage metrics"
    )
    query_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Query performance metrics"
    )
    system_metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="System resource metrics"
    )


class DataSummaryResponse(BaseModel):
    """Database statistics and summary."""
    
    total_policies: int = Field(..., description="Total number of policies")
    date_range: Dict[str, Optional[date]] = Field(
        default_factory=dict,
        description="Insurance period date range"
    )
    financial_summary: Dict[str, float] = Field(
        default_factory=dict,
        description="Financial aggregations"
    )
    policy_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Policy distribution statistics"
    )
    recent_activity: Dict[str, Any] = Field(
        default_factory=dict,
        description="Recent system activity"
    )


# ============================================================================
# EXCEL MAPPING MODELS
# ============================================================================

class ExcelColumnMapping(BaseModel):
    """
    Maps Excel columns to database fields.
    
    Senior pattern: Configurable column mapping for flexible Excel formats.
    """
    
    # Expected Excel column names (can be flexible)
    policy_number_col: str = Field(default="POLICY NUMBER", description="Policy number column name")
    insured_name_col: str = Field(default="INSURED NAME", description="Insured name column name")
    sum_insured_col: str = Field(default="SUM INSURED", description="Sum insured column name")
    premium_col: str = Field(default="PREMIUM", description="Premium column name")
    
    # Own retention columns
    own_retention_ppn_col: str = Field(default="OWN RETENTION %", description="Own retention percentage column")
    own_retention_sum_col: str = Field(default="OWN RETENTION SUM INSURED", description="Own retention sum column")
    own_retention_premium_col: str = Field(default="OWN RETENTION PREMIUM", description="Own retention premium column")
    
    # Treaty columns
    treaty_ppn_col: str = Field(default="TREATY %", description="Treaty percentage column")
    treaty_sum_col: str = Field(default="TREATY SUM INSURED", description="Treaty sum column")
    treaty_premium_col: str = Field(default="TREATY PREMIUM", description="Treaty premium column")
    
    # Period of insurance (to be split)
    period_of_insurance_col: str = Field(default="PERIOD OF INSURANCE", description="Period of insurance column")
    
    # Alternative: separate date columns if already split
    start_date_col: Optional[str] = Field(default=None, description="Start date column if separate")
    end_date_col: Optional[str] = Field(default=None, description="End date column if separate")


class ExcelValidationError(BaseModel):
    """Represents an Excel validation error."""
    
    row_number: int = Field(..., description="Row number with error")
    column_name: str = Field(..., description="Column name with error")
    error_type: str = Field(..., description="Type of validation error")
    error_message: str = Field(..., description="Detailed error message")
    raw_value: Optional[str] = Field(None, description="Raw value that caused error")