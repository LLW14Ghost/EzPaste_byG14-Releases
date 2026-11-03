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
import hashlib
import subprocess
import time
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
APP_VERSION = "v0.1.9"

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
    "tray_notify_msg": ("EzPaste is put away. Click its taskbar button or tray icon to bring it back.",
                        "EzPaste 已收起，点击任务栏按钮或托盘图标即可还原。"),
    "tray_ask_close": ("Ask what [X] does", "询问 [X] 的操作"),
    # --- close / put away ---
    "close_title": ("Close EzPaste", "关闭 EzPaste"),
    "close_question": ("What should [X] do?", "点击 [X] 时要怎么做？"),
    "close_away": ("📥 Put away\n(taskbar + tray)", "📥 收起\n（任务栏 + 托盘）"),
    "close_quit": ("⏻ Quit EzPaste", "⏻ 退出 EzPaste"),
    "close_remember": ("Remember my choice", "记住我的选择"),
    "close_reset_done": ("[X] will ask again next time.", "下次点击 [X] 时会再次询问。"),
    "dc_close_reset": ("❔ Ask Again What [X] Does", "❔ 重新询问 [X] 的操作"),
    "tab_show": ("Show EzPaste", "显示 EzPaste"),
    "tab_away": ("Put away", "收起"),
    "tab_quit": ("Quit (Ctrl+Q)", "退出 (Ctrl+Q)"),
    # --- quick start ---
    "qs_title": ("EzPaste Quick Start", "EzPaste 快速上手"),
    "qs_heading": ("🚀 EzPaste in one minute", "🚀 一分钟上手 EzPaste"),
    "qs_btn": ("🚀 Quick Start", "🚀 快速上手"),
    "qs_reopen": ("You can open this again from ❓ Manual.", "以后可以在「❓ 说明」里再次打开。"),
    "qs_copy_h": ("📋 Click a card to copy", "📋 点击卡片即复制"),
    "qs_copy_t": ("Click any reply card and its text is on your clipboard; paste it anywhere. "
                  "Right-click a card to edit, recolour, rename or delete it.",
                  "点击任意回复卡片，内容就会复制到剪贴板，直接粘贴即可。右键卡片可编辑、改颜色、重命名或删除。"),
    "qs_search_h": ("🔍 Search everything", "🔍 全局搜索"),
    "qs_search_t": ("Type in the box at the bottom to find a reply by name or text in every category. Esc clears it.",
                    "在底部搜索框输入，可在所有分类中按名称或内容查找回复，按 Esc 清空。"),
    "qs_keys_h": ("⌨️ Keyboard", "⌨️ 键盘操作"),
    "qs_keys_t": ("Arrow keys move the highlight, Enter copies it. In search, Enter copies the top match. "
                  "Alt+1 to 9 copies the card with that badge. Tab / Shift+Tab (or PageDown / PageUp) switch "
                  "category; Esc clears the search.",
                  "方向键移动高亮，按 Enter 复制。搜索时按 Enter 复制最靠前的匹配项。Alt+1 到 9 复制对应角标的卡片。"
                  "Tab / Shift+Tab（或 PageDown / PageUp）切换分类；Esc 清空搜索。"),
    "qs_edge_h": ("⚡ Tuck it at the screen edge", "⚡ 贴边收起"),
    "qs_edge_t": ("Drag the window to the right edge of your screen. When the mouse leaves, it slides away "
                  "and leaves a blue tab. Rest the mouse on the edge or click the tab to bring it back; "
                  "right-click the tab for Show / Put away / Quit.",
                  "把窗口拖到屏幕右边缘，鼠标离开后会自动滑走，只留下蓝色标签。鼠标停在边缘或点击标签即可展开；"
                  "右键标签可选择 显示 / 收起 / 退出。"),
    "qs_close_h": ("✕ Put away or quit", "✕ 收起或退出"),
    "qs_close_t": ("[X] asks whether to put EzPaste away (taskbar + tray) or quit; tick 'Remember my choice' "
                   "to skip the question. Ctrl+Q quits at once.{hotkey}",
                   "点击 [X] 会询问收起（任务栏 + 托盘）还是退出；勾选“记住我的选择”后不再询问。按 Ctrl+Q 立即退出。{hotkey}"),
    "qs_close_hotkey": (" {hotkey} shows or hides it from anywhere.", "在任何地方按 {hotkey} 可显示或隐藏窗口。"),
    "qs_cat_h": ("📂 Personal or shared categories", "📂 个人或共享分类"),
    "qs_cat_t": ("'+ Category' asks where a category lives: Personal stays on this PC only; Public is shared "
                 "with the team through ⚙️ Data Center's cloud sync. '+ Reply Block' adds a card. "
                 "⭐ Frequent at the top shows the replies you copy most (counted on this PC only).",
                 "「+ 分类」会询问存放位置：个人分类只保存在本机；公共分类通过「⚙️ 数据中心」的云端同步与团队共享。"
                 "「+ 回复块」用于添加卡片。顶部的「⭐ 常用」显示你复制最多的回复（只在本机统计）。"),
    "qs_look_h": ("🌗 Theme and language", "🌗 主题与语言"),
    "qs_look_t": ("The buttons at the bottom right switch light / dark and English / 中文.",
                  "右下角按钮可切换浅色 / 深色模式和 English / 中文。"),
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
    "frequent": ("⭐ Frequent", "⭐ 常用"),
    "frequent_empty": ("Nothing here yet. The replies you copy most often will show up here.",
                       "这里还没有内容。你最常复制的回复会显示在这里。"),
    "frequent_add_hint": ("Pick a normal category first, then add the reply block there.",
                          "请先选择一个普通分类，再在其中添加回复块。"),
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
    "update_prompt": ("New version {v} is available.\nUpdate now? EzPaste will close, install the update and reopen by itself.",
                      "发现新版本 {v}。\n现在更新吗？EzPaste 将自动关闭、安装更新并重新打开。"),
    "update_now": ("Update now", "立即更新"),
    "update_browser": ("Open download page", "打开下载页面"),
    "update_later": ("Later", "稍后"),
    "update_dl_title": ("Downloading Update", "正在下载更新"),
    "update_downloading": ("Downloading EzPaste {v}...", "正在下载 EzPaste {v}..."),
    "update_progress": ("{done} of {total} MB", "{done} / {total} MB"),
    "update_verifying": ("Verifying download...", "正在校验下载文件..."),
    "update_starting": ("Starting installer...", "正在启动安装程序..."),
    "update_failed": ("Update Failed", "更新失败"),
    "update_dl_fail": ("Download failed:\n{msg}", "下载失败：\n{msg}"),
    "update_hash_fail": ("The downloaded file failed its SHA-256 check, so it was deleted and not run.",
                         "下载的文件未通过 SHA-256 校验，已被删除且不会运行。"),
    "update_no_hash": ("This release has no SHA-256 hash to verify the download, so it can't be installed automatically.\nOpen the download page in your browser instead?",
                       "此版本没有可用于校验下载文件的 SHA-256 哈希，因此无法自动安装。\n是否改为在浏览器中打开下载页面？"),
    "update_bad_file": ("The downloaded file is not a valid Windows installer.", "下载的文件不是有效的 Windows 安装程序。"),
    "update_bad_url": ("The update address is not an official GitHub release link, so it was not downloaded.",
                       "更新地址不是官方 GitHub 发布链接，已取消下载。"),
    "update_launch_fail": ("Could not start the installer:\n{msg}", "无法启动安装程序：\n{msg}"),
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
        "Press Esc to clear. While a search is active the docked window will not retract.\n\n"
        "3. 【Frequent】\n"
        "   - The Frequent category at the top of the list shows the replies you copy most. It is built from "
        "a file on this PC only (usage_stats.json) and is never synced, pushed or exported.\n\n"
        "4. 【Keyboard】\n"
        "   - Arrow keys move the highlight over the replies; Enter copies the highlighted one.\n"
        "   - In the search box, Enter copies the top match (it is highlighted for you).\n"
        "   - Alt + 1 to 9 copies the reply with that number badge, even while typing in search.\n"
        "   - Tab / Shift+Tab (or PageDown / PageUp) switch to the next / previous category.\n"
        "   - Esc clears the search.\n\n"
        "5. 【Screen Edge, [X], Tray & Hotkey】\n"
        "   - Drag the window to the right edge of your screen: it tucks away when the mouse leaves. "
        "Rest the mouse on the edge (or click the blue tab) to bring it back; right-click the tab for more.\n"
        "   - [X] asks: put away (taskbar + tray) or quit. Tick 'Remember my choice' to skip the question; "
        "Data Center or the tray menu lets it ask again.\n"
        "   - Ctrl+Q quits at once. EzPaste stays out of Alt+Tab and the taskbar while it is open.\n"
        "{hotkey_line}\n"
        "6. 【Theme & Language】\n"
        "   - Use the Theme and language buttons at the bottom right to switch light/dark mode "
        "and English/中文. Your replies and category names are never translated.",
        "欢迎使用 EzPaste {version}！\n\n"
        "1. 【个人本地 / 公共云端回复】\n"
        "   - 新建分类时可选择【个人本地】（仅保存在本机，永不上传）或【公共云端】（通过仓库与团队共享）。\n\n"
        "2. 【搜索】\n"
        "   - 使用底部搜索框，可跨所有分类按名称或内容查找回复，按 Esc 清空搜索。搜索进行时，贴边窗口不会收起。\n\n"
        "3. 【常用】\n"
        "   - 列表顶部的“常用”分类显示你复制次数最多的回复。它只由本机上的一个文件（usage_stats.json）生成，"
        "不会被同步、推送或导出。\n\n"
        "4. 【键盘操作】\n"
        "   - 方向键移动高亮的回复，按 Enter 复制当前高亮的回复。\n"
        "   - 在搜索框中按 Enter 会复制最靠前的匹配项（它会自动高亮）。\n"
        "   - Alt + 数字 1 到 9 可复制带有对应数字角标的回复，即使正在搜索框中输入也可使用。\n"
        "   - Tab / Shift+Tab（或 PageDown / PageUp）切换到下一个 / 上一个分类。\n"
        "   - Esc 清空搜索。\n\n"
        "5. 【贴边、[X]、托盘与快捷键】\n"
        "   - 把窗口拖到屏幕右边缘：鼠标离开后会自动收起。鼠标停在边缘（或点击蓝色标签）即可展开，右键标签有更多选项。\n"
        "   - 点击 [X] 时会询问：收起（任务栏 + 托盘）或退出。勾选“记住我的选择”后不再询问；可在数据管理中心或托盘菜单中恢复询问。\n"
        "   - 按 Ctrl+Q 立即退出。窗口打开时不会出现在 Alt+Tab 和任务栏中。\n"
        "{hotkey_line}\n"
        "6. 【主题与语言】\n"
        "   - 使用右下角的主题按钮和语言按钮，可切换浅色/深色模式与 English/中文 界面。"
        "你的回复和分类名称不会被翻译。",
    ),
    # --- change log ---
    "changelog_win_title": ("Version Change History - {v}", "版本更新日志 - {v}"),
    "changelog_heading": ("📜 EzPaste Version Change History", "📜 EzPaste 版本更新日志"),
    "changelog_body": (
        "【Current Version: {version}】\n"
        " - Switching light / dark no longer makes the window vanish and reappear like a restart.\n"
        " - Screen-edge hiding rebuilt: minimizing, Win+D and Alt+Tab no longer stop it from working.\n"
        " - Fixed the window growing each time it slid in or out on screens with display scaling above 100%.\n"
        " - Slides out only when the mouse rests on the edge for a moment; smoother slide; docks only on an outer screen edge (multi-monitor).\n"
        " - Out of Alt+Tab / Win+Tab and the taskbar while open; a taskbar button appears while it is put away.\n"
        " - [X] asks: put away or quit, with 'Remember my choice'. Ctrl+Q quits; right-click the blue tab for a menu.\n"
        " - Faster reply list: cards are reused instead of rebuilt on every search, category switch or resize.\n"
        " - New Quick Start guide: shown once on first run, reopen it from ❓ Manual.\n\n"
        "【Version: v0.1.8】\n"
        " - New keyboard navigation: arrow keys move over the replies, Enter copies, Alt+1 to 9 copies the numbered reply, Tab / PageUp / PageDown switch category.\n"
        " - New: Enter in the search box copies the top match.\n"
        " - New Frequent category showing your most-copied replies. It stays on your PC only (usage_stats.json) and is never synced, pushed or exported.\n"
        " - The hotkey now also brings forward a window that is visible but behind other apps, and selects the old search text.\n\n"
        "【Version: v0.1.7】\n"
        " - New Update now button: EzPaste downloads the installer, verifies its SHA-256 hash, installs silently and reopens itself.\n"
        " - Fixed the window retracting to the screen edge too easily, even with the mouse inside it.\n"
        " - The docked window now waits briefly before retracting and never retracts during dialogs, dragging, or while a search is active.\n\n"
        "【Version: v0.1.6】\n"
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
        " - 切换浅色/深色时，窗口不再像重启一样消失再出现。\n"
        " - 重做贴边隐藏：最小化、Win+D、Alt+Tab 后不会再失效。\n"
        " - 修复在显示缩放大于 100% 的屏幕上，窗口每次滑入滑出都会变大的问题。\n"
        " - 鼠标需在边缘停留片刻才会展开；滑动更顺滑；多显示器时只在最外侧边缘贴边。\n"
        " - 窗口打开时不出现在 Alt+Tab / Win+Tab 和任务栏；收起时显示任务栏按钮。\n"
        " - 点击 [X] 可选择收起或退出，并可“记住我的选择”。Ctrl+Q 退出；右键蓝色标签有菜单。\n"
        " - 回复列表更快：搜索、切换分类、调整大小时复用卡片，不再全部重建。\n"
        " - 新增“快速上手”引导：首次打开时显示一次，之后可在「❓ 说明」中再次打开。\n\n"
        "【版本：v0.1.8】\n"
        " - 新增键盘操作：方向键移动高亮，Enter 复制，Alt+1 到 9 复制带数字角标的回复，Tab / PageUp / PageDown 切换分类。\n"
        " - 新增：在搜索框中按 Enter 复制最靠前的匹配项。\n"
        " - 新增“常用”分类，显示你复制最多的回复；仅保存在本机（usage_stats.json），不会同步、推送或导出。\n"
        " - 快捷键现在也能把被其他程序挡住的窗口调到前台，并自动选中上次的搜索文字。\n\n"
        "【版本：v0.1.7】\n"
        " - 新增“立即更新”按钮：自动下载安装程序，校验 SHA-256 哈希，静默安装并自动重新打开。\n"
        " - 修复窗口贴边后过于灵敏、鼠标仍在窗口内也会收起的问题。\n"
        " - 贴边窗口现在会稍作等待再收起，并且在弹窗、拖动窗口或使用搜索时不会收起。\n\n"
        "【版本：v0.1.6】\n"
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
EDGE_HIDE_DELAY = 0.8  # seconds the mouse must stay outside before the docked window retracts
EDGE_MARGIN = 12  # extra pixels around the window that still count as "inside"
FREQUENT_KEY = "__frequent__"  # virtual category: never stored in the data files
FREQUENT_LIMIT = 12  # how many replies the Frequent category shows
PEEK_DELAY = 0.25  # seconds the mouse must rest at the screen edge before a tucked window slides out
EDGE_TAB_PX = 14  # width of the blue tab left on screen while the window is tucked away

# Data lives next to the script / exe (same place as before), no matter
# which directory the app is launched from.
BASE_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

DATA_FILE = BASE_DIR / "clipboard_data.json"
LOCAL_ONLY_FILE = BASE_DIR / "local_replies.json"  # personal replies, never synced
SYNC_CONFIG_FILE = BASE_DIR / "sync_settings.json"
PREFS_FILE = BASE_DIR / "user_prefs.json"
USAGE_FILE = BASE_DIR / "usage_stats.json"  # local-only counters for Frequent; never synced or exported
LOG_FILE = BASE_DIR / "ezpaste.log"


def _find_icon():
    """EzPaste.ico: bundled into the exe by the build, or next to the script while developing."""
    bundle = Path(getattr(sys, "_MEIPASS", BASE_DIR))
    for path in (bundle / "EzPaste.ico", BASE_DIR / "EzPaste.ico", BASE_DIR / "installer" / "EzPaste.ico"):
        if path.is_file():
            return path
    return None


APP_ICON = _find_icon()


def apply_window_icon(window):
    """Use the EzPaste icon for a window (Windows only; harmless if the file is missing)."""
    if APP_ICON is None or sys.platform != "win32":
        return
    try:
        window.iconbitmap(str(APP_ICON))
    except Exception:
        pass

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


class UpdateCancelled(Exception):
    """Raised inside the download worker when the user presses Cancel."""


def pick_update_asset(assets):
    """Choose the release file to download. Returns a dict, or None if the release has no files."""

    def lname(a):
        return str(a.get("name", "")).lower()

    installers = [a for a in assets if lname(a).endswith(".exe") and "setup" in lname(a)]
    packages = [a for a in assets if lname(a).endswith((".exe", ".msi", ".zip"))]
    pool = installers or packages or assets
    if not pool:
        return None
    chosen = pool[0]
    name = str(chosen.get("name", ""))

    # GitHub exposes a "sha256:<hex>" digest for release files; otherwise look for "<file>.sha256"
    digest = str(chosen.get("digest") or "")
    sha = digest.split(":", 1)[1] if digest.lower().startswith("sha256:") else ""
    if not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
        sha = ""
    sidecar = next((a for a in assets
                    if lname(a) in (name.lower() + ".sha256", name.lower() + ".sha256.txt")), None)
    return {
        "name": name,
        "url": chosen.get("browser_download_url") or "",
        "size": int(chosen.get("size") or 0),
        "sha256": sha,
        "sidecar_url": (sidecar.get("browser_download_url") if sidecar else "") or "",
        "installer": bool(installers),
    }


def fetch_sidecar_hash(url):
    """Read a SHA-256 hash from a small 'file.exe.sha256' release asset."""
    if not url or not url.startswith("https://github.com/"):
        return ""
    req = urllib.request.Request(url, headers={"User-Agent": "EzPaste-Updater"})
    with urllib.request.urlopen(req, timeout=15, context=make_ssl_context()) as resp:
        text = resp.read(4096).decode("utf-8", "ignore")
    match = re.search(r"\b[0-9a-fA-F]{64}\b", text)
    return match.group(0) if match else ""


def center_window_on_parent(window, parent, width, height):
    parent.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
    y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


# --- Windows window helpers --------------------------------------------------
class _MonitorInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("rcMonitor", ctypes.c_long * 4),
                ("rcWork", ctypes.c_long * 4), ("dwFlags", ctypes.c_uint32)]


