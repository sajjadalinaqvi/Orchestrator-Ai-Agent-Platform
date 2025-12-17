import asyncio
import logging
from typing import List, Dict, Any, Optional
from config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.groq_client = None
        self.openai_client = None
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize LLM clients based on available API keys"""
        try:
            if settings.groq_api_key:
                import groq
                self.groq_client = groq.Groq(api_key=settings.groq_api_key)
                logger.info("Groq client initialized")
        except ImportError:
            logger.warning("Groq library not available")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")

        try:
            if settings.openai_api_key:
                import openai
                self.openai_client = openai.OpenAI(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_api_base
                )
                logger.info("OpenAI client initialized")
        except ImportError:
            logger.warning("OpenAI library not available")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")

    async def generate_response(
            self,
            messages: List[Dict[str, str]],
            model: Optional[str] = None,
            max_tokens: Optional[int] = None,
            temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """Generate response using available LLM client with fallback"""

        model = model or settings.default_model
        max_tokens = max_tokens or settings.max_tokens
        temperature = temperature or settings.temperature

        # Try Groq first (cheaper and faster)
        if self.groq_client and model.startswith(("llama", "mixtral")):
            try:
                response = await self._call_groq(messages, model, max_tokens, temperature)
                return {
                    "content": response,
                    "provider": "groq",
                    "model": model,
                    "tokens_used": len(response.split()) * 1.3  # Rough estimate
                }
            except Exception as e:
                logger.warning(f"Groq API failed: {e}, falling back to OpenAI")

        # Fallback to OpenAI
        if self.openai_client:
            try:
                response = await self._call_openai(messages, settings.fallback_model, max_tokens, temperature)
                return {
                    "content": response,
                    "provider": "openai",
                    "model": settings.fallback_model,
                    "tokens_used": len(response.split()) * 1.3  # Rough estimate
                }
            except Exception as e:
                logger.error(f"OpenAI API failed: {e}")
                raise Exception("All LLM providers failed")

        # If no clients available, return mock response
        return {
            "content": "I'm a mock AI response. Please configure LLM API keys.",
            "provider": "mock",
            "model": "mock",
            "tokens_used": 10
        }

    async def _call_groq(self, messages: List[Dict[str, str]], model: str, max_tokens: int, temperature: float) -> str:
        """Call Groq API"""
        try:
            response = self.groq_client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise

    async def _call_openai(self, messages: List[Dict[str, str]], model: str, max_tokens: int,
                           temperature: float) -> str:
        """Call OpenAI API"""
        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise


# Global LLM client instance
llm_client = LLMClient()