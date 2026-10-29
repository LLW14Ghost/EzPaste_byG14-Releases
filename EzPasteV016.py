import copy
import ctypes
import json
import logging
import os
import queue
import re
import shutil
import ssl
import sys
import tempfile
import threading
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import base64
from pathlib import Path
from tkinter import messagebox, filedialog

import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw

# Optional dependencies: the app works without them.
try:
    import certifi  # better CA bundle inside a PyInstaller exe
except ImportError:
    certifi = None
try:
    import keyring  # store the GitHub token in the OS credential vault
except ImportError:
    keyring = None
try:
    import keyboard  # global hotkey (Ctrl+Alt+E) to show/hide the window
except ImportError:
    keyboard = None

# ---------------------------------------------------------------------------
# Constants & paths
# ---------------------------------------------------------------------------
APP_VERSION = "v0.1.6"

# ---------------------------------------------------------------------------
# Language support: every UI label lives here as (English, 中文).
# Reply blocks and category names are user data and are never translated.
# ---------------------------------------------------------------------------
LANG = "en"  # current UI language, "en" or "zh" (saved in user_prefs.json)

STRINGS = {
    # --- window / tray ---
    "app_name": ("EzPaste Quick Reply Assistant", "EzPaste 快捷回复助手"),
    "copied_title": ("EzPaste ✓ Copied to clipboard!", "EzPaste ✓ 已复制到剪贴板！"),
    "tray_restore": ("Restore Window", "还原窗口"),
    "tray_exit": ("Exit Completely", "完全退出程序"),
    "tray_tooltip": ("EzPaste Quick Reply Assistant", "EzPaste 快捷回复助手"),
    "tray_notify_title": ("Background Running", "后台运行中"),
    "tray_notify_msg": ("EzPaste minimized to system tray. Click tray icon to restore.",
                        "EzPaste 已最小化到系统托盘，点击托盘图标即可还原。"),
    # --- generic ---
    "success": ("Success", "成功"),
    "error": ("Error", "错误"),
    "warning": ("Warning", "警告"),
    "cleared": ("Cleared", "已清除"),
    "confirm": ("Confirm", "确定"),
    "cancel": ("Cancel", "取消"),
    "close": ("Close", "关闭"),
    "got_it": ("Got it", "我知道了"),
    "keyring": ("your system keyring", "系统密钥环"),
    "scope_local": ("Local", "本地"),
    "scope_cloud": ("Cloud", "云端"),
    "local_tag": ("[Local]", "[本地]"),
    # --- main window ---
    "always_on_top": ("Always on Top", "窗口置顶"),
    "data_center": ("⚙️ Data Center", "⚙️ 数据中心"),
    "edit_mode": ("🛠️ Edit Mode", "🛠️ 编辑模式"),
    "exit_edit": ("✓ Exit Edit", "✓ 退出编辑"),
    "manual": ("❓ Manual", "❓ 说明"),
    "add_category": ("+ Category", "+ 分类"),
    "add_reply": ("+ Reply Block", "+ 回复块"),
    "search_ph": ("🔍 Search...", "🔍 搜索..."),
    "lang_btn": ("🌐 中文", "🌐 English"),
    "to_dark": ("🌙 Dark", "🌙 深色"),
    "to_light": ("💡 Light", "💡 浅色"),
    "categories": (" Categories ", " 分类 "),
    "no_results": ("No matching replies", "没有匹配的回复"),
    "edit_active": ("🔧 Edit Mode Active", "🔧 编辑模式中"),
    "click_copy": ("📋 Click to Copy", "📋 点击复制"),
    # --- data center ---
    "dc_title": ("Data Management Center", "数据管理中心"),
    "dc_cfg": ("☁️ Configure Cloud Sync", "☁️ 配置云端同步"),
    "dc_pull": ("🔄 Pull from Cloud Now", "🔄 立即从云端拉取"),
    "dc_push": ("🚀 Push Local to Cloud", "🚀 推送本地到云端"),
    "dc_update": ("🔍 Check App Updates", "🔍 检查应用更新"),
    "dc_import": ("🔄 Import JSON Config", "🔄 导入 JSON 配置"),
    "dc_export": ("📤 Export Backup Copy", "📤 导出备份副本"),
    "import_dlg_title": ("Select JSON Config", "选择 JSON 配置文件"),
    "export_dlg_title": ("Export Backup", "导出备份"),
    "json_files": ("JSON Files", "JSON 文件"),
    "all_files": ("All Files", "所有文件"),
    "import_invalid": ("That file is empty or not a valid EzPaste config.", "该文件为空或不是有效的 EzPaste 配置。"),
    "import_ok": ("Configuration imported successfully!", "配置导入成功！"),
    "import_fail": ("Failed to parse file:\n{e}", "解析文件失败：\n{e}"),
    "export_ok": ("Backup exported successfully to:\n{path}", "备份已成功导出到：\n{path}"),
    "export_fail": ("Failed to write file:\n{e}", "写入文件失败：\n{e}"),
    "save_failed": ("Save Failed", "保存失败"),
    "save_cloud_fail": ("Could not save clipboard_data.json. See ezpaste.log.",
                        "无法保存 clipboard_data.json，详见 ezpaste.log。"),
    "save_local_fail": ("Could not save local_replies.json. See ezpaste.log.",
                        "无法保存 local_replies.json，详见 ezpaste.log。"),
    # --- sync / update / push ---
    "sync_cfg_title": ("Cloud Sync Configuration", "云端同步设置"),
    "sync_cfg_url_prompt": ("Enter GitHub API URL (e.g., api.github.com/repos/<owner>/<repo>/contents/<file>?ref=main):",
                            "请输入 GitHub API 地址（例如 api.github.com/repos/<owner>/<repo>/contents/<file>?ref=main）："),
    "token_title": ("Access Token (PAT)", "访问令牌 (PAT)"),
    "token_prompt_cfg": ("Enter GitHub Personal Access Token (PAT) for private repo:",
                         "请输入私有仓库的 GitHub 个人访问令牌 (PAT)："),
    "bad_url_title": ("Unrecognized URL", "无法识别的地址"),
    "bad_url_msg": ("Expected: https://api.github.com/repos/<owner>/<repo>/contents/<path>\n"
                    "Pull may still work, but Push needs this format.",
                    "期望格式：https://api.github.com/repos/<owner>/<repo>/contents/<path>\n"
                    "拉取可能仍可使用，但推送需要此格式。"),
    "sync_saved": ("Sync settings saved (token stored in {where}).", "同步设置已保存（令牌存放于 {where}）。"),
    "sync_cleared": ("Sync configuration cleared.", "同步配置已清除。"),
    "not_configured": ("Not Configured", "尚未配置"),
    "not_cfg_msg_dc": ("Please configure your Cloud Sync URL in the Data Center first.",
                       "请先在数据中心配置云端同步地址。"),
    "not_cfg_msg": ("Please configure your Cloud Sync URL first!", "请先配置云端同步地址！"),
    "sync_failed": ("Sync Failed", "同步失败"),
    "sync_conn_fail": ("Could not connect or parse link:\n{msg}", "无法连接或解析链接：\n{msg}"),
    "cloud_invalid": ("The cloud file is empty or not in the expected format.", "云端文件为空或格式不正确。"),
    "sync_success": ("Sync Success", "同步成功"),
    "sync_success_msg": ("Successfully pulled latest config from cloud repository!", "已成功从云端仓库拉取最新配置！"),
    "check_updates_title": ("Check Updates", "检查更新"),
    "up_to_date": ("Current version ({v}) is up to date!", "当前版本 ({v}) 已是最新！"),
    "github_fail": ("Could not connect to GitHub:\n{msg}", "无法连接到 GitHub：\n{msg}"),
    "new_version_title": ("New Version Available", "发现新版本"),
    "new_version_msg": ("New version ({v}) found! Download now?", "发现新版本 ({v})！是否立即下载？"),
    "unsupported_title": ("Unsupported URL", "不支持的地址"),
    "unsupported_msg": ("Push needs: https://api.github.com/repos/<owner>/<repo>/contents/<path>[?ref=<branch>]",
                        "推送需要：https://api.github.com/repos/<owner>/<repo>/contents/<path>[?ref=<branch>]"),
    "auth_title": ("Authentication", "身份验证"),
    "auth_prompt": ("Enter your GitHub Personal Access Token (PAT):", "请输入你的 GitHub 个人访问令牌 (PAT)："),
    "push_success": ("Push Success", "推送成功"),
    "push_success_msg": ("Public changes pushed successfully to your GitHub repo!",
                         "公共更改已成功推送到你的 GitHub 仓库！"),
    "push_failed": ("Push Failed", "推送失败"),
    "push_status": ("Unexpected status: {status}", "意外的状态码：{status}"),
    "push_fail": ("Could not push to GitHub:\n{msg}", "无法推送到 GitHub：\n{msg}"),
    # --- block / category popups and dialogs ---
    "block_title": ("Block: {name} ({scope})", "回复块：{name}（{scope}）"),
    "cat_title": ("Category: {name} ({scope})", "分类：{name}（{scope}）"),
    "edit_content": ("✏️ Edit Content", "✏️ 编辑内容"),
    "change_color": ("🎨 Change Color", "🎨 更改颜色"),
    "rename_block": ("🏷️ Rename Block", "🏷️ 重命名回复块"),
    "delete_reply": ("❌ Delete Reply", "❌ 删除回复"),
    "rename_category": ("✏️ Rename Category", "✏️ 重命名分类"),
    "delete_category": ("❌ Delete Category", "❌ 删除分类"),
    "edit_content_title": ("Edit Reply Content", "编辑回复内容"),
    "edit_content_prompt": ("Enter new text for【{name}】:", "请输入【{name}】的新内容："),
    "rename_block_title": ("Rename Block", "重命名回复块"),
    "rename_block_prompt": ("Enter new name for【{name}】:", "请输入【{name}】的新名称："),
    "rename_cat_title": ("Rename Category", "重命名分类"),
    "rename_cat_prompt": ("Enter new name for【{name}】:", "请输入【{name}】的新名称："),
    "block_exists": ("A block with this name already exists!", "已存在同名回复块！"),
    "cat_exists": ("Category name already exists (cloud or local)!", "分类名称已存在（云端或本地）！"),
    "confirm_delete": ("Confirm Delete", "确认删除"),
    "delete_block_msg": ("Are you sure you want to delete【{name}】?", "确定要删除【{name}】吗？"),
    "delete_cat_msg": ("Delete category【{name}】 and all its blocks?", "删除分类【{name}】及其所有回复块？"),
    "new_cat_title": ("New Category", "新建分类"),
    "new_cat_prompt": ("Enter new category name:", "请输入新分类名称："),
    "new_reply_title": ("New Reply Block", "新建回复块"),
    "new_reply_prompt": ("Category:【{cat}】({scope})\nEnter block title/name:",
                         "分类：【{cat}】（{scope}）\n请输入回复块标题/名称："),
    "reply_content_title": ("Reply Content", "回复内容"),
    "reply_content_prompt": ("Enter reply text for【{name}】:", "请输入【{name}】的回复内容："),
    "color_title": ("Theme Color", "选择色彩"),
    "color_cat": ("Select Category Color:", "选择分类颜色："),
    "color_block": ("Select Block Color:", "选择回复块颜色："),
    "scope_title": ("Category Scope", "选择范围"),
    "scope_label": ("Select storage scope for category:", "请选择分类的存储范围："),
    "scope_personal": ("🔒 Personal (Local)\n(Never Cloud Synced)", "🔒 个人（本地）\n（永不同步到云端）"),
    "scope_public": ("☁️ Public (Cloud)\n(Synced to Repo)", "☁️ 公共（云端）\n（同步到仓库）"),
    # --- manual ---
    "manual_title": ("EzPaste User Manual", "EzPaste 使用说明"),
    "manual_heading": ("💡 EzPaste Core Operation Guide", "💡 EzPaste 核心操作指南"),
    "changelog_btn": ("📜 Change Log", "📜 更新日志"),
    "manual_hotkey_on": ("   - Press {hotkey} anywhere to show/hide the window.\n",
                         "   - 在任意位置按下 {hotkey} 可显示/隐藏窗口。\n"),
    "manual_hotkey_off": ("   - Install the optional 'keyboard' package to enable a global show/hide hotkey.\n",
                          "   - 安装可选的 keyboard 包后，可启用全局显示/隐藏快捷键。\n"),
    "manual_body": (
        "Welcome to EzPaste {version}!\n\n"
        "1. 【Personal Local vs. Public Cloud Replies】\n"
        "   - When creating a new category, choose [Personal Local] (saved on this PC only, never uploaded) "
        "or [Public Cloud] (shared through your repo).\n\n"
        "2. 【Search】\n"
        "   - Use the search box at the bottom to find a reply by name or text across all categories. "
        "Press Esc to clear.\n\n"
        "3. 【System Tray & Hotkey】\n"
        "   - Clicking [X] minimizes the app to the system tray. Right-click the tray icon to exit.\n"
        "{hotkey_line}\n"
        "4. 【Theme & Language】\n"
        "   - Use the Theme and language buttons at the bottom right to switch light/dark mode "
        "and English/中文. Your replies and category names are never translated.",
        "欢迎使用 EzPaste {version}！\n\n"
        "1. 【个人本地 / 公共云端回复】\n"
        "   - 新建分类时可选择【个人本地】（仅保存在本机，永不上传）或【公共云端】（通过仓库与团队共享）。\n\n"
        "2. 【搜索】\n"
        "   - 使用底部搜索框，可跨所有分类按名称或内容查找回复，按 Esc 清空搜索。\n\n"
        "3. 【系统托盘与快捷键】\n"
        "   - 点击 [X] 会最小化到系统托盘，右键托盘图标可完全退出。\n"
        "{hotkey_line}\n"
        "4. 【主题与语言】\n"
        "   - 使用右下角的主题按钮和语言按钮，可切换浅色/深色模式与 English/中文 界面。"
        "你的回复和分类名称不会被翻译。",
    ),
    # --- change log ---
    "changelog_win_title": ("Version Change History - {v}", "版本更新日志 - {v}"),
    "changelog_heading": ("📜 EzPaste Version Change History", "📜 EzPaste 版本更新日志"),
    "changelog_body": (
        "【Current Version: {version}】\n"
        " - One-click English / 中文 interface switch (bottom right).\n"
        " - Network calls run in background threads; the UI no longer freezes.\n"
        " - TLS certificate verification enabled; token masked and kept in the system keyring when available.\n"
        " - Atomic saves with automatic .bak backup; corrupt files are preserved as .corrupt.\n"
        " - Search across all categories; optional global hotkey.\n"
        " - Thread-safe system tray; debounced window resize.\n"
        " - Fixed colour mapping, category tuple, update version compare and name-collision bugs.\n\n"
        "【Version: v0.1.5】\n"
        " - added English support\n"
        " - minimized light dark mode switch\n"
        " - Added dual personal (local-only) vs public (cloud-synced) data scopes.\n\n"
        "【Version: v0.1.4】\n"
        " - Added system tray background operation and window close minimization.\n"
        " - Fixed category switching scroll offset bug.\n"
        " - Added Windows single instance mutex check.\n\n"
        "【Version: v0.1.3】\n"
        " - Added secure GitHub private repo API support.",
        "【当前版本：{version}】\n"
        " - 新增右下角 English / 中文 一键界面语言切换。\n"
        " - 网络请求改为后台线程，界面不再卡顿。\n"
        " - 启用 TLS 证书验证；令牌输入打码，并优先存入系统密钥环。\n"
        " - 原子化保存并自动生成 .bak 备份；损坏的文件会另存为 .corrupt。\n"
        " - 新增跨分类搜索与可选的全局快捷键。\n"
        " - 托盘线程安全，窗口缩放防抖。\n"
        " - 修复颜色映射、分类键类型、版本比较与重名冲突等问题。\n\n"
        "【版本：v0.1.5】\n"
        " - 全面引入英文与多语言国际化支持\n"
        " - 优化并精简了右下角主题切换按钮布局\n"
        " - 新增个人（仅本地）与公共（云端同步）双数据范围。\n\n"
        "【版本：v0.1.4】\n"
        " - 新增系统托盘后台运行与关闭窗口最小化。\n"
        " - 修复切换分类时滚动位置偏移的问题。\n"
        " - 新增 Windows 单实例互斥检查。\n\n"
        "【版本：v0.1.3】\n"
        " - 新增 GitHub 私有仓库 API 安全支持。",
    ),
}


