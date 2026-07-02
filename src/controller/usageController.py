from datetime import datetime, timedelta
from typing import Any

from controller.baseController import BaseHandler
from service import usageService


class UsageSummaryHandler(BaseHandler):
    """GET /usage/summary.json — Token 用量统计面板数据"""

    async def get(self) -> None:
        team_id = self.get_argument("team_id", None)
        agent_ids = self.get_argument("agent_ids", None)
        days = self.get_argument("days", "7")

        team_id_int = int(team_id) if team_id is not None else None
        agent_ids_list = [int(x) for x in agent_ids.split(",") if x] if agent_ids else None

        try:
            days_int = max(1, min(int(days), 90))
        except ValueError:
            days_int = 7

        until = datetime.now()
        since = until - timedelta(days=days_int - 1)

        summary = await usageService.get_usage_summary(
            team_id=team_id_int,
            agent_ids=agent_ids_list,
            since=since,
            until=until,
        )
        self.return_json(summary)


class UsageTotalHandler(BaseHandler):
    """GET /usage/total.json — Token 用量汇总"""

    async def get(self) -> None:
        team_id = self.get_argument("team_id", None)
        days = self.get_argument("days", "7")

        team_id_int = int(team_id) if team_id is not None else None

        try:
            days_int = max(1, min(int(days), 90))
        except ValueError:
            days_int = 7

        until = datetime.now()
        since = until - timedelta(days=days_int - 1)

        total = await usageService.get_usage_total(
            team_id=team_id_int,
            since=since,
            until=until,
        )
        self.return_json(total)