class WinAPI:
    """Small ctypes layer for the main window (Windows only). Every call fails soft: on any
    error, or on another OS, it returns None / False and the caller uses its Tk fallback."""

    def __init__(self):
        self.ok = False
        if sys.platform != "win32":
            return
        try:
            from ctypes import wintypes as w
            u = ctypes.WinDLL("user32", use_last_error=True)  # private copy, shared prototypes untouched
            u.GetParent.argtypes = [w.HWND]
            u.GetParent.restype = w.HWND
            u.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
            u.GetWindowRect.restype = w.BOOL
            u.MonitorFromWindow.argtypes = [w.HWND, w.DWORD]
            u.MonitorFromWindow.restype = w.HMONITOR
            u.MonitorFromPoint.argtypes = [w.POINT, w.DWORD]
            u.MonitorFromPoint.restype = w.HMONITOR
            u.GetMonitorInfoW.argtypes = [w.HMONITOR, ctypes.POINTER(_MonitorInfo)]
            u.GetMonitorInfoW.restype = w.BOOL
            u.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       w.UINT]
            u.SetWindowPos.restype = w.BOOL
            u.SendMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
            u.SendMessageW.restype = ctypes.c_ssize_t
            u.GetForegroundWindow.argtypes = []
            u.GetForegroundWindow.restype = w.HWND
            u.GetAsyncKeyState.argtypes = [ctypes.c_int]
            u.GetAsyncKeyState.restype = ctypes.c_short
            self.u, self.w = u, w
            try:
                d = ctypes.WinDLL("dwmapi")
                d.DwmSetWindowAttribute.argtypes = [w.HWND, w.DWORD, ctypes.c_void_p, w.DWORD]
                d.DwmSetWindowAttribute.restype = ctypes.c_long
                self.dwm = d
            except Exception:
                self.dwm = None
            self.ok = True
        except Exception:
            log.exception("WinAPI setup failed")

    def outer_hwnd(self, widget):
        """The window Windows actually draws (title bar included) for a Tk toplevel."""
        if not self.ok:
            return None
        try:
            return self.u.GetParent(widget.winfo_id()) or widget.winfo_id()
        except Exception:
            return None

    def window_rect(self, hwnd):
        if not (self.ok and hwnd):
            return None
        r = self.w.RECT()
        if self.u.GetWindowRect(hwnd, ctypes.byref(r)):
            return r.left, r.top, r.right, r.bottom
        return None

    def _info(self, hmon):
        if not hmon:
            return None
        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(_MonitorInfo)
        if self.u.GetMonitorInfoW(hmon, ctypes.byref(info)):
            return tuple(info.rcMonitor), tuple(info.rcWork)
        return None

    def monitor_of_window(self, hwnd):
        """(monitor rect, work-area rect) of the screen the window is mostly on."""
        if not (self.ok and hwnd):
            return None
        try:
            return self._info(self.u.MonitorFromWindow(hwnd, 2))  # MONITOR_DEFAULTTONEAREST
        except Exception:
            return None

    def monitor_at(self, x, y):
        """True if some screen contains the point (x, y)."""
        if not self.ok:
            return False
        try:
            return bool(self.u.MonitorFromPoint(self.w.POINT(int(x), int(y)), 0))  # MONITOR_DEFAULTTONULL
        except Exception:
            return False

    def left_button_down(self):
        if not self.ok:
            return False
        try:
            return bool(self.u.GetAsyncKeyState(0x01) & 0x8000)
        except Exception:
            return False

    def set_dark_titlebar(self, hwnd, dark):
        """Recolour the title bar in place. CustomTkinter does this by hiding and re-showing the
        whole window, which looked like the app closing and reopening; we only repaint the frame."""
        if not (self.ok and hwnd and self.dwm):
            return
        try:
            value = ctypes.c_int(1 if dark else 0)
            for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE, then the pre-20H1 number
                if self.dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                    break
            # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
            self.u.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)
            active = 1 if self.u.GetForegroundWindow() == hwnd else 0
            self.u.SendMessageW(hwnd, 0x0086, 1 - active, 0)  # WM_NCACTIVATE: flip, then back,
            self.u.SendMessageW(hwnd, 0x0086, active, 0)  # so Windows repaints the title bar now
        except Exception:
            log.exception("Title bar recolour failed")


