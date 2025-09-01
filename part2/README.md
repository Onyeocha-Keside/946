# Insurance Agentic RAG API

A production-ready FastAPI application that provides intelligent question-answering capabilities for insurance policy data using agentic workflows and Google Gemini AI.

## Overview

This system combines Excel data ingestion, PostgreSQL storage, and multi-step AI reasoning to answer complex insurance queries. The agentic workflow analyzes queries, generates SQL, executes database operations, and formats comprehensive responses.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Excel Files   │───▶│  FastAPI Server  │───▶│   PostgreSQL    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Agentic Workflow │
                       │                  │
                       │  1. Query Analysis│
                       │  2. SQL Generation│
                       │  3. Data Retrieval│
                       │  4. Answer Format │
                       └──────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   Google Gemini  │
                       │      AI LLM      │
                       └──────────────────┘
```

## Features

### Core Functionality
- **Excel Data Ingestion**: Automated parsing and transformation of insurance policy spreadsheets
- **Intelligent Query Processing**: Multi-step agentic reasoning for complex insurance questions
- **Natural Language Interface**: Ask questions in plain English about your insurance data
- **Real-time Analytics**: Generate insights, summaries, and calculations on demand

### Technical Capabilities
- **Robust Error Handling**: Graceful failure recovery with detailed error responses
- **Database Optimization**: Connection pooling, query optimization, and transaction management
- **Rate Limiting**: Built-in protection against API abuse and cost optimization
- **Comprehensive Logging**: Structured logging for debugging and monitoring
- **Type Safety**: Full Pydantic validation for request/response schemas

## Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 13+
- Google AI API Key ([Get one here](https://aistudio.google.com/app/apikey))

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd insurance-rag-api
```

2. **Set up Python environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Configure PostgreSQL**
```bash
# Create database and user
createdb insurance_rag
psql -c "CREATE USER insurance_user WITH PASSWORD 'your_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE insurance_rag TO insurance_user;"
```

4. **Environment Configuration**
```bash
cp .env.example .env
# Edit .env with your settings
```

Required environment variables:
```env
# Google AI API Key
GOOGLE_API_KEY=your_google_api_key_here

# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=insurance_rag
DB_USER=insurance_user
DB_PASSWORD=your_password

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
ENVIRONMENT=development
```

5. **Initialize Database**
```bash
# Run migrations
alembic upgrade head

# Generate sample data (optional)
python src/sample_excel.py
```

6. **Start the Server**
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

### Interactive Documentation
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Core Endpoints

#### Data Ingestion
```http
POST /ingest-excel
Content-Type: multipart/form-data

# Upload Excel file with insurance policy data
curl -X POST "http://localhost:8000/ingest-excel" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_data.xlsx"
```

#### Natural Language Queries
```http
POST /query
Content-Type: application/json

{
  "question": "What is the total sum insured for all policies?",
  "max_results": 10,
  "include_reasoning": true,
  "use_cache": true
}
```

#### System Monitoring
```http
GET /health       # System health check
GET /metrics      # Usage metrics and performance stats
GET /data-summary # Database statistics and insights
```

## Data Format

### Excel Schema
Your Excel files should contain these columns:

| Column Name | Type | Description |
|-------------|------|-------------|
| POLICY NUMBER | String | Unique policy identifier |
| INSURED NAME | String | Name of insured party |
| SUM INSURED | Number | Total coverage amount |
| PREMIUM | Number | Annual premium amount |
| OWN RETENTION % | Number | Retention percentage (0-100) |
| OWN RETENTION SUM INSURED | Number | Retention coverage amount |
| OWN RETENTION PREMIUM | Number | Retention premium amount |
| TREATY % | Number | Treaty percentage (0-100) |
| TREATY SUM INSURED | Number | Treaty coverage amount |
| TREATY PREMIUM | Number | Treaty premium amount |
| PERIOD OF INSURANCE | String | Date range (DD/MM/YYYY - DD/MM/YYYY) |

### Sample Data Generation
```bash
python src/sample_excel.py
```

This creates `sample_data.xlsx` with 50 realistic insurance policy records.

## Usage Examples

### Query Examples

**Financial Analysis**
```json
{
  "question": "What is the average premium amount by insured name?",
  "max_results": 20
}
```

**Policy Filtering**
```json
{
  "question": "Show me all policies with sum insured over $1,000,000",
  "max_results": 50
}
```

**Date-based Queries**
```json
{
  "question": "Find policies where the insurance period ended before 2024",
  "max_results": 100
}
```

**Treaty Analysis**
```json
{
  "question": "Which insured party has the highest treaty rate and what percentage of total claims does the treaty cover?",
  "max_results": 10
}
```

### Response Structure
```json
{
  "query_id": "uuid4-string",
  "question": "User's original question",
  "answer": "Comprehensive AI-generated response",
  "confidence_score": 0.85,
  "workflow_steps": [
    {
      "step_name": "analyze_query",
      "step_type": "analysis",
      "execution_time_ms": 150.2,
      "success": true
    }
  ],
  "source_policies": ["POL001", "POL002"],
  "total_processing_time_ms": 1240.5,
  "database_query_time_ms": 45.2,
  "llm_processing_time_ms": 1195.3,
  "tokens_used": 890
}
```

## Architecture Details

### Agentic Workflow
The system uses a custom multi-step reasoning approach:

