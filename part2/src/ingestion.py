import asyncio
import logging
import time
import re
from io import BytesIO
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
from uuid import UUID

import pandas as pd
from pydantic import ValidationError

from src.schema import InsurancePolicyCreate, ExcelColumnMapping, ExcelValidationError, ExcelIngestionRequest, ExcelIngestionResponse
from src.database import get_policy_repository, get_audit_repository
from src.config import Settings


logger = logging.getLogger(__name__)


class ExcelParser:
    """
    Excel file parser with flexible column mapping.
    Robust Excel parsing with configurable mapping
    and comprehensive error handling for real-world data variations.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Default column mapping (can be customized)
        self.default_mapping = ExcelColumnMapping()
        
        # Date parsing patterns for "PERIOD OF INSURANCE"
        self.date_patterns = [
            r'(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})',  # DD/MM/YYYY - DD/MM/YYYY
            r'(\d{4}-\d{1,2}-\d{1,2})\s*-\s*(\d{4}-\d{1,2}-\d{1,2})',  # YYYY-MM-DD - YYYY-MM-DD
            r'(\d{1,2}-\d{1,2}-\d{4})\s*-\s*(\d{1,2}-\d{1,2}-\d{4})',  # DD-MM-YYYY - DD-MM-YYYY
            r'(\d{1,2}\.\d{1,2}\.\d{4})\s*-\s*(\d{1,2}\.\d{1,2}\.\d{4})'  # DD.MM.YYYY - DD.MM.YYYY
        ]
        
        # Date format mappings
        self.date_formats = [
            "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", 
            "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"
        ]
    
    async def parse_excel_file(
        self, 
        file_content: bytes, 
        filename: str,
        column_mapping: Optional[ExcelColumnMapping] = None
    ) -> Tuple[pd.DataFrame, List[ExcelValidationError]]:
        """
        Parse Excel file with flexible column mapping.
        Comprehensive parsing with error collection
        and flexible schema handling for real-world variations.
        """
        mapping = column_mapping or self.default_mapping
        errors = []
        
        try:
            # Read Excel file
            df = pd.read_excel(BytesIO(file_content), sheet_name=0)
            logger.info(f"Read Excel file: {len(df)} rows, {len(df.columns)} columns")
            
            # Standardize column names (remove extra spaces, case variations)
            df.columns = df.columns.str.strip().str.upper()
            
            # Log available columns for debugging
            logger.info(f"Available columns: {list(df.columns)}")
            
            # Map columns to expected names
            column_map = self._create_column_mapping(df.columns, mapping)
            logger.info(f"Column mapping: {column_map}")
            
            # Validate required columns exist
            missing_columns = self._validate_required_columns(column_map)
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Rename columns
            df = df.rename(columns=column_map)
            
            # Clean and validate data
            df, validation_errors = await self._clean_and_validate_data(df)
            errors.extend(validation_errors)
            
            # Transform PERIOD OF INSURANCE if present
            if 'period_of_insurance' in df.columns:
                df, date_errors = self._transform_period_column(df)
                errors.extend(date_errors)
            
            # Drop rows with critical errors
            valid_df = df.dropna(subset=['policy_number', 'insured_name'])
            
            if len(valid_df) < len(df):
                dropped_rows = len(df) - len(valid_df)
                logger.warning(f"Dropped {dropped_rows} rows with missing critical data")
            
            logger.info(f"Successfully parsed {len(valid_df)} valid rows")
            return valid_df, errors
            
        except Exception as e:
            logger.error(f"Error parsing Excel file {filename}: {str(e)}")
            raise ValueError(f"Excel parsing failed: {str(e)}")
    
    def _create_column_mapping(
        self, 
        excel_columns: List[str], 
        mapping: ExcelColumnMapping
    ) -> Dict[str, str]:
        """
        Create flexible column mapping from Excel columns to database fields.
        Fuzzy matching for real-world Excel variations.
        """
        column_map = {}
        
        # Define mapping rules (Excel column -> database field)
        mapping_rules = {
            # Policy information
            'policy_number': [mapping.policy_number_col, 'POLICY NO', 'POLICY_NUMBER', 'POLICY'],
            'insured_name': [mapping.insured_name_col, 'INSURED', 'CUSTOMER_NAME', 'CLIENT_NAME'],
            'sum_insured': [mapping.sum_insured_col, 'SUM_INSURED', 'COVERAGE_AMOUNT', 'INSURED_AMOUNT'],
            'premium': [mapping.premium_col, 'PREMIUM_AMOUNT', 'ANNUAL_PREMIUM'],
            
            # Own retention fields
            'own_retention_ppn': [mapping.own_retention_ppn_col, 'OWN_RETENTION_PCT', 'RETENTION_%'],
            'own_retention_sum_insured': [mapping.own_retention_sum_col, 'OWN_RETENTION_SUM', 'RETENTION_SUM'],
            'own_retention_premium': [mapping.own_retention_premium_col, 'OWN_RETENTION_PREM', 'RETENTION_PREMIUM'],
            
            # Treaty fields
            'treaty_ppn': [mapping.treaty_ppn_col, 'TREATY_PCT', 'TREATY_%'],
            'treaty_sum_insured': [mapping.treaty_sum_col, 'TREATY_SUM', 'TREATY_COVERAGE'],
            'treaty_premium': [mapping.treaty_premium_col, 'TREATY_PREM'],
            
            # Date fields
            'period_of_insurance': [mapping.period_of_insurance_col, 'INSURANCE_PERIOD', 'POLICY_PERIOD'],
            'insurance_period_start_date': [mapping.start_date_col] if mapping.start_date_col else [],
            'insurance_period_end_date': [mapping.end_date_col] if mapping.end_date_col else []
        }
        
        # Find best matches for each field
        for db_field, possible_names in mapping_rules.items():
            best_match = self._find_best_column_match(excel_columns, possible_names)
            if best_match:
                column_map[best_match] = db_field
        
        return column_map
    
    def _find_best_column_match(
        self, 
        excel_columns: List[str], 
        possible_names: List[str]
    ) -> Optional[str]:
        """Find best matching column name using fuzzy matching."""
        for possible_name in possible_names:
            # Exact match
            if possible_name.upper() in excel_columns:
                return possible_name.upper()
            
            # Partial match
            for col in excel_columns:
                if possible_name.upper() in col or col in possible_name.upper():
                    return col
        
        return None
    
    def _validate_required_columns(self, column_map: Dict[str, str]) -> List[str]:
        """Validate that required columns are present."""
        required_fields = [
            'policy_number', 'insured_name', 'sum_insured', 'premium',
            'own_retention_ppn', 'own_retention_sum_insured', 'own_retention_premium',
            'treaty_ppn', 'treaty_sum_insured', 'treaty_premium'
        ]
        
        mapped_fields = set(column_map.values())
        missing_fields = []
        
        for field in required_fields:
            if field not in mapped_fields:
                missing_fields.append(field)
        
        # Check for date fields (either combined or separate)
        has_period = 'period_of_insurance' in mapped_fields
        has_separate_dates = (
            'insurance_period_start_date' in mapped_fields and 
            'insurance_period_end_date' in mapped_fields
        )
        
        if not has_period and not has_separate_dates:
            missing_fields.append('insurance period dates')
        
        return missing_fields
    
    async def _clean_and_validate_data(
        self, 
        df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, List[ExcelValidationError]]:
        """
        Clean and validate DataFrame data.
        Comprehensive data cleaning with error tracking.
        """
        errors = []
        
        # Clean string fields
        string_fields = ['policy_number', 'insured_name']
        for field in string_fields:
            if field in df.columns:
                df[field] = df[field].astype(str).str.strip()
                df[field] = df[field].replace('nan', '')
        
        # Clean and validate numeric fields
        numeric_fields = [
            'sum_insured', 'premium', 'own_retention_ppn', 'own_retention_sum_insured',
            'own_retention_premium', 'treaty_ppn', 'treaty_sum_insured', 'treaty_premium'
        ]
        
        for field in numeric_fields:
            if field in df.columns:
                df, field_errors = self._clean_numeric_field(df, field)
                errors.extend(field_errors)
        
        # Validate percentage fields
        percentage_fields = ['own_retention_ppn', 'treaty_ppn']
        for field in percentage_fields:
            if field in df.columns:
                invalid_pct = (df[field] < 0) | (df[field] > 100)
                for idx in df[invalid_pct].index:
                    errors.append(ExcelValidationError(
                        row_number=idx + 2,  # +2 for Excel row number (1-indexed + header)
                        column_name=field,
                        error_type="invalid_percentage",
                        error_message=f"Percentage must be between 0 and 100, got {df.loc[idx, field]}",
                        raw_value=str(df.loc[idx, field])
                    ))
        
        return df, errors
    
    def _clean_numeric_field(
        self, 
        df: pd.DataFrame, 
        field: str
    ) -> Tuple[pd.DataFrame, List[ExcelValidationError]]:
        """Clean and validate a numeric field."""
        errors = []
        
        if field not in df.columns:
            return df, errors
        
        # Convert to string first to handle mixed types
        df[field] = df[field].astype(str)
        
        # Remove common non-numeric characters
        df[field] = df[field].str.replace(',', '')  # Remove thousands separators
        df[field] = df[field].str.replace('₦', '')  # Remove currency symbols  
        df[field] = df[field].str.replace('%', '')  # Remove percentage symbols
        df[field] = df[field].str.strip()
        
        # Convert to numeric, track errors
        for idx, value in df[field].items():
            try:
                if pd.isna(value) or value == '' or value.lower() in ['nan', 'null', 'none']:
                    df.loc[idx, field] = 0.0
                else:
                    df.loc[idx, field] = float(value)
            except (ValueError, TypeError):
                errors.append(ExcelValidationError(
                    row_number=idx + 2,
                    column_name=field,
                    error_type="invalid_numeric",
                    error_message=f"Cannot convert '{value}' to number",
                    raw_value=str(value)
                ))
                df.loc[idx, field] = 0.0  # Set default value
        
        return df, errors
    
    def _transform_period_column(
        self, 
        df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, List[ExcelValidationError]]:
        """
        Transform PERIOD OF INSURANCE column to start_date and end_date.
        Robust date parsing with multiple format support.
        """
        errors = []
        
        if 'period_of_insurance' not in df.columns:
            return df, errors
        
        start_dates = []
        end_dates = []
        
        for idx, period_value in df['period_of_insurance'].items():
            try:
                start_date, end_date = self._parse_insurance_period(str(period_value))
                start_dates.append(start_date)
                end_dates.append(end_date)
            except Exception as e:
                errors.append(ExcelValidationError(
                    row_number=idx + 2,
                    column_name='period_of_insurance',
                    error_type="invalid_date_format",
                    error_message=f"Cannot parse date range: {str(e)}",
                    raw_value=str(period_value)
                ))
                # Set default dates (current year)
                start_dates.append(date(2024, 1, 1))
                end_dates.append(date(2024, 12, 31))
        
        # Add new date columns
        df['insurance_period_start_date'] = start_dates
        df['insurance_period_end_date'] = end_dates
        
        # Remove original period column
        df = df.drop('period_of_insurance', axis=1)
        
        return df, errors
    
    def _parse_insurance_period(self, period_str: str) -> Tuple[date, date]:
        """
        Parse insurance period string into start and end dates.
        
        Supports various formats:
        - "01/01/2024 - 31/12/2024"
        - "2024-01-01 - 2024-12-31"
        - "1-Jan-2024 to 31-Dec-2024"
        """
        period_str = period_str.strip()
        
        # Try different regex patterns
        for pattern in self.date_patterns:
            match = re.search(pattern, period_str)
            if match:
                start_str, end_str = match.groups()
                
                # Try different date formats
                start_date = self._parse_single_date(start_str)
                end_date = self._parse_single_date(end_str)
                
                if start_date and end_date:
                    return start_date, end_date
        
        raise ValueError(f"Cannot parse insurance period: {period_str}")
    
    def _parse_single_date(self, date_str: str) -> Optional[date]:
        """Parse a single date string using multiple formats."""
        date_str = date_str.strip()
        
        for fmt in self.date_formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        return None


class InsuranceDataIngestionPipeline:
    """
    Complete data ingestion pipeline for insurance policies.
    End-to-end pipeline with comprehensive error handling,
    audit logging, and performance optimization.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.excel_parser = ExcelParser(settings)
    
    async def ingest_excel_file(
        self,
        file_content: bytes,
        filename: str,
        request: ExcelIngestionRequest
    ) -> ExcelIngestionResponse:
        """
        Complete Excel ingestion workflow.
        
        Orchestrates parsing, validation, transformation,
        and database storage with comprehensive audit trail.
        """
        start_time = time.time()
        
        try:
            # Get repository instances
            policy_repo = await get_policy_repository()
            audit_repo = await get_audit_repository()
            
            # Parse Excel file
            logger.info(f"Starting ingestion of {filename}")
            df, parsing_errors = await self.excel_parser.parse_excel_file(
                file_content, filename
            )
            
            if df.empty:
                raise ValueError("No valid data found in Excel file")
            
            # Convert DataFrame to Pydantic models
            policies_data = []
            conversion_errors = []
            
            for idx, row in df.iterrows():
                try:
                    policy_data = self._convert_row_to_policy(row)
                    policies_data.append(policy_data)
                except Exception as e:
                    conversion_errors.append(f"Row {idx + 2}: {str(e)}")
            
            # Bulk insert to database
            successful_count, failed_count, db_errors = await policy_repo.bulk_create_policies(
                policies_data, 
                batch_size=request.batch_size
            )
            
            # Calculate metrics
            processing_time = (time.time() - start_time) * 1000
            total_rows = len(df)
            total_errors = parsing_errors + conversion_errors + db_errors
            
            # Determine status
            if failed_count == 0:
                status = "success"
            elif successful_count > 0:
                status = "partial"
            else:
                status = "failed"
            
            # Log to audit trail
            await audit_repo.log_data_ingestion(
                filename=filename,
                file_size_bytes=len(file_content),
                rows_processed=total_rows,
                rows_successful=successful_count,
                rows_failed=failed_count,
                processing_time_ms=processing_time,
                status=status,
                error_details="; ".join(total_errors) if total_errors else None
            )
            
            logger.info(
                f"Ingestion complete: {successful_count} success, "
                f"{failed_count} failed, {processing_time:.1f}ms"
            )
            
            return ExcelIngestionResponse(
                ingestion_id=UUID('12345678-1234-1234-1234-123456789012'),  # Would use actual UUID from audit log
                filename=filename,
                total_rows=total_rows,
                processed_rows=successful_count,
                failed_rows=failed_count,
                processing_time_ms=processing_time,
                status=status,
                errors=[str(e) for e in total_errors],
                warnings=[]
            )
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            logger.error(f"Ingestion failed for {filename}: {str(e)}")
            
            # Log failure
            try:
                audit_repo = await get_audit_repository()
                await audit_repo.log_data_ingestion(
                    filename=filename,
                    file_size_bytes=len(file_content),
                    rows_processed=0,
                    rows_successful=0,
                    rows_failed=0,
                    processing_time_ms=processing_time,
                    status="failed",
                    error_details=str(e)
                )
            except Exception as audit_error:
                logger.error(f"Failed to log ingestion failure: {str(audit_error)}")
            
            return ExcelIngestionResponse(
                ingestion_id=UUID('00000000-0000-0000-0000-000000000000'),
                filename=filename,
                total_rows=0,
                processed_rows=0,
                failed_rows=0,
                processing_time_ms=processing_time,
                status="failed",
                errors=[str(e)],
                warnings=[]
            )
    
    def _convert_row_to_policy(self, row: pd.Series) -> InsurancePolicyCreate:
        """
        Convert DataFrame row to InsurancePolicyCreate model.
        Robust data conversion with validation.
        """
        try:
            # Extract data with defaults
            policy_data = {
                "policy_number": str(row.get('policy_number', '')).strip(),
                "insured_name": str(row.get('insured_name', '')).strip(),
                "sum_insured": float(row.get('sum_insured', 0)),
                "premium": float(row.get('premium', 0)),
                "own_retention_ppn": float(row.get('own_retention_ppn', 0)),
                "own_retention_sum_insured": float(row.get('own_retention_sum_insured', 0)),
                "own_retention_premium": float(row.get('own_retention_premium', 0)),
                "treaty_ppn": float(row.get('treaty_ppn', 0)),
                "treaty_sum_insured": float(row.get('treaty_sum_insured', 0)),
                "treaty_premium": float(row.get('treaty_premium', 0)),
                "insurance_period_start_date": row.get('insurance_period_start_date'),
                "insurance_period_end_date": row.get('insurance_period_end_date')
            }
            
            # Validate required fields
            if not policy_data["policy_number"]:
                raise ValueError("Policy number is required")
            
            if not policy_data["insured_name"]:
                raise ValueError("Insured name is required")
            
            # Convert dates if they're strings
            for date_field in ['insurance_period_start_date', 'insurance_period_end_date']:
                if isinstance(policy_data[date_field], str):
                    policy_data[date_field] = datetime.strptime(
                        policy_data[date_field], 
                        "%Y-%m-%d"
                    ).date()
            
            return InsurancePolicyCreate(**policy_data)
            
        except Exception as e:
            raise ValueError(f"Data conversion error: {str(e)}")
    
    async def validate_excel_structure(
        self, 
        file_content: bytes, 
        filename: str
    ) -> Dict[str, Any]:
        """
        Validate Excel file structure without processing data.
        Pre-processing validation to catch issues early.
        """
        try:
            df = pd.read_excel(BytesIO(file_content), sheet_name=0)
            
            # Basic structure validation
            validation_result = {
                "valid": True,
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "columns": list(df.columns),
                "issues": [],
                "recommendations": []
            }
            
            # Check file size
            if len(df) > self.settings.max_excel_rows:
                validation_result["issues"].append(
                    f"File has {len(df)} rows, maximum is {self.settings.max_excel_rows}"
                )
                validation_result["valid"] = False
            
            # Check for empty file
            if len(df) == 0:
                validation_result["issues"].append("File contains no data rows")
                validation_result["valid"] = False
            
            # Check for required columns (flexible matching)
            mapping = ExcelColumnMapping()
            column_map = self.excel_parser._create_column_mapping(
                df.columns.str.strip().str.upper(), 
                mapping
            )
            
            missing_columns = self.excel_parser._validate_required_columns(column_map)
            if missing_columns:
                validation_result["issues"].extend([
                    f"Missing required column: {col}" for col in missing_columns
                ])
                validation_result["valid"] = False
            
            # Provide recommendations
            if validation_result["valid"]:
                validation_result["recommendations"].append(
                    "Excel structure looks good, ready for processing"
                )
            
            return validation_result
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "total_rows": 0,
                "total_columns": 0,
                "columns": [],
                "issues": [f"Cannot read Excel file: {str(e)}"],
                "recommendations": [
                    "Ensure file is a valid Excel format (.xlsx or .xls)",
                    "Check that file is not corrupted or password protected"
                ]
            }