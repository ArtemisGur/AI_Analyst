import asyncio
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from pydantic import SecretStr

from app.core.config import Settings
from app.datasets.schemas import ColumnMetadata, DatasetResponse
from app.llm.openai_provider import OpenAIProvider, compatible_analysis_content


def test_relaymodels_uses_chat_completions_with_json_object(monkeypatch):
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
        "timeout": 45.0,
        "max_retries": 0,
    }
    request = captured["request"]
    assert request["model"] == "gpt-5.6-terra"
    assert request["response_format"]["type"] == "json_object"
    assert result.usage.input_tokens == 11
    assert result.usage.output_tokens == 7


def test_compatible_analysis_content_limits_unverified_lists():
    content = compatible_analysis_content(
        '{"summary":"Готово","key_findings":["1","2","3","4","5","6"],'
        '"limitations":["1","2","3","4"],"evidence":[]}'
    )

    assert content.key_findings == ["1", "2", "3", "4", "5"]
    assert content.limitations == ["1", "2", "3"]
    assert content.evidence == []


def test_agent_multiple_steps_and_budget(monkeypatch):
    import pytest

    from app.agent.tools import ExecutedTool
    from app.llm.provider import LLMProviderError

    requests = []
    repeat = False

    class Completions:
        async def create(self, **kwargs):
            requests.append(kwargs)
            number = len(requests)
            calls = (
                [
                    SimpleNamespace(
                        id=str(number),
                        function=SimpleNamespace(name="dataset_summary", arguments="{}"),
                    )
                ]
                if repeat or number < 3
                else []
            )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            tool_calls=calls,
                            content='{"summary":"Done","key_findings":["Fact"],"limitations":[]}',
                        )
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            )

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=Completions())

    monkeypatch.setattr("app.llm.openai_provider.AsyncOpenAI", Client)
    provider = OpenAIProvider(Settings(openai_api_key=SecretStr("test"), openai_base_url=None))
    dataset = DatasetResponse(
        id=uuid4(),
        name="test",
        original_filename="test.csv",
        row_count=1,
        column_count=1,
        created_at=datetime.now(),
        schema_metadata=[],
        preview=[],
    )
    executed = []

    def tool(name, args):
        executed.append(name)
        return ExecutedTool(name=name, result={"rows": 1}, trace_summary="Verified")

    result = asyncio.run(provider.analyze_dataset(dataset, "Inspect", tool))
    assert len(result.analysis_trace) == 2
    assert result.analysis_trace[0].turn == 1
    assert result.analysis_trace[0].arguments == {}
    assert result.analysis_trace[0].duration_ms >= 0
    assert result.analysis_trace[0].result_preview == '{"rows": 1}'
    assert result.usage.input_tokens == 40
    assert requests[0]["tool_choice"] == "required"
    assert "column_statistics" in {t["function"]["name"] for t in requests[0]["tools"]}
    assert "create_chart" in {t["function"]["name"] for t in requests[0]["tools"]}
    assert requests[1]["tool_choice"] == "auto"
    assert "response_format" not in requests[0]
    assert "response_format" not in requests[1]
    assert requests[1]["messages"][2].tool_calls[0].id == "1"
    assert requests[3]["response_format"]["type"] == "json_object"
    assert "tools" not in requests[3]
    requests.clear()
    executed.clear()
    repeat = True
    with pytest.raises(LLMProviderError, match="budget"):
        asyncio.run(provider.analyze_dataset(dataset, "Inspect", tool))
    assert len(requests) == 6
    assert len(executed) == 5
    assert requests[-1]["tool_choice"] == "none"
    assert requests[-1]["response_format"]["type"] == "json_object"


def test_agent_recovers_from_rejected_tool(monkeypatch):
    from app.agent.tools import ExecutedTool, ToolExecutionError

    requests = []

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        async def create(self, **kwargs):
            requests.append(kwargs)
            calls = (
                []
                if len(requests) == 3
                else [
                    SimpleNamespace(
                        id=str(len(requests)),
                        function=SimpleNamespace(name="execute_sql", arguments="{}"),
                    )
                ]
            )
            return SimpleNamespace(
                usage=None,
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            tool_calls=calls,
                            content='{"summary":"Done","key_findings":["Fact"],"limitations":[]}',
                        )
                    )
                ],
            )

    monkeypatch.setattr("app.llm.openai_provider.AsyncOpenAI", Client)
    provider = OpenAIProvider(Settings(openai_api_key=SecretStr("test")))
    dataset = DatasetResponse(
        id=uuid4(),
        name="test",
        original_filename="test.csv",
        row_count=1,
        column_count=1,
        created_at=datetime.now(),
        schema_metadata=[],
        preview=[],
    )
    attempts = 0

    def tool(name, args):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ToolExecutionError("private detail")
        return ExecutedTool(
            name=name,
            result={"rows": [[1]]},
            trace_summary="Calculated",
            sql_query="SELECT COUNT(*) FROM dataset",
        )

    result = asyncio.run(provider.analyze_dataset(dataset, "Count", tool))
    assert [step.status for step in result.analysis_trace] == ["failed", "completed"]
    assert result.analysis_trace[1].sql_query == "SELECT COUNT(*) FROM dataset"
    assert "private detail" not in str(requests)
    assert "Tool rejected" in str(requests)
