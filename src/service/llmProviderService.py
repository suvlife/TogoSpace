"""LLM 厂商预设目录服务。

读取 assets/llm_providers/catalog.json，为前端提供下拉选择厂商后一键生成 LlmServiceConfig 的能力。
"""
from __future__ import annotations

import json
import os
from typing import Any

import appPaths

_CATALOG: dict[str, dict[str, Any]] | None = None


def _catalog_path() -> str:
    return os.path.join(appPaths.ASSETS_DIR, "llm_providers", "catalog.json")


def load_catalog() -> dict[str, dict[str, Any]]:
    """加载并缓存 LLM 厂商预设目录。"""
    global _CATALOG
    if _CATALOG is not None:
        return _CATALOG

    path = _catalog_path()
    if not os.path.isfile(path):
        _CATALOG = {}
        return _CATALOG

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        _CATALOG = {}
        return _CATALOG

    _CATALOG = {entry["id"]: entry for entry in data if isinstance(entry, dict) and "id" in entry}
    return _CATALOG


def reload_catalog() -> dict[str, dict[str, Any]]:
    """强制重新加载厂商目录。"""
    global _CATALOG
    _CATALOG = None
    return load_catalog()


def get_provider(provider_id: str) -> dict[str, Any] | None:
    """按 ID 获取单个厂商预设。"""
    return load_catalog().get(provider_id)


def build_llm_service_from_provider(
    provider_id: str,
    api_key: str,
    model: str | None = None,
    custom_name: str | None = None,
) -> dict[str, Any] | None:
    """根据厂商预设和 API Key 生成一个完整的 LlmServiceConfig 字典。

    Args:
        provider_id: 厂商目录中的 id，如 "kimi" / "deepseek"
        api_key: 用户填写的 API Key
        model: 可选，覆盖默认模型
        custom_name: 可选，覆盖生成的服务名称

    Returns:
        完整的 LlmServiceConfig 字典；厂商不存在时返回 None
    """
    provider = get_provider(provider_id)
    if provider is None:
        return None

    service_name = custom_name or provider_id
    service_model = model or provider.get("default_model", "")
    base_url = provider.get("base_url", "")
    svc_type = provider.get("type", "openai-compatible")

    return {
        "name": service_name,
        "type": svc_type,
        "base_url": base_url,
        "api_key": api_key,
        "model": service_model,
        "enable": True,
        "context_window_tokens": provider.get("context_window_tokens", 131072),
        "reserve_output_tokens": provider.get("reserve_output_tokens", 16384),
        "compact_trigger_ratio": provider.get("compact_trigger_ratio", 0.85),
        "extra_headers": {"User-Agent": "opencode"},
        "provider_params": {},
    }
