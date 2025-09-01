import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
import json

import google.generativeai as genai
from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

class GeminiManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        genai.configure(api_key=settings.google_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        self._request_count = 0
        self._total_tokens_used = 0
    
    async def generate_response(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> Dict[str, Any]:
        try:
            # Convert messages to single prompt
            prompt = messages[-1]["content"] if messages else ""
            
            response = await asyncio.to_thread(
                self.model.generate_content, 
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature or self.settings.gemini_temperature,
                    max_output_tokens=self.settings.gemini_max_tokens
                )
            )
            
            self._request_count += 1
            estimated_tokens = len(response.text.split()) * 1.3
            self._total_tokens_used += int(estimated_tokens)
            
            return {
                "content": response.text,
                "success": True,
                "estimated_tokens": {"total_tokens": int(estimated_tokens)},
                "processing_time_ms": 100
            }
        except Exception as e:
            return {"content": f"Error: {str(e)}", "success": False, "estimated_tokens": {"total_tokens": 0}}
    
    async def generate_structured_response(self, prompt: str, expected_format: str = "json", max_retries: int = 2) -> Dict[str, Any]:
        system_prompt = f"Respond only in valid {expected_format} format. No explanations."
        full_prompt = f"{system_prompt}\n\n{prompt}"
        
        response = await self.generate_response([{"role": "user", "content": full_prompt}])
        
        if response["success"] and expected_format.lower() == "json":
            try:
                content = response["content"].strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                response["parsed_content"] = json.loads(content)
            except:
                response["parsed_content"] = {}
        
        return response
    
    def get_usage_stats(self) -> Dict[str, Any]:
        return {"total_requests": self._request_count, "total_tokens_used": self._total_tokens_used}
    
    async def health_check(self) -> Dict[str, Any]:
        test_response = await self.generate_response([{"role": "user", "content": "Health check: respond with 'OK'"}])
        return {"status": "healthy" if "OK" in test_response["content"] else "unhealthy"}

# Keep your InsurancePromptTemplates class exactly as is

class InsurancePromptTemplates:
    """
    Insurance domain-specific prompt templates.
    Domain expertise encoded in reusable,
    optimized prompt templates for consistent results.
    """
    
    @staticmethod
    def query_analysis_prompt(question: str) -> str:
        """Prompt for analyzing insurance queries."""
        return f"""You are an expert insurance data analyst. Analyze this insurance-related query to determine the best data processing approach.

Query: "{question}"

Your task is to classify the query and extract key information that will help generate accurate SQL queries against an insurance policy database.

The database contains insurance policies with these fields:
- policy_number (VARCHAR): Unique policy identifier
- insured_name (VARCHAR): Name of insured party
- sum_insured (FLOAT): Total coverage amount
- premium (FLOAT): Annual premium amount
- own_retention_ppn (FLOAT): Own retention percentage (0-100)
- own_retention_sum_insured (FLOAT): Own retention amount
- own_retention_premium (FLOAT): Own retention premium
- treaty_ppn (FLOAT): Treaty percentage (0-100)
- treaty_sum_insured (FLOAT): Treaty coverage amount
- treaty_premium (FLOAT): Treaty premium
- insurance_period_start_date (DATE): Coverage start date
- insurance_period_end_date (DATE): Coverage end date

Classify the query and respond in JSON format:
{{
    "query_type": "simple_lookup|aggregation|comparison|date_analysis|complex_analysis",
    "intent": "Brief description of what user wants to know",
    "entities": {{
        "policy_numbers": ["list of policy numbers mentioned"],
        "insured_names": ["list of names mentioned"],
        "amounts": ["list of monetary amounts mentioned"],
        "date_ranges": ["list of date ranges mentioned"],
        "percentages": ["list of percentages mentioned"]
    }},
    "required_operations": ["database_query", "aggregation", "calculation", "comparison"],
    "sql_strategy": {{
        "target_fields": ["fields to select"],
        "aggregations": ["SUM", "AVG", "COUNT", "MAX", "MIN"],
        "filters": ["WHERE clause conditions"],
        "grouping": ["GROUP BY fields if needed"],
        "sorting": ["ORDER BY requirements"]
    }},
    "complexity_level": "low|medium|high",
    "estimated_steps": 2
}}"""

    @staticmethod
    def sql_generation_prompt(question: str, analysis: Dict[str, Any]) -> str:
        """Prompt for generating SQL queries."""
        return f"""You are an expert PostgreSQL developer specializing in insurance data queries. Generate a safe, efficient SQL query.

Original Question: "{question}"

Query Analysis:
{json.dumps(analysis, indent=2)}

Database Schema:
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

Generate a PostgreSQL query that:
1. Accurately answers the user's question
2. Uses proper SQL syntax and PostgreSQL-specific functions
3. Includes appropriate WHERE clauses for filtering
4. Uses correct aggregation functions (SUM, AVG, COUNT, etc.)
5. Includes LIMIT clause for safety (max 1000 rows)
6. Handles NULL values appropriately
7. Uses meaningful column aliases for readability
8. Is optimized for performance

SAFETY RULES:
- ONLY SELECT statements allowed
- NO DROP, DELETE, UPDATE, INSERT statements
- Always include LIMIT clause
- Use parameterized conditions to prevent injection
- Validate date formats properly

Respond with ONLY the SQL query, no explanations or markdown formatting:"""

    @staticmethod
    def answer_generation_prompt(question: str, data: List[Dict], calculations: Dict[str, Any]) -> str:
        """Prompt for generating final answers."""
        data_summary = f"{len(data)} records" if data else "No data found"
        sample_data = json.dumps(data[:3], indent=2, default=str) if data else "No sample data"
        calculations_summary = json.dumps(calculations, indent=2) if calculations else "No calculations performed"
        
        return f"""You are an expert insurance analyst providing insights to business users. Generate a comprehensive, accurate answer based on the data analysis results.

Original Question: "{question}"

Data Retrieved: {data_summary}
Sample Data:
{sample_data}

Calculations Performed:
{calculations_summary}

Instructions:
1. Answer the user's question directly and clearly
2. Include specific numbers, percentages, and monetary amounts
3. Explain any calculations or aggregations performed
4. Use proper insurance terminology
5. If multiple policies are involved, mention key policy numbers
6. If no data was found, explain why and suggest alternatives
7. Format monetary amounts with proper currency symbols and commas
8. Be professional yet accessible to business users
9. Include insights or observations that might be valuable
10. If the data reveals interesting patterns, highlight them

Structure your response:
- Direct answer to the question
- Supporting details with specific numbers
- Key insights or observations
- Data source summary (number of policies analyzed)

Provide a complete, professional response:"""

    @staticmethod
    def error_handling_prompt(question: str, error: str, context: Dict[str, Any]) -> str:
        """Prompt for handling errors gracefully."""
        return f"""You are a helpful insurance system assistant. A user asked a question but an error occurred during processing.

User Question: "{question}"
Error: {error}
Context: {json.dumps(context, indent=2)}

Generate a helpful, professional response that:
1. Acknowledges the user's question
2. Explains that a technical issue occurred (without technical details)
3. Suggests alternative ways to get the information
4. Offers specific next steps
5. Maintains a professional, helpful tone

Do not include technical error details or blame the user. Focus on being helpful and solution-oriented."""


# Global Gemini manager instance
gemini_manager = None


async def get_gemini_manager() -> GeminiManager:
    """Get or create Gemini manager instance."""
    global gemini_manager
    if gemini_manager is None:
        settings = get_settings()
        gemini_manager = GeminiManager(settings)
    return gemini_manager