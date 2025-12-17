import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import re

from .memory import HybridMemorySystem, MemoryItem

logger = logging.getLogger(__name__)


@dataclass
class Document:
    id: str
    title: str
    content: str
    metadata: Dict[str, Any]
    chunks: List[str] = None


@dataclass
class RetrievalResult:
    content: str
    source: str
    relevance_score: float
    metadata: Dict[str, Any]


class DocumentProcessor:
    """Process and chunk documents for ingestion"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def process_document(self, document: Document) -> List[str]:
        """Process a document and return chunks"""
        # Simple text chunking by sentences and size
        sentences = re.split(r'[.!?]+', document.content)
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if adding this sentence would exceed chunk size
            if len(current_chunk) + len(sentence) > self.chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                # Start new chunk with overlap
                overlap_words = current_chunk.split()[-self.chunk_overlap:]
                current_chunk = " ".join(overlap_words) + " " + sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence

        # Add the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        document.chunks = chunks
        return chunks

    def extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text (simple implementation)"""
        # Remove punctuation and convert to lowercase
        clean_text = re.sub(r'[^\w\s]', '', text.lower())
        words = clean_text.split()

        # Filter out common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
        }

        keywords = [word for word in words if len(word) > 2 and word not in stop_words]

        # Return unique keywords, limited to top 10 by frequency
        from collections import Counter
        word_counts = Counter(keywords)
        return [word for word, count in word_counts.most_common(10)]


class RAGSystem:
    """Retrieval-Augmented Generation system"""

    def __init__(self, memory_system: HybridMemorySystem = None):
        self.memory_system = memory_system or HybridMemorySystem()
        self.document_processor = DocumentProcessor()
        self.documents: Dict[str, Document] = {}

    async def ingest_document(self, title: str, content: str, metadata: Dict[str, Any] = None) -> str:
        """Ingest a document into the RAG system"""
        doc_id = f"doc_{len(self.documents)}"

        document = Document(
            id=doc_id,
            title=title,
            content=content,
            metadata=metadata or {}
        )

        # Process document into chunks
        chunks = self.document_processor.process_document(document)

        # Store document
        self.documents[doc_id] = document

        # Add chunks to long-term memory
        for i, chunk in enumerate(chunks):
            chunk_metadata = {
                "document_id": doc_id,
                "document_title": title,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "keywords": self.document_processor.extract_keywords(chunk),
                **(metadata or {})
            }

            await self.memory_system.add_to_knowledge_base(chunk, chunk_metadata)

        logger.info(f"Ingested document '{title}' with {len(chunks)} chunks")
        return doc_id

    async def ingest_text(self, text: str, source: str = "user_input", metadata: Dict[str, Any] = None) -> str:
        """Ingest raw text (e.g., from user conversations)"""
        text_metadata = {
            "source": source,
            "type": "text_snippet",
            "keywords": self.document_processor.extract_keywords(text),
            **(metadata or {})
        }

        return await self.memory_system.add_to_knowledge_base(text, text_metadata)

    async def retrieve(self, query: str, session_id: str = None, limit: int = 5) -> List[RetrievalResult]:
        """Retrieve relevant information for a query"""
        # Perform hybrid search
        memory_items = await self.memory_system.hybrid_search(query, session_id, limit)

        # Convert to retrieval results
        results = []
        for item in memory_items:
            # Calculate simple relevance score based on keyword matching
            relevance_score = self._calculate_relevance(query, item)

            result = RetrievalResult(
                content=item.content,
                source=item.metadata.get("source", "unknown"),
                relevance_score=relevance_score,
                metadata=item.metadata
            )
            results.append(result)

        # Sort by relevance score
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        return results

    async def retrieve_with_context(self, query: str, session_id: str, limit: int = 5) -> Tuple[
        List[RetrievalResult], List[MemoryItem]]:
        """Retrieve relevant information along with session context"""
        # Get retrieval results
        results = await self.retrieve(query, session_id, limit)

        # Get session context
        context = self.memory_system.get_session_context(session_id)

        return results, context

    def _calculate_relevance(self, query: str, item: MemoryItem) -> float:
        """Calculate relevance score between query and memory item"""
        query_lower = query.lower()
        content_lower = item.content.lower()

        # Simple scoring based on:
        # 1. Exact phrase matches
        # 2. Individual word matches
        # 3. Keyword matches from metadata
        # 4. Access frequency

        score = 0.0

        # Exact phrase match (highest weight)
        if query_lower in content_lower:
            score += 1.0

        # Individual word matches
        query_words = set(query_lower.split())
        content_words = set(content_lower.split())
        word_overlap = len(query_words.intersection(content_words))
        if len(query_words) > 0:
            score += (word_overlap / len(query_words)) * 0.5

        # Keyword matches from metadata
        keywords = item.metadata.get("keywords", [])
        keyword_matches = sum(1 for word in query_words if word in keywords)
        if len(query_words) > 0:
            score += (keyword_matches / len(query_words)) * 0.3

        # Access frequency bonus (popular items get slight boost)
        score += min(item.access_count * 0.01, 0.1)

        return score

    async def add_conversation_turn(self, session_id: str, user_message: str, assistant_response: str):
        """Add a conversation turn to session memory"""
        # Add user message
        await self.memory_system.add_to_session(
            session_id,
            user_message,
            {"type": "user_message", "role": "user"}
        )

        # Add assistant response
        await self.memory_system.add_to_session(
            session_id,
            assistant_response,
            {"type": "assistant_response", "role": "assistant"}
        )

    def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a document by ID"""
        return self.documents.get(doc_id)

    def list_documents(self) -> List[Document]:
        """List all ingested documents"""
        return list(self.documents.values())

    async def search_documents(self, query: str, limit: int = 5) -> List[Document]:
        """Search for documents by title or content"""
        query_lower = query.lower()
        matching_docs = []

        for doc in self.documents.values():
            if (query_lower in doc.title.lower() or
                    query_lower in doc.content.lower()):
                matching_docs.append(doc)

        return matching_docs[:limit]