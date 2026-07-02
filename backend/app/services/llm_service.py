from typing import Optional
from fastapi import Depends
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings


class LLMService:
    def __init__(self):
        self._model: Optional[BaseChatModel] = None

    def _get_model(self) -> BaseChatModel:
        if self._model is not None:
            return self._model
        provider = settings.LLM_PROVIDER
        if provider == "openai":
            from langchain_openai import ChatOpenAI
            self._model = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                temperature=settings.TEMPERATURE,
                max_tokens=settings.MAX_TOKENS,
            )
        else:
            from langchain_ollama import ChatOllama
            self._model = ChatOllama(
                model=settings.OLLAMA_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=settings.TEMPERATURE,
                num_predict=settings.MAX_TOKENS,
            )
        return self._model

    def get_model(self) -> BaseChatModel:
        return self._get_model()

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        model = self._get_model()
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        chain = model | StrOutputParser()
        return await chain.ainvoke(messages)

    async def generate_with_context(self, system_prompt: str, context: str, user_query: str) -> str:
        model = self._get_model()
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Context:\n{context}\n\nQuery: {user_query}"),
        ]
        chain = model | StrOutputParser()
        return await chain.ainvoke(messages)


llm_service = LLMService()


async def get_llm_service() -> LLMService:
    return llm_service