WIN = WinAPI()


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
        # CustomTkinter puts its own icon on new windows after ~200 ms; ours goes on after that
        self.after(300, lambda: apply_window_icon(self))
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


class QuickStartDialog(ThemedDialog):
    """Short first-run guide (like the OMS Toolkit's 快速上手). Not blocking; reopen from ❓ Manual."""

    SECTIONS = ("copy", "search", "keys", "edge", "close", "cat", "look")

    def __init__(self, parent, is_light, hotkey_text=""):
        super().__init__(parent, tr("qs_title"), 540, 520, is_light)
        t = self.t
        ctk.CTkLabel(self, text=tr("qs_heading"), font=("Microsoft YaHei", 15, "bold"),
                     text_color=t["text"]).pack(pady=(14, 6))
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill=ctk.BOTH, expand=True, padx=16, pady=(0, 4))
        for key in self.SECTIONS:
            card = ctk.CTkFrame(body, fg_color=t["card"], corner_radius=10, border_width=1, border_color=t["border"])
            card.pack(fill=ctk.X, pady=5, padx=2)
            ctk.CTkLabel(card, text=tr(f"qs_{key}_h"), font=("Microsoft YaHei", 12, "bold"), text_color=t["text"],
                         anchor="w", justify="left").pack(fill=ctk.X, padx=12, pady=(8, 2))
            text = tr(f"qs_{key}_t", hotkey=hotkey_text) if key == "close" else tr(f"qs_{key}_t")
            ctk.CTkLabel(card, text=text, font=("Microsoft YaHei", 11), text_color=t["text"], anchor="w",
                         justify="left", wraplength=450).pack(fill=ctk.X, padx=12, pady=(0, 9))
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill=ctk.X, side=ctk.BOTTOM, padx=18, pady=(4, 12))
        ctk.CTkLabel(bottom, text=tr("qs_reopen"), font=("Microsoft YaHei", 10), text_color=t["muted"]
                     ).pack(side=ctk.LEFT)
        ok = ctk.CTkButton(bottom, text=tr("got_it"), width=120, height=32, font=("Microsoft YaHei", 11, "bold"),
                           fg_color=t["primary"], command=self.finish)
        ok.pack(side=ctk.RIGHT)
        self.bind("<Escape>", lambda e: self.finish())
        self.bind("<Return>", lambda e: self.finish())
        ok.focus_set()


