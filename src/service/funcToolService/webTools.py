"""Web 搜索与网页抓取工具。

通过 Tavily API 提供联网搜索能力，并支持抓取任意网页的文本内容。
API key 从环境变量 TAVILY_API_KEY 或 setting.json 的 provider_params 中读取。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import aiohttp

from service.roomService import ToolCallContext

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30)
_TAVILY_SEARCH_URL = "https://api.tavily.com/search"
_TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"


def _get_tavily_api_key() -> str | None:
    """按优先级读取 Tavily API Key：环境变量 > setting.json 配置。"""
    env_key = os.environ.get("TAVILY_API_KEY")
    if env_key:
        return env_key

    try:
        from util import configUtil

        setting = configUtil.get_app_config().setting
        # 允许用户在 setting.json 中任意一个 llm_service 的 provider_params 里配置 tavily_api_key
        for svc in setting.llm_services:
            key = (svc.provider_params or {}).get("tavily_api_key")
            if key:
                return str(key)
    except Exception:
        pass

    return None


async def web_search(
    query: str,
    count: int = 5,
    search_depth: str = "basic",
    include_answer: bool = True,
    _context: Optional[ToolCallContext] = None,
) -> dict:
    """使用 Tavily 搜索网络信息。

    Args:
        query: 搜索关键词
        count: 返回结果数量，默认 5，最大 20
        search_depth: 搜索深度，basic 或 advanced
        include_answer: 是否返回 Tavily 生成的综合答案
    """
    api_key = _get_tavily_api_key()
    if not api_key:
        return {
            "success": False,
            "message": "未配置 Tavily API Key。请在环境变量 TAVILY_API_KEY 或 setting.json 的 llm_services[].provider_params.tavily_api_key 中配置。",
        }

    count = max(1, min(int(count), 20))
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": count,
        "search_depth": search_depth,
        "include_answer": bool(include_answer),
        "include_images": False,
        "include_raw_content": False,
    }

    try:
        async with aiohttp.ClientSession(timeout=_DEFAULT_TIMEOUT) as session:
            async with session.post(_TAVILY_SEARCH_URL, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return {
                        "success": False,
                        "message": f"Tavily 搜索失败 (HTTP {resp.status}): {text[:200]}",
                    }
                data = await resp.json()
    except Exception as e:
        logger.warning("Tavily 搜索异常: %s", e)
        return {"success": False, "message": f"Tavily 搜索请求异常: {e}"}

    answer = data.get("answer", "")
    results = data.get("results", [])
    simplified = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0),
        }
        for r in results
    ]

    return {
        "success": True,
        "message": f"搜索到 {len(simplified)} 条结果",
        "query": query,
        "answer": answer,
        "results": simplified,
    }


async def web_fetch(
    url: str,
    extract_depth: str = "basic",
    _context: Optional[ToolCallContext] = None,
) -> dict:
    """使用 Tavily Extract 抓取指定网页的文本内容。

    Args:
        url: 要抓取的网页 URL
        extract_depth: 提取深度，basic 或 advanced
    """
    api_key = _get_tavily_api_key()
    if not api_key:
        return {
            "success": False,
            "message": "未配置 Tavily API Key。请在环境变量 TAVILY_API_KEY 或 setting.json 的 llm_services[].provider_params.tavily_api_key 中配置。",
        }

    if not url or not url.startswith(("http://", "https://")):
        return {"success": False, "message": "URL 格式不正确，必须以 http:// 或 https:// 开头"}

    payload = {
        "api_key": api_key,
        "urls": [url],
        "extract_depth": extract_depth,
    }

    try:
        async with aiohttp.ClientSession(timeout=_DEFAULT_TIMEOUT) as session:
            async with session.post(_TAVILY_EXTRACT_URL, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    return {
                        "success": False,
                        "message": f"Tavily 抓取失败 (HTTP {resp.status}): {text[:200]}",
                    }
                data = await resp.json()
    except Exception as e:
        logger.warning("Tavily 抓取异常: %s", e)
        return {"success": False, "message": f"Tavily 抓取请求异常: {e}"}

    extraction = (data.get("results") or [{}])[0]
    raw_content = extraction.get("raw_content", "")
    if not raw_content:
        raw_content = extraction.get("content", "")

    # 截断过长的原始内容，避免消耗过多 token
    MAX_CONTENT_LENGTH = 8000
    truncated = len(raw_content) > MAX_CONTENT_LENGTH
    display_content = raw_content[:MAX_CONTENT_LENGTH] + ("\n\n[内容已截断，完整内容请访问原网页]" if truncated else "")

    return {
        "success": True,
        "message": "网页抓取成功",
        "url": url,
        "title": extraction.get("title", ""),
        "content": display_content,
        "truncated": truncated,
    }
