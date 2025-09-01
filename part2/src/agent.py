
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID, uuid4

from src.schema import QueryRequest, QueryResponse, QueryStepResult
from src.langraph_workflows import get_insurance_workflow
from src.gemini_integration import get_gemini_manager
from src.database import get_policy_repository, get_audit_repository
from src.config import Settings, get_settings


logger = logging.getLogger(__name__)


class InsuranceRAGAgent:
    """
    Main Insurance RAG Agent using LangGraph workflows.
    Clean orchestration layer that delegates complex
    reasoning to LangGraph workflows while maintaining system integration.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Cache for response optimization
        self._response_cache: Dict[str, QueryResponse] = {}
        self._cache_stats = {"hits": 0, "misses": 0}
        
        logger.info("InsuranceRAGAgent initialized with LangGraph workflows")
    
    async def process_query(self, request: QueryRequest) -> QueryResponse:
        """
        Process query using LangGraph workflow.
        Clean integration layer with caching,
        error handling, and comprehensive monitoring.
        """
        start_time = time.time()
        
        try:
            # Check cache if enabled
            if request.use_cache:
                cache_key = self._get_cache_key(request)
                cached_response = self._response_cache.get(cache_key)
                
                if cached_response:
                    self._cache_stats["hits"] += 1
                    logger.info(f"Returning cached response for query: {request.question[:50]}...")
                    
                    # Update timing to reflect cache hit
                    cached_response.total_processing_time_ms = (time.time() - start_time) * 1000
                    return cached_response
                
                self._cache_stats["misses"] += 1
            
            # Get LangGraph workflow instance
            workflow = await get_insurance_workflow()
            
            # Process through LangGraph workflow
            logger.info(f"Processing query through LangGraph: {request.question[:100]}...")
            response = await workflow.process_query(request)
            
            # Cache successful responses
            if request.use_cache and response.confidence_score > 0.7:
                cache_key = self._get_cache_key(request)
                self._response_cache[cache_key] = response
            
            # Log successful processing
            logger.info(
                f"Query processed successfully: confidence={response.confidence_score:.2f}, "
                f"time={response.total_processing_time_ms:.1f}ms, "
                f"steps={len(response.workflow_steps)}"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            
            # Return error response
            total_time = (time.time() - start_time) * 1000
            
            return QueryResponse(
                query_id=uuid4(),
                question=request.question,
                answer=f"I apologize, but I encountered an error while processing your question: {str(e)}",
                confidence_score=0.0,
                workflow_steps=[],
                source_policies=[],
                total_processing_time_ms=total_time,
                database_query_time_ms=0,
                llm_processing_time_ms=0,
                tokens_used=0
            )
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        try:
            # Get component statuses
            gemini_manager = await get_gemini_manager()
            policy_repo = await get_policy_repository()
            
            # Check Gemini health
            gemini_health = await gemini_manager.health_check()
            
            # Get database metrics
            db_manager = policy_repo.db_manager
            db_health = await db_manager.health_check()
            
            # Get usage statistics
            gemini_usage = gemini_manager.get_usage_stats()
            
            # Get recent query stats
            audit_repo = await get_audit_repository()
            query_stats = await audit_repo.get_ingestion_stats(days=1)  # Last 24 hours
            
            return {
                "status": "healthy" if gemini_health.get("status") == "healthy" and db_health.get("status") == "healthy" else "degraded",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {
                    "gemini_llm": gemini_health,
                    "database": db_health,
                    "langgraph_workflow": {"status": "ready", "version": "0.0.38"},
                    "cache": {
                        "status": "active",
                        "size": len(self._response_cache),
                        "hit_rate": self._cache_stats["hits"] / max(sum(self._cache_stats.values()), 1),
                        "stats": self._cache_stats
                    }
                },
                "usage_metrics": {
                    "gemini_api": gemini_usage,
                    "recent_queries": query_stats,
                    "cache_performance": self._cache_stats
                },
                "version": "2.0.0"
            }
            
        except Exception as e:
            logger.error(f"Error getting system status: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _get_cache_key(self, request: QueryRequest) -> str:
        """Generate cache key for request."""
        import hashlib
        import json
        
        # Create hash from relevant request components
        cache_data = {
            "question": request.question.lower().strip(),
            "max_results": request.max_results
        }
        
        cache_string = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_string.encode()).hexdigest()
    
    def clear_cache(self):
        """Clear response cache."""
        self._response_cache.clear()
        self._cache_stats = {"hits": 0, "misses": 0}
        logger.info("Response cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._response_cache),
            "hit_rate": self._cache_stats["hits"] / max(sum(self._cache_stats.values()), 1),
            "total_requests": sum(self._cache_stats.values()),
            **self._cache_stats
        }


class SampleQueryHandler:
    """
    Handles specific sample queries from the requirements.
    Demonstrates system capabilities with
    realistic insurance business scenarios.
    """
    
    def __init__(self, agent: InsuranceRAGAgent):
        self.agent = agent
        
        # Sample queries from requirements
        self.sample_queries = [
            "What is the total sum insured for all policies?",
            "Show me all policies with sum insured over $500,000",
            "Which insured party has the highest treaty rate?",
            "Find policies where the insurance period ended before 2024",
            "Calculate the average premium amount by insured name",
            "What percentage of total sum insured does the treaty cover?"
        ]
    
    async def demonstrate_capabilities(self) -> List[Dict[str, Any]]:
        """
        Demonstrate system capabilities with sample queries.
        Automated testing and demonstration of
        system capabilities with realistic business scenarios.
        """
        results = []
        
        for i, query_text in enumerate(self.sample_queries):
            try:
                logger.info(f"Processing sample query {i+1}/{len(self.sample_queries)}: {query_text}")
                
                request = QueryRequest(
                    question=query_text,
                    max_results=10,
                    include_reasoning=True,
                    use_cache=False  # Don't use cache for demonstrations
                )
                
                response = await self.agent.process_query(request)
                
                results.append({
                    "query_number": i + 1,
                    "question": query_text,
                    "answer": response.answer,
                    "confidence_score": response.confidence_score,
                    "processing_time_ms": response.total_processing_time_ms,
                    "workflow_steps": len(response.workflow_steps),
                    "source_policies_count": len(response.source_policies),
                    "success": response.confidence_score > 0.5
                })
                
                # Small delay between queries to avoid rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in sample query {i+1}: {str(e)}")
                results.append({
                    "query_number": i + 1,
                    "question": query_text,
                    "error": str(e),
                    "success": False
                })
        
        # Calculate summary statistics
        successful_queries = [r for r in results if r.get("success", False)]
        
        summary = {
            "total_queries": len(self.sample_queries),
            "successful_queries": len(successful_queries),
            "success_rate": len(successful_queries) / len(self.sample_queries),
            "avg_confidence": sum(r.get("confidence_score", 0) for r in successful_queries) / len(successful_queries) if successful_queries else 0,
            "avg_processing_time_ms": sum(r.get("processing_time_ms", 0) for r in successful_queries) / len(successful_queries) if successful_queries else 0,
            "results": results
        }
        
        logger.info(
            f"Sample queries completed: {len(successful_queries)}/{len(self.sample_queries)} successful "
            f"(success rate: {summary['success_rate']:.1%})"
        )
        
        return summary


# Factory functions for dependency injection
async def get_insurance_rag_agent() -> InsuranceRAGAgent:
    """Get or create InsuranceRAGAgent instance."""
    settings = get_settings()
    return InsuranceRAGAgent(settings)


async def get_sample_query_handler() -> SampleQueryHandler:
    """Get SampleQueryHandler instance."""
    agent = await get_insurance_rag_agent()
    return SampleQueryHandler(agent)


# Legacy compatibility - keep the same interface for existing code
InsuranceRAGAgent.get_system_status = InsuranceRAGAgent.get_system_status
InsuranceRAGAgent.clear_cache = InsuranceRAGAgent.clear_cache
InsuranceRAGAgent.get_cache_stats = InsuranceRAGAgent.get_cache_stats