class CloseChoiceDialog(ThemedDialog):
    """Asked when [X] is clicked. Result: ("away" | "quit", remember: bool) or None (cancelled)."""

    def __init__(self, parent, is_light):
        super().__init__(parent, tr("close_title"), 360, 190, is_light)
        t = self.t
        ctk.CTkLabel(self, text=tr("close_question"), font=("Microsoft YaHei", 12, "bold"),
                     text_color=t["text"]).pack(pady=(15, 8))
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(padx=20, pady=4, fill=ctk.X)
        self.remember = tk.BooleanVar(value=False)
        away = ctk.CTkButton(frame, text=tr("close_away"), width=150, height=48,
                             font=("Microsoft YaHei", 10, "bold"), fg_color="#2563eb", hover_color="#1d4ed8",
                             command=lambda: self.finish(("away", self.remember.get())))
        away.pack(side=ctk.LEFT, padx=5)
        ctk.CTkButton(frame, text=tr("close_quit"), width=150, height=48,
                      font=("Microsoft YaHei", 10, "bold"), fg_color=t["danger"], text_color=t["danger_text"],
                      hover_color=t["danger_hover"],
                      command=lambda: self.finish(("quit", self.remember.get()))).pack(side=ctk.RIGHT, padx=5)
        ctk.CTkCheckBox(self, text=tr("close_remember"), variable=self.remember, font=("Microsoft YaHei", 10),
                        text_color=t["text"], checkbox_width=18, checkbox_height=18).pack(pady=(12, 0))
        self.bind("<Escape>", lambda e: self.cancel())
        self.bind("<Return>", lambda e: self.finish(("away", self.remember.get())))
        away.focus_set()
        self.wait_window()


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------
class UpdateDialog(ThemedDialog):
    """Result: "now" (install inside the app), "browser" (open the download page) or None (later)."""

    def __init__(self, parent, version, is_light, can_install):
        super().__init__(parent, tr("new_version_title"), 460, 200, is_light)
        t = self.t
        text = tr("update_prompt", v=version) if can_install else tr("new_version_msg", v=version)
        ctk.CTkLabel(self, text=text, font=("Microsoft YaHei", 12), text_color=t["text"],
                     wraplength=410, justify="left").pack(anchor="w", padx=25, pady=(22, 8))

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(padx=20, pady=14, fill=ctk.X, side=ctk.BOTTOM)
        if can_install:
            ctk.CTkButton(frame, text=tr("update_now"), width=110, height=32,
                          font=("Microsoft YaHei", 11, "bold"), fg_color=t["primary"],
                          command=lambda: self.finish("now")).pack(side=ctk.RIGHT, padx=(8, 0))
        ctk.CTkButton(frame, text=tr("update_browser"), width=140, height=32, font=("Microsoft YaHei", 11),
                      fg_color=t["btn"], text_color=t["btn_text"], hover_color=t["btn_hover"],
                      command=lambda: self.finish("browser")).pack(side=ctk.RIGHT)
        ctk.CTkButton(frame, text=tr("update_later"), width=80, height=32, font=("Microsoft YaHei", 11),
                      fg_color=t["cancel"], text_color=t["text"],
                      command=self.cancel).pack(side=ctk.LEFT)
        self.wait_window()


