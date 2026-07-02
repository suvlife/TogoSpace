"""Token 用量统计服务。

基于 agent_activities 表中 LLM_INFER / COMPACT 活动的 metadata 字段，
提供按 agent / model / day 等维度的聚合统计。
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from constants import AgentActivityType
from model.dbModel.gtAgentActivity import GtAgentActivity

logger = logging.getLogger(__name__)


def _extract_tokens_from_metadata(metadata: dict | None) -> tuple[int, int, int]:
    """从 activity metadata 中提取 prompt/completion/total tokens。"""
    if metadata is None:
        return 0, 0, 0
    prompt = metadata.get("prompt_tokens") or 0
    completion = metadata.get("completion_tokens") or 0
    total = metadata.get("total_tokens") or (prompt + completion)
    return int(prompt), int(completion), int(total)


def _build_base_query(
    team_id: int | None = None,
    agent_ids: list[int] | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Any:
    """构建针对 LLM_INFER 活动的基础查询。"""
    query = GtAgentActivity.select().where(
        GtAgentActivity.activity_type == AgentActivityType.LLM_INFER,
        GtAgentActivity.status != "CANCELLED",
    )
    if team_id is not None:
        query = query.where(GtAgentActivity.team_id == team_id)
    if agent_ids:
        query = query.where(GtAgentActivity.agent_id.in_(agent_ids))
    if since is not None:
        query = query.where(GtAgentActivity.started_at >= since)
    if until is not None:
        query = query.where(GtAgentActivity.started_at <= until)
    return query


async def get_usage_summary_by_agent(
    team_id: int | None = None,
    agent_ids: list[int] | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict[str, Any]]:
    """按 Agent 聚合 token 用量。"""
    rows = await _build_base_query(team_id, agent_ids, since, until).aio_execute()

    agg: dict[int, dict[str, Any]] = defaultdict(lambda: {
        "agent_id": 0,
        "request_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    })
    for row in rows:
        prompt, completion, total = _extract_tokens_from_metadata(row.metadata)
        if total <= 0:
            continue
        entry = agg[row.agent_id]
        entry["agent_id"] = row.agent_id
        entry["request_count"] += 1
        entry["prompt_tokens"] += prompt
        entry["completion_tokens"] += completion
        entry["total_tokens"] += total

    return sorted(agg.values(), key=lambda x: x["total_tokens"], reverse=True)


async def get_usage_summary_by_day(
    since: datetime,
    until: datetime,
    team_id: int | None = None,
    agent_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    """按天聚合 token 用量，返回时间序列。"""
    rows = await _build_base_query(team_id, agent_ids, since, until).aio_execute()

    agg: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "date": "",
        "request_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    })

    for row in rows:
        prompt, completion, total = _extract_tokens_from_metadata(row.metadata)
        if total <= 0:
            continue
        day = row.started_at.strftime("%Y-%m-%d")
        entry = agg[day]
        entry["date"] = day
        entry["request_count"] += 1
        entry["prompt_tokens"] += prompt
        entry["completion_tokens"] += completion
        entry["total_tokens"] += total

    # 填充无数据的日期为 0
    result = []
    cursor = since.date()
    end = until.date()
    while cursor <= end:
        day_str = cursor.strftime("%Y-%m-%d")
        result.append(agg.get(day_str, {
            "date": day_str,
            "request_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }))
        cursor += timedelta(days=1)

    return result


async def get_usage_summary_by_model(
    team_id: int | None = None,
    agent_ids: list[int] | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict[str, Any]]:
    """按模型聚合 token 用量（metadata.model）。"""
    rows = await _build_base_query(team_id, agent_ids, since, until).aio_execute()

    agg: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "model": "unknown",
        "request_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    })

    for row in rows:
        prompt, completion, total = _extract_tokens_from_metadata(row.metadata)
        if total <= 0:
            continue
        model = (row.metadata or {}).get("model") or "unknown"
        if not isinstance(model, str):
            model = "unknown"

        entry = agg[model]
        entry["model"] = model
        entry["request_count"] += 1
        entry["prompt_tokens"] += prompt
        entry["completion_tokens"] += completion
        entry["total_tokens"] += total

    return sorted(agg.values(), key=lambda x: x["total_tokens"], reverse=True)


async def get_usage_total(
    team_id: int | None = None,
    agent_ids: list[int] | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict[str, Any]:
    """汇总 token 总量、请求次数、compact 触发次数、overflow retry 次数。"""
    rows = await _build_base_query(team_id, agent_ids, since, until).aio_execute()

    total_prompt = 0
    total_completion = 0
    total_tokens = 0
    request_count = 0

    compact_query = GtAgentActivity.select().where(
        GtAgentActivity.activity_type == AgentActivityType.COMPACT,
        GtAgentActivity.status != "CANCELLED",
    )
    if team_id is not None:
        compact_query = compact_query.where(GtAgentActivity.team_id == team_id)
    if agent_ids:
        compact_query = compact_query.where(GtAgentActivity.agent_id.in_(agent_ids))
    if since is not None:
        compact_query = compact_query.where(GtAgentActivity.started_at >= since)
    if until is not None:
        compact_query = compact_query.where(GtAgentActivity.started_at <= until)
    compact_count = await compact_query.count()

    overflow_count = 0
    for row in rows:
        prompt, completion, total = _extract_tokens_from_metadata(row.metadata)
        if total <= 0:
            continue
        request_count += 1
        total_prompt += prompt
        total_completion += completion
        total_tokens += total
        if (row.metadata or {}).get("overflow_retry"):
            overflow_count += 1

    return {
        "request_count": request_count,
        "prompt_tokens": total_prompt,
        "completion_tokens": total_completion,
        "total_tokens": total_tokens,
        "compact_count": compact_count,
        "overflow_retry_count": overflow_count,
    }


async def get_usage_summary(
    team_id: int | None = None,
    agent_ids: list[int] | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict[str, Any]:
    """返回完整的 token 用量统计面板数据。"""
    return {
        "total": await get_usage_total(team_id, agent_ids, since, until),
        "by_agent": await get_usage_summary_by_agent(team_id, agent_ids, since, until),
        "by_model": await get_usage_summary_by_model(team_id, agent_ids, since, until),
        "by_day": await get_usage_summary_by_day(
            since or (datetime.now() - timedelta(days=6)),
            until or datetime.now(),
            team_id,
            agent_ids,
        ),
    }
