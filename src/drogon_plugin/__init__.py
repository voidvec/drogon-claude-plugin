"""drogon-claude-plugin — PyPI 发行包（CLI 安装器）.

本包将 drogon 插件的完整资产（skills / hooks / CLAUDE.md / .claude-plugin /
.zcode-plugin）一并打包进 wheel，通过 `drogon-claude-plugin` 命令安装到目标
项目的 .drogon-plugin/ 子目录（Claude Code 与 ZCode 双宿主可用）。

插件本体仓库: https://github.com/voidvec/drogon-claude-plugin
"""

__version__ = "0.4.0"

# 打包进 wheel 的插件资产
PLUGIN_VERSION = "0.4.0"

__all__ = ["__version__", "PLUGIN_VERSION"]