class DownloadDialog(ThemedDialog):
    """Progress window for the update download. It does not block; the app updates it from a worker."""

    def __init__(self, parent, version, is_light, on_cancel):
        super().__init__(parent, tr("update_dl_title"), 400, 170, is_light)
        t = self.t
        self._on_cancel = on_cancel
        self.status = ctk.CTkLabel(self, text=tr("update_downloading", v=version),
                                   font=("Microsoft YaHei", 12, "bold"), text_color=t["text"])
        self.status.pack(pady=(20, 8))
        self.bar = ctk.CTkProgressBar(self, width=340)
        self.bar.set(0)
        self.bar.pack(pady=4)
        self.detail = ctk.CTkLabel(self, text="", font=("Microsoft YaHei", 10), text_color=t["muted"])
        self.detail.pack(pady=(4, 0))
        self.cancel_btn = ctk.CTkButton(self, text=tr("cancel"), width=90, height=28,
                                        font=("Microsoft YaHei", 11), fg_color=t["cancel"],
                                        text_color=t["text"], command=self.cancel)
        self.cancel_btn.pack(pady=12, side=ctk.BOTTOM)

    def set_progress(self, fraction, text):
        self.bar.set(max(0.0, min(1.0, fraction)))
        self.detail.configure(text=text)

    def set_status(self, text):
        self.status.configure(text=text)
        self.cancel_btn.configure(state="disabled")  # too late to cancel once we are verifying/installing

    def cancel(self):
        self._on_cancel()
        self.finish(None)


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
        self._modal_count = 0  # > 0 while a dialog or message box is open (never retract then)
        self._card_cache = {}  # (category, reply name) -> reusable reply card widgets
        self._no_results_label = None
        self.right_click_event = "<Button-2>" if self.root.tk.call("tk", "windowingsystem") == "aqua" else "<Button-3>"

        self.is_light_mode = self.load_user_preferences()
        self.root.title(app_title())

        self.cloud_data = self.load_data()
        self.local_data = self.load_local_data()
        self.data = {}
        self._rebuild_data()
        self.usage = self.load_usage()  # local-only "most used" counters (never synced)
        self._frequent_cache = None
        self._shown_entries = []  # (category, name, info) for the cards on screen
        self._card_buttons = []
        self._highlight = None  # keyboard-selected card index
        self.current_category = self._initial_category()

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

        self.setup_window_states()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close_window)
        self.root.bind_all("<Control-q>", lambda e: self._quit())
        self.root.bind_all("<Control-Q>", lambda e: self._quit())
        self.tray_icon = None
        self.setup_system_tray()
        self.setup_hotkey()
        self.setup_keyboard()

        self.root.after(100, self._poll_ui_queue)
        self.root.after(500, lambda: self.sync_pull_from_cloud(silent=True))
        self.root.after(2000, lambda: self.check_for_app_updates(manual_check=False))
        if not self.prefs.get("quickstart_seen"):
            self.root.after(900, self.show_quick_start_first_run)

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
        self._modal_count += 1
        try:
            fn = {"info": messagebox.showinfo, "warn": messagebox.showwarning,
                  "error": messagebox.showerror}[kind]
            fn(title, text, parent=self.root)
        finally:
            self._modal_count -= 1
            self.toggle_on_top()

    def _ask(self, title, text):
        self.root.attributes("-topmost", False)
        self._modal_count += 1
        try:
            return messagebox.askyesno(title, text, parent=self.root)
        finally:
            self._modal_count -= 1
            self.toggle_on_top()

    def _file_dialog(self, dialog_fn, **kwargs):
        self._modal_count += 1
        try:
            return dialog_fn(**kwargs)
        finally:
            self._modal_count -= 1

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
        self.prefs = prefs if isinstance(prefs, dict) else {}
        if self.prefs.get("close_action") not in ("away", "quit"):
            self.prefs.pop("close_action", None)  # unknown value: ask again
        set_language(self.prefs.get("language", "en"))
        return self.prefs.get("theme_mode", "dark") == "light"

    def save_user_preferences(self):
        try:
            self.prefs.update({"theme_mode": "light" if self.is_light_mode else "dark", "language": LANG})
            atomic_write_json(PREFS_FILE, self.prefs)
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
        if APP_ICON is not None:
            try:
                icon = Image.open(APP_ICON)
                icon.size = (64, 64)  # pick the 64 px frame of the .ico
                return icon.convert("RGBA")
            except Exception:
                log.exception("Could not load the tray icon")
        image = Image.new("RGB", (64, 64), color="#1e222b")
        dc = ImageDraw.Draw(image)
        dc.rectangle([16, 16, 48, 48], fill="#3b82f6")
        dc.text((22, 22), "EP", fill="white")
        return image

    def setup_system_tray(self):
        def run_tray():
            menu = pystray.Menu(
                pystray.MenuItem(lambda item: tr("tray_restore"), self.restore_from_tray, default=True),
                pystray.MenuItem(lambda item: tr("tray_ask_close"), lambda icon, item: self.post(self.reset_close_choice),
                                 visible=lambda item: "close_action" in self.prefs),
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

    def _toggle_visibility(self):  # global hotkey
        if self.mode == "away" or self.root.state() in ("withdrawn", "iconic"):
            self._do_restore()
        elif self.mode == "tucked":
            self._do_restore()  # slide out and focus search
        elif self._app_has_focus():
            self.put_away(taskbar=False)  # quick hide: tray only, the hotkey brings it back
        else:
            self._do_restore()  # visible but behind other apps: bring it forward and focus search

    def on_close_window(self):
        """[X]: put away or quit, as chosen (and optionally remembered) by the user."""
        choice = self.prefs.get("close_action")
        if choice is None:
            self._modal_count += 1
            try:
                self.root.attributes("-topmost", False)
                answer = CloseChoiceDialog(self.root, self.is_light_mode).result
            finally:
                self._modal_count -= 1
                self.toggle_on_top()
            if not answer:
                return
            choice, remember = answer
            if remember:
                self.prefs["close_action"] = choice
                self.save_user_preferences()
                self._refresh_tray_menu()
        if choice == "quit":
            self._quit()
            return
        first_time = not self.prefs.get("away_notified")
        self.put_away(taskbar=True)
        if first_time and self.tray_icon:  # explain once where it went, not every time
            self.prefs["away_notified"] = True
            self.save_user_preferences()
            try:
                self.tray_icon.notify(tr("tray_notify_msg"), tr("tray_notify_title"))
            except Exception:
                pass

    def reset_close_choice(self):
        self.prefs.pop("close_action", None)
        self.save_user_preferences()
        self._refresh_tray_menu()
        if self.mode != "away":
            self._msg("info", tr("close_title"), tr("close_reset_done"))

    def _refresh_tray_menu(self):
        if self.tray_icon is not None:
            try:
                self.tray_icon.update_menu()
            except Exception:
                pass

    def restore_from_tray(self, icon=None, item=None):  # runs on the tray thread
        self.post(self._do_restore)

    def _do_restore(self):
        if self.mode == "tucked":
            self.show_from_edge()
        else:
            self.root.deiconify()
            if self.mode == "away":
                self._return_from_away()
        self._refresh_frequent_view()
        self.root.lift()
        self.root.focus_force()
        self.toggle_on_top()
        try:
            self.search_entry.focus_set()
            self.search_entry.select_range(0, tk.END)
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
        try:
            if self.tray_icon:
                self.tray_icon.stop()
        except Exception:
            pass
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
        if not self._category_valid(self.current_category):
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
                    info = pick_update_asset(assets)
                    self.post(lambda: self.prompt_update_dialog(latest, info))
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

    def prompt_update_dialog(self, new_version, info):
        can_install = bool(info and info.get("installer") and info.get("url") and sys.platform == "win32")
        self.root.attributes("-topmost", False)
        choice = UpdateDialog(self.root, new_version, self.is_light_mode, can_install).result
        self.toggle_on_top()
        if choice == "now" and can_install:
            self.start_update_install(new_version, info)
        elif choice == "browser":
            self._open_download_page(info)

    def _open_download_page(self, info=None):
        webbrowser.open((info or {}).get("url") or f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases")

    def start_update_install(self, version, info):
        """Download the installer, verify its SHA-256, then run it silently and exit."""
        url = info.get("url", "")
        if not url.startswith("https://github.com/"):
            self._msg("error", tr("update_failed"), tr("update_bad_url"))
            return

        cancel_event = threading.Event()
        dlg = DownloadDialog(self.root, version, self.is_light_mode, cancel_event.set)
        state = {"last": 0.0}

        def on_ui(fn):
            """Run fn on the UI thread, but only while the progress window is still open."""
            def runner():
                try:
                    if dlg.winfo_exists():
                        fn()
                except tk.TclError:
                    pass
            self.post(runner)

        def close_dialog():
            try:
                dlg.finish(None)
            except Exception:
                pass

        def fail(message, fallback=False):
            def show():
                close_dialog()
                if fallback:
                    if self._ask(tr("update_failed"), message):
                        self._open_download_page(info)
                else:
                    self._msg("error", tr("update_failed"), message)
            self.post(show)

        def worker():
            tmp_dir = None
            try:
                expected = info.get("sha256") or fetch_sidecar_hash(info.get("sidecar_url"))
                if not expected:
                    fail(tr("update_no_hash"), fallback=True)
                    return

                tmp_dir = tempfile.mkdtemp(prefix="ezpaste_update_")
                file_name = re.sub(r"[^\w.\-]", "_", os.path.basename(info.get("name") or "EzPaste_Setup.exe"))
                dest = os.path.join(tmp_dir, file_name)
                req = urllib.request.Request(url, headers={"User-Agent": "EzPaste-Updater"})
                digest = hashlib.sha256()
                with urllib.request.urlopen(req, timeout=20, context=make_ssl_context()) as resp, \
                        open(dest, "wb") as out:
                    total = int(resp.headers.get("Content-Length") or info.get("size") or 0)
                    done = 0
                    while True:
                        if cancel_event.is_set():
                            raise UpdateCancelled()
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        out.write(chunk)
                        digest.update(chunk)
                        done += len(chunk)
                        now = time.monotonic()
                        if now - state["last"] >= 0.1:
                            state["last"] = now
                            done_mb = f"{done / 1048576:.1f}"
                            if total:
                                text = tr("update_progress", done=done_mb, total=f"{total / 1048576:.1f}")
                                frac = done / total
                            else:
                                text, frac = f"{done_mb} MB", 0.0
                            on_ui(lambda f=frac, s=text: dlg.set_progress(f, s))

                on_ui(lambda: dlg.set_status(tr("update_verifying")))
                if digest.hexdigest().lower() != expected.lower():
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    fail(tr("update_hash_fail"))
                    return
                with open(dest, "rb") as f:
                    if f.read(2) != b"MZ":  # not a Windows executable
                        shutil.rmtree(tmp_dir, ignore_errors=True)
                        fail(tr("update_bad_file"))
                        return
                self.post(lambda: self._launch_installer(dest, dlg))
            except UpdateCancelled:
                if tmp_dir:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception as e:
                log.exception("Update download failed")
                if tmp_dir:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                fail(tr("update_dl_fail", msg=str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _launch_installer(self, path, dlg):
        try:
            dlg.set_status(tr("update_starting"))
        except Exception:
            pass
        try:
            # ping -n 3 waits about 2 seconds so this process has exited (and released its
            # single-instance lock) before the installer starts. /SILENT shows only a progress bar;
            # the installer reuses the existing folder and leaves your shortcuts alone.
            subprocess.Popen(
                ["cmd.exe", "/c", "ping", "127.0.0.1", "-n", "3", ">nul", "&", path,
                 "/SILENT", "/NOCANCEL", "/CLOSEAPPLICATIONS", "/NORESTART"],
                creationflags=0x08000000 | 0x00000200,  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True)
        except Exception as e:
            log.exception("Could not start installer")
            try:
                dlg.finish(None)
            except Exception:
                pass
            self._msg("error", tr("update_failed"), tr("update_launch_fail", msg=str(e)))
            return
        self._quit()

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
        self.apply_titlebar_theme()

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

        # Virtual "Frequent" category (built from the local usage file, never synced)
        freq_selected = self.current_category == FREQUENT_KEY
        if freq_selected:
            f_btn = "#333333" if light else "#ffffff"
            f_txt = "#ffffff" if light else "#11111b"
            f_hov = "#4b5563" if light else "#e6e6e6"
        elif light:
            f_btn, f_txt, f_hov = adjust_brightness(default_cat, 1.1), "#333333", adjust_brightness(default_cat, 0.9)
        else:
            f_btn, f_txt, f_hov = adjust_brightness(default_cat, 0.8), "#e2e8f0", adjust_brightness(default_cat, 1.1)
        freq_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        freq_frame.pack(fill=ctk.X, padx=4, pady=3)
        ctk.CTkButton(freq_frame, text=tr("frequent"), fg_color=f_btn, text_color=f_txt, hover_color=f_hov,
                      height=36, corner_radius=6, anchor="w",
                      font=("Microsoft YaHei", 11, "bold" if freq_selected else "normal"),
                      command=lambda: self.switch_category(FREQUENT_KEY)).pack(fill=ctk.X, expand=True)

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
        elif self.current_category == FREQUENT_KEY:
            entries = self._frequent_entries()
        elif self.current_category in self.data:
            for name, info in self.data[self.current_category]["items"].items():
                entries.append((self.current_category, name, info))
        return entries

    def refresh_right_buttons(self):
        """Show the reply cards for the current category, Frequent or search. Cards are kept and
        reused: building CustomTkinter widgets is slow, so search, category switches and resizing
        only rearrange existing cards and build the ones that are new or changed."""
        light = self.is_light_mode
        t = self.theme
        searching = bool(self.search_query.strip())
        frequent_view = (not searching) and self.current_category == FREQUENT_KEY
        show_cat_hint = searching or frequent_view

        self.right_scroll.configure(fg_color=t["bg"])
        for canvas_attr in ("_parent_canvas", "_canvas", "canvas"):
            if hasattr(self.right_scroll, canvas_attr):
                try:
                    getattr(self.right_scroll, canvas_attr).configure(bg=t["bg"])
                except Exception:
                    pass

        entries = self._visible_entries()
        self._set_highlight(None)  # cards are reused: take the old keyboard highlight off first
        self._shown_entries = entries
        self._card_buttons = []
        if self._no_results_label is not None:
            self._no_results_label.grid_forget()

        wanted = set()
        cols = self.current_columns
        show_arrows = self.is_edit_mode and not searching and not frequent_view
        for index, (cat, btn_name, btn_info) in enumerate(entries):
            text_content = btn_info["text"]
            dark_c = valid_hex(btn_info.get("dark_color"), DEFAULT_ITEM_DARK)
            light_c = valid_hex(btn_info.get("light_color"), DEFAULT_ITEM_LIGHT)
            if light:
                colors = (light_c, "#eae2cf", "#2c2c2c", "#666666")
            else:
                colors = (adjust_brightness(dark_c, 0.6), adjust_brightness(dark_c, 0.8), "#ffffff", "#bfc7d5")
            look = (text_content, colors, t["border"], t["arrow_bg"], t["arrow_text"], show_arrows)

            if show_cat_hint:
                hint_txt = f"📂 {cat}"
            elif self.is_edit_mode:
                hint_txt = tr("edit_active")
            else:
                hint_txt = tr("click_copy")

            key = (cat, btn_name)
            card = self._card_cache.get(key)
            if card is None or card["look"] != look:
                if card is not None:
                    card["frame"].destroy()
                card = self._build_card(cat, btn_name, text_content, colors, show_arrows, hint_txt)
                card["look"] = look
                self._card_cache[key] = card
            elif card["hint"] != hint_txt:
                card["sub"].configure(text=hint_txt)
                card["hint"] = hint_txt

            badge_n = index + 1 if index < 9 else None  # Alt+1 ... Alt+9 copy the first nine cards
            if card["badge_n"] != badge_n:
                if badge_n is None:
                    card["badge"].place_forget()
                else:
                    card["badge"].configure(text=f"Alt+{badge_n}")
                    card["badge"].place(relx=0.96, rely=0.94, anchor="se")
                card["badge_n"] = badge_n

            card["frame"].grid(row=index // cols, column=index % cols, padx=12, pady=12)
            self._card_buttons.append(card["btn"])
            wanted.add(key)

        for key, card in list(self._card_cache.items()):
            if key in wanted:
                continue
            cat, name = key
            if cat not in self.data or name not in self.data[cat]["items"]:  # deleted or renamed
                card["frame"].destroy()
                del self._card_cache[key]
            else:
                card["frame"].grid_forget()

        if not entries and (searching or frequent_view):
            if self._no_results_label is None:
                self._no_results_label = ctk.CTkLabel(self.right_scroll, text="", font=("Microsoft YaHei", 12),
                                                      wraplength=420)
            self._no_results_label.configure(text=tr("no_results") if searching else tr("frequent_empty"),
                                             text_color=t["muted"])
            self._no_results_label.grid(row=0, column=0, padx=20, pady=30)

        if searching and self._card_buttons:
            self._set_highlight(0, scroll=False)  # Enter copies the top match

    def _build_card(self, cat, btn_name, text_content, colors, show_arrows, hint_txt):
        bg_color, hover_color, title_text_color, sub_text_color = colors
        t = self.theme

        def copy(_event=None, c=cat, n=btn_name, tx=text_content):
            self.copy_reply(c, n, tx)

        def on_right(event, name=btn_name, c=cat):
            self.show_reply_popup_panel(event, name, c)

        card_frame = ctk.CTkFrame(self.right_scroll, fg_color="transparent", width=280, height=95)
        card_frame.grid_propagate(False)

        btn = ctk.CTkButton(card_frame, text="", fg_color=bg_color, hover_color=hover_color,
                            width=225 if show_arrows else 265, height=90, corner_radius=12,
                            border_width=1, border_color=t["border"], command=copy)
        btn.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True)

        label_title = ctk.CTkLabel(btn, text=f"【{btn_name}】", font=("Microsoft YaHei", 12, "bold"),
                                   text_color=title_text_color)
        label_title.place(relx=0.5, rely=0.3, anchor="center")
        label_sub = ctk.CTkLabel(btn, text=hint_txt, font=("Microsoft YaHei", 10), text_color=sub_text_color)
        label_sub.place(relx=0.5, rely=0.68, anchor="center")
        badge = ctk.CTkLabel(btn, text="", font=("Microsoft YaHei", 9), text_color=sub_text_color)  # placed by refresh

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

        for w in (btn, label_title, label_sub, badge):
            w.bind(self.right_click_event, on_right)
        for w in (label_title, label_sub, badge):
            w.bind("<Button-1>", copy)
        return {"frame": card_frame, "btn": btn, "sub": label_sub, "hint": hint_txt, "badge": badge, "badge_n": None}

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
        ] + ([(tr("dc_close_reset"), self.reset_close_choice)] if "close_action" in self.prefs else []),
            self.is_light_mode)

    def import_json_config(self):
        self.root.attributes("-topmost", False)
        file_path = self._file_dialog(filedialog.askopenfilename, title=tr("import_dlg_title"),
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
        file_path = self._file_dialog(filedialog.asksaveasfilename, title=tr("export_dlg_title"), initialdir=desktop_path,
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
                self.rename_usage_block(cat, name, new_name)
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
                self.rename_usage_category(old, new)
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
            if self.current_category == name or not self._category_valid(self.current_category):
                self.current_category = self._first_category()
            if was_local:
                self.save_local_data()
            else:
                self.save_data()
            self.refresh_left_menu()
            self.refresh_right_buttons()

    def switch_category(self, category):
        self._clear_search()
        if category == FREQUENT_KEY:
            self._frequent_cache = None  # recompute the ranking each time it is opened
        self.current_category = category
        for canvas_attr in ("_parent_canvas", "_canvas", "canvas"):
            if hasattr(self.right_scroll, canvas_attr):
                try:
                    getattr(self.right_scroll, canvas_attr).yview_moveto(0.0)
                except Exception:
                    pass
        self.refresh_left_menu()
        self.refresh_right_buttons()

    # --- local-only usage counters (feed the "Frequent" category) -------------------
    def load_usage(self):
        raw = load_json_file(USAGE_FILE)
        usage = {}
        if isinstance(raw, dict):
            for cat, blocks in raw.items():
                if not isinstance(blocks, dict):
                    continue
                for name, rec in blocks.items():
                    try:
                        n = int(rec.get("n", 0))
                        t = float(rec.get("t", 0))
                    except (AttributeError, TypeError, ValueError):
                        continue
                    if n > 0:
                        usage.setdefault(str(cat), {})[str(name)] = {"n": n, "t": t}
        return usage

    def save_usage(self):
        try:
            atomic_write_json(USAGE_FILE, self.usage)
        except Exception:
            log.exception("Saving usage counters failed")  # not worth interrupting the person for

    def record_usage(self, cat, name):
        rec = self.usage.setdefault(cat, {}).setdefault(name, {"n": 0, "t": 0.0})
        rec["n"] += 1
        rec["t"] = time.time()
        self.save_usage()

    def rename_usage_block(self, cat, old, new):
        blocks = self.usage.get(cat)
        if blocks and old in blocks:
            blocks[new] = blocks.pop(old)
            self.save_usage()
            self._frequent_cache = None

    def rename_usage_category(self, old, new):
        if old in self.usage:
            self.usage[new] = self.usage.pop(old)
            self.save_usage()
            self._frequent_cache = None

    def _frequent_keys(self):
        """(category, name) pairs, most used first. Cached so the cards don't reshuffle while you
        are using them; the cache is dropped when you switch to the Frequent category."""
        if self._frequent_cache is None:
            ranked = []
            for cat, blocks in self.usage.items():
                items = self.data.get(cat, {}).get("items", {})
                for name, rec in blocks.items():
                    if name in items:
                        ranked.append((-rec["n"], -rec["t"], cat, name))
            ranked.sort()
            self._frequent_cache = [(cat, name) for _n, _t, cat, name in ranked[:FREQUENT_LIMIT]]
        return self._frequent_cache

    def _frequent_entries(self):
        """Entries for the Frequent view. Each one carries its real category, so edit, rename,
        colour and delete act on the original reply."""
        entries = []
        for cat, name in self._frequent_keys():
            info = self.data.get(cat, {}).get("items", {}).get(name)
            if info is not None:
                entries.append((cat, name, info))
        return entries

    def _refresh_frequent_view(self):
        if self.current_category == FREQUENT_KEY and not self.search_query.strip():
            self._frequent_cache = None
            self.refresh_right_buttons()

    def _initial_category(self):
        return FREQUENT_KEY if self._frequent_keys() else self._first_category()

    def _category_valid(self, cat):
        return cat == FREQUENT_KEY or cat in self.data

    def copy_reply(self, cat, name, text):
        self.record_usage(cat, name)
        self.copy_to_clipboard(text)

    # --- keyboard navigation ------------------------------------------------------------
    def setup_keyboard(self):
        self.root.bind("<Key>", self._on_key)
        for n in range(1, 10):
            self.root.bind(f"<Alt-Key-{n}>", lambda event, i=n - 1: self._copy_nth(i))

    def _app_has_focus(self):
        try:
            return self.root.focus_get() is not None
        except Exception:
            return True

    def _search_has_focus(self):
        try:
            focused = self.root.focus_get()
            return focused is not None and str(focused).startswith(str(self.search_entry))
        except Exception:
            return False

    def _sync_search_now(self):
        """Apply what is typed in the search box right away (the normal update is debounced)."""
        current = self.search_entry.get()
        if current != self.search_query or self._refresh_job is not None:
            if self._refresh_job is not None:
                try:
                    self.root.after_cancel(self._refresh_job)
                except Exception:
                    pass
                self._refresh_job = None
            self.search_query = current
            self.refresh_right_buttons()

    def _on_key(self, event):
        key = event.keysym
        if key in ("Up", "Down"):
            self._sync_search_now()
            self._move_highlight(0, -1 if key == "Up" else 1)
        elif key in ("Left", "Right") and not self._search_has_focus():
            self._move_highlight(-1 if key == "Left" else 1, 0)
        elif key in ("Return", "KP_Enter"):
            self._sync_search_now()
            self._copy_highlighted()
        elif key == "Escape":
            if self.search_query.strip() or self.search_entry.get():
                self._clear_search()
                self.refresh_right_buttons()
            else:
                self._set_highlight(None)
        elif key in ("Tab", "ISO_Left_Tab", "Prior", "Next"):
            backwards = key in ("ISO_Left_Tab", "Prior") or (key == "Tab" and bool(event.state & 0x1))
            self._cycle_category(-1 if backwards else 1)
        else:
            return None
        return "break"

    def _move_highlight(self, dx, dy):
        count = len(self._shown_entries)
        if not count:
            return
        if self._highlight is None:
            new = 0
        else:
            new = self._highlight + dx + dy * max(1, self.current_columns)
        self._set_highlight(max(0, min(count - 1, new)))

    def _copy_highlighted(self):
        idx = self._highlight
        if idx is None and self.search_query.strip() and self._shown_entries:
            idx = 0  # nothing chosen yet: Enter copies the top search match
        if idx is None or not (0 <= idx < len(self._shown_entries)):
            return False
        self._copy_nth(idx)
        return True

    def _copy_nth(self, index):
        self._sync_search_now()
        if 0 <= index < len(self._shown_entries):
            cat, name, info = self._shown_entries[index]
            self._set_highlight(index, scroll=False)
            self.copy_reply(cat, name, info["text"])
        return "break"

    def _set_highlight(self, index, scroll=True):
        """Mark one card as the keyboard selection (None clears it)."""
        old = self._highlight
        if old is not None and 0 <= old < len(self._card_buttons):
            try:
                self._card_buttons[old].configure(border_width=1, border_color=self.theme["border"])
            except tk.TclError:
                pass
        self._highlight = index
        if index is not None and 0 <= index < len(self._card_buttons):
            btn = self._card_buttons[index]
            try:
                btn.configure(border_width=3, border_color="#3b82f6")
            except tk.TclError:
                pass
            if scroll:
                self._scroll_card_into_view(btn)

    def _scroll_card_into_view(self, btn):
        try:
            canvas = self.right_scroll._parent_canvas
            self.right_scroll.update_idletasks()
            total = max(1, self.right_scroll.winfo_height())
            card = btn.master  # the fixed-size card frame in the grid
            top = card.winfo_y()
            bottom = top + card.winfo_height()
            first, last = canvas.yview()
            if top / total < first:
                canvas.yview_moveto(max(0.0, (top - 12) / total))
            elif bottom / total > last:
                canvas.yview_moveto(min(1.0, (bottom + 12) / total - (last - first)))
        except Exception:
            pass

    def _cycle_category(self, step):
        order = [FREQUENT_KEY] + list(self.data.keys())
        try:
            i = order.index(self.current_category)
        except ValueError:
            i = 0
        self.switch_category(order[(i + step) % len(order)])

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
        if cat == FREQUENT_KEY:
            self._msg("info", tr("frequent"), tr("frequent_add_hint"))
            return
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
        ctk.CTkButton(bot_frame, text=tr("qs_btn"), width=110, height=32, font=("Microsoft YaHei", 11),
                      fg_color="#6366f1", hover_color="#4f46e5",
                      command=self.open_quick_start).pack(side=ctk.LEFT, padx=(8, 0))
        ctk.CTkButton(bot_frame, text=tr("got_it"), width=120, height=32,
                      font=("Microsoft YaHei", 11, "bold"), fg_color=t["primary"],
                      command=close).pack(side=ctk.RIGHT)

    def show_quick_start_first_run(self):
        if self.prefs.get("quickstart_seen") or self.mode != "shown":
            return
        self.prefs["quickstart_seen"] = True  # once only, even if it is closed with [X]
        self.save_user_preferences()
        self.open_quick_start()

    def open_quick_start(self):
        hotkey = tr("qs_close_hotkey", hotkey=HOTKEY.upper()) if keyboard is not None else ""
        self.root.attributes("-topmost", False)
        dlg = QuickStartDialog(self.root, self.is_light_mode, hotkey)
        dlg.bind("<Destroy>", lambda e: self.toggle_on_top() if e.widget is dlg else None, add="+")
        return dlg

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

    # --- window states: shown / tucked at the screen edge / put away --------------------
    #  "shown"  : a normal window. When its right side touches the outer right edge of its
    #             screen ("docked"), it tucks away once the mouse has been outside it briefly.
    #  "tucked" : slid off that edge; only the blue tab stays visible. Resting the mouse on
    #             the edge (or clicking the tab) slides it back.
    #  "away"   : put away by [X], the hotkey, or Windows minimizing it. Any way back
    #             (taskbar button, tray, hotkey) returns it to "shown".
    # One check runs every 100 ms and moves between these states. Each state is handled
    # explicitly, so minimizing, Win+D and Alt+Tab can no longer leave it half hidden.
    def setup_window_states(self):
        self.mode = "shown"
        self.is_animating = False
        self._anim_started = 0.0
        self._anim_job = None
        self.visible_pixel = EDGE_TAB_PX
        self._dock_right = None  # x of the screen edge the window is tucked against
        self._dock_vrange = None  # (top, bottom) of that screen
        self._outside_since = None
        self._peek_since = None
        self._last_toggle = 0.0
        self._away_taskbar = False
        self._last_edge_error = None
        self.setup_indicator()
        self._set_tool_window(True)  # no Alt+Tab / Win+Tab entry and no taskbar button while open
        self.root.after(200, self.apply_titlebar_theme)  # the outer frame exists once mapped
        self.start_edge_check_loop()

    def apply_titlebar_theme(self):
        WIN.set_dark_titlebar(WIN.outer_hwnd(self.root), not self.is_light_mode)

    def _set_tool_window(self, on):
        """Tool window = small title bar, not in Alt+Tab / Win+Tab, no taskbar button.
        Tk rebuilds the outer frame for this, so the title bar colour is applied again."""
        if sys.platform != "win32":
            return
        try:
            self.root.attributes("-toolwindow", bool(on))
            self.root.after(30, self.apply_titlebar_theme)
        except Exception:
            log.exception("Could not change the tool-window style")

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
        # Hovering is handled by the edge check (with the peek delay); a click shows it at once.
        for w in (container, lbl):
            w.bind("<Button-1>", lambda e: self.show_from_edge())
            w.bind(self.right_click_event, self._show_tab_menu)

    def _show_tab_menu(self, event):
        menu = tk.Menu(self.indicator, tearoff=0)
        menu.add_command(label=tr("tab_show"), command=self.show_from_edge)
        menu.add_command(label=tr("tab_away"), command=lambda: self.put_away(taskbar=True))
        menu.add_separator()
        menu.add_command(label=tr("tab_quit"), command=self._quit)
        self._peek_since = None
        self._modal_count += 1  # don't slide out underneath the open menu
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
            self.root.after(300, self._end_tab_menu)

    def _end_tab_menu(self):
        self._modal_count = max(0, self._modal_count - 1)
        self._last_toggle = time.monotonic()

    # --- geometry helpers --------------------------------------------------------------
    def _window_rect(self):
        """Outer window rectangle (title bar and borders included) in screen pixels."""
        rect = WIN.window_rect(WIN.outer_hwnd(self.root))
        if rect:
            return rect
        x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
        return x - 8, y - 40, x + self.root.winfo_width() + 8, y + self.root.winfo_height() + 8

    def _screen_areas(self):
        """(monitor rect, work-area rect) of the screen the window is on."""
        areas = WIN.monitor_of_window(WIN.outer_hwnd(self.root))
        if areas:
            return areas
        full = (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        return full, full

    def _dock_edge(self, rect):
        """x of the screen edge the window is docked against, or None. Only the outer right
        edge counts: if another screen continues to the right, tucking would just push the
        window onto that screen."""
        left, top, right, bottom = rect
        mon, work = self._screen_areas()
        edge = work[2]
        if not (edge - 15 <= right and left < edge):
            return None
        if WIN.monitor_at(mon[2] + 2, max(mon[1], min(mon[3] - 1, (top + bottom) // 2))):
            return None
        self._dock_vrange = (mon[1], mon[3])
        return edge

    def _move_outer_left(self, x, y=None):
        """Move the window so its outer left edge is at x. Position only: the old code also
        passed the size, which CustomTkinter multiplies by the Windows display scaling, so on
        screens set above 100 % the window grew every time it slid in or out."""
        if y is None:
            y = self._window_rect()[1]
        tk.Tk.wm_geometry(self.root, f"+{int(x)}+{int(y)}")

    # --- the check ---------------------------------------------------------------------
    def start_edge_check_loop(self):
        try:
            self._edge_check()
        except Exception as exc:
            if repr(exc) != self._last_edge_error:  # log each new problem once, not 10x a second
                self._last_edge_error = repr(exc)
                log.exception("Edge check failed")
        try:
            self.root.after(100, self.start_edge_check_loop)
        except tk.TclError:
            pass  # window destroyed

    def _edge_check(self):
        now = time.monotonic()
        if self.is_animating:
            if now - self._anim_started > 2.0:  # safety net: a slide can never block for good
                self.is_animating = False
            return

        state = self.root.state()
        if self.mode == "away":
            if state in ("normal", "zoomed"):  # brought back from the taskbar, tray or another way
                self._return_from_away()
            return
        if state == "iconic":  # Windows minimized it (Win+M, Win+D, …): treat as put away
            self.put_away(taskbar=True)
            return
        if state == "withdrawn":  # hidden some other way: keep the books straight
            self.indicator.withdraw()
            self.mode = "away"
            return

        rect = self._window_rect()
        mx, my = self.root.winfo_pointerx(), self.root.winfo_pointery()

        if self.mode == "tucked":
            self._outside_since = None
            left = rect[0]
            if left < self._dock_right - self.visible_pixel - 30:  # moved back on screen some other way
                self.mode = "shown"
                self.indicator.withdraw()
                self._peek_since = None
                return
            vtop, vbottom = self._dock_vrange or (-10 ** 6, 10 ** 6)
            at_edge = self._dock_right - 3 <= mx <= self._dock_right + 1 and vtop <= my < vbottom
            on_tab = self._pointer_on_tab(mx, my)
            if (at_edge or on_tab) and self._modal_count == 0 and now - self._last_toggle >= 0.4:
                if self._peek_since is None:
                    self._peek_since = now
                elif now - self._peek_since >= PEEK_DELAY:
                    self._peek_since = None
                    self.show_from_edge()
            else:
                self._peek_since = None
            return

        # mode == "shown"
        self._peek_since = None
        edge = self._dock_edge(rect)
        if edge is None:
            self._outside_since = None
            return
        left, top, right, bottom = rect
        m = EDGE_MARGIN
        inside = (left - m <= mx <= right + m) and (top - m <= my <= bottom + m)
        if inside or self._keep_visible() or now - self._last_toggle < 1.0:
            self._outside_since = None
            return
        # The mouse has to stay outside for EDGE_HIDE_DELAY seconds in a row before we tuck.
        if self._outside_since is None:
            self._outside_since = now
        elif now - self._outside_since >= EDGE_HIDE_DELAY:
            self._outside_since = None
            self.tuck(edge)

    def _pointer_on_tab(self, mx, my):
        try:
            if not self.indicator.winfo_viewable():
                return False
            x, y = self.indicator.winfo_rootx(), self.indicator.winfo_rooty()
            return x <= mx <= x + self.indicator.winfo_width() and y <= my <= y + self.indicator.winfo_height()
        except tk.TclError:
            return False

    def _keep_visible(self):
        """True while the window must NOT tuck away: a dialog or menu is open, a mouse button
        is held (dragging or selecting), or a search is in use."""
        if self._modal_count > 0:
            return True
        if self.search_query.strip():  # an active search keeps the window open until it is cleared
            return True
        try:
            for w in self.root.winfo_children():
                if isinstance(w, tk.Toplevel) and w is not self.indicator and w.winfo_viewable():
                    return True
        except tk.TclError:
            pass
        if WIN.left_button_down():
            return True
        try:
            focused = self.root.focus_get()
            if focused is not None and str(focused).startswith(str(self.search_entry)):
                return True
        except Exception:
            pass
        return False

    # --- moves -------------------------------------------------------------------------
    def _slide_to(self, target_x, on_done):
        """Ease-out slide of the whole window to an outer-left x, then on_done()."""
        self.is_animating = True
        self._anim_started = time.monotonic()
        left, top = self._window_rect()[:2]
        start_x, steps = left, 9

        def step(i):
            try:
                t = i / steps
                eased = 1 - (1 - t) ** 3
                self._move_outer_left(start_x + (target_x - start_x) * eased, top)
                if i < steps:
                    self._anim_job = self.root.after(12, lambda: step(i + 1))
                    return
            except Exception:
                log.exception("Slide failed")
            self.is_animating = False
            self._anim_job = None
            on_done()

        step(1)

    def tuck(self, edge):
        if self.is_animating or self.mode != "shown":
            return
        self._dock_right = edge
        self._slide_to(edge - self.visible_pixel, self._on_tucked)

    def _on_tucked(self):
        self.mode = "tucked"
        self._last_toggle = time.monotonic()
        top, bottom = self._window_rect()[1], self._window_rect()[3]
        vtop, vbottom = self._dock_vrange or (top, bottom)
        y = max(vtop, min(vbottom - 120, (top + bottom) // 2 - 60))
        self.indicator.geometry(f"{self.visible_pixel}x120+{self._dock_right - self.visible_pixel}+{y}")
        self.indicator.deiconify()
        self.indicator.lift()

    def show_from_edge(self):
        if self.is_animating or self.mode != "tucked":
            return
        self.indicator.withdraw()
        left, top, right, bottom = self._window_rect()

        def done():
            self.mode = "shown"
            self._last_toggle = time.monotonic()
            self._outside_since = None
            try:
                self.root.lift()
                self.toggle_on_top()
            except tk.TclError:
                pass

        self._slide_to(self._dock_right - (right - left), done)

    def put_away(self, taskbar=True):
        """Hide the window. taskbar=True: minimized with a taskbar button (plus the tray icon);
        False: tray icon only."""
        if self._anim_job is not None:
            try:
                self.root.after_cancel(self._anim_job)
            except Exception:
                pass
            self._anim_job = None
            self.is_animating = False
        if self.mode == "tucked" and self._dock_right is not None:
            left, _t, right, _b = self._window_rect()
            self._move_outer_left(self._dock_right - (right - left))  # come back fully on screen
        self.indicator.withdraw()
        self._peek_since = self._outside_since = None
        self.mode = "away"
        self._away_taskbar = bool(taskbar) and sys.platform == "win32"
        if self._away_taskbar:
            if self.root.state() != "iconic":
                self.root.withdraw()  # change the style while hidden, so nothing flickers
            self._set_tool_window(False)  # an ordinary window gets a taskbar button again
            self.root.iconify()
        else:
            self.root.withdraw()

    def _return_from_away(self):
        self.mode = "shown"
        self._last_toggle = time.monotonic()
        if self._away_taskbar:
            self._away_taskbar = False
            self._set_tool_window(True)  # out of the taskbar and Alt+Tab again
        self._refresh_frequent_view()
        try:
            self.toggle_on_top()
            self.root.lift()
            self.search_entry.focus_set()
            self.search_entry.select_range(0, tk.END)
        except Exception:
            pass

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

    # CustomTkinter recolours the Windows title bar by hiding and re-showing the whole window,
    # which made a theme switch look like the app closing and reopening. We repaint it ourselves.
    ctk.CTk._deactivate_windows_window_header_manipulation = True
    root = ctk.CTk()
    apply_window_icon(root)
    app = FastCopyApp(root)
    root.mainloop()
