import tkinter as tk
from tkinter import Toplevel, Label, messagebox, Grid
import tkinter.font as tkfont # 引入字体测量模块
import uiautomation as auto
import sys
import json
import os
import csv
import datetime
import time
import winreg # [新增] 用于操作注册表

# === 1. 配置与常量 ===
CONFIG_FILE = "monitor_config.json"
DETAILED_LOG_FILE = "detailed_log.csv"
HISTORY_FILE = "history.csv"

DEFAULT_CONFIG = {
    "work": ["visual studio", "WPS", "教学网", "课堂实录", "obsidian","Rstudio","Gemini","deepseek"],
    "play": ["北大树洞","bilibili", "哔哩哔哩", "知乎", "贴吧", "steam", "game", "视频", "douyin", "youtube"],
    "goal_work": 300,
    "goal_play": 120,
    "day_start_hour": 0,
    "run_at_startup": False  # [新增] 默认关闭自启动
}

current_config = DEFAULT_CONFIG.copy()

REFRESH_RATE = 1000
NORMAL_WIDTH = 260
NORMAL_HEIGHT = 175 
MINI_HEIGHT = 36
OPACITY = 0.9
BG_COLOR = '#2C2C2C'
TOP_BTN_FONT = ("Arial", 10, "bold") 
MAIN_BTN_FONT = ("Arial", 12, "bold")

stats = {"学习/工作": 0, "摸鱼/娱乐": 0, "其他": 0}
current_full_name = ""

auto.SetGlobalSearchTimeout(1)

def get_adjusted_today():
    now = datetime.datetime.now()
    start_hour = current_config.get("day_start_hour", 0)
    if now.hour < start_hour:
        return now.date() - datetime.timedelta(days=1)
    else:
        return now.date()

# === 修复1：基于像素宽度的文本截断函数 ===
def truncate_text_by_width(text, font, max_width):
    """
    根据给定的最大像素宽度截断文本，并在末尾添加省略号。
    """
    ellipsis = "..."
    # 如果文本本身宽度就小于最大宽度，直接返回
    if font.measure(text) <= max_width:
        return text

    # 开始尝试截断
    # 从完整文本长度开始递减
    for i in range(len(text), 0, -1):
        truncated = text[:i] + ellipsis
        # 如果截断后的文本宽度小于等于最大宽度，就找到了
        if font.measure(truncated) <= max_width:
            return truncated
    
    # 如果连一个字符加省略号都放不下，就只返回省略号（极端情况）
    return ellipsis

# === ToolTip 实现 (保持不变) ===
class ToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.waittime = 500 
        self.wraplength = 180
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        self.tw.attributes('-topmost', True) 
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background="#ffffe0", relief='solid', borderwidth=1,
                       wraplength = self.wraplength,
                       font=("微软雅黑", 9))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw= None
        if tw:
            tw.destroy()
    
    def update_text(self, text):
        self.text = text

# === 2. 数据 IO 模块 (保持不变) ===
def load_config():
    global current_config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                current_config.update(saved)
        except: pass
    else:
        save_config()

def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current_config, f, ensure_ascii=False, indent=4)
    except: pass

# ================= [新增] 开机自启动相关函数 =================
def set_startup_registry(enable=True):
    """通过修改注册表实现开机自启动"""
    # 注册表路径：HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "MiniTimeMonitor"  # 注册表中显示的名称，最好用英文
    
    try:
        # 获取当前运行的 exe 的完整路径
        exe_path = sys.executable
        # 如果是在 IDE 中运行源码，sys.executable 是 python.exe，此时不应设置自启动
        if not exe_path.lower().endswith(".exe") or "python" in exe_path.lower():
            print("[提示] 开发环境下不设置开机自启动")
            return

        # 打开注册表键
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        
        if enable:
            # 写入键值：名称和 exe 路径
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
            print("[成功] 已开启开机自启动")
        else:
            # 尝试删除键值
            try:
                winreg.DeleteValue(key, app_name)
                print("[成功] 已关闭开机自启动")
            except FileNotFoundError:
                pass # 本来就没设置，忽略
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[错误] 设置开机自启动失败: {e}")
        # 在实际应用中，这里最好弹窗提示用户权限不足或被杀毒软件拦截
