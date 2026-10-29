import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import json
import os
import urllib.request
import urllib.error
import ssl  # 🌟 统一在头部导入，完美解决 SSL 证书验证失败问题

DATA_FILE = "clipboard_data.json"
SYNC_CONFIG_FILE = "sync_settings.json"

# --- GitHub 应用更新配置 ---
GITHUB_REPO_OWNER = "LLW14Ghost"
GITHUB_REPO_NAME = "EzPaste_byG14-Releases"  # 您的 .exe Releases 公开仓库名

# --- 限定美学颜色池 ---
DARK_THEME_COLORS = ["#35363a", "#2c3e50", "#27ae60", "#2980b9", "#8e44ad", "#c0392b"]
LIGHT_THEME_COLORS = ["#fffdf9", "#f2ebd9", "#e2d7bd", "#d4e6d5", "#d6e4f0", "#f5dcd7"]


def get_mapped_color(chosen_color, from_light_mode):
    source_pool = LIGHT_THEME_COLORS if from_light_mode else DARK_THEME_COLORS
    target_pool = DARK_THEME_COLORS if from_light_mode else LIGHT_THEME_COLORS
    try:
        idx = source_pool.index(chosen_color)
        return target_pool[idx]
    except ValueError:
        return target_pool


DEFAULT_DATA = {
    "通用话术": {
        "config": {"dark_color": "#2c3e50", "light_color": "#eae2cf"},
        "items": {
            "欢迎": {"text": "Hello dear customer, how may I help you today?",
                     "dark_color": "#35363a", "light_color": "#fffdf9"},
            "请稍等": {"text": "Please wait for just a moment, thank you!",
                       "dark_color": "#35363a", "light_color": "#fffdf9"}
        }
    }
}


def center_window_on_parent(window, parent, width, height):
    parent.update_idletasks()
    parent_x = parent.winfo_x()
    parent_y = parent.winfo_y()
    parent_w = parent.winfo_width()
    parent_h = parent.winfo_height()
    x = parent_x + (parent_w // 2) - (width // 2)
    y = parent_y + (parent_h // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


class CTKModernActionPopup(ctk.CTkToplevel):
    def __init__(self, parent, title, options, is_light_mode):
        super().__init__(parent)
        self.title(title)
        width = 240
        height = 65 + (len(options) * 45)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        center_window_on_parent(self, parent, width, height)
        bg = "#f7f4eb" if is_light_mode else "#1e222b"
        txt_c = "#333333" if is_light_mode else "#ffffff"
        card_bg = "#fffdf9" if is_light_mode else "#242936"
        self.configure(fg_color=bg)
        self.lift()
        self.focus_force()
        self.grab_set()

        title_lbl = ctk.CTkLabel(self, text=title, font=("Microsoft YaHei", 12, "bold"), text_color=txt_c)
        title_lbl.pack(pady=(12, 10))

        container = ctk.CTkFrame(self, fg_color=card_bg, corner_radius=10,
                                 border_width=1, border_color="#eae2cf" if is_light_mode else "#2e3547")
        container.pack(fill=ctk.BOTH, expand=True, padx=15, pady=(0, 15))

        for label, callback in options:
            if "删除" in label:
                btn_fg = "#fee2e2" if is_light_mode else "#c0392b"
                btn_txt = "#991b1b" if is_light_mode else "#ffffff"
                btn_hov = "#fca5a5" if is_light_mode else "#e74c3c"
            else:
                btn_fg = "#eae2cf" if is_light_mode else "#2a3142"
                btn_txt = "#333333" if is_light_mode else "#ffffff"
                btn_hov = "#dcd3bc" if is_light_mode else "#4f5d75"

            btn = ctk.CTkButton(container, text=label, font=("Microsoft YaHei", 11, "bold"),
                                fg_color=btn_fg, text_color=btn_txt, hover_color=btn_hov,
                                height=34, corner_radius=6, command=lambda cb=callback: self.trigger(cb))
            btn.pack(fill=ctk.X, padx=12, pady=6)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def trigger(self, callback):
        self.grab_release()
        self.destroy()
        callback()


class ColorPaletteDialog(ctk.CTkToplevel):
    def __init__(self, parent, is_light_mode, is_category=False):
        super().__init__(parent)
        self.title("选择主题色彩")
        width, height = 320, 180
        self.resizable(False, False)
        self.attributes("-topmost", True)
        center_window_on_parent(self, parent, width, height)
        self.configure(fg_color="#1e222b" if not is_light_mode else "#f7f4eb")
        self.result = None
        self.lift()
        self.focus_force()
        self.grab_set()

        title_text = "请指定左侧侧栏颜色:" if is_category else "请指定快捷方块底色:"
        txt_c = "#ffffff" if not is_light_mode else "#333333"
        lbl = ctk.CTkLabel(self, text=title_text, font=("Microsoft YaHei", 12, "bold"), text_color=txt_c)
        lbl.pack(pady=(15, 10))

        colors_to_show = LIGHT_THEME_COLORS if is_light_mode else DARK_THEME_COLORS
        grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        grid_frame.pack(padx=20, pady=5)
        for i, color in enumerate(colors_to_show):
            row = i // 3
            col = i % 3
            btn = ctk.CTkButton(grid_frame, text="", fg_color=color, hover_color=color,
                                width=75, height=36, corner_radius=6, border_width=1, border_color="#cccccc",
                                command=lambda c=color: self.select_color(c))
            btn.grid(row=row, column=col, padx=8, pady=8)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.wait_window()

    def select_color(self, color):
        self.result = color
        self.grab_release()
        self.destroy()

    def close(self):
        self.result = None
        self.grab_release()
        self.destroy()


class ModernInputDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, prompt, is_light, initial_value=""):
        super().__init__(parent)
        self.title(title)
        width, height = 400, 170
        self.resizable(False, False)
        self.attributes("-topmost", True)
        center_window_on_parent(self, parent, width, height)
        bg = "#f7f4eb" if is_light else "#1e222b"
        txt = "#333333" if is_light else "#cdd6f4"
        box_bg = "#fffdf9" if is_light else "#242936"
        self.configure(fg_color=bg)
        self.result = None
        self.lift()
        self.focus_force()
        self.grab_set()

        label = ctk.CTkLabel(self, text=prompt, font=("Microsoft YaHei", 12, "bold"), text_color=txt)
        label.pack(anchor="w", padx=20, pady=(15, 5))
        self.entry = ctk.CTkEntry(self, width=360, font=("Microsoft YaHei", 11),
                                  fg_color=box_bg, text_color=txt, corner_radius=6,
                                  border_width=1, border_color="#eae2cf" if is_light else "#2e3547")
        self.entry.pack(padx=20, pady=5)
        if initial_value:
            self.entry.insert(0, initial_value)
            self.entry.select_range(0, tk.END)
        self.entry.focus_set()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=20, pady=12, fill=ctk.X, side=ctk.BOTTOM)
        ok_btn = ctk.CTkButton(btn_frame, text="确 定", width=80, height=28, font=("Microsoft YaHei", 11, "bold"),
                               fg_color="#2b3e50" if is_light else "#3b82f6", command=self.on_ok)
        ok_btn.pack(side=ctk.RIGHT, padx=(10, 0))
        cancel_btn = ctk.CTkButton(btn_frame, text="取 消", fg_color="#e2d7bd" if is_light else "#45475a",
                                   text_color=txt, width=80, height=28, font=("Microsoft YaHei", 11),
                                   command=self.on_cancel)
        cancel_btn.pack(side=ctk.RIGHT)
        self.entry.bind("<Return>", lambda e: self.on_ok())
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.wait_window()

    def on_ok(self):
        self.result = self.entry.get()
        self.grab_release()
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


class ModernLargeTextDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, prompt, is_light, initial_value=""):
        super().__init__(parent)
        self.title(title)
        width, height = 500, 320
        self.resizable(False, False)
        self.attributes("-topmost", True)
        center_window_on_parent(self, parent, width, height)
        bg = "#f7f4eb" if is_light else "#1e222b"
        txt = "#333333" if is_light else "#cdd6f4"
        box_bg = "#fffdf9" if is_light else "#242936"
        self.configure(fg_color=bg)
        self.result = None
        self.initial_value = initial_value
        self.lift()
        self.focus_force()
        self.grab_set()

        label = ctk.CTkLabel(self, text=prompt, font=("Microsoft YaHei", 12, "bold"), text_color=txt)
        label.pack(anchor="w", padx=20, pady=(15, 5))
        self.textbox = ctk.CTkTextbox(self, width=460, height=180, font=("Microsoft YaHei", 11),
                                      fg_color=box_bg, text_color=txt, corner_radius=10,
                                      border_width=1, border_color="#eae2cf" if is_light else "#2e3547")
        self.textbox.pack(padx=20, pady=5, fill=ctk.BOTH, expand=True)
        if self.initial_value:
            self.textbox.insert("1.0", self.initial_value)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=20, pady=15, fill=ctk.X, side=ctk.BOTTOM)
        ok_btn = ctk.CTkButton(btn_frame, text="确 定", width=90, height=32, font=("Microsoft YaHei", 11, "bold"),
                               fg_color="#2b3e50" if is_light else "#3b82f6", command=self.on_ok)
        ok_btn.pack(side=ctk.RIGHT, padx=(10, 0))
        cancel_btn = ctk.CTkButton(btn_frame, text="取 消", fg_color="#e2d7bd" if is_light else "#45475a",
                                   text_color=txt, width=90, height=32, font=("Microsoft YaHei", 11),
                                   command=self.on_cancel)
        cancel_btn.pack(side=ctk.RIGHT)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.wait_window()

    def on_ok(self):
        self.result = self.textbox.get("1.0", "end-1c")
        self.grab_release()
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


