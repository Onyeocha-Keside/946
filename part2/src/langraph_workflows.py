import asyncio
import time
from typing import Dict, Any, List
from uuid import uuid4

from src.schema import QueryRequest, QueryResponse, QueryStepResult
from src.database import get_policy_repository
from src.gemini_integration import get_gemini_manager, InsurancePromptTemplates

class AgenticWorkflow:
    async def process_query(self, request: QueryRequest) -> QueryResponse:
        start_time = time.time()
        steps = []
        tokens_used = 0
        
        # Step 1: Analyze query
        analysis_result = await self._analyze_query(request.question)
        steps.append(analysis_result["step"])
        tokens_used += analysis_result["tokens"]
        
        if not analysis_result["success"]:
            return self._error_response(request, "Query analysis failed", steps, tokens_used)
        
        # Step 2: Generate SQL
        sql_result = await self._generate_sql(request.question, analysis_result["analysis"])
        steps.append(sql_result["step"])
        tokens_used += sql_result["tokens"]
        
        if not sql_result["success"]:
            return self._error_response(request, "SQL generation failed", steps, tokens_used)
        
        # Step 3: Execute query
        exec_result = await self._execute_query(sql_result["sql"])
        steps.append(exec_result["step"])
        
        # Step 4: Generate answer
        answer_result = await self._generate_answer(request.question, exec_result["data"])
        steps.append(answer_result["step"])
        tokens_used += answer_result["tokens"]
        
        total_time = (time.time() - start_time) * 1000
        
        return QueryResponse(
            query_id=uuid4(),
            question=request.question,
            answer=answer_result["answer"],
            confidence_score=0.85 if exec_result["success"] else 0.3,
            workflow_steps=steps,
            source_policies=[row.get("policy_number", "") for row in exec_result["data"][:5]],
            total_processing_time_ms=total_time,
            database_query_time_ms=exec_result["db_time"],
            llm_processing_time_ms=total_time - exec_result["db_time"],
            tokens_used=tokens_used
        )
    
    async def _analyze_query(self, question: str) -> Dict[str, Any]:
        step_start = time.time()
        try:
            gemini = await get_gemini_manager()
            prompt = InsurancePromptTemplates.query_analysis_prompt(question)
            response = await gemini.generate_structured_response(prompt, "json")
            
            return {
                "success": response["success"],
                "analysis": response.get("parsed_content", {}),
                "tokens": response.get("estimated_tokens", {}).get("total_tokens", 0),
                "step": QueryStepResult(
                    step_name="analyze_query",
                    step_type="analysis",
                    input_data={"question": question},
                    output_data=response.get("parsed_content", {}),
                    execution_time_ms=(time.time() - step_start) * 1000,
                    success=response["success"]
                )
            }
        except Exception as e:
            return {"success": False, "tokens": 0, "step": self._error_step("analyze_query", str(e), step_start)}
    
    async def _generate_sql(self, question: str, analysis: Dict) -> Dict[str, Any]:
        step_start = time.time()
        try:
            gemini = await get_gemini_manager()
            prompt = InsurancePromptTemplates.sql_generation_prompt(question, analysis)
            response = await gemini.generate_response([{"role": "user", "content": prompt}])
            
            sql = response["content"].strip()
            if not sql.upper().startswith("SELECT"):
                sql = f"SELECT * FROM insurance_policies LIMIT {10}"
            
            return {
                "success": response["success"],
                "sql": sql,
                "tokens": response.get("estimated_tokens", {}).get("total_tokens", 0),
                "step": QueryStepResult(
                    step_name="generate_sql",
                    step_type="query_generation",
                    input_data={"analysis": analysis},
                    output_data={"sql": sql},
                    execution_time_ms=(time.time() - step_start) * 1000,
                    success=response["success"]
                )
            }
        except Exception as e:
            return {"success": False, "tokens": 0, "step": self._error_step("generate_sql", str(e), step_start)}
    
    async def _execute_query(self, sql: str) -> Dict[str, Any]:
        step_start = time.time()
        try:
            repo = await get_policy_repository()
            data = await repo.execute_custom_query(sql)
            db_time = (time.time() - step_start) * 1000
            
            return {
                "success": True,
                "data": data,
                "db_time": db_time,
                "step": QueryStepResult(
                    step_name="execute_query",
                    step_type="database_query",
                    input_data={"sql": sql},
                    output_data={"result_count": len(data)},
                    execution_time_ms=db_time,
                    success=True
                )
            }
        except Exception as e:
            return {"success": False, "data": [], "db_time": 0, "step": self._error_step("execute_query", str(e), step_start)}
    
    async def _generate_answer(self, question: str, data: List[Dict]) -> Dict[str, Any]:
        step_start = time.time()
        try:
            gemini = await get_gemini_manager()
            prompt = InsurancePromptTemplates.answer_generation_prompt(question, data, {})
            response = await gemini.generate_response([{"role": "user", "content": prompt}])
            
            return {
                "answer": response["content"],
                "tokens": response.get("estimated_tokens", {}).get("total_tokens", 0),
                "step": QueryStepResult(
                    step_name="generate_answer",
                    step_type="response_generation",
                    input_data={"data_count": len(data)},
                    output_data={"answer_length": len(response["content"])},
                    execution_time_ms=(time.time() - step_start) * 1000,
                    success=response["success"]
                )
            }
        except Exception as e:
            return {"answer": f"Error generating answer: {str(e)}", "tokens": 0, "step": self._error_step("generate_answer", str(e), step_start)}
    
    def _error_response(self, request: QueryRequest, error: str, steps: List, tokens: int) -> QueryResponse:
        return QueryResponse(
            query_id=uuid4(),
            question=request.question,
            answer=f"I encountered an error: {error}. Please try rephrasing your question.",
            confidence_score=0.0,
            workflow_steps=steps,
            source_policies=[],
            total_processing_time_ms=100,
            database_query_time_ms=0,
            llm_processing_time_ms=100,
            tokens_used=tokens
        )
    
    def _error_step(self, name: str, error: str, start_time: float) -> QueryStepResult:
        return QueryStepResult(
            step_name=name,
            step_type="error",
            input_data={},
            output_data={},
            execution_time_ms=(time.time() - start_time) * 1000,
            success=False,
            error_message=error
        )

async def get_insurance_workflow():
    return AgenticWorkflow()