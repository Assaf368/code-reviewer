"""Tests for counting tool calls and tokens over the agent's messages."""

from langchain_core.messages import AIMessage, ToolMessage

from code_reviewer.pipeline import usage


def test_usage_counts_tool_calls_by_name_and_sums_tokens():
    messages = [
        AIMessage(
            content="",
            tool_calls=[{"name": "read_file", "args": {}, "id": "1"}],
            usage_metadata={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
        ),
        ToolMessage(content="code", tool_call_id="1"),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "run_python", "args": {}, "id": "2"},
                {"name": "run_python", "args": {}, "id": "3"},
            ],
            usage_metadata={"input_tokens": 200, "output_tokens": 20, "total_tokens": 220},
        ),
    ]

    tool_calls, tokens = usage(messages)

    assert tool_calls == {"read_file": 1, "run_python": 2}
    assert tokens == {"input": 300, "output": 30}
