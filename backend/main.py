from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import os
import sys

import logging
from config import settings
from llm_client import llm_client

# Add packages to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'packages'))
from orchestrator import AgentOrchestrator, OrchestrationContext
from rag import RAGSystem
from tools_registry import ToolsRegistry

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Agent Platform",
    description="A simple AI agent platform with orchestrator, RAG, and connectors",
    version="1.0.0"
)

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    tenant_id: Optional[str] = "default"
    max_steps: Optional[int] = 5


class ChatResponse(BaseModel):
    response: str
    steps: List[Dict[str, Any]]
    tokens_used: int
    status: str


class HealthResponse(BaseModel):
    status: str
    version: str


class DocumentUpload(BaseModel):
    title: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


class DocumentResponse(BaseModel):
    id: str
    title: str
    status: str
    chunks_created: Optional[int] = None


# In-memory storage for simplicity
sessions = {}
tenant_configs = {}

# Initialize RAG system, tools registry, and orchestrator
rag_system = RAGSystem()
tools_registry = ToolsRegistry()
orchestrator = AgentOrchestrator(llm_client, tools_registry=tools_registry, rag_system=rag_system)


@app.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy", version="1.0.0")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint for AI agent interactions"""
    try:
        # Convert Pydantic models to dict format
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

        # Get the latest user message
        user_message = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                user_message = msg["content"]
                break

        # Get tenant configuration
        tenant_config = tenant_configs.get(request.tenant_id, {
            "allowed_tools": ["web_search", "email"],
            "max_steps": request.max_steps or settings.max_orchestrator_steps
        })
        # Create orchestration context
        context = OrchestrationContext(
            session_id=f"{request.tenant_id}_{len(sessions)}",
            tenant_id=request.tenant_id,
            user_message=user_message,
            conversation_history=messages[:-1],  # Exclude current message
            available_tools=tenant_config["allowed_tools"],
            max_steps=tenant_config["max_steps"]
        )

        # Execute orchestration
        result = await orchestrator.orchestrate(context)

        logger.info(f"Orchestration completed for tenant: {request.tenant_id}, steps: {len(result['steps'])}")
        return ChatResponse(**result)

    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tenants/{tenant_id}/config")
async def get_tenant_config(tenant_id: str):
    """Get configuration for a specific tenant"""
    config = tenant_configs.get(tenant_id, {
        "allowed_tools": ["web_search", "email"],
        "max_steps": 5,
        "guardrails": {
            "pii_redaction": True,
            "toxicity_filter": True
        }
    })
    return config


@app.post("/tenants/{tenant_id}/config")
async def update_tenant_config(tenant_id: str, config: Dict[str, Any]):
    """Update configuration for a specific tenant"""
    tenant_configs[tenant_id] = config
    return {"status": "updated", "tenant_id": tenant_id}


@app.get("/tools")
async def list_available_tools():
    """List all available tools and connectors"""
    return {
        "tools": [
            {"name": "web_search", "description": "Search the web for information"},
            {"name": "email", "description": "Send and receive emails"},
            {"name": "slack", "description": "Interact with Slack"},
            {"name": "document_search", "description": "Search through documents using RAG"}
        ]
    }


@app.post("/documents", response_model=DocumentResponse)
async def upload_document(document: DocumentUpload):
    """Upload a document to the RAG system"""
    try:
        doc_id = await rag_system.ingest_document(
            title=document.title,
            content=document.content,
            metadata=document.metadata or {}
        )

        # Get the document to count chunks
        doc = rag_system.get_document(doc_id)
        chunks_created = len(doc.chunks) if doc and doc.chunks else 0

        logger.info(f"Document '{document.title}' uploaded with ID: {doc_id}")
        return DocumentResponse(
            id=doc_id,
            title=document.title,
            status="success",
            chunks_created=chunks_created
        )

    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents():
    """List all uploaded documents"""
    try:
        documents = rag_system.list_documents()
        return {
            "documents": [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "chunks": len(doc.chunks) if doc.chunks else 0,
                    "metadata": doc.metadata
                }
                for doc in documents
            ]
        }
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    """Get a specific document by ID"""
    try:
        document = rag_system.get_document(doc_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            "id": document.id,
            "title": document.title,
            "content": document.content,
            "chunks": document.chunks,
            "metadata": document.metadata
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/documents/search")
async def search_documents(query: Dict[str, str]):
    """Search through documents"""
    try:
        search_query = query.get("query", "")
        if not search_query:
            raise HTTPException(status_code=400, detail="Query is required")

        results = await rag_system.retrieve(search_query, limit=10)

        return {
            "query": search_query,
            "results": [
                {
                    "content": result.content,
                    "source": result.source,
                    "relevance_score": result.relevance_score,
                    "metadata": result.metadata
                }
                for result in results
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )