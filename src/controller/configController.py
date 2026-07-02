import os
from constants import DriverType
from controller.baseController import BaseHandler
from service import llmProviderService
from util import configUtil, assertUtil
import appPaths


class ConfigHandler(BaseHandler):
    """GET /config/frontend.json - 获取前端所需的全局配置"""

    async def get(self) -> None:
        app_config = configUtil.get_app_config()
        setting = app_config.setting

        # 提取可用模型列表
        models = [
            {
                "name": s.name,
                "model": s.model,
                "enabled": s.enable,
            }
            for s in setting.llm_services
        ]

        # 提取 driver 类型列表
        driver_types = [
            {"name": dt.name, "description": _get_driver_description(dt)}
            for dt in DriverType
        ]

        self.return_json({
            "models": models,
            "driver_types": driver_types,
            "default_model": setting.default_llm_server,
            "demo_mode": setting.demo_mode,
        })


class LlmProviderCatalogHandler(BaseHandler):
    """GET /config/llm_providers/catalog.json — 返回 LLM 厂商预设目录"""

    async def get(self) -> None:
        catalog = llmProviderService.load_catalog()
        items = []
        for provider_id, entry in catalog.items():
            items.append({
                "id": provider_id,
                "display_name": entry.get("display_name", {}),
                "type": entry.get("type", "openai-compatible"),
                "base_url": entry.get("base_url", ""),
                "default_model": entry.get("default_model", ""),
                "signup_url": entry.get("signup_url", ""),
                "models": entry.get("models", []),
            })
        self.return_json({"providers": items})


class LlmServiceFromProviderHandler(BaseHandler):
    """POST /config/llm_services/from_provider.json — 根据厂商预设创建服务"""

    async def post(self) -> None:
        from util.configTypes import LlmServiceConfig
        from pydantic import ValidationError

        body = self.parse_request(dict)
        provider_id = body.get("provider_id", "")
        api_key = body.get("api_key", "")
        model = body.get("model")
        custom_name = body.get("name")

        assertUtil.assertTrue(
            bool(provider_id),
            error_message="provider_id 不能为空",
            error_code="missing_provider_id",
        )
        assertUtil.assertTrue(
            bool(api_key),
            error_message="api_key 不能为空",
            error_code="missing_api_key",
        )

        raw_service = llmProviderService.build_llm_service_from_provider(
            provider_id=provider_id,
            api_key=api_key,
            model=model,
            custom_name=custom_name,
        )
        assertUtil.assertNotNull(
            raw_service,
            error_message=f"不支持的厂商: {provider_id}",
            error_code="unknown_provider",
        )

        try:
            new_service = LlmServiceConfig(**raw_service)
        except ValidationError as e:
            self.return_with_error(
                error_code="validation_error",
                error_desc=str(e),
            )
            return

        setting = configUtil.get_app_config().setting
        existing_names = {s.name for s in setting.llm_services}
        if new_service.name in existing_names:
            # 自动编号避免冲突
            base_name = new_service.name
            suffix = 1
            while f"{base_name}_{suffix}" in existing_names:
                suffix += 1
            raw_service["name"] = f"{base_name}_{suffix}"
            new_service = LlmServiceConfig(**raw_service)

        def mutator(s):
            s.llm_services.append(new_service)
            if s.default_llm_server is None:
                s.default_llm_server = new_service.name

        configUtil.update_setting(mutator)
        self.return_json({
            "status": "ok",
            "service": new_service.model_dump(exclude_unset=True, mode="json"),
            "index": len(setting.llm_services) - 1,
        })


class DirectoriesHandler(BaseHandler):
    """GET /config/directories.json - 获取系统目录配置"""

    async def get(self) -> None:
        demo_mode = configUtil.get_app_config().setting.demo_mode
        if demo_mode.hide_sensitive:
            directories = {
                "storage_root": "",
                "config_dir": "",
                "workspace_dir": "",
                "data_dir": "",
                "log_dir": "",
            }
        else:
            directories = {
                "storage_root": appPaths.STORAGE_ROOT,
                "config_dir": appPaths.CONFIG_DIR,
                "workspace_dir": appPaths.WORKSPACE_ROOT,
                "data_dir": appPaths.DATA_DIR,
                "log_dir": appPaths.LOGS_DIR,
            }
        self.return_json({
            **directories,
            "demo_mode": configUtil.get_app_config().setting.demo_mode,
        })


def _get_driver_description(driver_type: DriverType) -> str:
    descriptions = {
        DriverType.NATIVE: "原生 OpenAI API 驱动",
        DriverType.CLAUDE_SDK: "Claude Agent SDK 驱动",
        DriverType.TSP: "TSP 协议驱动",
    }
    return descriptions.get(driver_type, "")
