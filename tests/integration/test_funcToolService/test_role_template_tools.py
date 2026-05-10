"""integration tests for role template management tools"""
import os
import sys
from typing import Optional

import service.agentService as agentService
import service.ormService as ormService
import service.persistenceService as persistenceService
import service.roomService as roomService
from constants import RoleTemplateType, ToolCategory
from dal.db import gtAgentManager, gtRoleTemplateManager, gtTeamManager
from model.dbModel.gtAgent import GtAgent
from model.dbModel.gtRoleTemplate import GtRoleTemplate
from model.dbModel.gtTeam import GtTeam
from service.funcToolService.toolLoader import get_function_metadata, build_tools, python_type_to_json_schema
from service.funcToolService.tools import (
    FUNCTION_REGISTRY,
    TOOL_CATEGORIES,
    delete_role_template,
    get_role_template,
    list_role_templates,
    save_role_template,
)
from ...base import ServiceTestCase

TEAM = "test_team"

if os.name == "posix" and sys.platform == "darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")


class TestRoleTemplateToolMetadata(ServiceTestCase):
    async def test_optional_list_str_maps_to_array(self):
        """Optional[list[str]] 应映射为 array。"""
        assert python_type_to_json_schema(Optional[list[str]]) == {"type": "array"}

    async def test_save_role_template_uses_array_schema_for_allowed_tools(self):
        """save_role_template 的 allowed_tools 参数应暴露为 array。"""
        props = get_function_metadata("save_role_template", save_role_template)["parameters"]["properties"]
        assert props["allowed_tools"]["type"] == "array"

    async def test_role_template_tools_registered(self):
        """role template 管理工具应加入注册表。"""
        assert {
            "list_role_templates",
            "get_role_template",
            "save_role_template",
            "delete_role_template",
        } <= set(FUNCTION_REGISTRY)

    async def test_role_template_tools_build(self):
        """role template 工具应能构建为 OpenAITool 定义。"""
        tools = build_tools({
            "list_role_templates": list_role_templates,
            "get_role_template": get_role_template,
            "save_role_template": save_role_template,
            "delete_role_template": delete_role_template,
        })
        assert {tool.function.name for tool in tools} == {
            "list_role_templates",
            "get_role_template",
            "save_role_template",
            "delete_role_template",
        }

    async def test_role_template_tool_metadata_exposes_category(self):
        """工具元数据应带上 category。"""
        metadata = get_function_metadata("save_role_template", save_role_template)
        assert metadata["category"] == ToolCategory.ADMIN

    async def test_all_local_tools_define_category(self):
        """每个本地工具都应声明 category。"""
        assert set(TOOL_CATEGORIES) == set(FUNCTION_REGISTRY)


class TestRoleTemplateTools(ServiceTestCase):
    @classmethod
    async def async_setup_class(cls):
        db_path = cls._get_test_db_path()
        await ormService.startup(db_path)
        await persistenceService.startup()
        await agentService.startup()
        await roomService.startup()
        team = await gtTeamManager.save_team(GtTeam(name=TEAM))
        await gtAgentManager.batch_save_agents(
            team.id,
            [
                GtAgent(team_id=team.id, name="alice", role_template_id=0),
                GtAgent(team_id=team.id, name="bob", role_template_id=0),
            ],
        )
        cls.team_id = team.id

    @classmethod
    async def async_teardown_class(cls):
        roomService.shutdown()
        await persistenceService.shutdown()
        await ormService.shutdown()

    async def test_list_role_templates_and_detail(self):
        """角色模板工具应支持列表和详情查询，列表不返回 soul。"""
        await gtRoleTemplateManager.save_role_template(
            GtRoleTemplate(
                name="planner",
                model="gpt-4o",
                soul="plan carefully",
                type=RoleTemplateType.USER,
                allowed_tools=["get_time"],
                i18n={"display_name": {"zh-CN": "规划师", "en": "Planner"}},
            )
        )

        list_result = await list_role_templates()
        detail_result = await get_role_template("planner")

        assert list_result["success"]
        planner = next(item for item in list_result["role_templates"] if item["name"] == "planner")
        assert planner["display_name"] == "规划师"
        assert "soul" not in planner
        assert detail_result["success"]
        assert detail_result["role_template"]["soul"] == "plan carefully"
        assert detail_result["role_template"]["type"] == "USER"

    async def test_save_role_template_creates_and_updates(self):
        """save_role_template 应按名称执行全字段 upsert。"""
        create_result = await save_role_template(
            name="writer",
            type="USER",
            soul="draft docs",
            allowed_tools=["get_time"],
            model="gpt-4o-mini",
            i18n={"display_name": {"zh-CN": "写手", "en": "Writer"}},
        )
        update_result = await save_role_template(
            name="writer",
            type="SYSTEM",
            soul="draft docs carefully",
            allowed_tools=["get_time", "get_room_info"],
            model="gpt-4.1",
            i18n={"display_name": {"zh-CN": "高级写手", "en": "Senior Writer"}},
        )

        assert create_result["success"]
        assert "已创建角色模板 writer" in create_result["message"]
        assert update_result["success"]
        assert "已更新角色模板 writer" in update_result["message"]
        detail = await gtRoleTemplateManager.get_role_template_by_name("writer")
        assert detail is not None
        assert detail.type == RoleTemplateType.SYSTEM
        assert detail.soul == "draft docs carefully"
        assert detail.allowed_tools == ["get_time", "get_room_info"]
        assert detail.model == "gpt-4.1"
        assert detail.i18n["display_name"]["zh-CN"] == "高级写手"

    async def test_save_role_template_rejects_invalid_type(self):
        """非法 type 应被工具层拒绝。"""
        result = await save_role_template(
            name="invalid_type_template",
            type="ADMIN",
            soul="noop",
            allowed_tools=[],
        )

        assert not result["success"]
        assert "SYSTEM 或 USER" in result["message"]

    async def test_save_role_template_rejects_system_create_and_update(self):
        """工具不允许创建或修改 SYSTEM 角色模板。"""
        create_result = await save_role_template(
            name="system_created_by_tool",
            type="SYSTEM",
            soul="noop",
            allowed_tools=[],
        )
        await gtRoleTemplateManager.save_role_template(
            GtRoleTemplate(
                name="built_in_system_template",
                soul="built in",
                type=RoleTemplateType.SYSTEM,
            )
        )
        update_result = await save_role_template(
            name="built_in_system_template",
            type="SYSTEM",
            soul="updated",
            allowed_tools=[],
        )

        assert not create_result["success"]
        assert "不允许通过工具创建" in create_result["message"]
        assert not update_result["success"]
        assert "不允许通过工具修改" in update_result["message"]

    async def test_delete_role_template_supports_missing_unused_and_in_use(self):
        """删除角色模板时应分别处理不存在、未引用、被引用三种情况。"""
        missing_result = await delete_role_template("missing_template")

        await gtRoleTemplateManager.save_role_template(
            GtRoleTemplate(
                name="deletable_template",
                soul="temporary",
                type=RoleTemplateType.USER,
            )
        )
        delete_result = await delete_role_template("deletable_template")

        in_use = await gtRoleTemplateManager.save_role_template(
            GtRoleTemplate(
                name="in_use_template",
                soul="bound to alice",
                type=RoleTemplateType.USER,
            )
        )
        alice = await gtAgentManager.get_agent(self.team_id, "alice")
        assert alice is not None
        alice.role_template_id = in_use.id
        await alice.aio_save()
        in_use_result = await delete_role_template("in_use_template")

        assert not missing_result["success"]
        assert "未找到角色模板" in missing_result["message"]
        assert delete_result["success"]
        assert await gtRoleTemplateManager.get_role_template_by_name("deletable_template") is None
        assert not in_use_result["success"]
        assert in_use_result["agents"] == [{"name": "alice", "team_id": self.team_id}]
        assert "alice" in in_use_result["message"]

    async def test_delete_role_template_rejects_system_template(self):
        """工具不允许删除 SYSTEM 角色模板。"""
        await gtRoleTemplateManager.save_role_template(
            GtRoleTemplate(
                name="system_delete_forbidden",
                soul="built in",
                type=RoleTemplateType.SYSTEM,
            )
        )

        result = await delete_role_template("system_delete_forbidden")

        assert not result["success"]
        assert "不允许通过工具删除" in result["message"]
