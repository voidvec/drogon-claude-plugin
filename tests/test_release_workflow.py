# -*- coding: utf-8 -*-
"""发版工作流的失败语义守卫。

v0.5.0 实证(publish run 42360708155):npm 返回 403(需要带 2FA-bypass 的 granular
token)后作业中断,排在它后面的 `Create GitHub Release` 直接 skipped,PyPI 0.5.0 却
已经发布出去 —— 结果是"包能装但找不到发布说明与附件"的半发版状态,还得手工补救。
GitHub Release 是对外叙事(正文取自 RELEASE_TEMPLATE.md)+ wheel/sdist 附件载体,
它比任何一个渠道失败都更该活下来。
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLISH = REPO_ROOT / ".github" / "workflows" / "publish.yml"

STEP_NAME = re.compile(r"^      - name: (.+)$", re.M)


def _step_names():
    return STEP_NAME.findall(PUBLISH.read_text(encoding="utf-8"))


def test_publish_workflow_exists():
    assert PUBLISH.is_file(), "publish.yml 路径失效——本守卫失去事实源"


def test_github_release_created_before_channel_publishes():
    """Release 先建:后面的 PyPI/npm 失败只留下"draft 已含附件",不会让对外叙事消失。"""
    names = _step_names()
    assert "Create GitHub Release" in names, f"未找到 Release 步骤: {names}"
    idx_release = names.index("Create GitHub Release")
    for mandatory in ("Publish to PyPI", "Publish to npm"):
        assert mandatory in names, f"未找到 {mandatory} 步骤: {names}"
        assert idx_release < names.index(mandatory), (
            f"{mandatory} 排在 Create GitHub Release 之前:一旦它失败退出,"
            "Release 与附件就被 skipped,对外只剩半发版"
        )
