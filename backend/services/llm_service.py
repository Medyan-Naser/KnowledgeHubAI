"""LLM service for generating responses using Ollama."""

import httpx
import structlog
import ollama
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import get_settings

settings = get_settings()
logger = structlog.get_logger(__name__)

RAG_SYSTEM_PROMPT = """You are an Enterprise Knowledge Assistant. Your role is to answer questions based on the provided context from documentation.

IMPORTANT INSTRUCTIONS:
1. CAREFULLY READ the entire context below before answering
2. Answer questions using ONLY the information found in the context
3. If you find relevant information in the context, provide a detailed answer
4. If the context doesn't contain the answer, say "The provided context does not contain information about [topic]"
5. Be thorough and extract all relevant details from the context
6. Quote or paraphrase specific parts of the context in your answer
7. Do NOT say the context doesn't mention something if it actually does - read carefully!

Context from documentation:
{context}

Now answer the user's question based on the above context."""


class LLMService:
    """Service for LLM inference using Ollama."""

    def __init__(self):
        self.model = settings.llm_model
        self.client = ollama.Client(
            host=settings.ollama_host,
            timeout=httpx.Timeout(timeout=300.0),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def generate_response(
        self,
        query: str,
        context_chunks: list[str],
        return_prompts: bool = False,
    ) -> tuple[str, int | None, str, str]:
        """
        Generate a response to a query using RAG context.

        Args:
            query: User's question
            context_chunks: Retrieved context chunks
            return_prompts: If True, return system prompt and full prompt

        Returns:
            Tuple of (response text, token count, system_prompt, full_prompt)
        """
        import time
        
        start_time = time.time()
        context = "\n\n---\n\n".join(context_chunks)
        context_length = len(context)
        system_prompt = RAG_SYSTEM_PROMPT.format(context=context)

        logger.debug(
            "llm_request_starting",
            model=self.model,
            query_length=len(query),
            context_chunks=len(context_chunks),
            context_total_length=context_length,
        )

        response = self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
        )

        if hasattr(response, 'message'):
            response_text = response.message.content
            token_count = getattr(response, 'eval_count', None)
        else:
            response_text = response["message"]["content"]
            token_count = response.get("eval_count")
        elapsed_ms = (time.time() - start_time) * 1000

        logger.info(
            "llm_response_generated",
            model=self.model,
            query_length=len(query),
            context_chunks=len(context_chunks),
            response_length=len(response_text),
            token_count=token_count,
            elapsed_ms=round(elapsed_ms, 2),
        )

        # Build full prompt for debugging
        full_prompt = f"SYSTEM:\n{system_prompt}\n\nUSER:\n{query}" if return_prompts else ""

        return response_text, token_count, system_prompt, full_prompt

    def check_model_available(self) -> bool:
        """Check if the LLM model is available."""
        try:
            models = self.client.list()
            model_names = [m["name"].split(":")[0] for m in models.get("models", [])]
            return self.model in model_names
        except Exception as e:
            logger.error("model_check_failed", error=str(e))
            return False