# ============================================================

def log_detailed(category, app_name):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        exists = os.path.exists(DETAILED_LOG_FILE)
        with open(DETAILED_LOG_FILE, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if not exists: writer.writerow(["Timestamp", "Category", "AppName"])
            writer.writerow([ts, category, app_name])
    except: pass

def save_daily_summary():
    today_str = get_adjusted_today().isoformat()
    new_row = [today_str, stats["学习/工作"], stats["摸鱼/娱乐"], stats["其他"]]
    rows = []
    found = False
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8-sig", newline="") as f:
                rows = list(csv.reader(f))
        except: pass
    updated_rows = []
    if not rows: updated_rows.append(["日期", "学习", "娱乐", "其他"])
    for r in rows:
        if len(r) > 0 and r[0] == today_str:
            updated_rows.append(new_row)
            found = True
        else:
            updated_rows.append(r)
    if not found: updated_rows.append(new_row)
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8-sig", newline="") as f:
            csv.writer(f).writerows(updated_rows)
    except Exception as e: print(f"保存失败: {e}")

def load_today_from_history():
    today = get_adjusted_today().isoformat()
    if not os.path.exists(HISTORY_FILE): return
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8-sig") as f:
            for r in csv.reader(f):
                if len(r) >= 4 and r[0] == today:
                    stats["学习/工作"] = int(r[1])
                    stats["摸鱼/娱乐"] = int(r[2])
                    stats["其他"] = int(r[3])
    except: pass

# === 3. 抓取逻辑 (保持不变) ===
def get_window_content_robust():
    try:
        window = auto.GetForegroundControl()
        if not window: return "无窗口"
        full_name = window.Name
        class_name = window.ClassName
        if "Chrome_WidgetWin_1" in class_name:
            try:
                pane = window.PaneControl(searchDepth=1)
                if pane.Exists(0, 0) and len(pane.Name) > len(full_name):
                    full_name = pane.Name
            except: pass
            try:
                target_text = window.TextControl(searchDepth=4, foundIndex=1)
                if target_text.Exists(0, 0) and len(target_text.Name) > 1:
                    full_name = target_text.Name
            except: pass
        return full_name
    except: return "Error"

# === 4. 仪表盘 (保持不变) ===
class DashboardWindow:
    def __init__(self, parent):
        self.win = tk.Toplevel(parent)
        self.win.title("数据中心")
        self.win.geometry("900x500") 
        self.win.configure(bg="#1E1E1E")
        self.current_date = get_adjusted_today()
        self.setup_ui()
        self.load_timeline()
        self.draw_line_chart()

    def setup_ui(self):
        top = tk.Frame(self.win, bg="#1E1E1E")
        top.pack(fill="x", pady=15)
        top_inner = tk.Frame(top, bg="#1E1E1E")
        top_inner.pack(anchor="center")
        tk.Button(top_inner, text="<", command=lambda: self.change_date(-1), bg="#333", fg="white", bd=0, width=3).pack(side="left", padx=20)
        self.lbl_date = tk.Label(top_inner, text=str(self.current_date), bg="#1E1E1E", fg="white", font=("Bold", 14))
        self.lbl_date.pack(side="left")
        tk.Button(top_inner, text=">", command=lambda: self.change_date(1), bg="#333", fg="white", bd=0, width=3).pack(side="left", padx=20)

        start_h = current_config.get("day_start_hour", 0)
        tk.Label(self.win, text=f"今日时间轴 (起始: {start_h:02d}:00)", bg="#1E1E1E", fg="gray").pack(anchor="center", pady=(5,0))
        
        self.timeline = tk.Canvas(self.win, bg="#101010", height=80, highlightthickness=0)
        self.timeline.pack(fill="x", padx=40, pady=5)
        
        self.bot_container = tk.Frame(self.win, bg="#1E1E1E")
        self.bot_container.pack(fill="both", expand=True, pady=10)
        self.center_frame = tk.Frame(self.bot_container, bg="#1E1E1E")
        self.center_frame.pack(anchor="center", expand=True, fill="both", padx=50)

        self.lbl_summary = tk.Label(self.center_frame, text="加载中...", bg="#1E1E1E", fg="#CCC", justify="left", font=("微软雅黑", 10))
        self.lbl_summary.pack(side="left", anchor="center", padx=(0, 40))
        
        self.chart_frame = tk.Frame(self.center_frame, bg="#1E1E1E")
        self.chart_frame.pack(side="right", fill="both", expand=True)
        tk.Label(self.chart_frame, text="近7天趋势", bg="#1E1E1E", fg="gray").pack(anchor="n")
        self.chart_canvas = tk.Canvas(self.chart_frame, bg="#1E1E1E", highlightthickness=0)
        self.chart_canvas.pack(fill="both", expand=True)

    def change_date(self, d):
        self.current_date += datetime.timedelta(days=d)
        self.lbl_date.config(text=str(self.current_date))
        self.load_timeline()

    def load_timeline(self):
        self.timeline.delete("all")
        w = self.timeline.winfo_width()
        if w < 100: w = 820
        
        start_hour = current_config.get("day_start_hour", 0)
        day_start_dt = datetime.datetime.combine(self.current_date, datetime.time(start_hour, 0))
        day_end_dt = day_start_dt + datetime.timedelta(hours=24)

        self.timeline.create_line(0, 60, w, 60, fill="#444")
        for i in range(25):
            display_hour = (start_hour + i) % 24
            x = (i/24)*w
            self.timeline.create_line(x, 60, x, 65, fill="#666")
            if i % 4 == 0: 
                self.timeline.create_text(x, 75, text=f"{display_hour}:00", fill="#888", font=("Arial", 8))
        
        daily_total = {"学习/工作":0, "摸鱼/娱乐":0, "其他":0}
        if os.path.exists(DETAILED_LOG_FILE):
            try:
                with open(DETAILED_LOG_FILE, "r", encoding="utf-8-sig") as f:
                    for row in csv.reader(f):
                        if len(row) < 3 or row[0] == "Timestamp": continue
                        log_dt = datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                        if day_start_dt <= log_dt < day_end_dt:
                            seconds_offset = (log_dt - day_start_dt).total_seconds()
                            x = (seconds_offset / 86400) * w
                            cat = row[1]
                            if cat in daily_total: daily_total[cat] += 1
                            col = "#00FF7F" if cat=="学习/工作" else "#FF4500" if cat=="摸鱼/娱乐" else "#888888"
                            if col: self.timeline.create_line(x, 10, x, 60, fill=col, width=2)
            except Exception as e: print(f"Timeline error: {e}")

        def fmt(s): return f"{s//3600}h {(s%3600)//60}m"
        txt = (f"📅 {self.current_date}\n\n"
               f"🟢 学习: {fmt(daily_total['学习/工作'])}\n"
               f"🔴 娱乐: {fmt(daily_total['摸鱼/娱乐'])}\n"
               f"⚪ 其他: {fmt(daily_total['其他'])}\n\n"
               f"目标: {current_config['goal_work']}m / {current_config['goal_play']}m")
        self.lbl_summary.config(text=txt)

    def draw_line_chart(self):
        self.chart_canvas.delete("all")
        data = [] 
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8-sig") as f:
                    reader = list(csv.reader(f))[1:]
                    reader.sort(key=lambda x: x[0])
                    data = reader[-7:]
            except: pass
        if not data:
            self.chart_canvas.create_text(200, 100, text="数据不足", fill="gray"); return

        dates = [d[0][5:] for d in data]
        works = [int(d[1]) for d in data]
        plays = [int(d[2]) for d in data]
        max_w = max(works) if works and max(works)>0 else 1
        max_p = max(plays) if plays and max(plays)>0 else 1

        W = self.chart_canvas.winfo_width()
        H = self.chart_canvas.winfo_height()
        if W < 50: W=550; H=250

        pad_l = 65; pad_r = 50; pad_b = 30; pad_t = 20
        inner_margin = 30
        gw = W - pad_l - pad_r - (inner_margin * 2) 
        gh = H - pad_t - pad_b
        
        def get_axis_label(seconds):
            if seconds < 3600: return f"{int(seconds//60)}m"
            else: return f"{seconds/3600:.1f}h"

        self.chart_canvas.create_line(pad_l, pad_t, pad_l, H-pad_b, fill="#00FF7F", width=2)
        for i in range(3): 
            y = (H-pad_b) - (i/2)*gh
            val_sec = (i/2)*max_w
            self.chart_canvas.create_line(pad_l-5, y, pad_l, y, fill="#00FF7F")
            self.chart_canvas.create_text(pad_l-10, y, text=get_axis_label(val_sec), fill="#00FF7F", font=("Arial", 8), anchor="e")

        self.chart_canvas.create_line(W-pad_r, pad_t, W-pad_r, H-pad_b, fill="#FF4500", width=2)
        for i in range(3):
            y = (H-pad_b) - (i/2)*gh
            val_sec = (i/2)*max_p
            self.chart_canvas.create_line(W-pad_r, y, W-pad_r+5, y, fill="#FF4500")
            self.chart_canvas.create_text(W-pad_r+10, y, text=get_axis_label(val_sec), fill="#FF4500", font=("Arial", 8), anchor="w")

        self.chart_canvas.create_line(pad_l, H-pad_b, W-pad_r, H-pad_b, fill="gray")

        step_x = gw / (len(data) - 1) if len(data) > 1 else gw
        pts_w = []; pts_p = []
        for i in range(len(data)):
            x = pad_l + inner_margin + i * step_x
            y_w = (H - pad_b) - (works[i] / max_w) * gh
            y_p = (H - pad_b) - (plays[i] / max_p) * gh
            pts_w.append((x, y_w)); pts_p.append((x, y_p))
            self.chart_canvas.create_text(x, H-pad_b+15, text=dates[i], fill="#888", font=("Arial", 8))

        for i in range(len(pts_w)-1):
            self.chart_canvas.create_line(pts_w[i][0], pts_w[i][1], pts_w[i+1][0], pts_w[i+1][1], fill="#00FF7F", width=2)
        for i in range(len(pts_p)-1):
            self.chart_canvas.create_line(pts_p[i][0], pts_p[i][1], pts_p[i+1][0], pts_p[i+1][1], fill="#FF4500", width=2)
        for x, y in pts_w: self.chart_canvas.create_oval(x-3, y-3, x+3, y+3, fill="#00FF7F", outline="#1E1E1E")
        for x, y in pts_p: self.chart_canvas.create_oval(x-3, y-3, x+3, y+3, fill="#FF4500", outline="#1E1E1E")

# === 5. 设置窗口 (保持不变) ===
class SettingsWindow:
    def __init__(self, parent):
        self.win = tk.Toplevel(parent)
        self.win.title("设置")
        self.win.geometry("400x570") 
        self.win.configure(bg="#1E1E1E")
        self.setup_ui(); self.load_values()
        
    def setup_ui(self):
        lbl_style = {"bg": "#1E1E1E", "fg": "#DDD", "font": ("微软雅黑", 10)}
        entry_style = {"bg": "#333", "fg": "white", "insertbackground": "white", "bd": 1, "relief": "solid"}
        
        tk.Label(self.win, text="每日目标 (分钟)", **lbl_style).pack(pady=(20, 10))
        f = tk.Frame(self.win, bg="#1E1E1E"); f.pack()
        tk.Label(f, text="学习:", **lbl_style).grid(row=0, column=0, padx=5)
        self.ew = tk.Entry(f, width=8, **entry_style); self.ew.grid(row=0, column=1, padx=5)
        tk.Label(f, text="娱乐:", **lbl_style).grid(row=0, column=2, padx=5)
        self.ep = tk.Entry(f, width=8, **entry_style); self.ep.grid(row=0, column=3, padx=5)
        
        tk.Label(self.win, text="新的一天开始于 (0-23点)", **lbl_style).pack(pady=(20, 5))
        self.es = tk.Entry(self.win, width=8, **entry_style)
        self.es.pack()

        tk.Label(self.win, text="关键词 (一行一个)", **lbl_style).pack(pady=(20, 5))
        txt_style = {"bg": "#333", "fg": "white", "insertbackground": "white", "height": 5, "bd": 1, "relief": "solid"}
        tk.Label(self.win, text="[学习/工作]", bg="#1E1E1E", fg="#00FF7F", font=("bold", 9)).pack(anchor="w", padx=30)
        self.tw = tk.Text(self.win, **txt_style); self.tw.pack(padx=30, fill="x")
        tk.Label(self.win, text="[摸鱼/娱乐]", bg="#1E1E1E", fg="#FF4500", font=("bold", 9)).pack(anchor="w", padx=30, pady=(10, 0))
        self.tp = tk.Text(self.win, **txt_style); self.tp.pack(padx=30, fill="x")
        # === [新增] 开机自启动复选框 ===
        self.startup_var = tk.BooleanVar()
        cb_startup = tk.Checkbutton(self.win, text="开机自动启动", variable=self.startup_var,
                                    bg="#1E1E1E", fg="#DDD", selectcolor="#444", activebackground="#1E1E1E", activeforeground="#DDD")
        cb_startup.pack(pady=(15, 0))
        
        tk.Button(self.win, text="保存并生效", command=self.save, bg="#00FF7F", fg="black", font=("bold", 10), bd=0, padx=20, pady=5).pack(pady=20)

    def load_values(self):
        self.ew.insert(0, current_config["goal_work"])
        self.ep.insert(0, current_config["goal_play"])
        self.es.insert(0, current_config.get("day_start_hour", 0))
        self.tw.insert("1.0", "\n".join(current_config["work"]))
        self.tp.insert("1.0", "\n".join(current_config["play"]))
        # === [新增] 加载自启动状态 ===
        self.startup_var.set(current_config.get("run_at_startup", False))

    def save(self):
        try:
            current_config["goal_work"] = int(self.ew.get())
            current_config["goal_play"] = int(self.ep.get())
            start_h = int(self.es.get())
            if start_h < 0 or start_h > 23: raise ValueError("时间错误")
            current_config["day_start_hour"] = start_h
            # === [新增] 保存自启动配置并执行操作 ===
            new_startup_state = self.startup_var.get()
            current_config["run_at_startup"] = new_startup_state
            # 调用刚才写的函数去修改注册表
            set_startup_registry(new_startup_state)
            current_config["work"] = [x.strip() for x in self.tw.get("1.0","end").strip().splitlines() if x.strip()]
            current_config["play"] = [x.strip() for x in self.tp.get("1.0","end").strip().splitlines() if x.strip()]
            save_config(); self.win.destroy(); messagebox.showinfo("成功", "设置已更新，请重启软件以应用新的时间规则。")
        except: messagebox.showerror("错误", "输入格式有误 (时间必须是0-23的整数)")

# === 6. 主窗口 ===
class MiniMonitor:
    def __init__(self, root):
        self.root = root
        self.is_mini = False
        self.today_date = get_adjusted_today()
        
        load_config(); load_today_from_history()
        self.setup_window(normal=True)
        self.create_widgets()
        self.make_draggable()
        
        self.tooltip = ToolTip(self.lbl_status)
        # 修复1：初始化字体测量对象
        self.status_font = tkfont.Font(font=self.lbl_status['font'])

        self.counter = 0
        self.update_data()

    def setup_window(self, normal=True):
        self.root.overrideredirect(True); self.root.attributes('-topmost', True); self.root.attributes('-alpha', OPACITY)
        self.root.configure(bg=BG_COLOR)
        sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
        if normal: w, h = NORMAL_WIDTH, NORMAL_HEIGHT
        else: w, h = NORMAL_WIDTH, MINI_HEIGHT
        x = sw - w - 10; y = sh - h - 50 
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def create_widgets(self):
        self.frame_normal = tk.Frame(self.root, bg=BG_COLOR)
        self.frame_normal.pack(fill="both", expand=True)
        
        bot = tk.Frame(self.frame_normal, bg=BG_COLOR)
        bot.pack(side="bottom", fill="x", pady=5, padx=10)
        tk.Button(bot, text="⚙", command=lambda: SettingsWindow(self.root), bg="#444", fg="white", bd=0, width=3).pack(side="right", padx=2)
        tk.Button(bot, text="📊", command=lambda: DashboardWindow(self.root), bg="#444", fg="white", bd=0, width=3).pack(side="right", padx=2)
        self.lbl_status = tk.Label(bot, text="...", fg='#AAA', font=('微软雅黑', 8), bg=BG_COLOR, anchor="w")
        self.lbl_status.pack(side="left", fill="x", expand=True)

        # 修复2：使用更协调的 Unicode 符号：全角减号 和 投票框
        f_top = tk.Frame(self.frame_normal, bg=BG_COLOR)
        f_top.pack(side="top", fill="x", padx=5, pady=0)
        tk.Button(f_top, text="×", command=self.exit_app, bg=BG_COLOR, fg="#FF6347", bd=0, font=TOP_BTN_FONT, width=2, highlightthickness=0).pack(side="right")
        tk.Button(f_top, text="－", command=self.toggle_mode, bg=BG_COLOR, fg="gray", bd=0, font=TOP_BTN_FONT, width=2, highlightthickness=0).pack(side="right")

        self.f1 = tk.Frame(self.frame_normal, bg=BG_COLOR); self.f1.pack(side="top", fill="x", padx=15, pady=(0,0))
        self.l1 = tk.Label(self.f1, text="学习: 00:00", fg='#00FF7F', font=('微软雅黑', 12, 'bold'), bg=BG_COLOR); self.l1.pack(anchor="w")
        self.c1 = tk.Canvas(self.f1, height=4, bg="#444", highlightthickness=0); self.c1.pack(fill="x")
        self.b1 = self.c1.create_rectangle(0,0,0,4, fill="#00FF7F", width=0)
        
        self.f2 = tk.Frame(self.frame_normal, bg=BG_COLOR); self.f2.pack(side="top", fill="x", padx=15, pady=5)
        self.l2 = tk.Label(self.f2, text="摸鱼: 00:00", fg='#FF6347', font=('微软雅黑', 12, 'bold'), bg=BG_COLOR); self.l2.pack(anchor="w")
        self.c2 = tk.Canvas(self.f2, height=4, bg="#444", highlightthickness=0); self.c2.pack(fill="x")
        self.b2 = self.c2.create_rectangle(0,0,0,4, fill="#FF6347", width=0)

        self.l3 = tk.Label(self.frame_normal, text="其他: 00:00", fg='#AAA', font=('微软雅黑', 9), bg=BG_COLOR)
        self.l3.pack(side="top", anchor="w", padx=15, pady=(5,0))

        # === Mini模式布局 (保持不变) ===
        self.frame_mini = tk.Frame(self.root, bg=BG_COLOR)
        self.frame_mini.columnconfigure(1, weight=1)
        self.frame_mini.rowconfigure(0, weight=1) 

        self.lbl_mini = tk.Label(self.frame_mini, text="...", fg="#DDD", font=("微软雅黑", 9), bg=BG_COLOR, anchor="w")
        self.lbl_mini.grid(row=0, column=0, sticky="w", padx=(10, 5))

        self.c_mini = tk.Canvas(self.frame_mini, height=6, bg="#444", highlightthickness=0)
        self.c_mini.grid(row=0, column=1, sticky="ew", padx=5)
        self.b_mini = self.c_mini.create_rectangle(0,0,0,6, fill="#888", width=0)

        # 修复2：Mini模式也使用新的符号，并移除 pady，完全依赖 sticky="nsew" 对齐
        btn_restore = tk.Button(self.frame_mini, text="□", command=self.toggle_mode, bg=BG_COLOR, fg="gray", bd=0, font=MAIN_BTN_FONT, width=2, highlightthickness=0)
        btn_restore.grid(row=0, column=2, sticky="nsew", padx=(0, 2))

        btn_close = tk.Button(self.frame_mini, text="×", command=self.exit_app, bg=BG_COLOR, fg="#FF6347", bd=0, font=MAIN_BTN_FONT, width=2, highlightthickness=0)
        btn_close.grid(row=0, column=3, sticky="nsew", padx=(0, 5))

    def toggle_mode(self):
        self.is_mini = not self.is_mini
        if self.is_mini:
            self.frame_normal.pack_forget(); self.frame_mini.pack(fill="both", expand=True)
            self.setup_window(normal=False)
        else:
            self.frame_mini.pack_forget(); self.frame_normal.pack(fill="both", expand=True)
            self.setup_window(normal=True)

    def start_move(self, event):
        self.offset_x = event.x_root - self.root.winfo_x()
        self.offset_y = event.y_root - self.root.winfo_y()

    def do_move(self, event):
        if hasattr(self, 'offset_x'):
            x = event.x_root - self.offset_x
            y = event.y_root - self.offset_y
            self.root.geometry(f"+{x}+{y}")

    def make_draggable(self):
        self.root.bind("<Button-1>", self.start_move)
        self.root.bind("<B1-Motion>", self.do_move)
        self.root.bind("<Double-Button-1>", lambda e: self.toggle_mode())

    def exit_app(self):
        save_daily_summary(); sys.exit()

    def update_data(self):
        try:
            current_adjusted_date = get_adjusted_today()
            if current_adjusted_date != self.today_date:
                print(f"[系统] 检测到新的一天，正在重置数据...")
                save_daily_summary()
                global stats
                stats = {"学习/工作": 0, "摸鱼/娱乐": 0, "其他": 0}
                self.today_date = current_adjusted_date

            full_name = get_window_content_robust()
            global current_full_name
            current_full_name = full_name
            self.tooltip.update_text(current_full_name)

            cat = "其他"; low = full_name.lower()
            for k in current_config["play"]: 
                if k and k.lower() in low: cat = "摸鱼/娱乐"; break
            if cat == "其他":
                for k in current_config["work"]:
                    if k and k.lower() in low: cat = "学习/工作"; break
            
            print(f"\r[{cat}] {full_name[:30]}".ljust(80), end="")
            stats[cat] += 1
            log_detailed(cat, full_name)
            
            def fmt(s): return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
            gw = current_config["goal_work"]*60; gp = current_config["goal_play"]*60
            
            if not self.is_mini:
                # 修复1：使用基于像素宽度的智能截断
                available_width = self.lbl_status.winfo_width()
                # 预留一点边距
                truncated_text = truncate_text_by_width(full_name, self.status_font, available_width - 10)
                self.lbl_status.config(text=truncated_text)

                self.l1.config(text=f"学习: {fmt(stats['学习/工作'])}")
                self.l2.config(text=f"娱乐: {fmt(stats['摸鱼/娱乐'])}")
                self.l3.config(text=f"其他: {fmt(stats['其他'])}")
                pw = min(stats['学习/工作']/gw, 1) if gw>0 else 0
                pp = min(stats['摸鱼/娱乐']/gp, 1) if gp>0 else 0
                self.c1.coords(self.b1, 0, 0, (NORMAL_WIDTH-30)*pw, 4)
                self.c2.coords(self.b2, 0, 0, (NORMAL_WIDTH-30)*pp, 4)
                self.c2.itemconfig(self.b2, fill="#FF0000" if pp>=1 else "#FF6347")
            else:
                current_time_str = fmt(stats[cat])
                short_cat = cat.split("/")[0]
                self.lbl_mini.config(text=f"{short_cat}: {current_time_str}")
                
                mini_w = self.c_mini.winfo_width()
                if cat == "学习/工作":
                    self.c_mini.config(bg="#444") 
                    prog = min(stats[cat]/gw, 1) if gw>0 else 0
                    self.c_mini.coords(self.b_mini, 0, 0, mini_w*prog, 6)
                    self.c_mini.itemconfig(self.b_mini, fill="#00FF7F")
                elif cat == "摸鱼/娱乐":
                    self.c_mini.config(bg="#444")
                    prog = min(stats[cat]/gp, 1) if gp>0 else 0
                    self.c_mini.coords(self.b_mini, 0, 0, mini_w*prog, 6)
                    self.c_mini.itemconfig(self.b_mini, fill="#FF4500")
                else:
                    self.c_mini.config(bg=BG_COLOR)
                    self.c_mini.coords(self.b_mini, 0, 0, 0, 6)

            self.counter += 1
            if self.counter >= 30: save_daily_summary(); self.counter = 0
        except Exception as e: print(f"Error: {e}")
        self.root.after(REFRESH_RATE, self.update_data)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = MiniMonitor(root)
        root.mainloop()
    except KeyboardInterrupt: pass