def set_language(lang):
    global LANG
    LANG = lang if lang in ("en", "zh") else "en"


def tr(key, **kw):
    """Look up a UI string in the current language (optionally with {placeholders})."""
    pair = STRINGS.get(key)
    text = pair[1 if LANG == "zh" else 0] if pair else key
    return text.format(**kw) if kw else text


def app_title():
    return f"{tr('app_name')} {APP_VERSION}"


DEV_SIGNATURE = "Developed by G14"
HOTKEY = "ctrl+alt+e"

# Data lives next to the script / exe (same place as before), no matter
# which directory the app is launched from.
BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

DATA_FILE = BASE_DIR / "clipboard_data.json"
LOCAL_ONLY_FILE = BASE_DIR / "local_replies.json"  # personal replies, never synced
SYNC_CONFIG_FILE = BASE_DIR / "sync_settings.json"
PREFS_FILE = BASE_DIR / "user_prefs.json"
LOG_FILE = BASE_DIR / "ezpaste.log"

KEYRING_SERVICE = "EzPaste"
KEYRING_USER = "github_pat"

GITHUB_REPO_OWNER = "LLW14Ghost"
GITHUB_REPO_NAME = "EzPaste_byG14-Releases"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("ezpaste")

# ---------------------------------------------------------------------------
# Theme tables
# ---------------------------------------------------------------------------
DARK_THEME_COLORS = ["#35363a", "#2c3e50", "#27ae60", "#2980b9", "#8e44ad", "#c0392b"]
LIGHT_THEME_COLORS = ["#fffdf9", "#f2ebd9", "#e2d7bd", "#d4e6d5", "#d6e4f0", "#f5dcd7"]

THEMES = {
    "light": dict(
        bg="#f7f4eb", bar="#eae2cf", text="#333333", card="#fffdf9", border="#eae2cf",
        primary="#2b3e50", cancel="#e2d7bd", btn="#eae2cf", btn_text="#333333", btn_hover="#dcd3bc",
        danger="#fee2e2", danger_text="#991b1b", danger_hover="#fca5a5",
        muted="#6b7280", arrow_bg="#d1d5db", arrow_text="#333333",
    ),
    "dark": dict(
        bg="#1e222b", bar="#242936", text="#cdd6f4", card="#242936", border="#2e3547",
        primary="#3b82f6", cancel="#45475a", btn="#2a3142", btn_text="#ffffff", btn_hover="#4f5d75",
        danger="#c0392b", danger_text="#ffffff", danger_hover="#e74c3c",
        muted="#94a3b8", arrow_bg="#1e222b", arrow_text="#ffffff",
    ),
}

DEFAULT_CAT_DARK = "#242936"
DEFAULT_CAT_LIGHT = "#eae2cf"
DEFAULT_ITEM_DARK = "#242936"
DEFAULT_ITEM_LIGHT = "#fffdf9"

