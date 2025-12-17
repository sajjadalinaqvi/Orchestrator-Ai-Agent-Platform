import json
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class MemoryItem:
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    timestamp: datetime = None
    access_count: int = 0
    last_accessed: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.last_accessed is None:
            self.last_accessed = datetime.utcnow()


class ShortTermMemory:
    """In-memory storage for current session context"""

    def __init__(self, max_items: int = 100, ttl_minutes: int = 60):
        self.max_items = max_items
        self.ttl = timedelta(minutes=ttl_minutes)
        self.items: Dict[str, MemoryItem] = {}
        self.session_contexts: Dict[str, List[str]] = {}

    def add_item(self, session_id: str, content: str, metadata: Dict[str, Any] = None) -> str:
        """Add an item to short-term memory"""
        item_id = self._generate_id(content)

        item = MemoryItem(
            id=item_id,
            content=content,
            metadata=metadata or {},
            timestamp=datetime.utcnow()
        )

        self.items[item_id] = item

        # Add to session context
        if session_id not in self.session_contexts:
            self.session_contexts[session_id] = []
        self.session_contexts[session_id].append(item_id)

        # Cleanup old items
        self._cleanup()

        logger.debug(f"Added item {item_id} to short-term memory for session {session_id}")
        return item_id

    def get_session_context(self, session_id: str) -> List[MemoryItem]:
        """Get all items for a specific session"""
        if session_id not in self.session_contexts:
            return []

        items = []
        for item_id in self.session_contexts[session_id]:
            if item_id in self.items:
                item = self.items[item_id]
                item.access_count += 1
                item.last_accessed = datetime.utcnow()
                items.append(item)

        return items

    def search(self, query: str, session_id: str = None, limit: int = 5) -> List[MemoryItem]:
        """Simple keyword-based search in short-term memory"""
        query_lower = query.lower()
        results = []

        items_to_search = []
        if session_id and session_id in self.session_contexts:
            # Search within session context
            for item_id in self.session_contexts[session_id]:
                if item_id in self.items:
                    items_to_search.append(self.items[item_id])
        else:
            # Search all items
            items_to_search = list(self.items.values())

        for item in items_to_search:
            if query_lower in item.content.lower():
                item.access_count += 1
                item.last_accessed = datetime.utcnow()
                results.append(item)

        # Sort by relevance (simple scoring)
        results.sort(key=lambda x: (x.access_count, -abs((datetime.utcnow() - x.timestamp).total_seconds())))

        return results[:limit]

    def _generate_id(self, content: str) -> str:
        """Generate a unique ID for content"""
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _cleanup(self):
        """Remove old items and enforce size limits"""
        now = datetime.utcnow()

        # Remove expired items
        expired_ids = [
            item_id for item_id, item in self.items.items()
            if now - item.timestamp > self.ttl
        ]

        for item_id in expired_ids:
            del self.items[item_id]
            # Remove from session contexts
            for session_id, item_ids in self.session_contexts.items():
                if item_id in item_ids:
                    item_ids.remove(item_id)

        # Enforce size limit
        if len(self.items) > self.max_items:
            # Remove least recently accessed items
            sorted_items = sorted(
                self.items.items(),
                key=lambda x: x[1].last_accessed
            )

            items_to_remove = len(self.items) - self.max_items
            for item_id, _ in sorted_items[:items_to_remove]:
                del self.items[item_id]
                # Remove from session contexts
                for session_id, item_ids in self.session_contexts.items():
                    if item_id in item_ids:
                        item_ids.remove(item_id)


