from __future__ import annotations

import json
import logging

from util import llmApiUtil

logger = logging.getLogger(__name__)


class LlmRequestRule:
    def check_match(self, request: llmApiUtil.OpenAIRequest) -> bool:
        raise NotImplementedError

    def apply(self, request: llmApiUtil.OpenAIRequest) -> llmApiUtil.OpenAIRequest:
        raise NotImplementedError


class StripRequiredToolChoiceForReasoningRule(LlmRequestRule):
    """开启思考模式时，不能强制使用工具，否则 deepseek-v4-pro 等模型会报错。"""

    def check_match(self, request: llmApiUtil.OpenAIRequest) -> bool:
        reasoning_effort = (request.provider_params or {}).get("reasoning_effort")
        return (
            request.tool_choice == "required"
            and reasoning_effort not in (None, "")
        )

    def apply(self, request: llmApiUtil.OpenAIRequest) -> llmApiUtil.OpenAIRequest:
        return request.model_copy(update={"tool_choice": None})


def _is_thinking_enabled(request: llmApiUtil.OpenAIRequest) -> bool:
    """判断当前请求是否开启了思考模式（thinking.type == "enabled"）。"""
    thinking = (request.provider_params or {}).get("thinking") or {}
    return isinstance(thinking, dict) and thinking.get("type") == "enabled"


class FillMissingReasoningContentRule(LlmRequestRule):
    """开启思考模式时，历史中由非思考模型生成的 assistant tool_call 消息缺少
    reasoning_content 字段，DeepSeek 等模型会报 400 错误。
    对这类消息补填空字符串，使其满足 API 要求。
    """

    def check_match(self, request: llmApiUtil.OpenAIRequest) -> bool:
        if not _is_thinking_enabled(request):
            return False
        return any(
            msg.role == llmApiUtil.OpenaiApiRole.ASSISTANT
            and msg.tool_calls is not None and len(msg.tool_calls) > 0
            and msg.reasoning_content is None
            for msg in request.messages
        )

    def apply(self, request: llmApiUtil.OpenAIRequest) -> llmApiUtil.OpenAIRequest:
        new_messages = []
        for msg in request.messages:
            if (
                msg.role == llmApiUtil.OpenaiApiRole.ASSISTANT
                and msg.tool_calls is not None and len(msg.tool_calls) > 0
                and msg.reasoning_content is None
            ):
                msg = msg.model_copy(update={"reasoning_content": ""})
            new_messages.append(msg)
        return request.model_copy(update={"messages": new_messages})


class SanitizeToolCallArgumentsRule(LlmRequestRule):
    """修复历史消息中 tool_call 的无效 JSON arguments。

    LLM 返回的 tool_calls 中 arguments 可能包含无效 JSON，
    在发送给下一轮 LLM 前需要修复，否则会导致解析错误。
    """

    def check_match(self, request: llmApiUtil.OpenAIRequest) -> bool:
        return any(
            msg.tool_calls is not None
            and any(
                not self._is_valid_json(tc.function.get("arguments", "{}"))
                for tc in msg.tool_calls
            )
            for msg in request.messages
        )

    def apply(self, request: llmApiUtil.OpenAIRequest) -> llmApiUtil.OpenAIRequest:
        new_messages = []
        for msg in request.messages:
            if msg.tool_calls is None:
                new_messages.append(msg)
                continue
            new_tool_calls = []
            for tc in msg.tool_calls:
                args = tc.function.get("arguments", "{}")
                if not self._is_valid_json(args):
                    logger.warning(
                        "sanitizing invalid tool_call arguments: tool_call_id=%s, function=%s",
                        tc.id, tc.function.get("name"),
                    )
                    new_func = dict(tc.function)
                    new_func["arguments"] = "{}"
                    tc = tc.model_copy(update={"function": new_func})
                new_tool_calls.append(tc)
            new_messages.append(msg.model_copy(update={"tool_calls": new_tool_calls}))
        return request.model_copy(update={"messages": new_messages})

    @staticmethod
    def _is_valid_json(value: str) -> bool:
        if not value:
            return True
        try:
            json.loads(value)
            return True
        except (json.JSONDecodeError, ValueError):
            return False


_RULES: tuple[LlmRequestRule, ...] = (
    StripRequiredToolChoiceForReasoningRule(),
    FillMissingReasoningContentRule(),
    SanitizeToolCallArgumentsRule(),
)


def apply_llm_request_rules(
    request: llmApiUtil.OpenAIRequest,
) -> tuple[llmApiUtil.OpenAIRequest, tuple[str, ...]]:
    current_request = request
    applied_rules: list[str] = []

    for rule in _RULES:
        if not rule.check_match(current_request):
            continue
        logger.info(
            "llm request rule matched: rule=%s, model=%s, tool_choice=%s, provider_params=%s",
            rule.__class__.__name__,
            current_request.model,
            current_request.tool_choice,
            current_request.provider_params,
        )
        current_request = rule.apply(current_request)
        applied_rules.append(rule.__class__.__name__)

    return current_request, tuple(applied_rules)
