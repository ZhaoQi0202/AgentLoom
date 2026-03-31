from unittest.mock import MagicMock, patch

from langchain_core.language_models.chat_models import BaseChatModel

from agentloom.llm.factory import get_chat_model


def test_openai_no_key_returns_fake(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    m = get_chat_model("openai")
    assert m._llm_type == "agentloom-fake-chat"
    assert m.invoke("hi").content == "fake"


def test_anthropic_no_key_returns_fake(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    m = get_chat_model("anthropic")
    assert m._llm_type == "agentloom-fake-chat"
    assert m.invoke("hi").content == "fake"


def test_unknown_provider_returns_fake(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    m = get_chat_model("other")
    assert m._llm_type == "agentloom-fake-chat"
    assert m.invoke("x").content == "fake"


def test_openai_with_key_uses_chat_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    fake_real = MagicMock(spec=BaseChatModel)
    with patch("agentloom.llm.factory.ChatOpenAI", return_value=fake_real) as mock_cls:
        out = get_chat_model("openai", model="gpt-4o-mini")
    mock_cls.assert_called_once_with(model="gpt-4o-mini")
    assert out is fake_real


def test_anthropic_with_key_uses_chat_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    fake_real = MagicMock(spec=BaseChatModel)
    with patch("agentloom.llm.factory.ChatAnthropic", return_value=fake_real) as mock_cls:
        out = get_chat_model("anthropic", model="claude-3-5-sonnet-20241022")
    mock_cls.assert_called_once_with(model="claude-3-5-sonnet-20241022")
    assert out is fake_real
