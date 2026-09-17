import asyncio
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from pydantic import SecretStr

from app.core.config import Settings
from app.datasets.schemas import ColumnMetadata, DatasetResponse
from app.llm.openai_provider import OpenAIProvider


def test_relaymodels_uses_chat_completions_with_json_schema(monkeypatch):
    captured: dict[str, object] = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=(
                                '{"summary":"Выручка доступна в preview.",'
                                '"key_findings":["Есть две строки."],"limitations":[]}'
                            )
                        )
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
            )

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured["client_options"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("app.llm.openai_provider.AsyncOpenAI", FakeAsyncOpenAI)
    provider = OpenAIProvider(
        Settings(
            openai_api_key=SecretStr("test-key"),
            openai_base_url="https://api.relaymodels.com/v1",
            openai_model="gpt-5.6-terra",
        )
    )
    dataset = DatasetResponse(
        id=uuid4(),
        name="sales",
        original_filename="sales.csv",
        row_count=2,
        column_count=1,
        created_at=datetime.now(),
        schema_metadata=[ColumnMetadata(name="revenue", dtype="Int64", missing_count=0)],
        preview=[{"revenue": 10}, {"revenue": 12}],
    )

    result = asyncio.run(provider.analyze_dataset(dataset, "Что с выручкой?"))

    assert provider.provider_name == "relaymodels"
    assert captured["client_options"] == {
        "api_key": "test-key",
        "base_url": "https://api.relaymodels.com/v1",
    }
    request = captured["request"]
    assert request["model"] == "gpt-5.6-terra"
    assert request["response_format"]["type"] == "json_schema"
    assert result.usage.input_tokens == 11
    assert result.usage.output_tokens == 7
