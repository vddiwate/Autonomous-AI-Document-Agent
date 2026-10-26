import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional
from groq import (
    AsyncGroq,
    BadRequestError,
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    InternalServerError
)
from app.config import settings

logger = logging.getLogger("service.llm")

class LLMService:
    """
    Central LLM Service powered by Groq.
    Loads configurations strictly from environment settings.
    Handles fallback models, rate limit backoffs, 503 retries, and JSON extraction.
    """
    def __init__(self):
        try:
            self.client = AsyncGroq(
                api_key=settings.GROQ_API_KEY,
                timeout=float(settings.LLM_REQUEST_TIMEOUT)
            )
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
            raise RuntimeError(f"LLM initialization failed: {e}")

        self.primary_model = settings.MODEL_NAME
        self.fallback_model = settings.FALLBACK_MODEL_NAME
        self.temperature = settings.LLM_TEMPERATURE
        self.default_max_tokens = settings.LLM_MAX_TOKENS
        self.max_retries = settings.LLM_MAX_RETRIES

    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        preferred_model: Optional[str] = None
    ) -> str:
        """
        Executes completion with backoff retries and fallback across configured models.
        """
        temp = temperature if temperature is not None else self.temperature
        tokens_limit = max_tokens or self.default_max_tokens
        
        # Sequence of models from environment
        models_to_try: List[str] = []
        if preferred_model and preferred_model not in models_to_try:
            models_to_try.append(preferred_model)
        if self.primary_model and self.primary_model not in models_to_try:
            models_to_try.append(self.primary_model)
        if self.fallback_model and self.fallback_model not in models_to_try:
            models_to_try.append(self.fallback_model)

        errors_encountered: List[str] = []

        for model in models_to_try:
            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.info(f"Calling model '{model}' (Attempt {attempt}/{self.max_retries}, max_tokens={tokens_limit})")
                    kwargs: Dict[str, Any] = {
                        "model": model,
                        "messages": messages,
                        "temperature": temp,
                        "max_tokens": tokens_limit
                    }
                    if json_mode:
                        kwargs["response_format"] = {"type": "json_object"}

                    response = await self.client.chat.completions.create(**kwargs)
                    content = response.choices[0].message.content
                    if not content:
                        raise ValueError(f"Model '{model}' returned empty response.")
                    return content

                except RateLimitError as rle:
                    logger.warning(f"Rate limit on model '{model}' (Attempt {attempt}): {rle}")
                    errors_encountered.append(f"RateLimit ({model}): {rle}")
                    await asyncio.sleep(2.0 * attempt)
                    continue
                except InternalServerError as ise:
                    # Handle 503 Over Capacity with exponential backoff
                    logger.warning(f"503 Over capacity on model '{model}' (Attempt {attempt}): {ise}")
                    errors_encountered.append(f"OverCapacity ({model}): {ise}")
                    await asyncio.sleep(3.0 * attempt)
                    continue
                except (APIConnectionError, APITimeoutError) as net_err:
                    logger.warning(f"Network error on model '{model}' (Attempt {attempt}): {net_err}")
                    errors_encountered.append(f"NetworkError ({model}): {net_err}")
                    if attempt == self.max_retries:
                        break
                    await asyncio.sleep(1.5 * attempt)
                    continue
                except BadRequestError as bad_req:
                    logger.warning(f"Bad request for model '{model}': {bad_req}")
                    errors_encountered.append(f"BadRequest ({model}): {bad_req}")
                    break  # Switch to next model immediately (e.g. 404 model not found)
                except Exception as unk_err:
                    logger.error(f"Error calling model '{model}': {unk_err}")
                    errors_encountered.append(f"Error ({model}): {unk_err}")
                    break

        error_details = " | ".join(errors_encountered)
        raise RuntimeError(f"All configured models failed. Details: {error_details}")

    async def complete_json(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        preferred_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Requests JSON output and extracts dictionary safely with try-except.
        """
        try:
            raw_text = await self.complete(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
                preferred_model=preferred_model
            )
            return self._extract_json(raw_text)
        except Exception as e:
            logger.error(f"complete_json failed: {e}")
            raise

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Safely extracts JSON object from LLM response.
        """
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError as e:
                    raise ValueError(f"Failed to parse matched JSON: {e}")
            raise ValueError(f"LLM did not return valid JSON: {text[:200]}")

llm_service = LLMService()
