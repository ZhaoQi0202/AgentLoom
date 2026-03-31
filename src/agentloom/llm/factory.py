import os
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel, SimpleChatModel
from langchain_core.messages import BaseMessage
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_openai import ChatOpenAI


class _FixedFakeChatModel(SimpleChatModel):
    @property
    def _llm_type(self) -> str:
        return "agentloom-fake-chat"

    def _call(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> str:
        return "fake"


def _fake_chat_model() -> BaseChatModel:
    return _FixedFakeChatModel()


def get_chat_model(provider: str, **kwargs: Any) -> BaseChatModel:
    key = provider.lower().strip()
    if key == "openai":
        if os.environ.get("OPENAI_API_KEY"):
            return ChatOpenAI(**kwargs)
        return _fake_chat_model()
    if key == "anthropic":
        if os.environ.get("ANTHROPIC_API_KEY"):
            return ChatAnthropic(**kwargs)
        return _fake_chat_model()
    return _fake_chat_model()
