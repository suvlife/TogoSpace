"""Skill 导入/管理服务。

支持上传 zip 包或目录形式的 Skill，解压/复制到用户 skills 目录，并重新扫描。
"""
from __future__ import annotations

import logging
import os
import shutil
import tempfile
import zipfile
from typing import Any

import appPaths
import service.skillService as skillService

logger = logging.getLogger(__name__)


class SkillImportError(Exception):
    pass


def _sanitize_skill_name(name: str) -> str:
    """清理 skill 名称，仅保留字母、数字、下划线和连字符。"""
    sanitized = "".join(c for c in name if c.isalnum() or c in ("_", "-")).strip()
    if not sanitized:
        raise SkillImportError("skill 名称不合法")
    return sanitized


def _validate_skill_directory(skill_dir: str) -> dict[str, Any]:
    """校验目录是否符合 skill 规范，返回解析后的元信息。"""
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        raise SkillImportError(f"目录缺少 SKILL.md: {skill_dir}")

    info = skillService.load_skill_from_disk(skill_dir, is_builtin=False)
    if info is None:
        raise SkillImportError(f"无法解析 SKILL.md，请检查 front-matter")
    return {
        "name": info.name,
        "description": info.description,
        "files": info.files,
    }


def _move_to_user_skills(src_dir: str, skill_name: str) -> str:
    """将临时目录中的 skill 移动到用户 skills 目录。"""
    target_dir = os.path.join(appPaths.USER_SKILLS_DIR, skill_name)
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    shutil.move(src_dir, target_dir)
    return target_dir


async def import_skill_from_zip(zip_bytes: bytes, force: bool = False) -> dict[str, Any]:
    """从 zip 包导入 skill。

    Args:
        zip_bytes: zip 文件二进制内容
        force: 是否覆盖已存在的 skill

    Returns:
        {"success": True, "name": ..., "description": ..., "dir": ...}
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "skill.zip")
        with open(zip_path, "wb") as f:
            f.write(zip_bytes)

        extract_dir = os.path.join(tmpdir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_dir)

        # 支持两种打包格式：
        # 1) zip 根目录直接是 skill 文件（SKILL.md 在根）
        # 2) zip 根目录是一个子文件夹，里面是 skill 文件
        candidate_dirs = []
        if os.path.isfile(os.path.join(extract_dir, "SKILL.md")):
            candidate_dirs.append(extract_dir)
        for entry in os.listdir(extract_dir):
            entry_path = os.path.join(extract_dir, entry)
            if os.path.isdir(entry_path) and os.path.isfile(os.path.join(entry_path, "SKILL.md")):
                candidate_dirs.append(entry_path)

        if not candidate_dirs:
            raise SkillImportError("zip 包中未找到 SKILL.md")

        # 一次只导入一个 skill；如果找到多个，取第一个并提示
        skill_dir = candidate_dirs[0]
        meta = _validate_skill_directory(skill_dir)
        skill_name = _sanitize_skill_name(meta["name"])

        target_dir = os.path.join(appPaths.USER_SKILLS_DIR, skill_name)
        if os.path.exists(target_dir) and not force:
            raise SkillImportError(f"skill '{skill_name}' 已存在，设置 force=true 可覆盖")

        final_dir = _move_to_user_skills(skill_dir, skill_name)
        skillService.startup()  # 重新扫描索引

        return {
            "success": True,
            "name": skill_name,
            "description": meta["description"],
            "dir": final_dir,
        }


async def import_skill_from_directory(src_dir: str, force: bool = False) -> dict[str, Any]:
    """从本地目录导入 skill（服务器端使用）。"""
    if not os.path.isdir(src_dir):
        raise SkillImportError(f"目录不存在: {src_dir}")

    meta = _validate_skill_directory(src_dir)
    skill_name = _sanitize_skill_name(meta["name"])

    target_dir = os.path.join(appPaths.USER_SKILLS_DIR, skill_name)
    if os.path.exists(target_dir) and not force:
        raise SkillImportError(f"skill '{skill_name}' 已存在，设置 force=true 可覆盖")

    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    shutil.copytree(src_dir, target_dir)
    skillService.startup()

    return {
        "success": True,
        "name": skill_name,
        "description": meta["description"],
        "dir": target_dir,
    }


async def delete_user_skill(skill_name: str) -> dict[str, Any]:
    """删除用户导入的 skill（builtin skill 不允许删除）。"""
    skill_name = _sanitize_skill_name(skill_name)
    target_dir = os.path.join(appPaths.USER_SKILLS_DIR, skill_name)
    if not os.path.exists(target_dir):
        raise SkillImportError(f"skill '{skill_name}' 不存在")

    info = skillService.get_skill(skill_name)
    if info is not None and info.is_builtin:
        raise SkillImportError(f"builtin skill '{skill_name}' 不允许删除")

    shutil.rmtree(target_dir)
    skillService.startup()
    return {"success": True, "name": skill_name}
