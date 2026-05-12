from unittest.mock import AsyncMock

import pytest

from constants import ToolCategory
from service.agentService.toolRegistry import AgentToolRegistry, build_runtime_allow_specs
from service.roomService import ToolCallContext
from util import llmApiUtil


def _make_tool(name: str) -> llmApiUtil.OpenAITool:
    return llmApiUtil.OpenAITool(
        function=llmApiUtil.OpenAIFunction(
            name=name,
            description="",
            parameters=llmApiUtil.OpenAIFunctionParameter(type="object", properties={}, required=[]),
        ),
    )


def _register_tools(registry: AgentToolRegistry, *names: str) -> AsyncMock:
    handler = AsyncMock(return_value={"success": True})
    for name in names:
        registry.register(_make_tool(name), handler, marks_turn_finish=name == "finish_chat_turn")
    return handler


def test_build_runtime_allow_specs_filters_by_category_and_root_leader() -> None:
    registry = AgentToolRegistry()
    _register_tools(
        registry,
        "get_time",
        "send_chat_msg",
        "finish_chat_turn",
        "save_role_template",
        "execute_bash",
    )

    normal_specs = build_runtime_allow_specs(
        ["Category:Read"],
        is_root_leader=False,
    )
    registry.apply_tool_allow_specs(normal_specs)
    assert registry.list_enabled_tool_names() == ["get_time", "send_chat_msg", "finish_chat_turn"]

    root_specs = build_runtime_allow_specs(
        ["Category:Read"],
        is_root_leader=True,
    )
    registry.apply_tool_allow_specs(root_specs)
    assert registry.list_enabled_tool_names() == ["get_time", "send_chat_msg", "finish_chat_turn", "save_role_template"]


def test_registered_tool_keeps_category() -> None:
    registry = AgentToolRegistry()
    _register_tools(registry, "send_chat_msg")

    registered = registry.get_registered_tool("send_chat_msg")
    assert registered is not None
    assert registered.category == ToolCategory.BASIC


def test_build_runtime_allow_specs_with_none_defaults_to_all_except_admin() -> None:
    registry = AgentToolRegistry()
    _register_tools(
        registry,
        "get_time",
        "send_chat_msg",
        "finish_chat_turn",
        "execute_bash",
        "save_role_template",
    )

    all_specs = build_runtime_allow_specs(
        None,
        is_root_leader=False,
    )
    registry.apply_tool_allow_specs(all_specs)
    # 默认应包含 Read, Write, Execute, Basic，但不包含 Admin (save_role_template)
    enabled = registry.list_enabled_tool_names()
    assert "get_time" in enabled
    assert "send_chat_msg" in enabled
    assert "finish_chat_turn" in enabled
    assert "execute_bash" in enabled
    assert "save_role_template" not in enabled


@pytest.mark.asyncio
async def test_execute_tool_call_rejects_disabled_tool() -> None:
    registry = AgentToolRegistry()
    handler = _register_tools(registry, "get_time", "send_chat_msg")
    registry.apply_tool_allow_specs(["send_chat_msg"])

    result = await registry.execute_tool_call(
        llmApiUtil.OpenAIToolCall(id="tc_1", function={"name": "get_time", "arguments": "{}"}),
        context=ToolCallContext(agent_id=1, team_id=1, chat_room=object()),
    )

    assert result.success is False
    assert "工具无权限使用" in str(result.result.get("message", ""))
    handler.assert_not_called()