class FastCopyApp:
    def __init__(self, root):
        self.root = root
        # 🌟 版本升级为 v0.1.3 稳定版
        self.version_num = "v0.1.3"
        self.dev_signature = "Developed by G14"
        self.root.title(f"客服快捷回复助手 {self.version_num}")

        self.width = 800
        self.height = 480
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.resizable(True, True)
        self.root.attributes("-topmost", True)
        self.root.configure(fg_color="#1e222b")

        self.is_light_mode = False
        self.data = self.load_data()

        categories = list(self.data.keys())
        if categories:
            first_cat = categories[0]
            self.current_category = str(first_cat[0]) if isinstance(first_cat, (list, tuple)) else str(first_cat)
        else:
            self.current_category = ""

        self.selected_btn_name = ""
        self.selected_category_name = ""
        self.is_edit_mode = False
        self.current_columns = 2

        self.setup_ui()
        self.apply_theme_colors()

        self.screen_width = self.root.winfo_screenwidth()
        self.is_hidden = False
        self.is_animating = False
        self.visible_pixel = 14

        self.setup_indicator()
        self.start_edge_check_loop()

        self.root.after(500, lambda: self.sync_pull_from_cloud(silent=True))
        self.root.after(2000, lambda: self.check_for_app_updates(manual_check=False))

    def load_sync_config(self):
        """读取本地保存的同步配置（同时支持旧版字符串和新版字典格式）"""
        try:
            if os.path.exists(SYNC_CONFIG_FILE):
                with open(SYNC_CONFIG_FILE, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, dict):
                        return content.get("sync_url", "").strip(), content.get("token", "").strip()
                    elif isinstance(content, str):
                        return content.strip(), ""
        except Exception as e:
            print(f"读取同步配置异常: {e}")
        return "", ""

    def save_sync_config(self, url, token):
        """持久化保存同步链接与对应 Token 秘钥"""
        try:
            with open(SYNC_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"sync_url": url.strip(), "token": token.strip()}, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存同步配置异常: {e}")

    def configure_sync_url(self):
        """配置私有 API 链接及访问 Token"""
        self.root.attributes("-topmost", False)
        curr_url, curr_token = self.load_sync_config()

        dialog_url = ModernInputDialog(
            self.root,
            "云端同步链接配置",
            "请输入您的 GitHub API 链接 (如 api.github.com/...):",
            self.is_light_mode,
            initial_value=curr_url
        )
        new_url = dialog_url.result
        if new_url is not None:
            dialog_token = ModernInputDialog(
                self.root,
                "配置访问令牌 (PAT)",
                "请输入您的 GitHub Personal Access Token (PAT) 以便安全访问私有仓库:",
                self.is_light_mode,
                initial_value=curr_token
            )
            new_token = dialog_token.result
            if new_token is not None:
                self.save_sync_config(new_url, new_token)
                if new_url.strip():
                    messagebox.showinfo("保存成功",
                                        "云端同步配置及私有 Token 已安全保存！\n点击确定后将立即尝试拉取同步。")
                    self.sync_pull_from_cloud(silent=False)
                else:
                    messagebox.showinfo("已清空", "云端同步配置已清空。")
        self.toggle_on_top()

    def sync_pull_from_cloud(self, silent=True):
        """支持私有仓库 (Private Repo) 安全拉取 JSON 数据"""
        target_url, token = self.load_sync_config()
        if not target_url:
            if not silent:
                messagebox.showwarning("未配置", "检测到您尚未配置云端同步链接，请先在【数据管理中心】进行配置。")
            return

        try:
            context = ssl._create_unverified_context()
            headers = {
                'User-Agent': 'EzPaste-Client',
                'Cache-Control': 'no-cache',
                'Accept': 'application/vnd.github.v3.raw'
            }
            if token:
                headers['Authorization'] = f'Bearer {token}'

            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=6, context=context) as response:
                cloud_data = json.loads(response.read().decode('utf-8'))
                validated_data = self.load_data(cloud_data)
                if validated_data and len(validated_data.keys()) > 0:
                    self.data = validated_data
                    self.save_data()
                    categories = list(self.data.keys())
                    self.current_category = categories[0] if categories else ""
                    self.apply_theme_colors()
                    if not silent:
                        messagebox.showinfo("同步成功", "已成功从您的私有云端仓库安全拉取最新配置！")
                else:
                    if not silent:
                        messagebox.showwarning("格式警告", "云端返回的数据格式不匹配。")
        except urllib.error.HTTPError as e:
            if not silent:
                messagebox.showerror("同步失败 (404/403)",
                                     f"访问私有仓库被拒绝或路径错误 (HTTP {e.code})。\n请确认您的 API 链接格式正确且 Token 权限完整。")
        except Exception as e:
            print(f"云端同步拉取失败: {e}")
            if not silent:
                messagebox.showerror("同步失败", f"无法连接或解析该链接:\n{e}")

    def check_for_app_updates(self, manual_check=False):
        api_url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"
        try:
            context = ssl._create_unverified_context()
            req = urllib.request.Request(
                api_url,
                headers={'User-Agent': 'EzPaste-Updater', 'Accept': 'application/vnd.github.v3+json'}
            )
            with urllib.request.urlopen(req, timeout=6, context=context) as response:
                release_data = json.loads(response.read().decode('utf-8'))
                latest_version = release_data.get("tag_name", "").strip()

                if latest_version and latest_version != self.version_num:
                    download_url = None
                    assets = release_data.get("assets", [])
                    if assets:
                        download_url = assets[0].get("browser_download_url")
                    self.prompt_update_dialog(latest_version, download_url)
                else:
                    if manual_check:
                        messagebox.showinfo("检查更新", f"当前版本 ({self.version_num}) 已是最新版本，无需更新！")
        except Exception as e:
            print(f"检查应用更新失败: {e}")
            if manual_check:
                messagebox.showerror("检查更新", f"无法连接到 GitHub 检查更新，请检查网络连接:\n{e}")

    def prompt_update_dialog(self, new_version, download_url):
        self.root.attributes("-topmost", False)
        if messagebox.askyesno("发现新版本软件", f"检测到有新版本 ({new_version}) 发布！是否立即前往下载更新？"):
            import webbrowser
            if download_url:
                webbrowser.open(download_url)
            else:
                webbrowser.open(f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases")
        self.toggle_on_top()

    def push_data_to_github(self):
        _, saved_token = self.load_sync_config()
        self.root.attributes("-topmost", False)
        dialog = ModernInputDialog(
            self.root,
            "安全验证推送",
            "请输入您的 GitHub Personal Access Token (PAT):",
            self.is_light_mode,
            initial_value=saved_token
        )
        token = dialog.result
        self.toggle_on_top()

        if not token or not token.strip():
            return

        target_url, _ = self.load_sync_config()
        if not target_url:
            messagebox.showwarning("未配置", "请先配置您的专属云端同步链接！")
            return

        try:
            # 自动从 api.github.com/repos/OWNER/REPO/contents/PATH 提取信息
            parts = target_url.replace("https://api.github.com/repos/", "").split("/")
            owner = parts[0]
            repo_name = parts[1]
            file_path = "/".join(parts[4:])  # 跳过 contents 关键字

            if not os.path.exists(DATA_FILE):
                messagebox.showerror("错误", "找不到本地的 clipboard_data.json 文件。")
                return

            with open(DATA_FILE, "r", encoding="utf-8") as f:
                local_content = f.read()

            import base64
            encoded_content = base64.b64encode(local_content.encode("utf-8")).decode("utf-8")

            api_get_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{file_path}"
            headers = {
                "Authorization": f"Bearer {token.strip()}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "EzPaste-Client"
            }

            context = ssl._create_unverified_context()
            req_get = urllib.request.Request(api_get_url, headers=headers)
            sha = ""
            try:
                with urllib.request.urlopen(req_get, context=context) as response:
                    file_info = json.loads(response.read().decode("utf-8"))
                    sha = file_info.get("sha", "")
            except Exception:
                pass

            payload = {
                "message": f"Update clipboard_data.json via EzPaste App ({self.version_num})",
                "content": encoded_content,
                "branch": "main"
            }
            if sha:
                payload["sha"] = sha

            req_put_data = json.dumps(payload).encode("utf-8")
            req_put = urllib.request.Request(api_get_url, data=req_put_data, headers=headers, method="PUT")

            with urllib.request.urlopen(req_put, context=context) as response:
                if response.status in [200, 201]:
                    messagebox.showinfo("推送成功", "您的更改已成功加密推送并同步到私有 GitHub 仓库！")
                else:
                    messagebox.showwarning("提示", f"推送返回状态码: {response.status}")

        except Exception as e:
            messagebox.showerror("推送失败", f"无法推送到 GitHub，请检查您的 Token 权限或网络:\n{e}")

    def load_data(self, data_dict=None):
        try:
            if data_dict is None:
                if os.path.exists(DATA_FILE):
                    with open(DATA_FILE, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                    if not raw_data or not isinstance(raw_data, dict):
                        return DEFAULT_DATA
                else:
                    return DEFAULT_DATA
            else:
                raw_data = data_dict

            fixed_data = {}
            for cat, content in raw_data.items():
                clean_cat = str(cat[0]).strip() if isinstance(cat, (list, tuple)) and len(cat) > 0 else str(cat).strip()
                if not clean_cat: continue

                if isinstance(content, dict) and "items" in content and "config" in content:
                    fixed_data[clean_cat] = content
                else:
                    fixed_data[clean_cat] = {"config": {"dark_color": "#242936", "light_color": "#eae2cf"}, "items": {}}
                    items_source = content.get("items", content) if isinstance(content, dict) else content
                    if isinstance(items_source, dict):
                        for btn, btn_info in items_source.items():
                            text_val = btn_info.get("text", "") if isinstance(btn_info, dict) else str(btn_info)
                            d_c = btn_info.get("dark_color", "#242936") if isinstance(btn_info, dict) else "#242936"
                            l_c = btn_info.get("light_color", "#fffdf9") if isinstance(btn_info, dict) else "#fffdf9"
                            fixed_data[clean_cat]["items"][btn] = {"text": text_val, "dark_color": d_c,
                                                                   "light_color": l_c}

            return fixed_data if fixed_data else DEFAULT_DATA
        except Exception:
            return DEFAULT_DATA

    def save_data(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存失败: {e}")

    def setup_ui(self):
        self.top_frame = ctk.CTkFrame(self.root, height=50, corner_radius=0)
        self.top_frame.pack(fill=ctk.X, side=ctk.TOP)

        self.always_on_top_var = tk.BooleanVar(value=True)
        self.check_top = ctk.CTkCheckBox(self.top_frame, text="始终置顶", variable=self.always_on_top_var,
                                         font=("Microsoft YaHei", 10, "bold"), command=self.toggle_on_top,
                                         checkbox_width=18, checkbox_height=18)
        self.check_top.pack(side=ctk.LEFT, padx=15, pady=10)

        self.btn_data_center = ctk.CTkButton(self.top_frame, text="⚙️ 数据管理中心", width=120, height=30,
                                             font=("Microsoft YaHei", 10, "bold"), fg_color="#16a34a",
                                             hover_color="#15803d",
                                             command=self.open_data_management_popup)
        self.btn_data_center.pack(side=ctk.LEFT, padx=5, pady=10)

        self.btn_edit_mode = ctk.CTkButton(self.top_frame, text="🛠️ 进入编辑模式", width=110, height=30,
                                           font=("Microsoft YaHei", 10, "bold"), fg_color="#0891b2",
                                           hover_color="#0e7490", command=self.toggle_edit_mode)
        self.btn_edit_mode.pack(side=ctk.LEFT, padx=5, pady=10)

        self.btn_help = ctk.CTkButton(self.top_frame, text="❓ 使用说明", width=85, height=30,
                                      font=("Microsoft YaHei", 10, "bold"), fg_color="#6366f1", hover_color="#4f46e5",
                                      command=self.open_instruction_dialog)
        self.btn_help.pack(side=ctk.LEFT, padx=5, pady=10)

        self.btn_add_cat = ctk.CTkButton(self.top_frame, text="+ 新增话术分类", font=("Microsoft YaHei", 10, "bold"),
                                         height=30, corner_radius=6, command=self.add_category)
        self.btn_add_cat.pack(side=ctk.RIGHT, padx=10, pady=10)

        self.btn_add_reply = ctk.CTkButton(self.top_frame, text="+ 追加方块回复", font=("Microsoft YaHei", 10, "bold"),
                                           height=30, corner_radius=6, command=self.add_new_reply_button)
        self.btn_add_reply.pack(side=ctk.RIGHT, padx=5, pady=10)

        self.left_panel = ctk.CTkScrollableFrame(self.root, width=160, corner_radius=0)
        self.left_panel.pack(fill=tk.Y, side=ctk.LEFT)
        self.make_scroll_faster(self.left_panel)

        self.right_main_container = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        self.right_main_container.pack(fill=ctk.BOTH, expand=True, side=ctk.LEFT)

        self.right_scroll = ctk.CTkScrollableFrame(self.right_main_container, corner_radius=0, fg_color="transparent")
        self.right_scroll.pack(fill=ctk.BOTH, expand=True, side=ctk.TOP)
        self.make_scroll_faster(self.right_scroll)

        self.right_main_container.bind("<Configure>", self.on_right_scroll_configure)

        self.bot_status_bar = ctk.CTkFrame(self.right_main_container, height=34, corner_radius=0,
                                           fg_color="transparent")
        self.bot_status_bar.pack(fill=ctk.X, side=ctk.BOTTOM, padx=10, pady=4)

        self.theme_switch = ctk.CTkButton(self.bot_status_bar, text="💡 切换到浅色模式", width=120, height=26,
                                          font=("Microsoft YaHei", 9, "bold"), fg_color="#4b5563",
                                          hover_color="#374151", command=self.theme_swap_with_fade)
        self.theme_switch.pack(side=ctk.RIGHT)

    def make_scroll_faster(self, scrollable_frame):
        canvas = None
        for child in scrollable_frame.winfo_children():
            if isinstance(child, tk.Canvas):
                canvas = child
                break
        if not canvas:
            for attr in ["_canvas", "canvas"]:
                if hasattr(scrollable_frame, attr):
                    canvas = getattr(scrollable_frame, attr)
                    break

        if canvas:
            def _on_mousewheel(event):
                if event.delta:
                    move = int(-1 * (event.delta / 12))
                    canvas.yview_scroll(move, "units")
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
            self.refresh_right_buttons()

    def apply_theme_colors(self):
        if self.is_light_mode:
            ctk.set_appearance_mode("light")
            self.root.configure(fg_color="#f7f4eb")
            self.top_frame.configure(fg_color="#eae2cf")
            self.theme_switch.configure(text="🌙 切换到深色模式", fg_color="#2d3142", hover_color="#4f5d75",
                                        text_color="#ffffff")
            self.check_top.configure(text_color="#1a0f00", fg_color="#854d0e", hover_color="#b45309",
                                     border_color="#78350f")
            if hasattr(self, 'btn_data_center'): self.btn_data_center.configure(text_color="#ffffff")
            self.btn_help.configure(text_color="#ffffff")
            self.btn_add_cat.configure(fg_color="#4f5d75", hover_color="#2d3142", text_color="#ffffff")
            self.btn_add_reply.configure(fg_color="#27ae60", hover_color="#1e7e43", text_color="#ffffff")
        else:
            ctk.set_appearance_mode("dark")
            self.root.configure(fg_color="#1e222b")
            self.top_frame.configure(fg_color="#242936")
            self.theme_switch.configure(text="💡 切换到浅色模式", fg_color="#e2d7bd", hover_color="#eae2cf",
                                        text_color="#333333")
            self.check_top.configure(text_color="#cdd6f4", fg_color="#3b82f6", hover_color="#2563eb",
                                     border_color="#2e3547")
            if hasattr(self, 'btn_data_center'): self.btn_data_center.configure(text_color="#ffffff")
            self.btn_help.configure(text_color="#ffffff")
            self.btn_add_cat.configure(fg_color="#3b82f6", hover_color="#2563eb", text_color="#ffffff")
            self.btn_add_reply.configure(fg_color="#10b981", hover_color="#059669", text_color="#ffffff")

        self.refresh_left_menu()
        self.refresh_right_buttons()

    def refresh_left_menu(self):
        for w in self.left_panel.winfo_children(): w.destroy()
        cat_base_color = "#242936"
        if self.current_category and self.current_category in self.data:
            c_key = "light_color" if self.is_light_mode else "dark_color"
            cat_base_color = self.data[self.current_category]["config"].get(c_key,
                                                                            "#242936" if not self.is_light_mode else "#eae2cf")

        self.left_panel.configure(fg_color=cat_base_color)
        title_c = "#ffffff" if not self.is_light_mode else "#333333"
        title_lbl = ctk.CTkLabel(self.left_panel, text=" 产品目录分类 ", font=("Microsoft YaHei", 12, "bold"),
                                 text_color=title_c)
        title_lbl.pack(fill=ctk.X, pady=(5, 12))

        for cat, cat_info in self.data.items():
            c_key = "light_color" if self.is_light_mode else "dark_color"
            custom_color = cat_info["config"].get(c_key, "#242936" if not self.is_light_mode else "#eae2cf")

            if cat == self.current_category:
                btn_color = "#ffffff" if not self.is_light_mode else "#333333"
                text_color = "#11111b" if not self.is_light_mode else "#ffffff"
                hover_c = "#e6e6e6" if not self.is_light_mode else "#4b5563"
            else:
                if self.is_light_mode:
                    btn_color = self.adjust_brightness(custom_color, 1.1)
                    text_color = "#333333"
                    hover_c = self.adjust_brightness(custom_color, 0.9)
                else:
                    btn_color = self.adjust_brightness(custom_color, 0.8)
                    text_color = "#e2e8f0"
                    hover_c = self.adjust_brightness(custom_color, 1.1)

            font_w = "bold" if cat == self.current_category else "normal"
            item_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
            item_frame.pack(fill=ctk.X, padx=4, pady=3)

            btn = ctk.CTkButton(item_frame, text=f"📂 {cat}", fg_color=btn_color, text_color=text_color,
                                hover_color=hover_c, height=36, corner_radius=6, anchor="w",
                                font=("Microsoft YaHei", 11, font_w), command=lambda c=cat: self.switch_category(c))

            if self.is_edit_mode:
                btn.configure(width=100)
                btn._text_label.configure(wraplength=85, justify="left")
                btn.pack(side=ctk.LEFT, fill=ctk.X, expand=True)
                arr_txt_c = "#ffffff" if not self.is_light_mode else "#333333"
                arr_bg = "#1e222b" if not self.is_light_mode else "#d1d5db"
                btn_up = ctk.CTkButton(item_frame, text="▲", width=22, height=36, font=("Arial", 10, "bold"),
                                       fg_color=arr_bg, text_color=arr_txt_c, corner_radius=4,
                                       command=lambda c=cat: self.move_category(c, "up"))
                btn_up.pack(side=ctk.LEFT, padx=1)
                btn_down = ctk.CTkButton(item_frame, text="▼", width=22, height=36, font=("Arial", 10, "bold"),
                                         fg_color=arr_bg, text_color=arr_txt_c, corner_radius=4,
                                         command=lambda c=cat: self.move_category(c, "down"))
                btn_down.pack(side=ctk.LEFT, padx=1)
            else:
                btn.pack(fill=ctk.X, expand=True)

            r_ev = "<Button-2>" if self.root.tk.call('tk', 'windowingsystem') == 'aqua' else "<Button-3>"
            btn.bind(r_ev, lambda event, c=cat: self.show_category_popup_panel(event, c))

        sig_color = "#94a3b8" if not self.is_light_mode else "#6b7280"
        sig_lbl = ctk.CTkLabel(self.left_panel, text=f"{self.dev_signature}\n{self.version_num}",
                               font=("Arial", 9, "italic"), text_color=sig_color)
        sig_lbl.pack(side=tk.BOTTOM, fill=ctk.X, pady=(20, 5))

    def refresh_right_buttons(self):
        for w in self.right_scroll.winfo_children(): w.destroy()
        if not self.current_category or self.current_category not in self.data: return

        target_bg = "#1e222b" if not self.is_light_mode else "#f7f4eb"
        self.right_scroll.configure(fg_color=target_bg)
        for canvas_attr in ["_canvas", "canvas"]:
            if hasattr(self.right_scroll, canvas_attr):
                try:
                    getattr(self.right_scroll, canvas_attr).configure(bg=target_bg)
                except:
                    pass

        cols = self.current_columns
        for index, (btn_name, btn_info) in enumerate(self.data[self.current_category]["items"].items()):
            text_content = btn_info["text"]
            base_color = btn_info.get("dark_color", "#242936")
            if not isinstance(base_color, str) or not base_color.startswith("#"):
                base_color = "#242936"

            if self.is_light_mode:
                bg_color = "#fffdf9" if base_color.lower() in ["#35363a", "#242936", "#1e1e1e", "#000000"] else (
                    "#f5dcd7" if base_color.lower() == "#c0392b" else self.adjust_brightness(base_color, 1.6))
                hover_color = "#eae2cf"
                title_text_color = "#2c2c2c"
                sub_text_color = "#666666"
            else:
                bg_color = self.adjust_brightness(base_color, 0.6)
                hover_color = self.adjust_brightness(base_color, 0.8)
                title_text_color = "#ffffff"
                sub_text_color = "#bfc7d5"

            card_frame = ctk.CTkFrame(self.right_scroll, fg_color="transparent", width=280, height=95)
            card_frame.grid(row=index // cols, column=index % cols, padx=12, pady=12)
            card_frame.grid_propagate(False)

            btn = ctk.CTkButton(card_frame, text="", fg_color=bg_color, hover_color=hover_color,
                                width=265 if not self.is_edit_mode else 225, height=90, corner_radius=12,
                                border_width=1, border_color="#eae2cf" if self.is_light_mode else "#2e3547",
                                command=lambda t=text_content: self.copy_to_clipboard(t))
            btn.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True)

            label_title = ctk.CTkLabel(btn, text=f"【{btn_name}】", font=("Microsoft YaHei", 12, "bold"),
                                       text_color=title_text_color)
            label_title.place(relx=0.5, rely=0.3, anchor="center")

            hint_txt = "📋 点击快速复制话术" if not self.is_edit_mode else "🔧 移动微调模式激活"
            label_sub = ctk.CTkLabel(btn, text=hint_txt, font=("Microsoft YaHei", 10), text_color=sub_text_color)
            label_sub.place(relx=0.5, rely=0.68, anchor="center")

            if self.is_edit_mode:
                arrow_bar = ctk.CTkFrame(card_frame, fg_color="transparent", width=32)
                arrow_bar.pack(side=ctk.LEFT, fill=ctk.Y, padx=(4, 0))
                arr_txt_c = "#ffffff" if not self.is_light_mode else "#333333"
                arr_bg = "#1e222b" if not self.is_light_mode else "#d1d5db"
                btn_up = ctk.CTkButton(arrow_bar, text="▲", width=32, height=43, font=("Arial", 10, "bold"),
                                       fg_color=arr_bg, text_color=arr_txt_c, corner_radius=6,
                                       command=lambda name=btn_name: self.move_reply(name, "up"))
                btn_up.pack(side=ctk.TOP, pady=(0, 2))
                btn_down = ctk.CTkButton(arrow_bar, text="▼", width=32, height=43, font=("Arial", 10, "bold"),
                                         fg_color=arr_bg, text_color=arr_txt_c, corner_radius=6,
                                         command=lambda name=btn_name: self.move_reply(name, "down"))
                btn_down.pack(side=ctk.TOP)

            r_ev = "<Button-2>" if self.root.tk.call('tk', 'windowingsystem') == 'aqua' else "<Button-3>"
            btn.bind(r_ev, lambda event, name=btn_name: self.show_reply_popup_panel(event, name))
            label_title.bind(r_ev, lambda event, name=btn_name: self.show_reply_popup_panel(event, name))
            label_sub.bind(r_ev, lambda event, name=btn_name: self.show_reply_popup_panel(event, name))
            label_title.bind("<Button-1>", lambda event, t=text_content: self.copy_to_clipboard(t))
            label_sub.bind("<Button-1>", lambda event, t=text_content: self.copy_to_clipboard(t))

    def toggle_edit_mode(self):
        self.is_edit_mode = not self.is_edit_mode
        self.btn_edit_mode.configure(text="✓ 退出编辑模式" if self.is_edit_mode else "🛠️ 进入编辑模式",
                                     fg_color="#b45309" if self.is_edit_mode else "#0891b2",
                                     hover_color="#92400e" if self.is_edit_mode else "#0e7490")
        self.refresh_left_menu()
        self.refresh_right_buttons()

    def toggle_on_top(self):
        self.root.attributes("-topmost", self.always_on_top_var.get())

    def open_data_management_popup(self):
        CTKModernActionPopup(self.root, "数据管理中心", [
            ("☁️ 配置专属云端同步链接", self.configure_sync_url),
            ("🔄 立即从云端拉取同步", lambda: self.sync_pull_from_cloud(silent=False)),
            ("🚀 将本地修改推送至云端", self.push_data_to_github),
            ("🔍 检查软件更新 (.exe)", lambda: self.check_for_app_updates(manual_check=True)),
            ("🔄 导入本地JSON配置", self.import_json_config),
            ("📤 备份导出数据副本", self.export_json_config)
        ], self.is_light_mode)

    def import_json_config(self):
        self.root.attributes("-topmost", False)
        file_path = filedialog.askopenfilename(title="选择同步配置文件",
                                               filetypes=[("JSON配置序列", "*.json"), ("所有文件", "*.*")])
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    incoming_data = json.load(f)
                validated_data = self.load_data(incoming_data)
                if validated_data and len(validated_data.keys()) > 0:
                    self.data = validated_data
                    self.save_data()
                    categories = list(self.data.keys())
                    self.current_category = categories[0] if categories else ""
                    self.apply_theme_colors()
                    messagebox.showinfo("同步成功", "新话术及色彩配置已成功导入并刷新！")
                else:
                    messagebox.showwarning("格式警告", "导入的文件格式不匹配。")
            except Exception as e:
                messagebox.showerror("导入失败", f"文件解析异常:\n{e}")
        self.toggle_on_top()

    def export_json_config(self):
        self.root.attributes("-topmost", False)
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        file_path = filedialog.asksaveasfilename(title="选择导出数据副本的保存位置", initialdir=desktop_path,
                                                 initialfile="EzPaste_Backup_Data.json",
                                                 filetypes=[("JSON配置序列", "*.json"), ("所有文件", "*.*")])
        if file_path:
            if not file_path.lower().endswith(".json"): file_path += ".json"
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=4)
                messagebox.showinfo("导出成功", f"话术数据副本已安全无损导出至：\n{file_path}")
            except Exception as e:
                messagebox.showerror("导出失败", f"文件写入异常:\n{e}")
        self.toggle_on_top()

    def show_reply_popup_panel(self, event, name):
        self.selected_btn_name = name
        CTKModernActionPopup(self.root, f"方块管理: {name}", [
            ("✏️ 修改话术内容", self.edit_reply_content),
            ("🎨 更换方块色彩", self.change_reply_color),
            ("🏷️ 重命名该方块", self.rename_reply_button),
            ("❌ 永久删除回复", self.delete_reply_button)
        ], self.is_light_mode)

    def show_category_popup_panel(self, event, name):
        self.selected_category_name = name
        CTKModernActionPopup(self.root, f"分类管理: {name}", [
            ("🎨 修改分类色彩", self.change_category_color),
            ("✏️ 重命名该分类", self.rename_category),
            ("❌ 永久删除分类", self.delete_category)
        ], self.is_light_mode)

    def edit_reply_content(self):
        if not self.selected_btn_name or not self.current_category: return
        self.root.attributes("-topmost", False)
        curr_text = self.data[self.current_category]["items"][self.selected_btn_name]["text"]
        dialog = ModernLargeTextDialog(self.root, "修改话术内容",
                                       f"请在下方输入【{self.selected_btn_name}】的新话术内容:", self.is_light_mode,
                                       initial_value=curr_text)
        upd = dialog.result
        if upd is not None and upd.strip():
            self.data[self.current_category]["items"][self.selected_btn_name]["text"] = upd.strip()
            self.save_data()
            self.refresh_right_buttons()
        self.toggle_on_top()

    def rename_reply_button(self):
        if not self.selected_btn_name or not self.current_category: return
        self.root.attributes("-topmost", False)
        dialog = ModernInputDialog(self.root, "重命名方块", f"请输入方块【{self.selected_btn_name}】的新名字:",
                                   self.is_light_mode, initial_value=self.selected_btn_name)
        new_name = dialog.result
        if new_name and new_name.strip():
            new_name = new_name.strip()
            if new_name in self.data[self.current_category]["items"] and new_name != self.selected_btn_name:
                messagebox.showwarning("提示", "当前分类下已存在同名方块按钮！")
            elif new_name != self.selected_btn_name:
                self.data[self.current_category]["items"][new_name] = self.data[self.current_category]["items"].pop(
                    self.selected_btn_name)
                self.save_data()
                self.refresh_right_buttons()
        self.toggle_on_top()

    def delete_reply_button(self):
        if not self.selected_btn_name or not self.current_category: return
        self.root.attributes("-topmost", False)
        if messagebox.askyesno("确认删除", f"确定要永久删除【{self.selected_btn_name}】按钮及其话术吗？"):
            self.data[self.current_category]["items"].pop(self.selected_btn_name)
            self.save_data()
            self.refresh_right_buttons()
        self.toggle_on_top()

    def rename_category(self):
        if not self.selected_category_name: return
        self.root.attributes("-topmost", False)
        dialog = ModernInputDialog(self.root, "重命名分类", f"请输入【{self.selected_category_name}】的新名称:",
                                   self.is_light_mode, initial_value=self.selected_category_name)
        new = dialog.result
        if new and new.strip():
            new = new.strip()
            if new in self.data and new != self.selected_category_name:
                messagebox.showwarning("提示", "该分类名称已存在！")
            elif new != self.selected_category_name:
                self.data[new] = self.data.pop(self.selected_category_name)
                if self.current_category == self.selected_category_name: self.current_category = new
                self.save_data()
                self.refresh_left_menu()
        self.toggle_on_top()

    def delete_category(self):
        if not self.selected_category_name: return
        self.root.attributes("-topmost", False)
        if messagebox.askyesno("确认删除分类", f"确定删除【{self.selected_category_name}】分类及名下所有方块吗？"):
            self.data.pop(self.selected_category_name)
            cats = list(self.data.keys())
            self.current_category = cats[0] if cats else ""
            self.save_data()
            self.refresh_left_menu()
            self.refresh_right_buttons()
        self.toggle_on_top()

    def switch_category(self, category):
        self.current_category = category
        self.refresh_left_menu()
        self.refresh_right_buttons()

    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.title("✓ 已成功复制到剪贴板!")
        self.root.after(1000, lambda: self.root.title(f"客服快捷回复助手 {self.version_num}"))

    def add_category(self):
        self.root.attributes("-topmost", False)
        dialog = ModernInputDialog(self.root, "新增分类", "请输入新的产品/业务分类名称:", self.is_light_mode)
        new = dialog.result
        if new and new.strip():
            new = new.strip()
            if new in self.data:
                messagebox.showwarning("提示", "该分类名称已存在！")
            else:
                self.data[new] = {"config": {"dark_color": "#242936", "light_color": "#eae2cf"}, "items": {}}
                self.current_category = new
                self.save_data()
                self.refresh_left_menu()
                self.refresh_right_buttons()
        self.toggle_on_top()

    def add_new_reply_button(self):
        if not self.current_category: return
        self.root.attributes("-topmost", False)
        dialog = ModernInputDialog(self.root, "第一步：方块命名", "请输入这个快捷回复按钮的标题/名字:",
                                   self.is_light_mode)
        b_name = dialog.result
        if b_name and b_name.strip():
            b_name = b_name.strip()
            if b_name in self.data[self.current_category]["items"]:
                messagebox.showwarning("提示", "该方块名称已存在，请换个名字！")
            else:
                large_dialog = ModernLargeTextDialog(self.root, "第二步：输入内容",
                                                     f"请为【{b_name}】按钮输入实际复制的英文回复话术:",
                                                     self.is_light_mode)
                b_content = large_dialog.result
                if b_content and b_content.strip():
                    self.data[self.current_category]["items"][b_name] = {"text": b_content.strip(),
                                                                         "dark_color": "#242936",
                                                                         "light_color": "#fffdf9"}
                    self.save_data()
                    self.refresh_right_buttons()
        self.toggle_on_top()

    def move_dict_item(self, d, key, direction):
        keys = list(d.keys())
        if key not in keys: return d
        idx = keys.index(key)
        if direction == 'up' and idx > 0:
            keys[idx], keys[idx - 1] = keys[idx - 1], keys[idx]
        elif direction == 'down' and idx < len(keys) - 1:
            keys[idx], keys[idx + 1] = keys[idx + 1], keys[idx]
        return {k: d[k] for k in keys}

    def move_category(self, cat_name, direction):
        self.data = self.move_dict_item(self.data, cat_name, direction)
        self.save_data()
        self.refresh_left_menu()

    def move_reply(self, btn_name, direction):
        if not self.current_category: return
        items = self.data[self.current_category]["items"]
        self.data[self.current_category]["items"] = self.move_dict_item(items, btn_name, direction)
        self.save_data()
        self.refresh_right_buttons()

    def adjust_brightness(self, hex_color, factor):
        if not isinstance(hex_color, str): return "#2d3142"
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6: return "#313244"
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = min(255, max(0, int(r * factor)))
        g = min(255, max(0, int(g * factor)))
        b = min(255, max(0, int(b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    def open_instruction_dialog(self):
        self.root.attributes("-topmost", False)
        help_win = ctk.CTkToplevel(self.root)
        help_win.title("快捷回复助手 - 官方使用指南")
        width, height = 560, 430
        help_win.resizable(False, False)
        help_win.attributes("-topmost", True)
        center_window_on_parent(help_win, self.root, width, height)
        bg = "#f7f4eb" if self.is_light_mode else "#1e222b"
        txt_c = "#333333" if self.is_light_mode else "#cdd6f4"
        box_bg = "#fffdf9" if self.is_light_mode else "#242936"
        help_win.configure(fg_color=bg)
        help_win.lift()
        help_win.focus_force()
        help_win.grab_set()

        title_lbl = ctk.CTkLabel(help_win, text="💡 助手系统核心操作指南", font=("Microsoft YaHei", 14, "bold"),
                                 text_color=txt_c)
        title_lbl.pack(pady=(12, 5))
        textbox = ctk.CTkTextbox(help_win, width=520, height=290, font=("Microsoft YaHei", 11, "normal"),
                                 fg_color=box_bg, text_color=txt_c, corner_radius=10, border_width=1,
                                 border_color="#eae2cf" if self.is_light_mode else "#2e3547")
        textbox.pack(padx=20, pady=5, fill=ctk.BOTH, expand=True)
        instructions = (
            f"欢迎使用客服快捷回复助手 {self.version_num}！\n\n"
            "1. 【私有云端仓库安全同步】\n   - 点击 [⚙️ 数据管理中心] -> 可配置您的 GitHub API 链接及 Token 秘钥，安全同步和推送私有仓库数据。\n\n"
            "2. 【全自动应用版本更新检查】\n   - 软件会在启动时自动检测 GitHub Releases 是否有新版 .exe 发布（也支持在数据管理中心手动点击检查更新）。\n\n"
            "3. 【丝滑极速滚动体验】\n   - 优化了左右两侧滚动面板的鼠标响应阻尼，大幅加快滚动速度，高效查看海量话术。"
        )
        textbox.insert("1.0", instructions)
        textbox.configure(state="disabled")

        bot_frame = ctk.CTkFrame(help_win, fg_color="transparent")
        bot_frame.pack(side=ctk.BOTTOM, fill=ctk.X, padx=20, pady=10)
        history_btn = ctk.CTkButton(bot_frame, text="📜 查看更新历史", width=120, height=32,
                                    font=("Microsoft YaHei", 11), fg_color="#0891b2", hover_color="#0e7490",
                                    command=self.open_change_history_dialog)
        history_btn.pack(side=ctk.LEFT)
        close_btn = ctk.CTkButton(bot_frame, text="我知道了", width=100, height=32,
                                  font=("Microsoft YaHei", 11, "bold"),
                                  fg_color="#2b3e50" if self.is_light_mode else "#3b82f6",
                                  command=lambda: [help_win.grab_release(), help_win.destroy(), self.toggle_on_top()])
        close_btn.pack(side=ctk.RIGHT)
        help_win.protocol("WM_DELETE_WINDOW",
                          lambda: [help_win.grab_release(), help_win.destroy(), self.toggle_on_top()])

    def open_change_history_dialog(self):
        history_win = ctk.CTkToplevel(self.root)
        history_win.title(f"系统版本迭代日志 - {self.version_num}")
        width, height = 500, 380
        history_win.resizable(False, False)
        history_win.attributes("-topmost", True)
        center_window_on_parent(history_win, self.root, width, height)
        bg = "#f7f4eb" if self.is_light_mode else "#1e222b"
        txt_c = "#333333" if self.is_light_mode else "#cdd6f4"
        box_bg = "#fffdf9" if self.is_light_mode else "#242936"
        history_win.configure(fg_color=bg)
        history_win.lift()
        history_win.focus_force()
        history_win.grab_set()

        t_lbl = ctk.CTkLabel(history_win, text="📜 EzPaste 官方版本变更历史", font=("Microsoft YaHei", 13, "bold"),
                             text_color=txt_c)
        t_lbl.pack(pady=(12, 5))
        hist_box = ctk.CTkTextbox(history_win, width=460, height=250, font=("Microsoft YaHei", 10, "normal"),
                                  fg_color=box_bg, text_color=txt_c, corner_radius=8, border_width=1,
                                  border_color="#eae2cf" if self.is_light_mode else "#2e3547")
        hist_box.pack(padx=20, pady=5, fill=ctk.BOTH, expand=True)
        history_log = (
            "【当前最新版本: v0.1.3】\n"
            " - 全面支持私有 GitHub 数据仓库 (Private Repo API) 的安全拉取与 Token 校验存储。\n"
            " - 优化 Token 秘钥本地持久化记忆，免去每次重复输入的繁琐操作。\n\n"
            "【历史版本记录: v0.1.2】\n"
            " - 数据管理中心新增【🔍 检查软件更新 (.exe)】按钮与 SSL 证书校验规避。\n"
            " - 整合 Token 秘钥一键安全推送本地修改至云端仓库功能。\n\n"
            "【历史版本记录: v0.1.1】\n"
            " - 深度提速左右两侧滚动框架的鼠标滚轮阻尼（设为 12）。\n\n"
            "【历史版本记录: v0.1.0】\n"
            " - 增设用户自定义个人专属云端同步 URL 持久化记忆功能。"
        )
        hist_box.insert("1.0", history_log)
        hist_box.configure(state="disabled")
        c_btn = ctk.CTkButton(history_win, text="关闭日志", width=90, height=30, font=("Microsoft YaHei", 11),
                              fg_color="#e2d7bd" if self.is_light_mode else "#45475a", text_color=txt_c,
                              command=lambda: [history_win.grab_release(), history_win.destroy()])
        c_btn.pack(pady=10, side=ctk.BOTTOM)

    def theme_swap_with_fade(self):
        self.fade_window(start_alpha=1.0, target_alpha=0.2, duration=100, steps=8, callback=self._execute_theme_swap)

    def _execute_theme_swap(self):
        self.is_light_mode = not self.is_light_mode
        self.apply_theme_colors()
        self.fade_window(start_alpha=0.2, target_alpha=1.0, duration=150, steps=10)

    def fade_window(self, start_alpha, target_alpha, duration, steps=10, current_step=0, callback=None):
        try:
            alpha_step = (target_alpha - start_alpha) / steps
            current_alpha = start_alpha + (alpha_step * (current_step + 1))
            self.root.attributes("-alpha", current_alpha)
            if current_step < steps - 1:
                interval = int(duration / steps)
                self.root.after(interval,
                                lambda: self.fade_window(start_alpha, target_alpha, duration, steps, current_step + 1,
                                                         callback))
            else:
                self.root.attributes("-alpha", target_alpha)
                if callback: callback()
        except:
            if callback: callback()

    def setup_indicator(self):
        self.indicator = tk.Toplevel(self.root)
        self.indicator.overrideredirect(True)
        self.indicator.attributes("-topmost", True)
        self.indicator.configure(bg="#242936")
        container = ctk.CTkFrame(self.indicator, fg_color="#3b82f6", corner_radius=8, border_width=1,
                                 border_color="#60a5fa", width=self.visible_pixel, height=120)
        container.pack(fill=ctk.BOTH, expand=True)
        lbl = ctk.CTkLabel(container, text="⚡\n\n‹\n‹", font=("Microsoft YaHei", 11, "bold"), text_color="#ffffff")
        lbl.pack(fill=ctk.BOTH, expand=True)
        self.indicator.withdraw()
        self.indicator.update_idletasks()
        lbl.bind("<Enter>", lambda e: self.animate_show())
        container.bind("<Enter>", lambda e: self.animate_show())

    def start_edge_check_loop(self):
        if not self.is_animating:
            try:
                win_x = self.root.winfo_x()
                win_y = self.root.winfo_y()
                curr_w = self.root.winfo_width()
                curr_h = self.root.winfo_height()
                mouse_x = self.root.winfo_pointerx()
                mouse_y = self.root.winfo_pointery()
                is_at_right_edge = (win_x + curr_w) >= (self.screen_width - 15)
                if is_at_right_edge and not self.is_hidden:
                    if not (win_x <= mouse_x <= win_x + curr_w and win_y <= mouse_y <= win_y + curr_h):
                        self.animate_hide()
                elif self.is_hidden:
                    if mouse_x >= self.screen_width - 2:
                        self.animate_show()
                    elif win_x < self.screen_width - curr_w - 20:
                        self.is_hidden = False
                        self.indicator.withdraw()
            except:
                pass
        self.root.after(300, self.start_edge_check_loop)

    def animate_hide(self):
        if self.is_animating: return
        self.is_animating = True
        win_y = self.root.winfo_y()
        start_x = self.root.winfo_x()
        target_x = self.screen_width - self.visible_pixel
        steps = 10
        dx = (target_x - start_x) / steps

        def step(count):
            if count < steps:
                curr_x = int(start_x + dx * (count + 1))
                self.root.geometry(f"{self.root.winfo_width()}x{self.root.winfo_height()}+{curr_x}+{win_y}")
                self.root.after(15, lambda: step(count + 1))
            else:
                self.is_hidden = True
                self.is_animating = False
                self.indicator.geometry(
                    f"{self.visible_pixel}x120+{self.screen_width - self.visible_pixel}+{win_y + int(self.root.winfo_height() / 2) - 60}")
                self.indicator.deiconify()

        step(0)

    def animate_show(self):
        if self.is_animating: return
        self.is_animating = True
        self.indicator.withdraw()
        win_y = self.root.winfo_y()
        start_x = self.root.winfo_x()
        target_x = self.screen_width - self.root.winfo_width()
        steps = 10
        dx = (target_x - start_x) / steps

        def step(count):
            if count < steps:
                curr_x = int(start_x + dx * (count + 1))
                self.root.geometry(f"{self.root.winfo_width()}x{self.root.winfo_height()}+{curr_x}+{win_y}")
                self.root.after(15, lambda: step(count + 1))
            else:
                self.is_hidden = False
                self.is_animating = False

        step(0)

    def change_category_color(self):
        target_cat = self.selected_category_name if self.selected_category_name else self.current_category
        if not target_cat or target_cat not in self.data: return
        dialog = ColorPaletteDialog(self.root, self.is_light_mode, is_category=True)
        color_code = dialog.result
        if color_code and isinstance(color_code, str):
            mapped_color = get_mapped_color(color_code, from_light_mode=self.is_light_mode)
            if self.is_light_mode:
                self.data[target_cat]["config"]["light_color"] = color_code
                self.data[target_cat]["config"]["dark_color"] = mapped_color
            else:
                self.data[target_cat]["config"]["dark_color"] = color_code
                self.data[target_cat]["config"]["light_color"] = mapped_color
            self.current_category = target_cat
            self.save_data()
            self.refresh_left_menu()
            self.refresh_right_buttons()

    def change_reply_color(self):
        if not self.selected_btn_name or not self.current_category: return
        dialog = ColorPaletteDialog(self.root, self.is_light_mode, is_category=False)
        color_code = dialog.result
        if color_code and isinstance(color_code, str):
            mapped_color = get_mapped_color(color_code, from_light_mode=self.is_light_mode)
            if self.is_light_mode:
                self.data[self.current_category]["items"][self.selected_btn_name]["light_color"] = color_code
                self.data[self.current_category]["items"][self.selected_btn_name]["dark_color"] = mapped_color
            else:
                self.data[self.current_category]["items"][self.selected_btn_name]["dark_color"] = color_code
                self.data[self.current_category]["items"][self.selected_btn_name]["light_color"] = mapped_color
            self.save_data()
            self.refresh_right_buttons()


if __name__ == "__main__":
    root = ctk.CTk()
    app = FastCopyApp(root)
    root.mainloop()