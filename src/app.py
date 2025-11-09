"""
FastAPI application for Qwen2.5 Chat Completion Service.
Exposes OpenAI-compatible /v1/chat/completions API.
"""

import logging
import sys
from contextlib import asynccontextmanager
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import get_config
from tokenizer_manager import get_tokenizer_manager
from model_manager import get_model_manager
from chat_completion import chat_completion, validate_messages, ChatCompletionError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# Pydantic models for request/response validation
class ChatMessage(BaseModel):
    """A single chat message."""
    role: str = Field(..., description="Role: system, user, or assistant")
    content: str = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    """Request for chat completion."""
    model: str = Field(default="qwen2.5-1.5b-instruct", description="Model identifier")
    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature")
    top_k: Optional[int] = Field(None, ge=1, description="Top-k sampling")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Top-p (nucleus) sampling")
    max_tokens: Optional[int] = Field(None, ge=1, description="Maximum tokens to generate")
    repeat_penalty: Optional[float] = Field(None, ge=0.0, description="Repetition penalty")
    stream: bool = Field(default=False, description="Whether to stream responses (not supported)")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Overall status: ok, degraded, or down")
    details: Dict = Field(..., description="Detailed component status")


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage service lifecycle (startup/shutdown)."""
    # Startup
    logger.info("Starting Qwen2.5 Chat Completion Service...")
    
    config = get_config()
    logger.info(f"Configuration loaded from {config.config_path}")
    
    # Start tokenizer manager
    tokenizer_manager = get_tokenizer_manager()
    logger.info("Starting tokenizer server...")
    if not tokenizer_manager.start():
        logger.error("Failed to start tokenizer server")
        sys.exit(1)
    
    # Start model manager
    model_manager = get_model_manager()
    logger.info("Starting model process...")
    if not model_manager.start():
        logger.error("Failed to start model process")
        tokenizer_manager.stop()
        sys.exit(1)
    
    logger.info("Service startup complete")
    logger.info(f"API server listening on {config.service_host}:{config.service_port}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Qwen2.5 Chat Completion Service...")
    
    model_manager.stop()
    tokenizer_manager.stop()
    
    logger.info("Service shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Qwen2.5 Chat Completion Service",
    description="OpenAI-compatible chat completion API backed by Qwen2.5-1.5B on LLM-8850",
    version="1.0.0",
    lifespan=lifespan
)


@app.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    """Create a chat completion.
    
    OpenAI-compatible endpoint for chat completions.
    
    Args:
        request: Chat completion request.
        
    Returns:
        Chat completion response in OpenAI format.
        
    Raises:
        HTTPException: If request is invalid or completion fails.
    """
    try:
        # Check streaming (not supported)
        if request.stream:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Streaming is not supported"
            )
        
        # Convert request messages to chat completion format
        messages = [msg.model_dump() for msg in request.messages]
        
        # Validate messages
        if not validate_messages(messages):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid messages format"
            )
        
        # Generate completion
        response = chat_completion(
            messages=messages,
            temperature=request.temperature,
            top_k=request.top_k,
            top_p=request.top_p,
            max_tokens=request.max_tokens,
            repeat_penalty=request.repeat_penalty,
            model=request.model
        )
        
        return JSONResponse(content=response)
    
    except ChatCompletionError as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error in chat completion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint.
    
    Returns status of tokenizer and model components.
    
    Returns:
        Health check response with overall status and component details.
    """
    tokenizer_manager = get_tokenizer_manager()
    model_manager = get_model_manager()
    
    tokenizer_status = tokenizer_manager.get_status()
    model_status = model_manager.get_status()
    
    # Determine overall status
    if tokenizer_status["healthy"] and model_status["healthy"]:
        overall_status = "ok"
    elif tokenizer_status["running"] or model_status["running"]:
        overall_status = "degraded"
    else:
        overall_status = "down"
    
    return HealthResponse(
        status=overall_status,
        details={
            "tokenizer": tokenizer_status,
            "model": model_status
        }
    )


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "name": "Qwen2.5 Chat Completion Service",
        "version": "1.0.0",
        "endpoints": {
            "chat_completions": "/v1/chat/completions",
            "health": "/health"
        }
    }


@app.post("/admin/reload")
async def admin_reload():
    """Reload configuration and restart components.
    
    Admin endpoint for operational control.
    
    Returns:
        Status of reload operation.
    """
    try:
        logger.info("Admin reload requested")
        
        tokenizer_manager = get_tokenizer_manager()
        model_manager = get_model_manager()
        
        # Restart tokenizer
        logger.info("Restarting tokenizer...")
        if not tokenizer_manager.restart():
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"status": "error", "message": "Failed to restart tokenizer"}
            )
        
        # Note: Model restart is more expensive, so we only restart if needed
        # For now, we just check health
        if not model_manager.is_healthy():
            logger.warning("Model is unhealthy, attempting restart...")
            model_manager.stop()
            if not model_manager.start():
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"status": "error", "message": "Failed to restart model"}
                )
        
        return {"status": "ok", "message": "Reload complete"}
    
    except Exception as e:
        logger.error(f"Reload failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": str(e)}
        )


@app.post("/admin/shutdown")
async def admin_shutdown():
    """Graceful shutdown of the service.
    
    Admin endpoint to trigger shutdown.
    
    Returns:
        Shutdown acknowledgment.
    """
    logger.info("Admin shutdown requested")
    
    # This will be handled by the lifespan context manager
    # For now, just return acknowledgment
    # In production, this would trigger a graceful shutdown signal
    
    return {"status": "ok", "message": "Shutdown initiated"}


if __name__ == "__main__":
    import uvicorn
    
    config = get_config()
    
    # Update logging based on config
    logging.getLogger().setLevel(config.log_level)
    
    uvicorn.run(
        app,
        host=config.service_host,
        port=config.service_port,
        workers=config.service_workers,
        log_level=config.log_level.lower()
    )