1. **Query Analysis**: Parse user intent and extract entities
2. **SQL Generation**: Create safe, optimized database queries
3. **Data Execution**: Retrieve relevant policy information
4. **Answer Synthesis**: Generate comprehensive, contextual responses

### Database Schema
```sql
CREATE TABLE insurance_policies (
    id UUID PRIMARY KEY,
    policy_number VARCHAR(50) UNIQUE NOT NULL,
    insured_name VARCHAR(200) NOT NULL,
    sum_insured FLOAT NOT NULL,
    premium FLOAT NOT NULL,
    own_retention_ppn FLOAT NOT NULL,
    own_retention_sum_insured FLOAT NOT NULL,
    own_retention_premium FLOAT NOT NULL,
    treaty_ppn FLOAT NOT NULL,
    treaty_sum_insured FLOAT NOT NULL,
    treaty_premium FLOAT NOT NULL,
    insurance_period_start_date DATE NOT NULL,
    insurance_period_end_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Security Features
- **Input Validation**: Comprehensive Pydantic schemas
- **SQL Injection Prevention**: Parameterized queries only
- **File Upload Security**: Type validation and size limits
- **Rate Limiting**: Configurable request throttling
- **Environment Isolation**: Secure configuration management

## Configuration

### Environment Variables
```env
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
ENVIRONMENT=development

# Google Gemini Settings
GEMINI_MODEL=gemini-pro
GEMINI_TEMPERATURE=0.1
GEMINI_MAX_TOKENS=2048
GEMINI_TOP_P=0.8
GEMINI_TOP_K=40

# Database Settings
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30

# Performance Settings
MAX_CONCURRENT_REQUESTS=10
REQUEST_TIMEOUT=30
QUERY_TIMEOUT=60

# Excel Processing
MAX_EXCEL_ROWS=100000
MAX_FILE_SIZE_MB=50

# Security
SECRET_KEY=your-production-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Database Migration
```bash
# Create new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Development

### Project Structure
```
part2/
├── src/                    # Source code
│   ├── main.py            # FastAPI application entry point
│   ├── agent.py           # RAG agent orchestration
│   ├── agentic_workflow.py # Multi-step reasoning logic
│   ├── database.py        # Database management and repositories
│   ├── gemini_integration.py # Google AI integration
│   ├── ingestion.py       # Excel processing pipeline
│   ├── model.py           # SQLAlchemy database models
│   ├── schema.py          # Pydantic request/response schemas
│   └── config.py          # Application configuration
├── migrations/            # Alembic database migrations
├── requirements.txt       # Python dependencies
├── alembic.ini           # Database migration configuration
├── .env                  # Environment variables
├── sample_data.xlsx      # Example insurance data
└── README.md             # This file
```

### Testing
```bash
# Run with test database
ENVIRONMENT=testing pytest tests/

# Test specific endpoint
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "How many policies do we have?", "max_results": 1}'
```

### Code Quality
```bash
# Format code
black src/
isort src/

# Lint
flake8 src/
mypy src/

# Security scan
bandit -r src/
```

## Monitoring & Observability

### Health Checks
```bash
curl http://localhost:8000/health
```

### Metrics Endpoint
```bash
curl http://localhost:8000/metrics
```

Provides:
- Database connection status
- API usage statistics
- LLM token consumption
- Query performance metrics
- Error rates and response times

### Logging
Structured JSON logging with correlation IDs for request tracing:
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "correlation_id": "uuid4-string",
  "message": "Query processed successfully",
  "metadata": {
    "processing_time_ms": 1240.5,
    "confidence_score": 0.85,
    "tokens_used": 890
  }
}
```

## Production Deployment

### Docker Support
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ ./src/
COPY alembic.ini .
COPY migrations/ ./migrations/

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment-specific Configurations
- **Development**: Debug logging, auto-reload, verbose error messages
- **Production**: Optimized logging, secure headers, performance monitoring
- **Testing**: In-memory database, mocked external services

## Performance Optimization

### Database Optimizations
- Connection pooling with configurable limits
- Query result caching for repeated requests
- Indexes on frequently queried fields
- Batch processing for large datasets

### AI/LLM Optimizations
- Response caching for identical queries
- Token usage tracking and optimization
- Rate limiting to prevent cost overruns
- Structured prompts for consistent outputs

### API Performance
- Async/await throughout the stack
- Request/response compression
- Configurable timeout settings
- Graceful degradation under load

## Troubleshooting

### Common Issues

**Database Connection Errors**
```bash
# Check PostgreSQL status
pg_ctl status
# Verify connection
psql -U insurance_user -d insurance_rag -h localhost
```

**Missing API Key**
```bash
echo $GOOGLE_API_KEY
# Should return your API key
```

**Excel Upload Failures**
- Verify column names match expected schema
- Check file size is under configured limit
- Ensure file format is .xlsx or .xls

### Debug Mode
```bash
export LOG_LEVEL=DEBUG
export DB_ECHO=true
uvicorn src.main:app --reload --log-level debug
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

### Development Guidelines
- Follow PEP 8 style guidelines
- Add type hints to all functions
- Include docstrings for public APIs
- Write tests for new features
- Update documentation as needed

**Built with**: FastAPI, PostgreSQL, Google Gemini AI, SQLAlchemy, Pydantic, Alembic