class LongTermMemory:
    """Persistent storage for knowledge base and learned information"""

    def __init__(self, storage_path: str = "memory_store.json"):
        self.storage_path = storage_path
        self.items: Dict[str, MemoryItem] = {}
        self.load_from_disk()

    def add_item(self, content: str, metadata: Dict[str, Any] = None, embedding: List[float] = None) -> str:
        """Add an item to long-term memory"""
        item_id = self._generate_id(content)

        item = MemoryItem(
            id=item_id,
            content=content,
            metadata=metadata or {},
            embedding=embedding,
            timestamp=datetime.utcnow()
        )

        self.items[item_id] = item
        self.save_to_disk()

        logger.debug(f"Added item {item_id} to long-term memory")
        return item_id

    def search(self, query: str, limit: int = 5) -> List[MemoryItem]:
        """Search in long-term memory using keyword matching"""
        query_lower = query.lower()
        results = []

        for item in self.items.values():
            # Simple keyword matching
            if query_lower in item.content.lower():
                item.access_count += 1
                item.last_accessed = datetime.utcnow()
                results.append(item)

        # Sort by relevance (access count and recency)
        results.sort(key=lambda x: (x.access_count, -abs((datetime.utcnow() - x.timestamp).total_seconds())))

        return results[:limit]

    def get_by_id(self, item_id: str) -> Optional[MemoryItem]:
        """Get a specific item by ID"""
        item = self.items.get(item_id)
        if item:
            item.access_count += 1
            item.last_accessed = datetime.utcnow()
        return item

    def _generate_id(self, content: str) -> str:
        """Generate a unique ID for content"""
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def save_to_disk(self):
        """Save memory to disk"""
        try:
            data = {}
            for item_id, item in self.items.items():
                data[item_id] = {
                    "id": item.id,
                    "content": item.content,
                    "metadata": item.metadata,
                    "embedding": item.embedding,
                    "timestamp": item.timestamp.isoformat(),
                    "access_count": item.access_count,
                    "last_accessed": item.last_accessed.isoformat()
                }

            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save memory to disk: {e}")

    def load_from_disk(self):
        """Load memory from disk"""
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)

            for item_id, item_data in data.items():
                item = MemoryItem(
                    id=item_data["id"],
                    content=item_data["content"],
                    metadata=item_data["metadata"],
                    embedding=item_data.get("embedding"),
                    timestamp=datetime.fromisoformat(item_data["timestamp"]),
                    access_count=item_data.get("access_count", 0),
                    last_accessed=datetime.fromisoformat(item_data["last_accessed"])
                )
                self.items[item_id] = item

            logger.info(f"Loaded {len(self.items)} items from long-term memory")

        except FileNotFoundError:
            logger.info("No existing memory file found, starting with empty long-term memory")
        except Exception as e:
            logger.error(f"Failed to load memory from disk: {e}")


class HybridMemorySystem:
    """Combines short-term and long-term memory with hybrid search"""

    def __init__(self, storage_path: str = "memory_store.json"):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(storage_path)

    async def add_to_session(self, session_id: str, content: str, metadata: Dict[str, Any] = None) -> str:
        """Add content to current session (short-term memory)"""
        return self.short_term.add_item(session_id, content, metadata)

    async def add_to_knowledge_base(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """Add content to knowledge base (long-term memory)"""
        return self.long_term.add_item(content, metadata)

    async def hybrid_search(self, query: str, session_id: str = None, limit: int = 5) -> List[MemoryItem]:
        """Perform hybrid search across both short-term and long-term memory"""
        # Search short-term memory (session context)
        short_term_results = self.short_term.search(query, session_id, limit // 2)

        # Search long-term memory (knowledge base)
        long_term_results = self.long_term.search(query, limit // 2)

        # Combine and deduplicate results
        all_results = short_term_results + long_term_results
        seen_ids = set()
        unique_results = []

        for item in all_results:
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                unique_results.append(item)

        # Sort by relevance (prioritize short-term memory for recency)
        unique_results.sort(key=lambda x: (
            1 if x in short_term_results else 0,  # Prioritize short-term
            x.access_count,
            -abs((datetime.utcnow() - x.timestamp).total_seconds())
        ), reverse=True)

        return unique_results[:limit]

    def get_session_context(self, session_id: str) -> List[MemoryItem]:
        """Get full context for a session"""
        return self.short_term.get_session_context(session_id)