DEFAULT_DATA = {
    "General Replies": {
        "config": {"dark_color": "#2c3e50", "light_color": "#eae2cf"},
        "items": {
            "Welcome": {"text": "Hello dear customer, how may I help you today?",
                        "dark_color": "#35363a", "light_color": "#fffdf9"},
            "Please Wait": {"text": "Please wait for just a moment, thank you!",
                            "dark_color": "#35363a", "light_color": "#fffdf9"},
        },
    }
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def valid_hex(value, default):
    if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value
    return default


def adjust_brightness(hex_color, factor):
    hex_color = valid_hex(hex_color, "#2d3142").lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = min(255, max(0, int(r * factor)))
    g = min(255, max(0, int(g * factor)))
    b = min(255, max(0, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def get_mapped_color(chosen_color, from_light_mode):
    """Map a colour from one theme pool to the same slot in the other pool."""
    source_pool = LIGHT_THEME_COLORS if from_light_mode else DARK_THEME_COLORS
    target_pool = DARK_THEME_COLORS if from_light_mode else LIGHT_THEME_COLORS
    try:
        return target_pool[source_pool.index(chosen_color)]
    except ValueError:
        return target_pool[0]  # was `return target_pool` (a list) in the old version


def parse_version(text):
    nums = re.findall(r"\d+", str(text))
    return tuple(int(n) for n in nums) if nums else (0,)


def atomic_write_json(path, obj):
    """Write JSON to a temp file, then swap it in, so a crash can't corrupt the data."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def load_json_file(path):
    """Return parsed JSON, or None if missing/corrupt. A corrupt file is kept as *.corrupt."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        log.exception("Could not parse %s", path)
        try:
            shutil.copy2(path, path.with_name(path.name + ".corrupt"))
        except OSError:
            pass
        return None


def backup_file(path):
    path = Path(path)
    if path.exists():
        try:
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        except OSError:
            log.exception("Backup of %s failed", path)


def normalize_data(raw):
    """Validate/repair a data dict. Returns a clean dict, or None if raw is unusable."""
    if not isinstance(raw, dict):
        return None
    fixed = {}
    for cat, content in raw.items():
        if isinstance(cat, (list, tuple)):
            clean_cat = str(cat[0]).strip() if cat else ""
        else:
            clean_cat = str(cat).strip()
        if not clean_cat:
            continue

        config = {}
        if isinstance(content, dict) and isinstance(content.get("items"), dict):
            items_source = content["items"]
            if isinstance(content.get("config"), dict):
                config = content["config"]
        elif isinstance(content, dict):
            items_source = content
        else:
            items_source = {}

        entry = {
            "config": {
                "dark_color": valid_hex(config.get("dark_color"), DEFAULT_CAT_DARK),
                "light_color": valid_hex(config.get("light_color"), DEFAULT_CAT_LIGHT),
            },
            "items": {},
        }
        for name, info in items_source.items():
            if isinstance(info, dict):
                text = str(info.get("text", ""))
                d_c = valid_hex(info.get("dark_color"), DEFAULT_ITEM_DARK)
                l_c = valid_hex(info.get("light_color"), DEFAULT_ITEM_LIGHT)
            else:
                text, d_c, l_c = str(info), DEFAULT_ITEM_DARK, DEFAULT_ITEM_LIGHT
            entry["items"][str(name)] = {"text": text, "dark_color": d_c, "light_color": l_c}
        fixed[clean_cat] = entry
    return fixed or None


def rename_key(d, old, new):
    """Rename a dict key while keeping its position."""
    return {(new if k == old else k): v for k, v in d.items()}


def move_dict_item(d, key, direction):
    keys = list(d.keys())
    if key not in keys:
        return d
    idx = keys.index(key)
    if direction == "up" and idx > 0:
        keys[idx], keys[idx - 1] = keys[idx - 1], keys[idx]
    elif direction == "down" and idx < len(keys) - 1:
        keys[idx], keys[idx + 1] = keys[idx + 1], keys[idx]
    return {k: d[k] for k in keys}


def make_ssl_context():
    """Normal certificate verification (the old code disabled it)."""
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def http_json(url, headers, payload=None, method=None, timeout=10):
    data = None
    headers = dict(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout, context=make_ssl_context()) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, (json.loads(body) if body.strip() else None)


def normalize_sync_url(url):
    url = (url or "").strip()
    if url and not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url


def parse_github_contents_url(url):
    """https://api.github.com/repos/<owner>/<repo>/contents/<path>[?ref=<branch>]"""
    try:
        p = urllib.parse.urlparse((url or "").strip())
        if p.netloc.lower() != "api.github.com":
            return None
        parts = [urllib.parse.unquote(x) for x in p.path.split("/") if x]
        if len(parts) < 5 or parts[0] != "repos" or parts[3] != "contents":
            return None
        branch = urllib.parse.parse_qs(p.query).get("ref", ["main"])[0]
        return {"owner": parts[1], "repo": parts[2], "path": "/".join(parts[4:]), "branch": branch}
    except Exception:
        return None


def center_window_on_parent(window, parent, width, height):
    parent.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
    y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


# --- Single instance (Windows) ---------------------------------------------
_MUTEX_HANDLE = None


def _activate_existing_window():
    """Find the running EzPaste window by title prefix (works even if the version changes)."""
    user32 = ctypes.windll.user32
    found = []
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _lparam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if buf.value.startswith("EzPaste"):
                found.append(hwnd)
                return False
        return True

    user32.EnumWindows(enum_proc(callback), 0)
    if found:
        hwnd = ctypes.c_void_p(found[0])
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)


def check_single_instance(mutex_name="EzPaste_SingleInstance_Mutex"):
    global _MUTEX_HANDLE
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.windll.kernel32
    _MUTEX_HANDLE = kernel32.CreateMutexW(None, False, mutex_name)
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        try:
            _activate_existing_window()
        except Exception:
            log.exception("Could not activate existing window")
        return False
    return True


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------
class ThemedDialog(ctk.CTkToplevel):
    """Shared base: theme, centering, modal grab, result handling."""

    def __init__(self, parent, title, width, height, is_light):
        super().__init__(parent)
        self.t = THEMES["light" if is_light else "dark"]
        self.is_light = is_light
        self.result = None
        self.title(title)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        center_window_on_parent(self, parent, width, height)
        self.configure(fg_color=self.t["bg"])
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            self.after(50, self._retry_grab)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def _retry_grab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def finish(self, result=None):
        self.result = result
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    def cancel(self):
        self.finish(None)


class CTKModernActionPopup(ThemedDialog):
    def __init__(self, parent, title, options, is_light_mode):
        super().__init__(parent, title, 240, 65 + len(options) * 45, is_light_mode)
        t = self.t
        ctk.CTkLabel(self, text=title, font=("Microsoft YaHei", 12, "bold"),
                     text_color=t["text"]).pack(pady=(12, 10))

        container = ctk.CTkFrame(self, fg_color=t["card"], corner_radius=10,
                                 border_width=1, border_color=t["border"])
        container.pack(fill=ctk.BOTH, expand=True, padx=15, pady=(0, 15))

        for label, callback in options:
            if "删除" in label or "Delete" in label:
                fg, txt, hov = t["danger"], t["danger_text"], t["danger_hover"]
            else:
                fg, txt, hov = t["btn"], t["btn_text"], t["btn_hover"]
            ctk.CTkButton(container, text=label, font=("Microsoft YaHei", 11, "bold"),
                          fg_color=fg, text_color=txt, hover_color=hov, height=34, corner_radius=6,
                          command=lambda cb=callback: self.trigger(cb)).pack(fill=ctk.X, padx=12, pady=6)

    def trigger(self, callback):
        self.finish()
        callback()


class ColorPaletteDialog(ThemedDialog):
    def __init__(self, parent, is_light_mode, is_category=False):
        super().__init__(parent, tr("color_title"), 320, 180, is_light_mode)
        title_text = tr("color_cat") if is_category else tr("color_block")
        ctk.CTkLabel(self, text=title_text, font=("Microsoft YaHei", 12, "bold"),
                     text_color=self.t["text"]).pack(pady=(15, 10))

        colors = LIGHT_THEME_COLORS if is_light_mode else DARK_THEME_COLORS
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(padx=20, pady=5)
        for i, color in enumerate(colors):
            ctk.CTkButton(grid, text="", fg_color=color, hover_color=color, width=75, height=36,
                          corner_radius=6, border_width=1, border_color="#cccccc",
                          command=lambda c=color: self.finish(c)).grid(row=i // 3, column=i % 3, padx=8, pady=8)
        self.wait_window()


class ModernInputDialog(ThemedDialog):
    def __init__(self, parent, title, prompt, is_light, initial_value="", secret=False):
        super().__init__(parent, title, 400, 170, is_light)
        t = self.t
        ctk.CTkLabel(self, text=prompt, font=("Microsoft YaHei", 12, "bold"),
                     text_color=t["text"]).pack(anchor="w", padx=20, pady=(15, 5))
        self.entry = ctk.CTkEntry(self, width=360, font=("Microsoft YaHei", 11), fg_color=t["card"],
                                  text_color=t["text"], corner_radius=6, border_width=1,
                                  border_color=t["border"], show="•" if secret else "")
        self.entry.pack(padx=20, pady=5)
        if initial_value:
            self.entry.insert(0, initial_value)
            self.entry.select_range(0, tk.END)
        self.entry.focus_set()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=20, pady=12, fill=ctk.X, side=ctk.BOTTOM)
        ctk.CTkButton(btn_frame, text=tr("confirm"), width=95, height=28,
                      font=("Microsoft YaHei", 11, "bold"), fg_color=t["primary"],
                      command=self.on_ok).pack(side=ctk.RIGHT, padx=(10, 0))
        ctk.CTkButton(btn_frame, text=tr("cancel"), fg_color=t["cancel"], text_color=t["text"],
                      width=95, height=28, font=("Microsoft YaHei", 11),
                      command=self.cancel).pack(side=ctk.RIGHT)
        self.entry.bind("<Return>", lambda e: self.on_ok())
        self.wait_window()

    def on_ok(self):
        self.finish(self.entry.get())


class ModernLargeTextDialog(ThemedDialog):
    def __init__(self, parent, title, prompt, is_light, initial_value=""):
        super().__init__(parent, title, 500, 320, is_light)
        t = self.t
        ctk.CTkLabel(self, text=prompt, font=("Microsoft YaHei", 12, "bold"),
                     text_color=t["text"]).pack(anchor="w", padx=20, pady=(15, 5))
        self.textbox = ctk.CTkTextbox(self, width=460, height=180, font=("Microsoft YaHei", 11),
                                      fg_color=t["card"], text_color=t["text"], corner_radius=10,
                                      border_width=1, border_color=t["border"])
        self.textbox.pack(padx=20, pady=5, fill=ctk.BOTH, expand=True)
        if initial_value:
            self.textbox.insert("1.0", initial_value)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=20, pady=15, fill=ctk.X, side=ctk.BOTTOM)
        ctk.CTkButton(btn_frame, text=tr("confirm"), width=100, height=32,
                      font=("Microsoft YaHei", 11, "bold"), fg_color=t["primary"],
                      command=self.on_ok).pack(side=ctk.RIGHT, padx=(10, 0))
        ctk.CTkButton(btn_frame, text=tr("cancel"), fg_color=t["cancel"], text_color=t["text"],
                      width=100, height=32, font=("Microsoft YaHei", 11),
                      command=self.cancel).pack(side=ctk.RIGHT)
        self.wait_window()

    def on_ok(self):
        self.finish(self.textbox.get("1.0", "end-1c"))


class ScopeDialog(ThemedDialog):
    """Result is "local", "cloud" or None."""

    def __init__(self, parent, is_light):
        super().__init__(parent, tr("scope_title"), 350, 160, is_light)
        ctk.CTkLabel(self, text=tr("scope_label"), font=("Microsoft YaHei", 12, "bold"),
                     text_color=self.t["text"]).pack(pady=(15, 10))
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(padx=20, pady=10, fill=ctk.X)
        ctk.CTkButton(frame, text=tr("scope_personal"), width=140, height=45,
                      font=("Microsoft YaHei", 10, "bold"), fg_color="#d97706", hover_color="#b45309",
                      command=lambda: self.finish("local")).pack(side=ctk.LEFT, padx=5)
        ctk.CTkButton(frame, text=tr("scope_public"), width=140, height=45,
                      font=("Microsoft YaHei", 10, "bold"), fg_color="#2563eb", hover_color="#1d4ed8",
                      command=lambda: self.finish("cloud")).pack(side=ctk.RIGHT, padx=5)
        self.wait_window()


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------
class FastCopyApp:
    def __init__(self, root):
        self.root = root
        self.version_num = APP_VERSION
        self.dev_signature = DEV_SIGNATURE
        self.root.title(app_title())

        self.width = 800
        self.height = 480
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.resizable(True, True)
        self.root.attributes("-topmost", True)
        self.root.configure(fg_color="#1e222b")

        # Thread -> UI hand-off (tkinter must only be touched from the main thread)
        self.ui_queue = queue.Queue()
        self.right_click_event = "<Button-2>" if self.root.tk.call("tk", "windowingsystem") == "aqua" else "<Button-3>"

        self.is_light_mode = self.load_user_preferences()
        self.root.title(app_title())

        self.cloud_data = self.load_data()
        self.local_data = self.load_local_data()
        self.data = {}
        self._rebuild_data()
        self.current_category = self._first_category()

        self.selected_btn_name = ""
        self.selected_btn_cat = ""
        self.selected_category_name = ""
        self.is_edit_mode = False
        self.current_columns = 2
        self.search_query = ""
        self._refresh_job = None
        self._search_job = None

        self.setup_ui()
        self.apply_theme_colors()

        self.screen_width = self.root.winfo_screenwidth()
        self.is_hidden = False
        self.is_animating = False
        self.visible_pixel = 14

        self.setup_indicator()
        self.start_edge_check_loop()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close_window)
        self.tray_icon = None
        self.setup_system_tray()
        self.setup_hotkey()

        self.root.after(100, self._poll_ui_queue)
        self.root.after(500, lambda: self.sync_pull_from_cloud(silent=True))
        self.root.after(2000, lambda: self.check_for_app_updates(manual_check=False))

    # --- small shared helpers -------------------------------------------
    @property
    def theme(self):
        return THEMES["light" if self.is_light_mode else "dark"]

    def post(self, fn):
        """Safe to call from any thread: runs fn on the Tk main thread."""
        self.ui_queue.put(fn)

    def _poll_ui_queue(self):
        try:
            while True:
                fn = self.ui_queue.get_nowait()
                try:
                    fn()
                except Exception:
                    log.exception("UI task failed")
        except queue.Empty:
            pass
        try:
            self.root.after(100, self._poll_ui_queue)
        except tk.TclError:
            pass  # window already destroyed

    def _msg(self, kind, title, text):
        self.root.attributes("-topmost", False)
        try:
            fn = {"info": messagebox.showinfo, "warn": messagebox.showwarning,
                  "error": messagebox.showerror}[kind]
            fn(title, text, parent=self.root)
        finally:
            self.toggle_on_top()

    def _ask(self, title, text):
        self.root.attributes("-topmost", False)
        try:
            return messagebox.askyesno(title, text, parent=self.root)
        finally:
            self.toggle_on_top()

    def _rebuild_data(self):
        self.data = {**self.cloud_data, **self.local_data}

    def _first_category(self):
        for key in self.data:
            return str(key)
        return ""

    def _scope_dict(self, cat):
        return self.local_data if cat in self.local_data else self.cloud_data

    def _save_for(self, cat):
        if cat in self.local_data:
            self.save_local_data()
        else:
            self.save_data()

    def _category_exists(self, name):
        return name in self.cloud_data or name in self.local_data

    # --- preferences / data persistence ----------------------------------
    def load_user_preferences(self):
        prefs = load_json_file(PREFS_FILE)
        if isinstance(prefs, dict):
            set_language(prefs.get("language", "en"))
            return prefs.get("theme_mode", "dark") == "light"
        return False

    def save_user_preferences(self):
        try:
            atomic_write_json(PREFS_FILE, {"theme_mode": "light" if self.is_light_mode else "dark", "language": LANG})
        except Exception:
            log.exception("Saving preferences failed")

    def load_data(self):
        raw = load_json_file(DATA_FILE)
        cleaned = normalize_data(raw)
        return cleaned if cleaned else copy.deepcopy(DEFAULT_DATA)

    def save_data(self):
        try:
            atomic_write_json(DATA_FILE, self.cloud_data)
        except Exception:
            log.exception("Saving cloud data failed")
            self._msg("error", tr("save_failed"), tr("save_cloud_fail"))

    def load_local_data(self):
        return normalize_data(load_json_file(LOCAL_ONLY_FILE)) or {}

    def save_local_data(self):
        try:
            atomic_write_json(LOCAL_ONLY_FILE, self.local_data)
        except Exception:
            log.exception("Saving local data failed")
            self._msg("error", tr("save_failed"), tr("save_local_fail"))

    # --- tray / hotkey / lifecycle ----------------------------------------
    def create_tray_image(self):
        image = Image.new("RGB", (64, 64), color="#1e222b")
        dc = ImageDraw.Draw(image)
        dc.rectangle([16, 16, 48, 48], fill="#3b82f6")
        dc.text((22, 22), "EP", fill="white")
        return image

    def setup_system_tray(self):
        def run_tray():
            menu = pystray.Menu(
                pystray.MenuItem(lambda item: tr("tray_restore"), self.restore_from_tray, default=True),
                pystray.MenuItem(lambda item: tr("tray_exit"), self.exit_completely),
            )
            self.tray_icon = pystray.Icon("EzPaste", self.create_tray_image(),
                                          tr("tray_tooltip"), menu)
            self.tray_icon.run()

        threading.Thread(target=run_tray, daemon=True).start()

    def setup_hotkey(self):
        if keyboard is None:
            return
        try:
            keyboard.add_hotkey(HOTKEY, lambda: self.post(self._toggle_visibility))
        except Exception:
            log.exception("Could not register hotkey")

    def _toggle_visibility(self):
        if self.root.state() == "withdrawn":
            self._do_restore()
        elif self.is_hidden:
            self.animate_show()
        else:
            self.root.withdraw()

    def on_close_window(self):
        self.root.withdraw()
        if self.tray_icon:
            try:
                self.tray_icon.notify(tr("tray_notify_msg"),
                                      tr("tray_notify_title"))
            except Exception:
                pass

    def restore_from_tray(self, icon=None, item=None):  # runs on the tray thread
        self.post(self._do_restore)

    def _do_restore(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.toggle_on_top()
        if self.is_hidden:
            self.animate_show()
        try:
            self.search_entry.focus_set()
        except Exception:
            pass

    def exit_completely(self, icon=None, item=None):  # runs on the tray thread
        try:
            if self.tray_icon:
                self.tray_icon.stop()
        except Exception:
            pass
        self.post(self._quit)

    def _quit(self):
        if keyboard is not None:
            try:
                keyboard.unhook_all()
            except Exception:
                pass
        self.root.quit()
        self.root.destroy()

    # --- sync settings -----------------------------------------------------
    def load_sync_config(self):
        url, token = "", ""
        content = load_json_file(SYNC_CONFIG_FILE)
        if isinstance(content, dict):
            url = str(content.get("sync_url", "")).strip()
            token = str(content.get("token", "")).strip()
        elif isinstance(content, str):
            url = content.strip()
        if keyring is not None:
            try:
                stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
                if stored:
                    token = stored
            except Exception:
                log.exception("Keyring read failed")
        return url, token

    def save_sync_config(self, url, token):
        url, token = normalize_sync_url(url), (token or "").strip()
        file_token = token
        if keyring is not None:
            try:
                if token:
                    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, token)
                else:
                    try:
                        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
                    except Exception:
                        pass
                file_token = ""  # token is in the vault, keep it out of the JSON file
            except Exception:
                log.exception("Keyring write failed, falling back to file")
                file_token = token
        try:
            atomic_write_json(SYNC_CONFIG_FILE, {"sync_url": url, "token": file_token})
        except Exception:
            log.exception("Saving sync config failed")

    def configure_sync_url(self):
        self.root.attributes("-topmost", False)
        curr_url, curr_token = self.load_sync_config()

        new_url = ModernInputDialog(
            self.root, tr("sync_cfg_title"),
            tr("sync_cfg_url_prompt"),
            self.is_light_mode, initial_value=curr_url).result
        if new_url is not None:
            new_token = ModernInputDialog(
                self.root, tr("token_title"),
                tr("token_prompt_cfg"),
                self.is_light_mode, initial_value=curr_token, secret=True).result
            if new_token is not None:
                new_url = normalize_sync_url(new_url)
                if new_url and not parse_github_contents_url(new_url):
                    self._msg("warn", tr("bad_url_title"),
                              tr("bad_url_msg"))
                self.save_sync_config(new_url, new_token)
                if new_url:
                    where = tr("keyring") if keyring is not None else "sync_settings.json"
                    self._msg("info", tr("success"), tr("sync_saved", where=where))
                    self.sync_pull_from_cloud(silent=False)
                else:
                    self._msg("info", tr("cleared"), tr("sync_cleared"))
        self.toggle_on_top()

    # --- network (all on worker threads) ----------------------------------
    def sync_pull_from_cloud(self, silent=True):
        target_url, token = self.load_sync_config()
        if not target_url:
            if not silent:
                self._msg("warn", tr("not_configured"),
                          tr("not_cfg_msg_dc"))
            return

        def worker():
            try:
                headers = {"User-Agent": "EzPaste-Client", "Cache-Control": "no-cache",
                           "Accept": "application/vnd.github.v3.raw"}
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                _, payload = http_json(target_url, headers, timeout=10)
                self.post(lambda: self._apply_cloud_data(payload, silent))
            except Exception as e:
                log.exception("Cloud sync pull failed")
                msg = str(e)
                if not silent:
                    self.post(lambda: self._msg("error", tr("sync_failed"),
                                                tr("sync_conn_fail", msg=msg)))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_cloud_data(self, payload, silent):
        validated = normalize_data(payload)
        if not validated:
            log.warning("Cloud payload was empty or invalid; local data left untouched")
            if not silent:
                self._msg("error", tr("sync_failed"), tr("cloud_invalid"))
            return
        backup_file(DATA_FILE)  # keep the previous copy as clipboard_data.json.bak
        self.cloud_data = validated
        self.save_data()
        self._rebuild_data()
        if self.current_category not in self.data:
            self.current_category = self._first_category()
        self.apply_theme_colors()
        if not silent:
            self._msg("info", tr("sync_success"), tr("sync_success_msg"))

    def check_for_app_updates(self, manual_check=False):
        api_url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"

        def worker():
            try:
                _, release = http_json(api_url, {"User-Agent": "EzPaste-Updater",
                                                 "Accept": "application/vnd.github.v3+json"})
                latest = str((release or {}).get("tag_name", "")).strip()
                if latest and parse_version(latest) > parse_version(self.version_num):
                    assets = (release or {}).get("assets", []) or []
                    chosen = next((a for a in assets
                                   if str(a.get("name", "")).lower().endswith((".exe", ".msi", ".zip"))),
                                  assets[0] if assets else None)
                    url = chosen.get("browser_download_url") if chosen else None
                    self.post(lambda: self.prompt_update_dialog(latest, url))
                elif manual_check:
                    self.post(lambda: self._msg(
                        "info", tr("check_updates_title"), tr("up_to_date", v=self.version_num)))
            except Exception as e:
                log.exception("Update check failed")
                msg = str(e)
                if manual_check:
                    self.post(lambda: self._msg("error", tr("check_updates_title"),
                                                tr("github_fail", msg=msg)))

        threading.Thread(target=worker, daemon=True).start()

    def prompt_update_dialog(self, new_version, download_url):
        if self._ask(tr("new_version_title"), tr("new_version_msg", v=new_version)):
            webbrowser.open(download_url or f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases")

    def push_data_to_github(self):
        target_url, saved_token = self.load_sync_config()
        if not target_url:
            self._msg("warn", tr("not_configured"), tr("not_cfg_msg"))
            return
        target = parse_github_contents_url(target_url)
        if not target:
            self._msg("error", tr("unsupported_title"),
                      tr("unsupported_msg"))
            return

        self.root.attributes("-topmost", False)
        token = ModernInputDialog(self.root, tr("auth_title"),
                                  tr("auth_prompt"),
                                  self.is_light_mode, initial_value=saved_token, secret=True).result
        self.toggle_on_top()
        if not token or not token.strip():
            return
        token = token.strip()

        content = json.dumps(self.cloud_data, ensure_ascii=False, indent=4)  # public data only
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        version = self.version_num

        def worker():
            try:
                quoted_path = urllib.parse.quote(target["path"], safe="/")
                api = f"https://api.github.com/repos/{target['owner']}/{target['repo']}/contents/{quoted_path}"
                headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json",
                           "User-Agent": "EzPaste-Client"}
                sha = None
                try:
                    _, info = http_json(f"{api}?ref={urllib.parse.quote(target['branch'])}", headers)
                    sha = (info or {}).get("sha")
                except urllib.error.HTTPError as e:
                    if e.code != 404:  # 404 = file doesn't exist yet, we'll create it
                        raise
                payload = {"message": f"Update clipboard_data.json via EzPaste App ({version})",
                           "content": encoded, "branch": target["branch"]}
                if sha:
                    payload["sha"] = sha
                status, _ = http_json(api, headers, payload, "PUT")
                if status in (200, 201):
                    self.post(lambda: self._msg("info", tr("push_success"),
                                                tr("push_success_msg")))
                else:
                    self.post(lambda: self._msg("error", tr("push_failed"), tr("push_status", status=status)))
            except Exception as e:
                log.exception("Push failed")
                msg = str(e)
                self.post(lambda: self._msg("error", tr("push_failed"), tr("push_fail", msg=msg)))

        threading.Thread(target=worker, daemon=True).start()

    # --- UI construction --------------------------------------------------
    def setup_ui(self):
        self.top_frame = ctk.CTkFrame(self.root, height=50, corner_radius=0)
        self.top_frame.pack(fill=ctk.X, side=ctk.TOP)

        self.always_on_top_var = tk.BooleanVar(value=True)
        self.check_top = ctk.CTkCheckBox(self.top_frame, text=tr("always_on_top"), variable=self.always_on_top_var,
                                         font=("Microsoft YaHei", 10, "bold"), command=self.toggle_on_top,
                                         checkbox_width=18, checkbox_height=18)
        self.check_top.pack(side=ctk.LEFT, padx=15, pady=10)

        self.btn_data_center = ctk.CTkButton(self.top_frame, text=tr("data_center"), width=115, height=30,
                                             font=("Microsoft YaHei", 10, "bold"), fg_color="#16a34a",
                                             hover_color="#15803d", command=self.open_data_management_popup)
        self.btn_data_center.pack(side=ctk.LEFT, padx=5, pady=10)

        self.btn_edit_mode = ctk.CTkButton(self.top_frame, text=tr("edit_mode"), width=105, height=30,
                                           font=("Microsoft YaHei", 10, "bold"), fg_color="#0891b2",
                                           hover_color="#0e7490", command=self.toggle_edit_mode)
        self.btn_edit_mode.pack(side=ctk.LEFT, padx=5, pady=10)

        self.btn_help = ctk.CTkButton(self.top_frame, text=tr("manual"), width=80, height=30,
                                      font=("Microsoft YaHei", 10, "bold"), fg_color="#6366f1",
                                      hover_color="#4f46e5", command=self.open_instruction_dialog)
        self.btn_help.pack(side=ctk.LEFT, padx=5, pady=10)

        self.btn_add_cat = ctk.CTkButton(self.top_frame, text=tr("add_category"), font=("Microsoft YaHei", 10, "bold"),
                                         height=30, corner_radius=6, command=self.add_category_prompt)
        self.btn_add_cat.pack(side=ctk.RIGHT, padx=10, pady=10)

        self.btn_add_reply = ctk.CTkButton(self.top_frame, text=tr("add_reply"),
                                           font=("Microsoft YaHei", 10, "bold"), height=30, corner_radius=6,
                                           command=self.add_new_reply_prompt)
        self.btn_add_reply.pack(side=ctk.RIGHT, padx=5, pady=10)

        self.left_panel = ctk.CTkScrollableFrame(self.root, width=160, corner_radius=0)
        self.left_panel.pack(fill=tk.Y, side=ctk.LEFT)
        self.make_scroll_faster(self.left_panel)

        self.right_main_container = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        self.right_main_container.pack(fill=ctk.BOTH, expand=True, side=ctk.LEFT)

        self.right_scroll = ctk.CTkScrollableFrame(self.right_main_container, corner_radius=0,
                                                   fg_color="transparent")
        self.right_scroll.pack(fill=ctk.BOTH, expand=True, side=ctk.TOP)
        self.make_scroll_faster(self.right_scroll)

        self.right_main_container.bind("<Configure>", self.on_right_scroll_configure)

        self.bot_status_bar = ctk.CTkFrame(self.right_main_container, height=34, corner_radius=0,
                                           fg_color="transparent")
        self.bot_status_bar.pack(fill=ctk.X, side=ctk.BOTTOM, padx=10, pady=4)

        self.theme_switch = ctk.CTkButton(self.bot_status_bar, text="💡 Theme", width=85, height=26,
                                          font=("Microsoft YaHei", 9, "bold"), fg_color="#4b5563",
                                          hover_color="#374151", command=self.theme_swap_with_fade)
        self.theme_switch.pack(side=ctk.RIGHT)

        self.lang_switch = ctk.CTkButton(self.bot_status_bar, text=tr("lang_btn"), width=90, height=26,
                                         font=("Microsoft YaHei", 9, "bold"), fg_color="#4b5563",
                                         hover_color="#374151", text_color="#ffffff",
                                         command=self.toggle_language)
        self.lang_switch.pack(side=ctk.RIGHT, padx=(0, 8))

        # Search across all categories (names and reply text)
        self.search_entry = ctk.CTkEntry(self.bot_status_bar, placeholder_text=tr("search_ph"),
                                         height=26, font=("Microsoft YaHei", 10))
        self.search_entry.pack(side=ctk.LEFT, fill=ctk.X, expand=True, padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self.on_search_changed)

    def make_scroll_faster(self, scrollable_frame):
        canvas = None
        for attr in ("_parent_canvas", "_canvas", "canvas"):
            if hasattr(scrollable_frame, attr):
                canvas = getattr(scrollable_frame, attr)
                break
        if canvas is None:
            for child in scrollable_frame.winfo_children():
                if isinstance(child, tk.Canvas):
                    canvas = child
                    break
        if not canvas:
            return

        def _on_mousewheel(event):
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 12)), "units")
            elif event.num == 4:
                canvas.yview_scroll(-6, "units")
            elif event.num == 5:
                canvas.yview_scroll(6, "units")

        scrollable_frame.bind("<MouseWheel>", _on_mousewheel, add="+")
        canvas.bind("<MouseWheel>", _on_mousewheel, add="+")

    def on_right_scroll_configure(self, event):
        available_width = max(100, event.width - 35)
        new_cols = max(1, available_width // 295)
        if new_cols != self.current_columns:
            self.current_columns = new_cols
            self._schedule_right_refresh()

    def _schedule_right_refresh(self, delay=120):
        """Debounce: resizing the window fires many events, rebuild only once it settles."""
        if self._refresh_job is not None:
            try:
                self.root.after_cancel(self._refresh_job)
            except Exception:
                pass
        self._refresh_job = self.root.after(delay, self._do_scheduled_refresh)

    def _do_scheduled_refresh(self):
        self._refresh_job = None
        self.refresh_right_buttons()

    def on_search_changed(self, event=None):
        if event is not None and event.keysym == "Escape":
            self.search_entry.delete(0, tk.END)
        new_query = self.search_entry.get()
        if new_query == self.search_query:
            return
        self.search_query = new_query
        self._schedule_right_refresh(150)

    def _clear_search(self):
        if self.search_query:
            self.search_query = ""
            self.search_entry.delete(0, tk.END)

    # --- theming ------------------------------------------------------------
    def apply_theme_colors(self):
        t = self.theme
        if self.is_light_mode:
            ctk.set_appearance_mode("light")
            self.theme_switch.configure(text=tr("to_dark"), fg_color="#2d3142", hover_color="#4f5d75",
                                        text_color="#ffffff")
            self.check_top.configure(text_color="#1a0f00", fg_color="#854d0e", hover_color="#b45309",
                                     border_color="#78350f")
            self.btn_add_cat.configure(fg_color="#4f5d75", hover_color="#2d3142", text_color="#ffffff")
            self.btn_add_reply.configure(fg_color="#27ae60", hover_color="#1e7e43", text_color="#ffffff")
        else:
            ctk.set_appearance_mode("dark")
            self.theme_switch.configure(text=tr("to_light"), fg_color="#e2d7bd", hover_color="#eae2cf",
                                        text_color="#333333")
            self.check_top.configure(text_color="#cdd6f4", fg_color="#3b82f6", hover_color="#2563eb",
                                     border_color="#2e3547")
            self.btn_add_cat.configure(fg_color="#3b82f6", hover_color="#2563eb", text_color="#ffffff")
            self.btn_add_reply.configure(fg_color="#10b981", hover_color="#059669", text_color="#ffffff")
        self.root.configure(fg_color=t["bg"])
        self.top_frame.configure(fg_color=t["bar"])
        self.btn_data_center.configure(text_color="#ffffff")
        self.btn_help.configure(text_color="#ffffff")

        self.refresh_left_menu()
        self.refresh_right_buttons()

    def refresh_left_menu(self):
        for w in self.left_panel.winfo_children():
            w.destroy()
        light = self.is_light_mode
        t = self.theme
        c_key = "light_color" if light else "dark_color"
        default_cat = DEFAULT_CAT_LIGHT if light else DEFAULT_CAT_DARK

        cat_base_color = default_cat
        if self.current_category in self.data:
            cat_base_color = valid_hex(self.data[self.current_category]["config"].get(c_key), default_cat)
        self.left_panel.configure(fg_color=cat_base_color)

        ctk.CTkLabel(self.left_panel, text=tr("categories"), font=("Microsoft YaHei", 12, "bold"),
                     text_color="#333333" if light else "#ffffff").pack(fill=ctk.X, pady=(5, 12))

        for cat, cat_info in self.data.items():
            custom_color = valid_hex(cat_info["config"].get(c_key), default_cat)
            if cat == self.current_category:
                btn_color = "#333333" if light else "#ffffff"
                text_color = "#ffffff" if light else "#11111b"
                hover_c = "#4b5563" if light else "#e6e6e6"
            elif light:
                btn_color = adjust_brightness(custom_color, 1.1)
                text_color = "#333333"
                hover_c = adjust_brightness(custom_color, 0.9)
            else:
                btn_color = adjust_brightness(custom_color, 0.8)
                text_color = "#e2e8f0"
                hover_c = adjust_brightness(custom_color, 1.1)

            font_w = "bold" if cat == self.current_category else "normal"
            item_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
            item_frame.pack(fill=ctk.X, padx=4, pady=3)

            display_title = f"📂 {tr('local_tag')} {cat}" if cat in self.local_data else f"📂 {cat}"
            btn = ctk.CTkButton(item_frame, text=display_title, fg_color=btn_color, text_color=text_color,
                                hover_color=hover_c, height=36, corner_radius=6, anchor="w",
                                font=("Microsoft YaHei", 11, font_w),
                                command=lambda c=cat: self.switch_category(c))

            if self.is_edit_mode:
                btn.configure(width=100)
                try:  # private attribute of CustomTkinter; tolerate it disappearing
                    btn._text_label.configure(wraplength=85, justify="left")
                except Exception:
                    pass
                btn.pack(side=ctk.LEFT, fill=ctk.X, expand=True)
                for sym, direction in (("▲", "up"), ("▼", "down")):
                    ctk.CTkButton(item_frame, text=sym, width=22, height=36, font=("Arial", 10, "bold"),
                                  fg_color=t["arrow_bg"], text_color=t["arrow_text"], corner_radius=4,
                                  command=lambda c=cat, d=direction: self.move_category(c, d)
                                  ).pack(side=ctk.LEFT, padx=1)
            else:
                btn.pack(fill=ctk.X, expand=True)

            btn.bind(self.right_click_event, lambda event, c=cat: self.show_category_popup_panel(event, c))

        ctk.CTkLabel(self.left_panel, text=f"{self.dev_signature}\n{self.version_num}",
                     font=("Arial", 9, "italic"), text_color=t["muted"]
                     ).pack(side=tk.BOTTOM, fill=ctk.X, pady=(20, 5))

    def _visible_entries(self):
        """List of (category, block_name, block_info) to display (search spans all categories)."""
        query = self.search_query.strip().casefold()
        entries = []
        if query:
            for cat, cinfo in self.data.items():
                for name, info in cinfo["items"].items():
                    if query in name.casefold() or query in info["text"].casefold():
                        entries.append((cat, name, info))
        elif self.current_category in self.data:
            for name, info in self.data[self.current_category]["items"].items():
                entries.append((self.current_category, name, info))
        return entries

    def refresh_right_buttons(self):
        for w in self.right_scroll.winfo_children():
            w.destroy()

        light = self.is_light_mode
        t = self.theme
        searching = bool(self.search_query.strip())

        self.right_scroll.configure(fg_color=t["bg"])
        for canvas_attr in ("_parent_canvas", "_canvas", "canvas"):
            if hasattr(self.right_scroll, canvas_attr):
                try:
                    getattr(self.right_scroll, canvas_attr).configure(bg=t["bg"])
                except Exception:
                    pass

        entries = self._visible_entries()
        if searching and not entries:
            ctk.CTkLabel(self.right_scroll, text=tr("no_results"),
                         font=("Microsoft YaHei", 12), text_color=t["muted"]).grid(row=0, column=0, padx=20, pady=30)
            return

        cols = self.current_columns
        for index, (cat, btn_name, btn_info) in enumerate(entries):
            text_content = btn_info["text"]
            dark_c = valid_hex(btn_info.get("dark_color"), DEFAULT_ITEM_DARK)
            light_c = valid_hex(btn_info.get("light_color"), DEFAULT_ITEM_LIGHT)

            if light:
                bg_color, hover_color = light_c, "#eae2cf"
                title_text_color, sub_text_color = "#2c2c2c", "#666666"
            else:
                bg_color = adjust_brightness(dark_c, 0.6)
                hover_color = adjust_brightness(dark_c, 0.8)
                title_text_color, sub_text_color = "#ffffff", "#bfc7d5"

            card_frame = ctk.CTkFrame(self.right_scroll, fg_color="transparent", width=280, height=95)
            card_frame.grid(row=index // cols, column=index % cols, padx=12, pady=12)
            card_frame.grid_propagate(False)

            show_arrows = self.is_edit_mode and not searching
            btn = ctk.CTkButton(card_frame, text="", fg_color=bg_color, hover_color=hover_color,
                                width=225 if show_arrows else 265, height=90, corner_radius=12,
                                border_width=1, border_color=t["border"],
                                command=lambda tx=text_content: self.copy_to_clipboard(tx))
            btn.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True)

            label_title = ctk.CTkLabel(btn, text=f"【{btn_name}】", font=("Microsoft YaHei", 12, "bold"),
                                       text_color=title_text_color)
            label_title.place(relx=0.5, rely=0.3, anchor="center")

            if searching:
                hint_txt = f"📂 {cat}"
            elif self.is_edit_mode:
                hint_txt = tr("edit_active")
            else:
                hint_txt = tr("click_copy")
            label_sub = ctk.CTkLabel(btn, text=hint_txt, font=("Microsoft YaHei", 10), text_color=sub_text_color)
            label_sub.place(relx=0.5, rely=0.68, anchor="center")

            if show_arrows:
                arrow_bar = ctk.CTkFrame(card_frame, fg_color="transparent", width=32)
                arrow_bar.pack(side=ctk.LEFT, fill=ctk.Y, padx=(4, 0))
                ctk.CTkButton(arrow_bar, text="▲", width=32, height=43, font=("Arial", 10, "bold"),
                              fg_color=t["arrow_bg"], text_color=t["arrow_text"], corner_radius=6,
                              command=lambda name=btn_name: self.move_reply(name, "up")
                              ).pack(side=ctk.TOP, pady=(0, 2))
                ctk.CTkButton(arrow_bar, text="▼", width=32, height=43, font=("Arial", 10, "bold"),
                              fg_color=t["arrow_bg"], text_color=t["arrow_text"], corner_radius=6,
                              command=lambda name=btn_name: self.move_reply(name, "down")
                              ).pack(side=ctk.TOP)

            def on_right(event, name=btn_name, c=cat):
                self.show_reply_popup_panel(event, name, c)

            for w in (btn, label_title, label_sub):
                w.bind(self.right_click_event, on_right)
            label_title.bind("<Button-1>", lambda event, tx=text_content: self.copy_to_clipboard(tx))
            label_sub.bind("<Button-1>", lambda event, tx=text_content: self.copy_to_clipboard(tx))

    # --- modes ------------------------------------------------------------
    def toggle_edit_mode(self):
        self.is_edit_mode = not self.is_edit_mode
        self.btn_edit_mode.configure(text=tr("exit_edit") if self.is_edit_mode else tr("edit_mode"),
                                     fg_color="#b45309" if self.is_edit_mode else "#0891b2",
                                     hover_color="#92400e" if self.is_edit_mode else "#0e7490")
        self.refresh_left_menu()
        self.refresh_right_buttons()

    def toggle_on_top(self):
        self.root.attributes("-topmost", self.always_on_top_var.get())

    # --- data center ---------------------------------------------------------
    def open_data_management_popup(self):
        CTKModernActionPopup(self.root, tr("dc_title"), [
            (tr("dc_cfg"), self.configure_sync_url),
            (tr("dc_pull"), lambda: self.sync_pull_from_cloud(silent=False)),
            (tr("dc_push"), self.push_data_to_github),
            (tr("dc_update"), lambda: self.check_for_app_updates(manual_check=True)),
            (tr("dc_import"), self.import_json_config),
            (tr("dc_export"), self.export_json_config),
        ], self.is_light_mode)

    def import_json_config(self):
        self.root.attributes("-topmost", False)
        file_path = filedialog.askopenfilename(title=tr("import_dlg_title"),
                                               filetypes=[(tr("json_files"), "*.json"), (tr("all_files"), "*.*")])
        self.toggle_on_top()
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                incoming = json.load(f)
            validated = normalize_data(incoming)
            if not validated:
                self._msg("error", tr("error"), tr("import_invalid"))
                return
            backup_file(DATA_FILE)
            self.cloud_data = validated
            self.save_data()
            self._rebuild_data()
            self.current_category = self._first_category()
            self._clear_search()
            self.apply_theme_colors()
            self._msg("info", tr("success"), tr("import_ok"))
        except Exception as e:
            log.exception("Import failed")
            self._msg("error", tr("error"), tr("import_fail", e=e))

    def export_json_config(self):
        self.root.attributes("-topmost", False)
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        file_path = filedialog.asksaveasfilename(title=tr("export_dlg_title"), initialdir=desktop_path,
                                                 initialfile="EzPaste_Backup.json",
                                                 filetypes=[(tr("json_files"), "*.json"), (tr("all_files"), "*.*")])
        self.toggle_on_top()
        if not file_path:
            return
        if not file_path.lower().endswith(".json"):
            file_path += ".json"
        try:
            atomic_write_json(file_path, self.data)
            self._msg("info", tr("success"), tr("export_ok", path=file_path))
        except Exception as e:
            log.exception("Export failed")
            self._msg("error", tr("error"), tr("export_fail", e=e))

    # --- popups -----------------------------------------------------------
    def show_reply_popup_panel(self, event, name, cat=None):
        self.selected_btn_name = name
        self.selected_btn_cat = cat or self.current_category
        scope = tr("scope_local") if self.selected_btn_cat in self.local_data else tr("scope_cloud")
        CTKModernActionPopup(self.root, tr("block_title", name=name, scope=scope), [
            (tr("edit_content"), self.edit_reply_content),
            (tr("change_color"), self.change_reply_color),
            (tr("rename_block"), self.rename_reply_button),
            (tr("delete_reply"), self.delete_reply_button),
        ], self.is_light_mode)

    def show_category_popup_panel(self, event, name):
        self.selected_category_name = name
        scope = tr("scope_local") if name in self.local_data else tr("scope_cloud")
        CTKModernActionPopup(self.root, tr("cat_title", name=name, scope=scope), [
            (tr("change_color"), self.change_category_color),
            (tr("rename_category"), self.rename_category),
            (tr("delete_category"), self.delete_category),
        ], self.is_light_mode)

    def _selected_block(self):
        """(category, name, items_dict) for the block chosen in the popup, or None."""
        cat, name = self.selected_btn_cat, self.selected_btn_name
        if not cat or not name:
            return None
        items = self._scope_dict(cat).get(cat, {}).get("items")
        if items is None or name not in items:
            return None
        return cat, name, items

    def edit_reply_content(self):
        sel = self._selected_block()
        if not sel:
            return
        cat, name, items = sel
        self.root.attributes("-topmost", False)
        upd = ModernLargeTextDialog(self.root, tr("edit_content_title"), tr("edit_content_prompt", name=name),
                                    self.is_light_mode, initial_value=items[name]["text"]).result
        if upd is not None and upd.strip():
            items[name]["text"] = upd.strip()
            self._save_for(cat)
            self.refresh_right_buttons()
        self.toggle_on_top()

    def rename_reply_button(self):
        sel = self._selected_block()
        if not sel:
            return
        cat, name, items = sel
        self.root.attributes("-topmost", False)
        new_name = ModernInputDialog(self.root, tr("rename_block_title"), tr("rename_block_prompt", name=name),
                                     self.is_light_mode, initial_value=name).result
        self.toggle_on_top()
        if new_name and new_name.strip():
            new_name = new_name.strip()
            if new_name != name and new_name in items:
                self._msg("warn", tr("warning"), tr("block_exists"))
            elif new_name != name:
                self._scope_dict(cat)[cat]["items"] = rename_key(items, name, new_name)
                self._rebuild_data()
                self._save_for(cat)
                self.refresh_right_buttons()

    def delete_reply_button(self):
        sel = self._selected_block()
        if not sel:
            return
        cat, name, items = sel
        if self._ask(tr("confirm_delete"), tr("delete_block_msg", name=name)):
            items.pop(name, None)
            self._save_for(cat)
            self.refresh_right_buttons()

    def rename_category(self):
        old = self.selected_category_name
        if not old:
            return
        self.root.attributes("-topmost", False)
        new = ModernInputDialog(self.root, tr("rename_cat_title"), tr("rename_cat_prompt", name=old),
                                self.is_light_mode, initial_value=old).result
        self.toggle_on_top()
        if new and new.strip():
            new = new.strip()
            if new != old and self._category_exists(new):
                self._msg("warn", tr("warning"), tr("cat_exists"))
            elif new != old:
                was_local = old in self.local_data
                if was_local:
                    self.local_data = rename_key(self.local_data, old, new)
                else:
                    self.cloud_data = rename_key(self.cloud_data, old, new)
                if self.current_category == old:
                    self.current_category = new
                self._rebuild_data()
                if was_local:
                    self.save_local_data()
                else:
                    self.save_data()
                self.refresh_left_menu()

    def delete_category(self):
        name = self.selected_category_name
        if not name:
            return
        if self._ask(tr("confirm_delete"), tr("delete_cat_msg", name=name)):
            was_local = name in self.local_data
            (self.local_data if was_local else self.cloud_data).pop(name, None)
            self._rebuild_data()
            if self.current_category == name or self.current_category not in self.data:
                self.current_category = self._first_category()
            if was_local:
                self.save_local_data()
            else:
                self.save_data()
            self.refresh_left_menu()
            self.refresh_right_buttons()

    def switch_category(self, category):
        self._clear_search()
        self.current_category = category
        for canvas_attr in ("_parent_canvas", "_canvas", "canvas"):
            if hasattr(self.right_scroll, canvas_attr):
                try:
                    getattr(self.right_scroll, canvas_attr).yview_moveto(0.0)
                except Exception:
                    pass
        self.refresh_left_menu()
        self.refresh_right_buttons()

    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        # keep the "EzPaste" prefix so the single-instance check can still find the window
        self.root.title(tr("copied_title"))
        self.root.after(1000, lambda: self.root.title(app_title()))

    # --- adding ------------------------------------------------------------
    def add_category_prompt(self):
        self.root.attributes("-topmost", False)
        scope = ScopeDialog(self.root, self.is_light_mode).result
        if scope is None:
            self.toggle_on_top()
            return
        new = ModernInputDialog(self.root, tr("new_cat_title"), tr("new_cat_prompt"),
                                self.is_light_mode).result
        self.toggle_on_top()
        if new and new.strip():
            new = new.strip()
            if self._category_exists(new):
                self._msg("warn", tr("warning"), tr("cat_exists"))
                return
            is_local = scope == "local"
            target = self.local_data if is_local else self.cloud_data
            target[new] = {"config": {"dark_color": DEFAULT_CAT_DARK, "light_color": DEFAULT_CAT_LIGHT},
                           "items": {}}
            self._clear_search()
            self.current_category = new
            self._rebuild_data()
            if is_local:
                self.save_local_data()
            else:
                self.save_data()
            self.refresh_left_menu()
            self.refresh_right_buttons()

    def add_new_reply_prompt(self):
        cat = self.current_category
        if not cat or cat not in self.data:
            return
        scope = tr("scope_local") if cat in self.local_data else tr("scope_cloud")
        self.root.attributes("-topmost", False)
        b_name = ModernInputDialog(self.root, tr("new_reply_title"),
                                   tr("new_reply_prompt", cat=cat, scope=scope),
                                   self.is_light_mode).result
        if b_name and b_name.strip():
            b_name = b_name.strip()
            items = self._scope_dict(cat)[cat]["items"]
            if b_name in items:
                self._msg("warn", tr("warning"), tr("block_exists"))
            else:
                b_content = ModernLargeTextDialog(self.root, tr("reply_content_title"), tr("reply_content_prompt", name=b_name),
                                                  self.is_light_mode).result
                if b_content and b_content.strip():
                    items[b_name] = {"text": b_content.strip(), "dark_color": DEFAULT_ITEM_DARK,
                                     "light_color": DEFAULT_ITEM_LIGHT}
                    self._save_for(cat)
                    self._clear_search()
                    self.refresh_right_buttons()
        self.toggle_on_top()

    # --- ordering ------------------------------------------------------------
    def move_category(self, cat_name, direction):
        if cat_name in self.local_data:
            self.local_data = move_dict_item(self.local_data, cat_name, direction)
            self.save_local_data()
        else:
            self.cloud_data = move_dict_item(self.cloud_data, cat_name, direction)
            self.save_data()
        self._rebuild_data()
        self.refresh_left_menu()

    def move_reply(self, btn_name, direction):
        cat = self.current_category
        if not cat or cat not in self.data:
            return
        container = self._scope_dict(cat)[cat]
        container["items"] = move_dict_item(container["items"], btn_name, direction)
        self._rebuild_data()
        self._save_for(cat)
        self.refresh_right_buttons()

    # --- help / changelog ------------------------------------------------------
    def open_instruction_dialog(self):
        self.root.attributes("-topmost", False)
        help_win = ThemedDialog(self.root, tr("manual_title"), 560, 440, self.is_light_mode)
        t = help_win.t

        def close():
            help_win.finish()
            self.toggle_on_top()

        help_win.protocol("WM_DELETE_WINDOW", close)
        ctk.CTkLabel(help_win, text=tr("manual_heading"), font=("Microsoft YaHei", 14, "bold"),
                     text_color=t["text"]).pack(pady=(12, 5))
        textbox = ctk.CTkTextbox(help_win, width=520, height=290, font=("Microsoft YaHei", 11),
                                 fg_color=t["card"], text_color=t["text"], corner_radius=10,
                                 border_width=1, border_color=t["border"])
        textbox.pack(padx=20, pady=5, fill=ctk.BOTH, expand=True)
        if keyboard is not None:
            hotkey_line = tr("manual_hotkey_on", hotkey=HOTKEY.upper())
        else:
            hotkey_line = tr("manual_hotkey_off")
        textbox.insert("1.0", tr("manual_body", version=self.version_num, hotkey_line=hotkey_line))
        textbox.configure(state="disabled")

        bot_frame = ctk.CTkFrame(help_win, fg_color="transparent")
        bot_frame.pack(side=ctk.BOTTOM, fill=ctk.X, padx=20, pady=10)
        ctk.CTkButton(bot_frame, text=tr("changelog_btn"), width=110, height=32, font=("Microsoft YaHei", 11),
                      fg_color="#0891b2", hover_color="#0e7490",
                      command=self.open_change_history_dialog).pack(side=ctk.LEFT)
        ctk.CTkButton(bot_frame, text=tr("got_it"), width=120, height=32,
                      font=("Microsoft YaHei", 11, "bold"), fg_color=t["primary"],
                      command=close).pack(side=ctk.RIGHT)

    def open_change_history_dialog(self):
        win = ThemedDialog(self.root, tr("changelog_win_title", v=self.version_num), 500, 380, self.is_light_mode)
        t = win.t
        ctk.CTkLabel(win, text=tr("changelog_heading"), font=("Microsoft YaHei", 13, "bold"),
                     text_color=t["text"]).pack(pady=(12, 5))
        box = ctk.CTkTextbox(win, width=460, height=250, font=("Microsoft YaHei", 10), fg_color=t["card"],
                             text_color=t["text"], corner_radius=8, border_width=1, border_color=t["border"])
        box.pack(padx=20, pady=5, fill=ctk.BOTH, expand=True)
        box.insert("1.0", tr("changelog_body", version=self.version_num))
        box.configure(state="disabled")
        ctk.CTkButton(win, text=tr("close"), width=90, height=30, font=("Microsoft YaHei", 11),
                      fg_color=t["cancel"], text_color=t["text"], command=win.finish
                      ).pack(pady=10, side=ctk.BOTTOM)

    # --- language switch -----------------------------------------------------------
    def toggle_language(self):
        set_language("zh" if LANG == "en" else "en")
        self.save_user_preferences()
        self.apply_language()

    def apply_language(self):
        """Re-label every static widget. Replies and category names are never translated."""
        self.root.title(app_title())
        self.check_top.configure(text=tr("always_on_top"))
        self.btn_data_center.configure(text=tr("data_center"))
        self.btn_edit_mode.configure(text=tr("exit_edit") if self.is_edit_mode else tr("edit_mode"))
        self.btn_help.configure(text=tr("manual"))
        self.btn_add_cat.configure(text=tr("add_category"))
        self.btn_add_reply.configure(text=tr("add_reply"))
        self.lang_switch.configure(text=tr("lang_btn"))
        try:
            self.search_entry.configure(placeholder_text=tr("search_ph"))
        except Exception:
            pass
        if self.tray_icon is not None:
            try:
                self.tray_icon.title = tr("tray_tooltip")
                self.tray_icon.update_menu()
            except Exception:
                log.exception("Could not update tray language")
        self.apply_theme_colors()  # also relabels the theme button and rebuilds both panels

    # --- theme switch animation ---------------------------------------------------
    def theme_swap_with_fade(self):
        self.fade_window(start_alpha=1.0, target_alpha=0.2, duration=100, steps=8,
                         callback=self._execute_theme_swap)

    def _execute_theme_swap(self):
        self.is_light_mode = not self.is_light_mode
        self.save_user_preferences()
        self.apply_theme_colors()
        self.fade_window(start_alpha=0.2, target_alpha=1.0, duration=150, steps=10)

    def fade_window(self, start_alpha, target_alpha, duration, steps=10, current_step=0, callback=None):
        try:
            alpha_step = (target_alpha - start_alpha) / steps
            self.root.attributes("-alpha", start_alpha + alpha_step * (current_step + 1))
            if current_step < steps - 1:
                self.root.after(int(duration / steps),
                                lambda: self.fade_window(start_alpha, target_alpha, duration, steps,
                                                         current_step + 1, callback))
            else:
                self.root.attributes("-alpha", target_alpha)
                if callback:
                    callback()
        except Exception:
            log.exception("fade_window failed")
            if callback:
                callback()

    # --- screen-edge auto hide -------------------------------------------------------
    def setup_indicator(self):
        self.indicator = tk.Toplevel(self.root)
        self.indicator.overrideredirect(True)
        self.indicator.attributes("-topmost", True)
        self.indicator.configure(bg="#242936")
        container = ctk.CTkFrame(self.indicator, fg_color="#3b82f6", corner_radius=8, border_width=1,
                                 border_color="#60a5fa", width=self.visible_pixel, height=120)
        container.pack(fill=ctk.BOTH, expand=True)
        lbl = ctk.CTkLabel(container, text="⚡\n\n‹\n‹", font=("Microsoft YaHei", 11, "bold"),
                           text_color="#ffffff")
        lbl.pack(fill=ctk.BOTH, expand=True)
        self.indicator.withdraw()
        self.indicator.update_idletasks()
        lbl.bind("<Enter>", lambda e: self.animate_show())
        container.bind("<Enter>", lambda e: self.animate_show())

    def start_edge_check_loop(self):
        if not self.is_animating and self.root.state() != "withdrawn":
            try:
                win_x, win_y = self.root.winfo_x(), self.root.winfo_y()
                curr_w, curr_h = self.root.winfo_width(), self.root.winfo_height()
                mouse_x, mouse_y = self.root.winfo_pointerx(), self.root.winfo_pointery()
                at_right_edge = (win_x + curr_w) >= (self.screen_width - 15)
                if at_right_edge and not self.is_hidden:
                    if not (win_x <= mouse_x <= win_x + curr_w and win_y <= mouse_y <= win_y + curr_h):
                        self.animate_hide()
                elif self.is_hidden:
                    if mouse_x >= self.screen_width - 2:
                        self.animate_show()
                    elif win_x < self.screen_width - curr_w - 20:
                        self.is_hidden = False
                        self.indicator.withdraw()
            except Exception:
                pass
        self.root.after(300, self.start_edge_check_loop)

    def _slide_window(self, target_x, on_done):
        self.is_animating = True
        win_y = self.root.winfo_y()
        start_x = self.root.winfo_x()
        steps = 10
        dx = (target_x - start_x) / steps

        def step(count):
            if count < steps:
                curr_x = int(start_x + dx * (count + 1))
                self.root.geometry(f"{self.root.winfo_width()}x{self.root.winfo_height()}+{curr_x}+{win_y}")
                self.root.after(15, lambda: step(count + 1))
            else:
                self.is_animating = False
                on_done(win_y)

        step(0)

    def animate_hide(self):
        if self.is_animating:
            return

        def done(win_y):
            self.is_hidden = True
            self.indicator.geometry(
                f"{self.visible_pixel}x120+{self.screen_width - self.visible_pixel}"
                f"+{win_y + int(self.root.winfo_height() / 2) - 60}")
            self.indicator.deiconify()

        self._slide_window(self.screen_width - self.visible_pixel, done)

    def animate_show(self):
        if self.is_animating:
            return
        self.indicator.withdraw()

        def done(_win_y):
            self.is_hidden = False

        self._slide_window(self.screen_width - self.root.winfo_width(), done)

    # --- colours -------------------------------------------------------------------
    def _apply_chosen_color(self, config, color_code):
        mapped = get_mapped_color(color_code, from_light_mode=self.is_light_mode)
        if self.is_light_mode:
            config["light_color"], config["dark_color"] = color_code, mapped
        else:
            config["dark_color"], config["light_color"] = color_code, mapped

    def change_category_color(self):
        cat = self.selected_category_name or self.current_category
        if not cat or cat not in self.data:
            return
        self.root.attributes("-topmost", False)
        color_code = ColorPaletteDialog(self.root, self.is_light_mode, is_category=True).result
        self.toggle_on_top()
        if color_code and isinstance(color_code, str):
            self._apply_chosen_color(self._scope_dict(cat)[cat]["config"], color_code)
            self.current_category = cat
            self._rebuild_data()
            self._save_for(cat)
            self.refresh_left_menu()
            self.refresh_right_buttons()

    def change_reply_color(self):
        sel = self._selected_block()
        if not sel:
            return
        cat, name, items = sel
        self.root.attributes("-topmost", False)
        color_code = ColorPaletteDialog(self.root, self.is_light_mode, is_category=False).result
        self.toggle_on_top()
        if color_code and isinstance(color_code, str):
            self._apply_chosen_color(items[name], color_code)
            self._save_for(cat)
            self.refresh_right_buttons()


if __name__ == "__main__":
    if not check_single_instance():
        sys.exit(0)

    root = ctk.CTk()
    app = FastCopyApp(root)
    root.mainloop()