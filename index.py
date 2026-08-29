# -*- coding: utf-8 -*-
import sys
import os
import random
import math
import json
import urllib.request
import urllib.error
import time
import winreg
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QMenu,
                             QPushButton, QGridLayout, QGroupBox,
                             QSpinBox, QCheckBox, QHBoxLayout, QAction,
                             QFrame, QVBoxLayout, QSystemTrayIcon,
                             QScrollArea, QPlainTextEdit)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QTime, QEasingCurve
from PyQt5.QtGui import QPixmap, QPainter, QFont, QColor, QPalette, QIcon

# 导入对话配置
from dialogues import get_dialogues

# ---------- APITube 配置 ----------
APITUBE_KEY = "api_live_hXW9AASSeVaFonFfjTYd7ft604DkPc2e6uF3s0eU9pQNZWxW3gFATTG6K"
APITUBE_BASE_URL = "https://api.apitube.io/v1/news/everything"

# ---------- 午夜新闻关键词（英文） ----------
MIDNIGHT_KEYWORDS = [
    "murder", "homicide", "killing", "slaying", "manslaughter",
    "shooting", "gunfire", "mass shooting", "active shooter",
    "stabbing", "knife attack", "violent crime",
    "sexual assault", "rape", "molestation",
    "robbery", "burglary", "theft", "larceny", "carjacking",
    "drug trafficking", "gang violence", "organized crime",
    "cartel", "mafia", "gang shooting",
    "arson", "terrorism", "terrorist attack", "bombing",
    "kidnapping", "hostage", "abduction", "human trafficking",
    "domestic violence", "assault", "battery",
    "arrest", "indictment", "conviction", "sentence",
    "police shooting", "manhunt", "fugitive", "suspect"
]

# ---------- 资源路径处理 ----------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ---------- Windows 开机自启 ----------
def set_windows_autostart(enabled=True):
    """将桌宠加入/移出当前 Windows 用户的开机启动。"""
    try:
        run_key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "DNTDesktopPet"

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            run_key_path,
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
        ) as key:
            if enabled:
                # .py 运行时使用 pythonw.exe，避免开机启动时弹出黑色命令行窗口；
                # PyInstaller 打包成 exe 时则直接使用 exe。
                executable = sys.executable
                if executable.lower().endswith("python.exe"):
                    pythonw = os.path.join(os.path.dirname(executable), "pythonw.exe")
                    if os.path.exists(pythonw):
                        executable = pythonw

                script_path = os.path.abspath(sys.argv[0])
                command = f'"{executable}" "{script_path}"'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
    except Exception as e:
        print(f"设置 Windows 开机自启失败: {e}")


# ---------- 获取屏幕尺寸 ----------
def get_screen_size():
    app = QApplication.instance()
    if app is None:
        return (1920, 1080)
    screen = app.primaryScreen()
    if screen is None:
        return (1920, 1080)
    geometry = screen.availableGeometry()
    return (geometry.width(), geometry.height())

# ---------- 新闻数据缓存 ----------
_news_cache = None
_cache_time = 0
CACHE_DURATION = 600
_midnight_cache = None
_midnight_cache_time = 0

# ---------- 翻译函数 ----------
def translate_to_chinese(text):
    """使用谷歌翻译将英文翻译为中文"""
    try:
        # 尝试导入googletrans，如果不可用则跳过
        from googletrans import Translator
        translator = Translator()
        result = translator.translate(text, src='en', dest='zh-cn')
        return result.text
    except Exception as e:
        print(f"翻译失败: {e}")
        return text

# ---------- 中文新闻API ----------
def fetch_news_zh():
    """获取中文新闻"""
    global _news_cache, _cache_time
    current_time = time.time()
    if _news_cache is not None and (current_time - _cache_time) < CACHE_DURATION:
        return _news_cache.copy()

    apis = [
        {
            "url": "https://aihot.virxact.com/api/v1/items",
            "params": {"mode": "selected", "window": "7d", "limit": 30},
            "parser": lambda data: [
                {"title": item.get("title", ""), "url": item.get("link", "#")}
                for item in data.get("data", [])[:30]
            ] if isinstance(data, dict) and data.get("data") else None
        },
        {
            "url": "https://60s.viki.moe/v2/it-news",
            "params": {},
            "parser": lambda data: [
                {"title": item.get("title", ""), "url": item.get("link", "#")}
                for item in data.get("data", [])[:30]
            ] if data.get("code") == 200 else None
        },
        {
            "url": "https://hot.imsyy.top/api/thepaper",
            "params": {},
            "parser": lambda data: [
                {"title": item.get("title", ""), "url": item.get("url", "#")}
                for item in data.get("data", [])[:30]
            ] if data.get("code") == 200 else None
        },
        {
            "url": "https://hot.imsyy.top/api/zhihu",
            "params": {},
            "parser": lambda data: [
                {"title": item.get("title", ""), "url": item.get("url", "#")}
                for item in data.get("data", [])[:30]
            ] if data.get("code") == 200 else None
        }
    ]

    raw_news = None
    for api in apis:
        try:
            url = api["url"]
            if api.get("params"):
                param_str = "&".join([f"{k}={v}" for k, v in api["params"].items()])
                url = f"{url}?{param_str}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                news_list = api["parser"](data)
                if news_list and len(news_list) > 0:
                    print(f"成功从 {api['url']} 获取新闻，共 {len(news_list)} 条")
                    raw_news = news_list
                    break
        except Exception as e:
            print(f"API {api['url']} 失败: {e}")
            continue

    if not raw_news:
        return None

    _news_cache = raw_news
    _cache_time = current_time
    return raw_news

# ---------- 英文新闻API (APITube - 使用urllib) ----------
def fetch_news_en():
    """获取英文今日新闻（调用午夜新闻API，但不进行关键词筛选）"""
    try:
        url = f"{APITUBE_BASE_URL}?api_key={APITUBE_KEY}&language.code=en&per_page=10"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data.get("status") == "ok":
                articles = data.get("results", [])
                if articles:
                    return [
                        {"title": article.get("title", ""), "url": article.get("href", "#")}
                        for article in articles if article.get("title")
                    ]
    except Exception as e:
        print(f"英文新闻获取失败: {e}")
    return None

# ---------- 午夜新闻（统一接口，支持中英文 - 纯urllib） ----------
def fetch_midnight_news(lang='zh'):
    """
    获取午夜新闻
    - 英文模式：直接获取英文犯罪新闻
    - 中文模式：获取英文犯罪新闻并翻译为中文
    - 本次运行中一旦筛选出新闻，后续不再重新筛选，始终使用首次筛选结果
    """
    global _midnight_cache, _midnight_cache_time
    
    # Midnight news is filtered only once after a valid result is obtained.
    # Once selected, keep using the same filtered news for this program run.
    if _midnight_cache is not None:
        return _midnight_cache.copy()

    current_time = time.time()

    try:
        # 构建请求URL（API Key放在URL中）
        url = f"{APITUBE_BASE_URL}?api_key={APITUBE_KEY}&language.code=en&per_page=10"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data.get("status") == "ok":
                articles = data.get("results", [])
                if articles:
                    # 筛选包含犯罪关键词的新闻
                    filtered_news = []
                    for article in articles:
                        title = article.get("title", "")
                        # 检查标题是否包含任何犯罪关键词
                        if any(keyword.lower() in title.lower() for keyword in MIDNIGHT_KEYWORDS):
                            filtered_news.append({
                                "title": title,
                                "url": article.get("href", "#")
                            })
                    
                    print(f"APITube 获取到 {len(articles)} 条新闻，筛选后保留 {len(filtered_news)} 条犯罪新闻")
                    
                    if filtered_news:
                        # 如果是中文模式，需要翻译
                        if lang == 'zh':
                            print("正在翻译新闻标题...")
                            translated_news = []
                            for item in filtered_news:
                                translated_title = translate_to_chinese(item["title"])
                                translated_news.append({
                                    "title": translated_title,
                                    "url": item["url"]
                                })
                            _midnight_cache = translated_news
                        else:
                            # 英文模式直接使用
                            _midnight_cache = filtered_news
                        
                        _midnight_cache_time = current_time
                        return _midnight_cache.copy()
                    else:
                        print("没有找到匹配的犯罪新闻，将使用默认午夜新闻")
                        return get_default_midnight_news(lang)
                else:
                    print("APITube 返回空结果，将使用默认午夜新闻")
            else:
                print(f"APITube 返回错误: {data.get('message', '未知错误')}")
    except Exception as e:
        print(f"午夜新闻获取失败: {e}")
    
    # API失败、无数据时使用默认新闻
    return get_default_midnight_news(lang)

def get_default_midnight_news(lang='zh'):
    """返回默认的午夜新闻"""
    if lang == 'zh':
        return [
            {"title": "警方破获一起重大刑事案件，嫌疑人已被抓获", "url": "https://www.gov.cn"},
            {"title": "某地发生枪击事件，警方已介入调查", "url": "https://www.gov.cn"},
            {"title": "法院审理一起谋杀案，被告当庭认罪", "url": "https://www.gov.cn"},
            {"title": "警方通报：命案嫌疑人已落网", "url": "https://www.gov.cn"},
            {"title": "暴力犯罪案件同比下降，社会治安持续好转", "url": "https://www.gov.cn"},
        ]
    else:
        return [
            {"title": "Police solve major criminal case, suspect arrested", "url": "https://www.gov.cn"},
            {"title": "Shooting incident under investigation by police", "url": "https://www.gov.cn"},
            {"title": "Court hears murder case, defendant pleads guilty", "url": "https://www.gov.cn"},
            {"title": "Police: homicide suspect apprehended", "url": "https://www.gov.cn"},
            {"title": "Violent crime rate declines, social order improves", "url": "https://www.gov.cn"},
        ]

# ---------- 今日新闻统一接口 ----------
def fetch_news(lang='zh'):
    if lang == 'en':
        return fetch_news_en()
    else:
        return fetch_news_zh()

# ---------- 便签文件 ----------
def get_note_path():
    """便签始终保存到桌宠程序（.py/.exe）所在目录下的 note.txt。"""
    return os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "note.txt")


def load_notes():
    """读取 note.txt，返回完整文本。"""
    path = get_note_path()
    try:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"读取便签失败: {e}")
        return ""


def save_notes(text):
    """覆盖保存完整便签内容。"""
    path = get_note_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return True
    except Exception as e:
        print(f"保存便签失败: {e}")
        return False


# ---------- 气泡控件 ----------
class BubbleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        screen_w, screen_h = get_screen_size()
        scale = min(screen_w / 1920, screen_h / 1080)

        self.bg_pixmap = QPixmap(resource_path("bubble.png"))
        scaled_width = int(self.bg_pixmap.width() * scale)
        scaled_height = int(self.bg_pixmap.height() * scale)
        self.bg_pixmap = self.bg_pixmap.scaled(scaled_width, scaled_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setFixedSize(self.bg_pixmap.size())

        self.label = QLabel(self)
        self.label.setGeometry(int(130 * scale), int(85 * scale), int(350 * scale), int(200 * scale))
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.label.setStyleSheet("background: transparent; color: #2c3e50;")
        self.normal_font = QFont("Microsoft YaHei", int(14 * scale))
        self.big_font = QFont("Microsoft YaHei", int(72 * scale))
        self.label.setFont(self.normal_font)

        self.full_text = ""
        self.char_index = 0
        self.typing_timer = QTimer(self)
        self.typing_timer.timeout.connect(self.type_char)
        self.typing_interval = 50

        self.is_typing = False
        self.is_complete = False

        # Reminder confirmation button for Drink / Lunch / Dinner / Sleep
        self.confirm_button = QPushButton(self)
        self.confirm_button.setCursor(Qt.PointingHandCursor)
        self.confirm_button.clicked.connect(self._confirm_clicked)
        self.confirm_button.hide()

        self.confirm_timer = QTimer(self)
        self.confirm_timer.setSingleShot(True)
        self.confirm_timer.timeout.connect(self._confirm_timeout)

        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(500)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.finished.connect(self.hide)

        self.move_to_bottom_right()
        self.hide()

    def _update_confirm_button_style(self):
        lang = getattr(self.parent(), "lang", "zh")
        self.confirm_button.setText("Confirm" if lang == "en" else "确认")

        screen_w, screen_h = get_screen_size()
        scale = min(screen_w / 1920, screen_h / 1080)

        self.confirm_button.setGeometry(
            self.width() - int(145 * scale),
            self.height() - int(58 * scale),
            int(115 * scale),
            int(38 * scale)
        )
        self.confirm_button.setStyleSheet(f"""
            QPushButton {{
                font-family: "Microsoft YaHei";
                font-size: {int(14 * scale)}px;
                font-weight: bold;
                color: white;
                background-color: #1a1a2c;
                border: none;
                border-radius: {int(8 * scale)}px;
                padding: {int(4 * scale)}px {int(10 * scale)}px;
            }}
            QPushButton:hover {{ background-color: #2a2a4c; }}
            QPushButton:pressed {{ background-color: #111122; }}
        """)

    def show_confirmation_button(self):
        self._update_confirm_button_style()
        self.confirm_button.show()
        self.confirm_button.raise_()
        self.confirm_timer.start(60000)

    def hide_confirmation_button(self):
        self.confirm_timer.stop()
        self.confirm_button.hide()

    def _confirm_clicked(self):
        self.hide_confirmation_button()
        if self.parent() is not None:
            self.parent().confirm_dialog()

    def _confirm_timeout(self):
        self.hide_confirmation_button()
        if self.parent() is not None:
            self.parent().confirm_dialog()

    def move_to_bottom_right(self):
        screen_w, screen_h = get_screen_size()
        x = screen_w - self.width() - 50
        y = screen_h - self.height() - 50
        self.move(x, y)

    def get_bubble_position(self):
        return self.x(), self.y()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.bg_pixmap)
        super().paintEvent(event)

    def type_char(self):
        if self.char_index < len(self.full_text):
            self.char_index += 1
            current_text = self.full_text[:self.char_index]
            self.label.setText(current_text)
        else:
            self.typing_timer.stop()
            self.is_typing = False
            self.is_complete = True
            self.parent().on_dialog_complete()

    def start_typing(self, text, requires_confirmation=False):
        self.label.setFont(self.normal_font)
        self.full_text = text
        self.char_index = 0
        self.label.clear()
        self.is_typing = True
        self.is_complete = False
        self.move_to_bottom_right()
        self.show()
        self.setWindowOpacity(1.0)
        self.fade_animation.stop()
        self.hide_confirmation_button()
        if requires_confirmation:
            self.show_confirmation_button()
        self.typing_timer.start(self.typing_interval)

    def show_big_text(self, text):
        self.label.setFont(self.big_font)
        self.label.setText(text)
        self.full_text = text
        self.is_typing = False
        self.is_complete = True
        self.move_to_bottom_right()
        self.show()
        self.setWindowOpacity(1.0)
        self.fade_animation.stop()
        self.hide_confirmation_button()

    def fade_out(self):
        self.hide_confirmation_button()
        if self.isVisible():
            self.fade_animation.start()

    def dismiss(self):
        self.typing_timer.stop()
        self.hide_confirmation_button()
        self.fade_animation.stop()
        self.hide()

# ---------- 基础面板类 ----------
class BasePanel(QWidget):
    def __init__(self, parent=None, panel_type="panel"):
        super().__init__(parent)
        self.parent_pet = parent
        self.panel_type = panel_type
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        screen_w, screen_h = get_screen_size()
        scale = min(screen_w / 1920, screen_h / 1080)
        self.panel_width = int(450 * scale)
        self.panel_height = int(500 * scale)
        self.setFixedSize(self.panel_width, self.panel_height)

        if panel_type == "control":
            bg_file = "panel.png"
        else:
            bg_file = "panel2.png"
        self.bg_pixmap = QPixmap(resource_path(bg_file))
        scaled_bg = self.bg_pixmap.scaled(self.panel_width, self.panel_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.bg_pixmap = scaled_bg
        self.setMask(self.bg_pixmap.mask())

        self._position_fixed = False
        self._fixed_x = 0
        self._fixed_y = 0
        self.scale = scale

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.bg_pixmap)
        super().paintEvent(event)

    def update_position(self):
        if self.panel_type == "control":
            self.move(10, 10)
            self.show()
            self.raise_()
            return

        bubble = self.parent_pet.bubble
        if bubble.isVisible():
            bx, by = bubble.get_bubble_position()
            if self.panel_type == "news":
                panel_x = bx + (bubble.width() - self.width()) // 2 - 800
            elif self.panel_type == "midnight":
                panel_x = bx + (bubble.width() - self.width()) // 2 - 1200
            elif self.panel_type == "note":
                panel_x = bx + (bubble.width() - self.width()) // 2
            else:
                panel_x = bx + (bubble.width() - self.width()) // 2
            panel_y = by - self.height() - int(20 * self.scale)

            if not self._position_fixed:
                self._fixed_x = panel_x
                self._fixed_y = panel_y
                self._position_fixed = True
            self.move(self._fixed_x, self._fixed_y)

# ---------- 新闻窗口 ----------
class NewsWindow(BasePanel):
    def __init__(self, parent=None):
        super().__init__(parent, panel_type="news")
        self.news_data = []
        self.current_page = 0
        self.page_size = 5
        self.is_loading = False

        self.container = QWidget(self)
        self.container.setGeometry(0, 0, self.panel_width, self.panel_height)
        self.container.setStyleSheet("background: transparent;")

        self.title_label = QLabel(self.container)
        self.title_label.setStyleSheet(f"color: #1a1a2c; font-size: {int(24 * self.scale)}px; font-weight: bold; background: transparent;")
        self.title_label.setGeometry(int(60 * self.scale), int(60 * self.scale), int(330 * self.scale), int(40 * self.scale))

        self.refresh_btn = QPushButton("🔄", self.container)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(18 * self.scale)}px;
                background: transparent;
                color: #1a1a2c;
                border: none;
                padding: {int(5 * self.scale)}px;
                min-width: {int(30 * self.scale)}px;
                min-height: {int(30 * self.scale)}px;
            }}
            QPushButton:hover {{ color: #3498db; }}
            QPushButton:pressed {{ color: #1a0dab; }}
        """)
        self.refresh_btn.setGeometry(int(380 * self.scale), int(15 * self.scale), int(40 * self.scale), int(40 * self.scale))
        self.refresh_btn.clicked.connect(self.refresh_news)
        self.refresh_btn.setToolTip("Refresh News")

        self.news_scroll = QScrollArea(self.container)
        self.news_scroll.setGeometry(int(60 * self.scale), int(110 * self.scale), int(330 * self.scale), int(320 * self.scale))
        self.news_scroll.setStyleSheet(f"""
            QScrollArea {{
                background: white;
                border-radius: {int(10 * self.scale)}px;
                border: none;
            }}
            QScrollBar:vertical {{
                background: #f0f0f0;
                width: {int(8 * self.scale)}px;
                border-radius: {int(4 * self.scale)}px;
            }}
            QScrollBar::handle:vertical {{
                background: #1a1a2c;
                border-radius: {int(4 * self.scale)}px;
                min-height: {int(30 * self.scale)}px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        self.news_scroll.setWidgetResizable(True)
        self.news_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.news_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.news_container = QWidget()
        self.news_container.setStyleSheet(f"background: white; border-radius: {int(10 * self.scale)}px;")
        self.news_layout = QVBoxLayout(self.news_container)
        self.news_layout.setSpacing(int(12 * self.scale))
        self.news_layout.setContentsMargins(int(15 * self.scale), int(12 * self.scale), int(35 * self.scale), int(12 * self.scale))
        self.news_layout.setAlignment(Qt.AlignTop)
        self.news_scroll.setWidget(self.news_container)

        self.loading_label = QLabel(self.container)
        self.loading_label.setStyleSheet(f"color: #666; font-size: {int(18 * self.scale)}px; background: transparent;")
        self.loading_label.setGeometry(int(60 * self.scale), int(200 * self.scale), int(330 * self.scale), int(50 * self.scale))
        self.loading_label.setAlignment(Qt.AlignCenter)

        self.retry_btn = QPushButton(self.container)
        self.retry_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(16 * self.scale)}px;
                background-color: #1a1a2c;
                color: white;
                border-radius: {int(8 * self.scale)}px;
                padding: {int(10 * self.scale)}px {int(20 * self.scale)}px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #2a2a4c; }}
        """)
        self.retry_btn.setGeometry(int(140 * self.scale), int(250 * self.scale), int(170 * self.scale), int(40 * self.scale))
        self.retry_btn.clicked.connect(self.retry_load)
        self.retry_btn.hide()

        btn_container = QWidget(self.container)
        btn_container.setGeometry(int(60 * self.scale), int(440 * self.scale), int(330 * self.scale), int(40 * self.scale))
        btn_container.setStyleSheet("background: transparent;")
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setSpacing(int(20 * self.scale))
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self.prev_btn = QPushButton()
        self.prev_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(14 * self.scale)}px;
                background-color: #1a1a2c;
                color: white;
                border-radius: {int(5 * self.scale)}px;
                padding: {int(5 * self.scale)}px {int(15 * self.scale)}px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #2a2a4c; }}
            QPushButton:disabled {{ background-color: #999; }}
        """)
        self.prev_btn.clicked.connect(self.prev_page)
        self.prev_btn.setEnabled(False)

        self.page_label = QLabel("1/1")
        self.page_label.setStyleSheet(f"color: #1a1a2c; font-size: {int(14 * self.scale)}px; background: transparent;")
        self.page_label.setAlignment(Qt.AlignCenter)

        self.next_btn = QPushButton()
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(14 * self.scale)}px;
                background-color: #1a1a2c;
                color: white;
                border-radius: {int(5 * self.scale)}px;
                padding: {int(5 * self.scale)}px {int(15 * self.scale)}px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #2a2a4c; }}
            QPushButton:disabled {{ background-color: #999; }}
        """)
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setEnabled(False)

        btn_layout.addWidget(self.prev_btn)
        btn_layout.addWidget(self.page_label)
        btn_layout.addWidget(self.next_btn)

        close_btn = QPushButton("✕", self.container)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(18 * self.scale)}px;
                background: transparent;
                color: #1a1a2c;
                border: none;
                padding: {int(5 * self.scale)}px;
            }}
            QPushButton:hover {{ color: #e74c3c; }}
        """)
        close_btn.setGeometry(int(410 * self.scale), int(10 * self.scale), int(30 * self.scale), int(30 * self.scale))
        close_btn.clicked.connect(self.hide)

        self.update_language(parent.lang if parent else 'zh')
        self.fetch_news()

    def update_language(self, lang):
        if lang == 'en':
            self.title_label.setText("Today's News")
            self.loading_label.setText("Loading news...")
            self.retry_btn.setText("Retry")
            self.prev_btn.setText("◀ Prev")
            self.next_btn.setText("Next ▶")
            self.refresh_btn.setToolTip("Refresh News")
        else:
            self.title_label.setText("今日新闻")
            self.loading_label.setText("正在加载新闻...")
            self.retry_btn.setText("重新加载")
            self.prev_btn.setText("◀ 上一页")
            self.next_btn.setText("下一页 ▶")
            self.refresh_btn.setToolTip("刷新新闻")

    def refresh_news(self):
        global _news_cache, _cache_time
        _news_cache = None
        _cache_time = 0
        self.is_loading = False
        self.fetch_news()

    def fetch_news(self):
        if self.is_loading:
            return
        self.is_loading = True
        self.loading_label.show()
        self.retry_btn.hide()
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        QTimer.singleShot(100, self._do_fetch_news)

    def _do_fetch_news(self):
        try:
            lang = self.parent_pet.lang if self.parent_pet else 'zh'
            news_data = fetch_news(lang)
            if news_data and len(news_data) > 0:
                self.news_data = news_data
                self.loading_label.hide()
                self.retry_btn.hide()
                self.current_page = 0
                self.show_page()
            else:
                self.use_fallback_data()
        except Exception as e:
            print(f"获取新闻出错: {e}")
            self.use_fallback_data()
        self.is_loading = False

    def use_fallback_data(self):
        if self.parent_pet and self.parent_pet.lang == 'en':
            self.news_data = [
                {"title": "Global tech giants announce new AI initiatives", "url": "https://example.com"},
                {"title": "Stock markets rally on positive economic data", "url": "https://example.com"},
                {"title": "New study reveals benefits of daily exercise", "url": "https://example.com"},
            ]
        else:
            self.news_data = [
                {"title": "中国空间站新一批航天员入驻，开展多项科学实验", "url": "https://www.gov.cn"},
                {"title": "国务院发布关于促进民营经济发展壮大的意见", "url": "https://www.gov.cn"},
                {"title": "我国新能源汽车产量突破2000万辆", "url": "https://www.gov.cn"},
            ]
        self.loading_label.hide()
        self.retry_btn.hide()
        self.current_page = 0
        self.show_page()

    def retry_load(self):
        self.fetch_news()

    def show_page(self):
        for i in reversed(range(self.news_layout.count())):
            widget = self.news_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        if not self.news_data:
            empty_label = QLabel("暂无新闻数据" if (self.parent_pet and self.parent_pet.lang == 'zh') else "No news data")
            empty_label.setStyleSheet(f"color: #999; font-size: {int(16 * self.scale)}px; background: transparent;")
            empty_label.setAlignment(Qt.AlignCenter)
            self.news_layout.addWidget(empty_label)
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            self.page_label.setText("0/0")
            return

        start = self.current_page * self.page_size
        end = min(start + self.page_size, len(self.news_data))

        for i in range(start, end):
            item = self.news_data[i]
            title = item.get("title", "无标题" if (self.parent_pet and self.parent_pet.lang == 'zh') else "No title")
            url = item.get("url", "#")

            item_widget = QWidget()
            item_widget.setStyleSheet(f"""
                QWidget {{
                    background: #f5f5f5;
                    border-radius: {int(8 * self.scale)}px;
                }}
                QWidget:hover {{ background: #e8e8e8; }}
            """)
            item_widget.setMinimumHeight(int(65 * self.scale))

            item_layout = QVBoxLayout(item_widget)
            item_layout.setSpacing(int(4 * self.scale))
            item_layout.setContentsMargins(int(10 * self.scale), int(8 * self.scale), int(10 * self.scale), int(8 * self.scale))

            title_row = QWidget()
            title_row.setStyleSheet("background: transparent;")
            title_layout = QHBoxLayout(title_row)
            title_layout.setContentsMargins(0, 0, 0, 0)
            title_layout.setSpacing(int(5 * self.scale))

            num_label = QLabel(f"{i+1}.")
            num_label.setStyleSheet(f"color: #1a1a2c; font-size: {int(14 * self.scale)}px; font-weight: bold; background: transparent;")
            num_label.setFixedWidth(int(25 * self.scale))

            title_label = QLabel(title)
            title_label.setStyleSheet(f"""
                QLabel {{
                    color: #1a1a2c;
                    font-size: {int(16 * self.scale)}px;
                    background: transparent;
                    font-weight: 500;
                }}
                QLabel:hover {{
                    color: #3498db;
                    text-decoration: underline;
                }}
            """)
            title_label.setWordWrap(True)
            title_label.setCursor(Qt.PointingHandCursor)
            title_label.mousePressEvent = lambda e, u=url: self.open_url(u)

            title_layout.addWidget(num_label)
            title_layout.addWidget(title_label)

            if url and url != "#":
                display_url = url
                if len(display_url) > 50:
                    display_url = display_url[:47] + "..."
                link_text = f"🔗 {display_url}"
                link_color = "#3498db"
                link_cursor = Qt.PointingHandCursor
                is_clickable = True
            else:
                link_text = "暂无链接" if (self.parent_pet and self.parent_pet.lang == 'zh') else "No link"
                link_color = "#999"
                link_cursor = Qt.ArrowCursor
                is_clickable = False

            url_label = QLabel(link_text)
            url_label.setStyleSheet(f"""
                QLabel {{
                    color: {link_color};
                    font-size: {int(12 * self.scale)}px;
                    background: transparent;
                    text-decoration: underline;
                }}
                QLabel:hover {{
                    color: #1a0dab;
                }}
            """)
            url_label.setWordWrap(True)
            url_label.setCursor(link_cursor)
            if is_clickable:
                url_label.mousePressEvent = lambda e, u=url: self.open_url(u)

            item_layout.addWidget(title_row)
            item_layout.addWidget(url_label)
            self.news_layout.addWidget(item_widget)

        total_pages = max(1, (len(self.news_data) + self.page_size - 1) // self.page_size)
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < total_pages - 1)
        self.page_label.setText(f"{self.current_page + 1}/{total_pages}")

    def open_url(self, url):
        import webbrowser
        if url and url != "#":
            webbrowser.open(url)

    def next_page(self):
        total_pages = (len(self.news_data) + self.page_size - 1) // self.page_size
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.show_page()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.show_page()

# ---------- 午夜新闻窗口 ----------
class MidnightNewsWindow(BasePanel):
    def __init__(self, parent=None):
        super().__init__(parent, panel_type="midnight")
        self.news_data = []
        self.current_page = 0
        self.page_size = 5
        self.is_loading = False

        self.container = QWidget(self)
        self.container.setGeometry(0, 0, self.panel_width, self.panel_height)
        self.container.setStyleSheet("background: transparent;")

        self.title_label = QLabel(self.container)
        self.title_label.setStyleSheet(f"color: #1a1a2c; font-size: {int(24 * self.scale)}px; font-weight: bold; background: transparent;")
        self.title_label.setGeometry(int(60 * self.scale), int(60 * self.scale), int(330 * self.scale), int(40 * self.scale))

        self.refresh_btn = QPushButton("🔄", self.container)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(18 * self.scale)}px;
                background: transparent;
                color: #1a1a2c;
                border: none;
                padding: {int(5 * self.scale)}px;
                min-width: {int(30 * self.scale)}px;
                min-height: {int(30 * self.scale)}px;
            }}
            QPushButton:hover {{ color: #3498db; }}
            QPushButton:pressed {{ color: #1a0dab; }}
        """)
        self.refresh_btn.setGeometry(int(380 * self.scale), int(15 * self.scale), int(40 * self.scale), int(40 * self.scale))
        self.refresh_btn.clicked.connect(self.refresh_news)
        self.refresh_btn.setToolTip("Refresh Midnight News")

        self.news_scroll = QScrollArea(self.container)
        self.news_scroll.setGeometry(int(60 * self.scale), int(110 * self.scale), int(330 * self.scale), int(320 * self.scale))
        self.news_scroll.setStyleSheet(f"""
            QScrollArea {{
                background: white;
                border-radius: {int(10 * self.scale)}px;
                border: none;
            }}
            QScrollBar:vertical {{
                background: #f0f0f0;
                width: {int(8 * self.scale)}px;
                border-radius: {int(4 * self.scale)}px;
            }}
            QScrollBar::handle:vertical {{
                background: #1a1a2c;
                border-radius: {int(4 * self.scale)}px;
                min-height: {int(30 * self.scale)}px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        self.news_scroll.setWidgetResizable(True)
        self.news_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.news_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.news_container = QWidget()
        self.news_container.setStyleSheet(f"background: white; border-radius: {int(10 * self.scale)}px;")
        self.news_layout = QVBoxLayout(self.news_container)
        self.news_layout.setSpacing(int(12 * self.scale))
        self.news_layout.setContentsMargins(int(15 * self.scale), int(12 * self.scale), int(35 * self.scale), int(12 * self.scale))
        self.news_layout.setAlignment(Qt.AlignTop)
        self.news_scroll.setWidget(self.news_container)

        self.loading_label = QLabel(self.container)
        self.loading_label.setStyleSheet(f"color: #666; font-size: {int(18 * self.scale)}px; background: transparent;")
        self.loading_label.setGeometry(int(60 * self.scale), int(200 * self.scale), int(330 * self.scale), int(50 * self.scale))
        self.loading_label.setAlignment(Qt.AlignCenter)

        self.retry_btn = QPushButton(self.container)
        self.retry_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(16 * self.scale)}px;
                background-color: #1a1a2c;
                color: white;
                border-radius: {int(8 * self.scale)}px;
                padding: {int(10 * self.scale)}px {int(20 * self.scale)}px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #2a2a4c; }}
        """)
        self.retry_btn.setGeometry(int(140 * self.scale), int(250 * self.scale), int(170 * self.scale), int(40 * self.scale))
        self.retry_btn.clicked.connect(self.retry_load)
        self.retry_btn.hide()

        btn_container = QWidget(self.container)
        btn_container.setGeometry(int(60 * self.scale), int(440 * self.scale), int(330 * self.scale), int(40 * self.scale))
        btn_container.setStyleSheet("background: transparent;")
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setSpacing(int(20 * self.scale))
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self.prev_btn = QPushButton()
        self.prev_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(14 * self.scale)}px;
                background-color: #1a1a2c;
                color: white;
                border-radius: {int(5 * self.scale)}px;
                padding: {int(5 * self.scale)}px {int(15 * self.scale)}px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #2a2a4c; }}
            QPushButton:disabled {{ background-color: #999; }}
        """)
        self.prev_btn.clicked.connect(self.prev_page)
        self.prev_btn.setEnabled(False)

        self.page_label = QLabel("1/1")
        self.page_label.setStyleSheet(f"color: #1a1a2c; font-size: {int(14 * self.scale)}px; background: transparent;")
        self.page_label.setAlignment(Qt.AlignCenter)

        self.next_btn = QPushButton()
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(14 * self.scale)}px;
                background-color: #1a1a2c;
                color: white;
                border-radius: {int(5 * self.scale)}px;
                padding: {int(5 * self.scale)}px {int(15 * self.scale)}px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #2a2a4c; }}
            QPushButton:disabled {{ background-color: #999; }}
        """)
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setEnabled(False)

        btn_layout.addWidget(self.prev_btn)
        btn_layout.addWidget(self.page_label)
        btn_layout.addWidget(self.next_btn)

        close_btn = QPushButton("✕", self.container)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(18 * self.scale)}px;
                background: transparent;
                color: #1a1a2c;
                border: none;
                padding: {int(5 * self.scale)}px;
            }}
            QPushButton:hover {{ color: #e74c3c; }}
        """)
        close_btn.setGeometry(int(410 * self.scale), int(10 * self.scale), int(30 * self.scale), int(30 * self.scale))
        close_btn.clicked.connect(self.hide)

        self.update_language(parent.lang if parent else 'zh')
        self.fetch_news()

    def update_language(self, lang):
        if lang == 'en':
            self.title_label.setText("Midnight News")
            self.loading_label.setText("Loading midnight news...")
            self.retry_btn.setText("Retry")
            self.prev_btn.setText("◀ Prev")
            self.next_btn.setText("Next ▶")
            self.refresh_btn.setToolTip("Refresh Midnight News")
        else:
            self.title_label.setText("午夜新闻")
            self.loading_label.setText("正在加载午夜新闻...")
            self.retry_btn.setText("重新加载")
            self.prev_btn.setText("◀ 上一页")
            self.next_btn.setText("下一页 ▶")
            self.refresh_btn.setToolTip("刷新午夜新闻")

    def refresh_news(self):
        global _midnight_cache, _midnight_cache_time
        _midnight_cache = None
        _midnight_cache_time = 0
        self.is_loading = False
        self.fetch_news()

    def fetch_news(self):
        if self.is_loading:
            return
        self.is_loading = True
        self.loading_label.show()
        self.retry_btn.hide()
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        QTimer.singleShot(100, self._do_fetch_news)

    def _do_fetch_news(self):
        try:
            lang = self.parent_pet.lang if self.parent_pet else 'zh'
            news_data = fetch_midnight_news(lang)
            if news_data and len(news_data) > 0:
                self.news_data = news_data
                self.loading_label.hide()
                self.retry_btn.hide()
                self.current_page = 0
                self.show_page()
            else:
                self.use_fallback_data()
        except Exception as e:
            print(f"获取午夜新闻出错: {e}")
            self.use_fallback_data()
        self.is_loading = False

    def use_fallback_data(self):
        # 午夜新闻不再使用默认数据，保持空列表显示
        self.news_data = []
        self.loading_label.hide()
        self.retry_btn.show()
        self.current_page = 0
        self.show_page()

    def retry_load(self):
        self.fetch_news()

    def show_page(self):
        for i in reversed(range(self.news_layout.count())):
            widget = self.news_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        if not self.news_data:
            empty_label = QLabel("暂无午夜新闻数据" if (self.parent_pet and self.parent_pet.lang == 'zh') else "No midnight news data")
            empty_label.setStyleSheet(f"color: #999; font-size: {int(16 * self.scale)}px; background: transparent;")
            empty_label.setAlignment(Qt.AlignCenter)
            self.news_layout.addWidget(empty_label)
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            self.page_label.setText("0/0")
            return

        start = self.current_page * self.page_size
        end = min(start + self.page_size, len(self.news_data))

        for i in range(start, end):
            item = self.news_data[i]
            title = item.get("title", "无标题" if (self.parent_pet and self.parent_pet.lang == 'zh') else "No title")
            url = item.get("url", "#")

            item_widget = QWidget()
            item_widget.setStyleSheet(f"""
                QWidget {{
                    background: #f5f5f5;
                    border-radius: {int(8 * self.scale)}px;
                }}
                QWidget:hover {{ background: #e8e8e8; }}
            """)
            item_widget.setMinimumHeight(int(65 * self.scale))

            item_layout = QVBoxLayout(item_widget)
            item_layout.setSpacing(int(4 * self.scale))
            item_layout.setContentsMargins(int(10 * self.scale), int(8 * self.scale), int(10 * self.scale), int(8 * self.scale))

            title_row = QWidget()
            title_row.setStyleSheet("background: transparent;")
            title_layout = QHBoxLayout(title_row)
            title_layout.setContentsMargins(0, 0, 0, 0)
            title_layout.setSpacing(int(5 * self.scale))

            num_label = QLabel(f"{i+1}.")
            num_label.setStyleSheet(f"color: #1a1a2c; font-size: {int(14 * self.scale)}px; font-weight: bold; background: transparent;")
            num_label.setFixedWidth(int(25 * self.scale))

            title_label = QLabel(title)
            title_label.setStyleSheet(f"""
                QLabel {{
                    color: #1a1a2c;
                    font-size: {int(16 * self.scale)}px;
                    background: transparent;
                    font-weight: 500;
                }}
                QLabel:hover {{
                    color: #3498db;
                    text-decoration: underline;
                }}
            """)
            title_label.setWordWrap(True)
            title_label.setCursor(Qt.PointingHandCursor)
            title_label.mousePressEvent = lambda e, u=url: self.open_url(u)

            title_layout.addWidget(num_label)
            title_layout.addWidget(title_label)

            if url and url != "#":
                display_url = url
                if len(display_url) > 50:
                    display_url = display_url[:47] + "..."
                link_text = f"🔗 {display_url}"
                link_color = "#3498db"
                link_cursor = Qt.PointingHandCursor
                is_clickable = True
            else:
                link_text = "暂无链接" if (self.parent_pet and self.parent_pet.lang == 'zh') else "No link"
                link_color = "#999"
                link_cursor = Qt.ArrowCursor
                is_clickable = False

            url_label = QLabel(link_text)
            url_label.setStyleSheet(f"""
                QLabel {{
                    color: {link_color};
                    font-size: {int(12 * self.scale)}px;
                    background: transparent;
                    text-decoration: underline;
                }}
                QLabel:hover {{
                    color: #1a0dab;
                }}
            """)
            url_label.setWordWrap(True)
            url_label.setCursor(link_cursor)
            if is_clickable:
                url_label.mousePressEvent = lambda e, u=url: self.open_url(u)

            item_layout.addWidget(title_row)
            item_layout.addWidget(url_label)
            self.news_layout.addWidget(item_widget)

        total_pages = max(1, (len(self.news_data) + self.page_size - 1) // self.page_size)
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < total_pages - 1)
        self.page_label.setText(f"{self.current_page + 1}/{total_pages}")

    def open_url(self, url):
        import webbrowser
        if url and url != "#":
            webbrowser.open(url)

    def next_page(self):
        total_pages = (len(self.news_data) + self.page_size - 1) // self.page_size
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.show_page()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.show_page()

# ---------- 便签窗口 ----------
class NoteWindow(BasePanel):
    """可编辑、可上下滚动并持久化到 note.txt 的便签。"""

    def __init__(self, parent=None):
        super().__init__(parent, panel_type="note")

        self.container = QWidget(self)
        self.container.setGeometry(0, 0, self.panel_width, self.panel_height)
        self.container.setStyleSheet("background: transparent;")

        self.title_label = QLabel(self.container)
        self.title_label.setStyleSheet(
            f"color: #1a1a2c; font-size: {int(24 * self.scale)}px; "
            "font-weight: bold; background: transparent;"
        )
        self.title_label.setGeometry(
            int(60 * self.scale), int(55 * self.scale),
            int(300 * self.scale), int(45 * self.scale)
        )

        self.note_edit = QPlainTextEdit(self.container)
        self.note_edit.setGeometry(
            int(55 * self.scale), int(105 * self.scale),
            int(340 * self.scale), int(315 * self.scale)
        )
        self.note_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.note_edit.setPlaceholderText("Write your notes here...")
        self.note_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background: white;
                color: #2c3e50;
                border: none;
                border-radius: {int(14 * self.scale)}px;
                padding: {int(14 * self.scale)}px;
                font-size: {int(20 * self.scale)}px;
                selection-background-color: #d9eaff;
            }}
            QScrollBar:vertical {{
                background: #f0f0f0;
                width: {int(8 * self.scale)}px;
                border-radius: {int(4 * self.scale)}px;
            }}
            QScrollBar::handle:vertical {{
                background: #1a1a2c;
                border-radius: {int(4 * self.scale)}px;
                min-height: {int(30 * self.scale)}px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        self.save_btn = QPushButton(self.container)
        self.save_btn.setGeometry(
            int(95 * self.scale), int(440 * self.scale),
            int(115 * self.scale), int(40 * self.scale)
        )
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(14 * self.scale)}px;
                background-color: #1a1a2c;
                color: white;
                border-radius: {int(7 * self.scale)}px;
                padding: {int(5 * self.scale)}px {int(10 * self.scale)}px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #2a2a4c; }}
            QPushButton:pressed {{ background-color: #111122; }}
        """)
        self.save_btn.clicked.connect(self.save_note)

        self.clear_btn = QPushButton(self.container)
        self.clear_btn.setGeometry(
            int(240 * self.scale), int(440 * self.scale),
            int(115 * self.scale), int(40 * self.scale)
        )
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(14 * self.scale)}px;
                background-color: #e67e22;
                color: white;
                border-radius: {int(7 * self.scale)}px;
                padding: {int(5 * self.scale)}px {int(10 * self.scale)}px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #f39c12; }}
            QPushButton:pressed {{ background-color: #d35400; }}
        """)
        self.clear_btn.clicked.connect(self.clear_note)

        self.close_btn = QPushButton("✕", self.container)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(18 * self.scale)}px;
                background: transparent;
                color: #1a1a2c;
                border: none;
                padding: {int(5 * self.scale)}px;
            }}
            QPushButton:hover {{ color: #e74c3c; }}
        """)
        self.close_btn.setGeometry(
            int(410 * self.scale), int(10 * self.scale),
            int(30 * self.scale), int(30 * self.scale)
        )
        self.close_btn.clicked.connect(self.hide)

        self.update_language(parent.lang if parent else "zh")
        self.reload_note()

    def reload_note(self):
        """每次打开前重新读取，确保显示 note.txt 当前的完整内容。"""
        self.note_edit.setPlainText(load_notes())
        self.note_edit.moveCursor(self.note_edit.textCursor().End)
        self.note_edit.verticalScrollBar().setValue(
            self.note_edit.verticalScrollBar().maximum()
        )

    def showEvent(self, event):
        super().showEvent(event)
        self.reload_note()
        self.note_edit.setFocus()

    def save_note(self):
        if save_notes(self.note_edit.toPlainText()):
            self.parent_pet.add_dialog(
                random.choice(get_dialogues(self.parent_pet.lang, "note_saved"))
            )
        else:
            self.parent_pet.add_dialog(
                random.choice(get_dialogues(self.parent_pet.lang, "note_error"))
            )

    def clear_note(self):
        self.note_edit.clear()
        self.save_note()

    def update_language(self, lang):
        if lang == "en":
            self.title_label.setText("Notes")
            self.note_edit.setPlaceholderText("Write your notes here...")
            self.save_btn.setText("Save")
            self.clear_btn.setText("Clear")
            self.close_btn.setToolTip("Close")
        else:
            self.title_label.setText("便签")
            self.note_edit.setPlaceholderText("在这里输入你的便签内容……")
            self.save_btn.setText("保存")
            self.clear_btn.setText("清空")
            self.close_btn.setToolTip("关闭")

# ---------- 控制面板 ----------
class ControlPanel(BasePanel):
    def __init__(self, parent=None):
        super().__init__(parent, panel_type="control")
        self.container = QWidget(self)
        self.container.setGeometry(0, 0, self.panel_width, self.panel_height)
        self.container.setStyleSheet("background: transparent;")

        self.title_label = QLabel(self.container)
        self.title_label.setStyleSheet(f"color: #1a1a2c; font-size: {int(28 * self.scale)}px; font-weight: bold; background: transparent;")
        self.title_label.setGeometry(int(60 * self.scale), int(60 * self.scale), int(330 * self.scale), int(40 * self.scale))

        # 番茄钟组
        group1 = QGroupBox(self.container)
        group1.setStyleSheet(f"""
            QGroupBox {{
                color: #1a1a2c;
                font-size: {int(20 * self.scale)}px;
                border: 3px solid #1a1a2c;
                border-radius: {int(10 * self.scale)}px;
                margin-top: {int(10 * self.scale)}px;
                background: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {int(10 * self.scale)}px;
                padding: 0 {int(10 * self.scale)}px;
                color: #1a1a2c;
                background: white;
            }}
        """)
        group1.setGeometry(int(60 * self.scale), int(110 * self.scale), int(280 * self.scale), int(140 * self.scale))

        layout1 = QGridLayout(group1)
        layout1.setSpacing(int(8 * self.scale))
        layout1.setContentsMargins(int(10 * self.scale), int(20 * self.scale), int(10 * self.scale), int(10 * self.scale))

        self.tomato_label = QLabel(self.container)
        self.tomato_label.setStyleSheet(f"font-size: {int(28 * self.scale)}px; color: #1a1a2c;")
        self.tomato_label.hide()

        self.tomato_spin = QSpinBox()
        self.tomato_spin.setRange(1, 120)
        self.tomato_spin.setValue(5)
        self.tomato_spin.setSuffix(" min" if (parent and parent.lang == 'en') else " 分钟")
        self.tomato_spin.setStyleSheet(f"font-size: {int(16 * self.scale)}px; background: white; color: #1a1a2c;")
        self.tomato_spin_label = QLabel()
        layout1.addWidget(self.tomato_spin_label, 1, 0)
        layout1.addWidget(self.tomato_spin, 1, 1)

        self.tomato_btn = QPushButton()
        self.tomato_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(16 * self.scale)}px;
                background-color: #27ae60;
                color: white;
                border-radius: {int(5 * self.scale)}px;
                padding: {int(5 * self.scale)}px {int(10 * self.scale)}px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #2ecc71; }}
            QPushButton:pressed {{ background-color: #229954; }}
        """)
        self.tomato_btn.clicked.connect(self.toggle_tomato)
        layout1.addWidget(self.tomato_btn, 2, 0)

        self.tomato_reset_btn = QPushButton()
        self.tomato_reset_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(16 * self.scale)}px;
                background-color: #e67e22;
                color: white;
                border-radius: {int(5 * self.scale)}px;
                padding: {int(5 * self.scale)}px {int(10 * self.scale)}px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #f39c12; }}
            QPushButton:pressed {{ background-color: #d35400; }}
        """)
        self.tomato_reset_btn.clicked.connect(self.reset_tomato)
        layout1.addWidget(self.tomato_reset_btn, 2, 1)

        self.tomato_timer = QTimer(self)
        self.tomato_timer.timeout.connect(self.update_tomato)
        self.tomato_remaining = 0
        self.tomato_running = False

        # 提醒设置组
        group2 = QGroupBox(self.container)
        group2.setStyleSheet(f"""
            QGroupBox {{
                color: #1a1a2c;
                font-size: {int(20 * self.scale)}px;
                border: 3px solid #1a1a2c;
                border-radius: {int(10 * self.scale)}px;
                margin-top: {int(10 * self.scale)}px;
                background: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {int(10 * self.scale)}px;
                padding: 0 {int(10 * self.scale)}px;
                color: #1a1a2c;
                background: white;
            }}
        """)
        group2.setGeometry(int(60 * self.scale), int(270 * self.scale), int(280 * self.scale), int(200 * self.scale))

        layout2 = QGridLayout(group2)
        layout2.setSpacing(int(5 * self.scale))
        layout2.setContentsMargins(int(10 * self.scale), int(20 * self.scale), int(10 * self.scale), int(10 * self.scale))

        self.drink_check = QCheckBox()
        self.drink_check.setChecked(True)
        self.drink_check.setStyleSheet(f"color: #1a1a2c; font-size: {int(14 * self.scale)}px;")
        layout2.addWidget(self.drink_check, 0, 0)
        self.drink_spin = QSpinBox()
        self.drink_spin.setRange(5, 120)
        self.drink_spin.setValue(45)
        self.drink_spin.setSuffix(" min" if (parent and parent.lang == 'en') else " 分钟")
        self.drink_spin.setStyleSheet(f"font-size: {int(14 * self.scale)}px; background: white; color: #1a1a2c;")
        layout2.addWidget(self.drink_spin, 0, 1)

        self.sleep_check = QCheckBox()
        self.sleep_check.setChecked(True)
        self.sleep_check.setStyleSheet(f"color: #1a1a2c; font-size: {int(14 * self.scale)}px;")
        layout2.addWidget(self.sleep_check, 1, 0)
        sleep_h_layout = QHBoxLayout()
        self.sleep_hour = QSpinBox()
        self.sleep_hour.setRange(0, 23)
        self.sleep_hour.setValue(22)
        self.sleep_hour.setStyleSheet(f"font-size: {int(14 * self.scale)}px; background: white; color: #1a1a2c;")
        self.sleep_min = QSpinBox()
        self.sleep_min.setRange(0, 59)
        self.sleep_min.setValue(0)
        self.sleep_min.setStyleSheet(f"font-size: {int(14 * self.scale)}px; background: white; color: #1a1a2c;")
        self.sleep_time_label = QLabel()
        sleep_h_layout.addWidget(self.sleep_time_label)
        sleep_h_layout.addWidget(self.sleep_hour)
        sleep_h_layout.addWidget(QLabel("h" if (parent and parent.lang == 'en') else "时"))
        sleep_h_layout.addWidget(self.sleep_min)
        sleep_h_layout.addWidget(QLabel("m" if (parent and parent.lang == 'en') else "分"))
        layout2.addLayout(sleep_h_layout, 1, 1)

        self.eat_label = QLabel()
        self.eat_label.setStyleSheet(f"font-size: {int(16 * self.scale)}px; color: #1a1a2c; padding: {int(5 * self.scale)}px 0;")
        layout2.addWidget(self.eat_label, 2, 0, 1, 2)

        self.reminder_elapsed = {'喝水': 0}
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self.check_reminders)
        self.reminder_timer.start(60000)

        self.lunch_triggered = False
        self.dinner_triggered = False
        self.sleep_triggered = False
        self.drag_pos = None

        self.update_language(parent.lang if parent else 'zh')
        self.update_tomato_display()

    def update_language(self, lang):
        if lang == 'en':
            self.title_label.setText("Control Panel")
            self.tomato_label.setText("")
            self.tomato_spin_label.setText("Set Duration:")
            self.tomato_btn.setText("▶ Start")
            self.tomato_reset_btn.setText("⟳ Reset")
            self.drink_check.setText("Drink")
            self.sleep_check.setText("Sleep")
            self.sleep_time_label.setText("Time:")
            self.eat_label.setText("Lunch: 12:00  |  Dinner: 18:00")
            group1 = self.findChild(QGroupBox)
            if group1:
                group1.setTitle("Focus")
            groups = self.findChildren(QGroupBox)
            if len(groups) > 1:
                groups[1].setTitle("Reminders")
        else:
            self.title_label.setText("控制面板")
            self.tomato_label.setText("")
            self.tomato_spin_label.setText("设置时长：")
            self.tomato_btn.setText("▶ 开始")
            self.tomato_reset_btn.setText("⟳ 重置")
            self.drink_check.setText("喝水")
            self.sleep_check.setText("睡觉")
            self.sleep_time_label.setText("时间：")
            self.eat_label.setText("午饭：12点  |  晚饭：18点")
            group1 = self.findChild(QGroupBox)
            if group1:
                group1.setTitle("番茄钟")
            groups = self.findChildren(QGroupBox)
            if len(groups) > 1:
                groups[1].setTitle("提醒设置")
        self.tomato_spin.setSuffix(" min" if lang == 'en' else " 分钟")
        self.drink_spin.setSuffix(" min" if lang == 'en' else " 分钟")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.bg_pixmap)
        super().paintEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
        elif event.button() == Qt.RightButton:
            self.close()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos is not None:
            self.move(event.globalPos() - self.drag_pos)
            self._fixed_x = self.x()
            self._fixed_y = self.y()
            self._position_fixed = True

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def toggle_tomato(self):
        if not self.tomato_running:
            minutes = self.tomato_spin.value()
            self.tomato_remaining = minutes * 60
            self.tomato_running = True
            lang = self.parent_pet.lang if self.parent_pet else 'zh'
            self.tomato_btn.setText("Pause" if lang == 'en' else "暂停")
            self.tomato_btn.setStyleSheet(f"""
                QPushButton {{
                    font-size: {int(16 * self.scale)}px;
                    background-color: #e67e22;
                    color: white;
                    border-radius: {int(5 * self.scale)}px;
                    padding: {int(5 * self.scale)}px {int(10 * self.scale)}px;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #f39c12; }}
                QPushButton:pressed {{ background-color: #d35400; }}
            """)
            self.tomato_timer.start(1000)
            self.update_tomato_display()
            self.parent_pet.start_tomato_display(self.tomato_remaining)
        else:
            self.tomato_timer.stop()
            self.tomato_running = False
            lang = self.parent_pet.lang if self.parent_pet else 'zh'
            self.tomato_btn.setText("▶ Continue" if lang == 'en' else "继续")
            self.tomato_btn.setStyleSheet(f"""
                QPushButton {{
                    font-size: {int(16 * self.scale)}px;
                    background-color: #27ae60;
                    color: white;
                    border-radius: {int(5 * self.scale)}px;
                    padding: {int(5 * self.scale)}px {int(10 * self.scale)}px;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #2ecc71; }}
                QPushButton:pressed {{ background-color: #229954; }}
            """)
            self.parent_pet.stop_tomato_display()

    def reset_tomato(self):
        self.tomato_timer.stop()
        self.tomato_running = False
        lang = self.parent_pet.lang if self.parent_pet else 'zh'
        self.tomato_btn.setText("▶ Start" if lang == 'en' else "▶ 开始")
        self.tomato_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: {int(16 * self.scale)}px;
                background-color: #27ae60;
                color: white;
                border-radius: {int(5 * self.scale)}px;
                padding: {int(5 * self.scale)}px {int(10 * self.scale)}px;
                border: none;
            }}
            QPushButton:hover {{ background-color: #2ecc71; }}
            QPushButton:pressed {{ background-color: #229954; }}
        """)
        minutes = self.tomato_spin.value()
        self.tomato_remaining = minutes * 60
        self.update_tomato_display()
        self.parent_pet.stop_tomato_display()

    def update_tomato(self):
        if self.tomato_remaining > 0:
            self.tomato_remaining -= 1
            self.update_tomato_display()
            self.parent_pet.update_tomato_display(self.tomato_remaining)
        else:
            self.tomato_timer.stop()
            self.tomato_running = False
            lang = self.parent_pet.lang if self.parent_pet else 'zh'
            self.tomato_btn.setText("▶ Start" if lang == 'en' else "▶ 开始")
            self.tomato_btn.setStyleSheet(f"""
                QPushButton {{
                    font-size: {int(16 * self.scale)}px;
                    background-color: #27ae60;
                    color: white;
                    border-radius: {int(5 * self.scale)}px;
                    padding: {int(5 * self.scale)}px {int(10 * self.scale)}px;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #2ecc71; }}
                QPushButton:pressed {{ background-color: #229954; }}
            """)
            self.parent_pet.stop_tomato_display()
            self.parent_pet.add_dialog(random.choice(get_dialogues(self.parent_pet.lang, 'drink')), requires_confirmation=True, priority=True)
            self.update_tomato_display()

    def update_tomato_display(self):
        m, s = divmod(self.tomato_remaining, 60)
        lang = self.parent_pet.lang if self.parent_pet else 'zh'
        if lang == 'en':
            self.tomato_label.setText(f"Rest Time: {m:02d}:{s:02d}")
        else:
            self.tomato_label.setText(f"休息倒计时：{m:02d}:{s:02d}")

    def check_reminders(self):
        now = QTime.currentTime()
        hour = now.hour()
        minute = now.minute()

        if self.drink_check.isChecked():
            self.reminder_elapsed['喝水'] += 1
            if self.reminder_elapsed['喝水'] >= self.drink_spin.value():
                self.parent_pet.add_dialog(random.choice(get_dialogues(self.parent_pet.lang, 'drink')), requires_confirmation=True, priority=True)
                self.reminder_elapsed['喝水'] = 0

        if hour == 12 and minute == 0 and not self.lunch_triggered:
            self.parent_pet.add_dialog(random.choice(get_dialogues(self.parent_pet.lang, 'lunch')), requires_confirmation=True, priority=True)
            self.lunch_triggered = True
        if hour != 12:
            self.lunch_triggered = False

        if hour == 18 and minute == 0 and not self.dinner_triggered:
            self.parent_pet.add_dialog(random.choice(get_dialogues(self.parent_pet.lang, 'dinner')), requires_confirmation=True, priority=True)
            self.dinner_triggered = True
        if hour != 18:
            self.dinner_triggered = False

        if self.sleep_check.isChecked():
            set_h = self.sleep_hour.value()
            set_m = self.sleep_min.value()
            if hour == set_h and minute == set_m and not self.sleep_triggered:
                self.parent_pet.add_dialog(random.choice(get_dialogues(self.parent_pet.lang, 'sleep')), requires_confirmation=True, priority=True)
                self.sleep_triggered = True
            if hour != set_h or minute != set_m:
                self.sleep_triggered = False

# ---------- 带淡入淡出的QLabel ----------
class FadeLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fade_duration = 150
        self.opacity_effect = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_effect.setDuration(self.fade_duration)
        self.opacity_effect.setEasingCurve(QEasingCurve.InOutQuad)
        self.setWindowOpacity(1.0)
        self._fade_in_pixmap = None
        self._is_fading = False
        self._pending_pixmap = None

    def setPixmapWithFade(self, pixmap, force=False):
        if pixmap is None or pixmap.isNull():
            return
        if self.pixmap() is None or self.pixmap().isNull():
            self.setPixmap(pixmap)
            self.setWindowOpacity(1.0)
            return
        if self._is_fading:
            self._pending_pixmap = pixmap
            return
        if force:
            self.setPixmap(pixmap)
            self.setWindowOpacity(1.0)
            return
        self._fade_in_pixmap = pixmap
        self.opacity_effect.stop()
        try:
            self.opacity_effect.finished.disconnect()
        except:
            pass
        self.opacity_effect.setStartValue(1.0)
        self.opacity_effect.setEndValue(0.0)
        self._is_fading = True
        self.opacity_effect.finished.connect(self._on_fade_out_complete)
        self.opacity_effect.start()

    def _on_fade_out_complete(self):
        self._is_fading = False
        try:
            self.opacity_effect.finished.disconnect()
        except:
            pass
        if self._pending_pixmap is not None:
            self._fade_in_pixmap = self._pending_pixmap
            self._pending_pixmap = None
        if self._fade_in_pixmap is not None:
            self.setPixmap(self._fade_in_pixmap)
            self._fade_in_pixmap = None
            self.opacity_effect.setStartValue(0.0)
            self.opacity_effect.setEndValue(1.0)
            try:
                self.opacity_effect.finished.disconnect()
            except:
                pass
            self.opacity_effect.start()

# ---------- 主窗口 ----------
class DesktopPet(QWidget):
    def __init__(self):
        super().__init__()
        # 开机自启：Windows 登录后自动启动桌宠。
        set_windows_autostart(True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        screen_w, screen_h = get_screen_size()
        self.setFixedSize(screen_w, screen_h)
        self.move(0, 0)

        self.scale = min(screen_w / 1920, screen_h / 1080)
        self.lang = 'zh'

        # 加载宠物动画帧
        self.pet_frames = []
        for i in range(1, 10):
            pixmap = QPixmap(resource_path(f"pet{i}.png"))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(int(pixmap.width() * self.scale),
                                              int(pixmap.height() * self.scale),
                                              Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.pet_frames.append(scaled_pixmap)
        if not self.pet_frames:
            self.pet_frames = [QPixmap(resource_path("pet.png"))]

        self.pet_static = QPixmap(resource_path("pet.png"))
        self.pet_static = self.pet_static.scaled(int(self.pet_static.width() * self.scale),
                                                 int(self.pet_static.height() * self.scale),
                                                 Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.pet_happy = QPixmap(resource_path("pet-happy.png"))
        self.pet_happy = self.pet_happy.scaled(int(self.pet_happy.width() * self.scale),
                                               int(self.pet_happy.height() * self.scale),
                                               Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.current_frame_index = 0
        self.current_pixmap = self.pet_frames[0]

        pet_w = self.pet_frames[0].width()
        pet_h = self.pet_frames[0].height()

        self.label = FadeLabel(self)
        self.label.setPixmap(self.pet_happy)
        self.label.setWindowOpacity(1.0)
        self.pet_x = (self.width() - pet_w) // 2
        self.pet_y = (self.height() - pet_h) // 2
        self.label.setGeometry(self.pet_x, self.pet_y, pet_w, pet_h)

        self.bubble = BubbleWidget(self)
        self.control_panel = None
        self.news_window = None
        self.midnight_window = None
        self.note_window = None

        self.animation_paused = False
        self.auto_dialog_enabled = True

        self.startup_frames = [self.pet_happy] + self.pet_frames
        self.startup_index = 0
        self.startup_timer = QTimer(self)
        self.startup_timer.timeout.connect(self.startup_animation)
        self.startup_timer.start(500)

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.next_frame)
        self.animation_timer_started = False

        self.bounce_timer = QTimer(self)
        self.bounce_timer.timeout.connect(self.update_bounce)
        self.bounce_timer.start(50)
        self.bounce_time = 0
        self.is_bouncing = True

        self.dialog_queue = []
        self.is_displaying = False
        self.dialog_timer = None
        self.current_dialog_requires_confirmation = False

        self.tomato_display_active = False
        self.tomato_update_timer = QTimer(self)

        self.create_tray_icon()

        self.menu = QMenu(self)
        self.control_action = QAction(self)
        self.control_action.triggered.connect(self.show_control_panel)
        self.flirt_action = QAction(self)
        self.flirt_action.triggered.connect(self.flirt)
        self.news_action = QAction(self)
        self.news_action.triggered.connect(self.show_news)
        self.midnight_action = QAction(self)
        self.midnight_action.triggered.connect(self.show_midnight_news)
        self.note_action = QAction(self)
        self.note_action.triggered.connect(self.show_note)
        self.toggle_animation_action = QAction(self)
        self.toggle_animation_action.triggered.connect(self.toggle_animation)
        self.toggle_visibility_action = QAction(self)
        self.toggle_visibility_action.triggered.connect(self.toggle_visibility_from_menu)
        self.toggle_auto_dialog_action = QAction(self)
        self.toggle_auto_dialog_action.triggered.connect(self.toggle_auto_dialog)
        self.lang_action = QAction(self)
        self.lang_action.triggered.connect(self.switch_language)
        self.quit_action = QAction(self)
        self.quit_action.triggered.connect(self.quit_app)

        self.menu.addAction(self.control_action)
        self.menu.addAction(self.note_action)
        self.menu.addAction(self.flirt_action)
        self.menu.addAction(self.news_action)
        self.menu.addAction(self.midnight_action)
        self.menu.addAction(self.toggle_animation_action)
        self.menu.addAction(self.toggle_visibility_action)
        self.menu.addAction(self.toggle_auto_dialog_action)
        self.menu.addSeparator()
        self.menu.addAction(self.lang_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)

        self.update_menu_language()

        self.drag_pos = None
        self.is_dragging = False

        self.random_timer = QTimer(self)
        self.random_timer.timeout.connect(self.random_dialog)
        self.random_timer.start(30 * 60 * 1000)

        # 每小时检查一次便签；若 note.txt 有内容，则随机抽取一句并附带角色台词。
        self.note_repeat_timer = QTimer(self)
        self.note_repeat_timer.timeout.connect(self.repeat_random_note)
        self.note_repeat_timer.start(60 * 1000)
        self.note_repeat_elapsed = 0

        self.add_dialog(random.choice(get_dialogues(self.lang, 'start')))

    def switch_language(self):
        if self.lang == 'zh':
            self.lang = 'en'
        else:
            self.lang = 'zh'
        self.update_menu_language()
        if self.bubble.isVisible() and self.current_dialog_requires_confirmation:
            self.bubble._update_confirm_button_style()
        if self.control_panel:
            self.control_panel.update_language(self.lang)
        if self.news_window:
            self.news_window.update_language(self.lang)
            self.news_window.refresh_news()
        if self.midnight_window:
            self.midnight_window.update_language(self.lang)
            self.midnight_window.refresh_news()
        if self.note_window:
            self.note_window.update_language(self.lang)

    def update_menu_language(self):
        if self.lang == 'en':
            self.control_action.setText("Control Panel")
            self.note_action.setText("Notes")
            self.flirt_action.setText("Flirt")
            self.news_action.setText("Today's News")
            self.midnight_action.setText("Midnight News")
            self.toggle_animation_action.setText("Pause Animation" if not self.animation_paused else "Start Animation")
            self.toggle_visibility_action.setText("Hide Pet" if self.isVisible() else "Show Pet")
            self.toggle_auto_dialog_action.setText("Pause Auto Dialog" if self.auto_dialog_enabled else "Start Auto Dialog")
            self.lang_action.setText("中文")
            self.quit_action.setText("Exit")
            if hasattr(self, 'tray_icon'):
                tray_menu = self.tray_icon.contextMenu()
                if tray_menu:
                    for action in tray_menu.actions():
                        if action.text() == "显示/隐藏":
                            action.setText("Show/Hide")
                        elif action.text() == "控制面板":
                            action.setText("Control Panel")
                        elif action.text() == "今日新闻":
                            action.setText("Today's News")
                        elif action.text() == "午夜新闻":
                            action.setText("Midnight News")
                        elif action.text() == "退出":
                            action.setText("Exit")
        else:
            self.control_action.setText("控制面板")
            self.note_action.setText("便签")
            self.flirt_action.setText("调情")
            self.news_action.setText("今日新闻")
            self.midnight_action.setText("午夜新闻")
            self.toggle_animation_action.setText("暂停动画" if not self.animation_paused else "开始动画")
            self.toggle_visibility_action.setText("隐藏桌宠" if self.isVisible() else "隐藏桌宠")
            self.toggle_auto_dialog_action.setText("暂停自动对话" if self.auto_dialog_enabled else "开始自动对话")
            self.lang_action.setText("English")
            self.quit_action.setText("退出")
            if hasattr(self, 'tray_icon'):
                tray_menu = self.tray_icon.contextMenu()
                if tray_menu:
                    for action in tray_menu.actions():
                        if action.text() == "Show/Hide":
                            action.setText("显示/隐藏")
                        elif action.text() == "Control Panel":
                            action.setText("控制面板")
                        elif action.text() == "Today's News":
                            action.setText("今日新闻")
                        elif action.text() == "Midnight News":
                            action.setText("午夜新闻")
                        elif action.text() == "Exit":
                            action.setText("退出")

    def create_tray_icon(self):
        icon_path = resource_path("favicon.ico")
        if not os.path.exists(icon_path):
            icon_path = resource_path("pet.png")
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(icon_path))
        self.tray_icon.setToolTip("Desk Pet - Click to show/hide")
        tray_menu = QMenu()
        show_action = QAction("显示/隐藏" if self.lang == 'zh' else "Show/Hide", self)
        show_action.triggered.connect(self.toggle_visibility)
        tray_menu.addAction(show_action)
        control_action = QAction("控制面板" if self.lang == 'zh' else "Control Panel", self)
        control_action.triggered.connect(self.show_control_panel)
        tray_menu.addAction(control_action)
        news_action = QAction("今日新闻" if self.lang == 'zh' else "Today's News", self)
        news_action.triggered.connect(self.show_news)
        tray_menu.addAction(news_action)
        midnight_action = QAction("午夜新闻" if self.lang == 'zh' else "Midnight News", self)
        midnight_action.triggered.connect(self.show_midnight_news)
        tray_menu.addAction(midnight_action)
        tray_menu.addSeparator()
        quit_action = QAction("退出" if self.lang == 'zh' else "Exit", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def toggle_visibility_from_menu(self):
        if self.isVisible():
            self.hide()
            self.toggle_visibility_action.setText("隐藏桌宠" if self.lang == 'zh' else "Hide Pet")
        else:
            self.show()
            self.raise_()
            self.toggle_visibility_action.setText("隐藏桌宠" if self.lang == 'zh' else "Hide Pet")

    def toggle_auto_dialog(self):
        self.auto_dialog_enabled = not self.auto_dialog_enabled
        if self.auto_dialog_enabled:
            self.toggle_auto_dialog_action.setText("暂停自动对话" if self.lang == 'zh' else "Pause Auto Dialog")
            self.random_timer.start(30 * 60 * 1000)
            msg = "就这么喜欢看着我对你碎碎念？你的脑子是不是有什么问题，还非得听到有人跟你说话才能动一动？" if self.lang == 'zh' else "Do you enjoy my nagging that much? Is your brain broken that you need someone to talk to you to get moving?"
            self.add_dialog(msg)
        else:
            self.toggle_auto_dialog_action.setText("开始自动对话" if self.lang == 'zh' else "Start Auto Dialog")
            self.random_timer.stop()
            msg = "也挺好的，至少我能安静会儿，你也能安静会儿……怎么，你很喜欢听到我念叨你？" if self.lang == 'zh' else "Good, at least I can have some peace, and you too... Wait, do you actually like my nagging?"
            self.add_dialog(msg)

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_visibility()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage("桌宠" if self.lang == 'zh' else "Desk Pet",
                                   "程序已最小化到系统托盘" if self.lang == 'zh' else "Program minimized to system tray",
                                   QSystemTrayIcon.Information, 2000)

    def startup_animation(self):
        self.startup_index += 1
        if self.startup_index < len(self.startup_frames):
            self.label.setPixmapWithFade(self.startup_frames[self.startup_index])
        else:
            self.startup_timer.stop()
            self.animation_timer_started = True
            self.animation_timer.start(300)
            self.current_frame_index = 0
            self.current_pixmap = self.pet_frames[0]
            self.label.setPixmap(self.current_pixmap)
            self.label.setWindowOpacity(1.0)

    def toggle_animation(self):
        self.animation_paused = not self.animation_paused
        if self.animation_paused:
            self.animation_timer.stop()
            self.label.setPixmapWithFade(self.pet_static)
            self.toggle_animation_action.setText("开始动画" if self.lang == 'zh' else "Start Animation")
        else:
            self.animation_timer.start(300)
            self.current_frame_index = 0
            self.current_pixmap = self.pet_frames[0]
            self.label.setPixmapWithFade(self.current_pixmap)
            self.toggle_animation_action.setText("暂停动画" if self.lang == 'zh' else "Pause Animation")

    def next_frame(self):
        if self.animation_paused or not self.animation_timer_started:
            return
        if not self.is_dragging and self.pet_frames:
            self.current_frame_index = (self.current_frame_index + 1) % len(self.pet_frames)
            self.current_pixmap = self.pet_frames[self.current_frame_index]
            if not self.is_dragging and not self.tomato_display_active:
                self.label.setPixmapWithFade(self.current_pixmap)

    def update_bounce(self):
        if not self.is_bouncing or self.tomato_display_active:
            return
        self.bounce_time += 0.15
        bounce_y = int(math.sin(self.bounce_time * 2.5) * 3 * self.scale)
        bounce_x = int(math.sin(self.bounce_time * 1.8) * 2 * self.scale)
        pet_w = self.pet_frames[0].width()
        pet_h = self.pet_frames[0].height()
        base_x = (self.width() - pet_w) // 2
        base_y = (self.height() - pet_h) // 2
        self.label.setGeometry(base_x + bounce_x, base_y + bounce_y, pet_w, pet_h)

    def start_tomato_display(self, seconds):
        self.tomato_display_active = True
        if self.is_displaying:
            self.bubble.typing_timer.stop()
            self.is_displaying = False
            self.clear_dialog_timer()
        self.bubble.show_big_text(self._format_time(seconds))
        self.tomato_update_timer.start(1000)

    def update_tomato_display(self, seconds):
        if self.tomato_display_active:
            self.bubble.show_big_text(self._format_time(seconds))

    def stop_tomato_display(self):
        self.tomato_display_active = False
        self.tomato_update_timer.stop()
        if self.dialog_queue:
            self.bubble.hide()
            self.show_next_dialog()
        else:
            self.bubble.fade_out()

    def _format_time(self, seconds):
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            self.is_dragging = False
            self.label.setPixmap(self.pet_happy)
            self.label.setWindowOpacity(1.0)
            self.is_bouncing = False
            if self.animation_timer_started:
                self.animation_timer.stop()
        elif event.button() == Qt.RightButton:
            if self.control_panel is not None and self.control_panel.isVisible():
                self.control_panel.close()
            elif self.news_window is not None and self.news_window.isVisible():
                self.news_window.hide()
            elif self.midnight_window is not None and self.midnight_window.isVisible():
                self.midnight_window.hide()
            elif self.note_window is not None and self.note_window.isVisible():
                self.note_window.hide()
            else:
                self.menu.exec_(event.globalPos())

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos is not None:
            distance = (event.globalPos() - self.frameGeometry().topLeft() - self.drag_pos).manhattanLength()
            if distance > 5:
                self.is_dragging = True
                self.move(event.globalPos() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.animation_paused:
                self.label.setPixmap(self.pet_static)
                self.label.setWindowOpacity(1.0)
            elif self.animation_timer_started:
                self.label.setPixmap(self.current_pixmap)
                self.label.setWindowOpacity(1.0)
            else:
                self.label.setPixmap(self.pet_frames[0])
                self.label.setWindowOpacity(1.0)
            self.is_bouncing = True
            if not self.animation_paused and self.animation_timer_started:
                self.animation_timer.start(300)
            if not self.is_dragging:
                pos = event.pos()
                pet_rect = self.label.geometry()
                if pet_rect.contains(pos):
                    self.on_pet_click()
            self.drag_pos = None
            self.is_dragging = False

    def clear_dialog_timer(self):
        if self.dialog_timer is not None:
            self.dialog_timer.stop()
            self.dialog_timer = None

    def add_dialog(self, text, requires_confirmation=False, priority=False):
        dialog_item = (text, requires_confirmation)

        if priority:
            # Scheduled reminders go to the front of the queue.
            # IMPORTANT: do not interrupt the dialogue that is currently playing.
            # Let the current random/ordinary dialogue finish first, then show
            # the scheduled reminder immediately afterward.
            self.dialog_queue.insert(0, dialog_item)
        else:
            self.dialog_queue.append(dialog_item)

        if self.tomato_display_active:
            return

        if not self.is_displaying:
            self.show_next_dialog()

    def show_next_dialog(self):
        if self.tomato_display_active:
            return
        self.clear_dialog_timer()
        if self.dialog_queue:
            self.is_displaying = True
            text, requires_confirmation = self.dialog_queue.pop(0)
            self.current_dialog_requires_confirmation = requires_confirmation
            self.bubble.start_typing(text, requires_confirmation)
        else:
            self.is_displaying = False
            self.current_dialog_requires_confirmation = False

    def on_dialog_complete(self):
        self.clear_dialog_timer()
        self.dialog_timer = QTimer(self)
        self.dialog_timer.setSingleShot(True)
        if self.dialog_queue:
            self.dialog_timer.timeout.connect(self.show_next_dialog)
        else:
            self.dialog_timer.timeout.connect(self._fade_and_reset)
        self.dialog_timer.start(
            60000 if self.current_dialog_requires_confirmation else 3000
        )

    def confirm_dialog(self):
        self.clear_dialog_timer()
        self.bubble.dismiss()
        self.is_displaying = False
        self.current_dialog_requires_confirmation = False
        if self.dialog_queue and not self.tomato_display_active:
            self.show_next_dialog()

    def _fade_and_reset(self):
        self.bubble.fade_out()
        self.is_displaying = False
        self.current_dialog_requires_confirmation = False
        self.dialog_timer = None

    def on_pet_click(self):
        if self.auto_dialog_enabled:
            self.add_dialog(random.choice(get_dialogues(self.lang, 'click')))

    def flirt(self):
        self.add_dialog(random.choice(get_dialogues(self.lang, 'flirt')))

    def random_dialog(self):
        # Random dialogue can play normally, but it never replaces an active
        # reminder or a dialogue that is already being displayed.
        if (
            self.auto_dialog_enabled
            and not self.tomato_display_active
            and not self.is_displaying
            and not self.current_dialog_requires_confirmation
        ):
            self.add_dialog(random.choice(get_dialogues(self.lang, 'random')))

    def show_note(self):
        if self.note_window is None:
            self.note_window = NoteWindow(self)
        self.note_window.update_language(self.lang)
        self.note_window.reload_note()
        self.note_window.update_position()
        self.note_window.show()
        self.note_window.raise_()
        self.note_window.note_edit.setFocus()

    def repeat_random_note(self):
        """每小时从 note.txt 随机抽取一句，并让角色一起复读。"""
        self.note_repeat_elapsed += 1
        if self.note_repeat_elapsed < 60:
            return
        self.note_repeat_elapsed = 0

        note_text = load_notes()
        if not note_text.strip():
            return

        # 空行作为分隔符；每一行视为一句话。若一行过长也保持完整，不截断。
        notes = [line.strip() for line in note_text.splitlines() if line.strip()]
        if not notes:
            return

        note_sentence = random.choice(notes)
        role_lines = get_dialogues(self.lang, "note_repeat")
        if not role_lines:
            return

        role_line = random.choice(role_lines)
        if self.lang == "en":
            message = f'You wrote: "{note_sentence}"{role_line}'
        else:
            message = f'你写过：" {note_sentence} "{role_line}'
        self.add_dialog(message)

    def show_control_panel(self):
        if self.control_panel is None:
            self.control_panel = ControlPanel(self)
        self.control_panel.update_position()
        self.control_panel.show()
        self.control_panel.raise_()

    def show_news(self):
        if self.news_window is None:
            self.news_window = NewsWindow(self)
        self.news_window.update_position()
        self.news_window.show()
        self.news_window.raise_()

    def show_midnight_news(self):
        if self.midnight_window is None:
            self.midnight_window = MidnightNewsWindow(self)
        self.midnight_window.update_position()
        self.midnight_window.show()
        self.midnight_window.raise_()

    def quit_app(self):
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        self.add_dialog(random.choice(get_dialogues(self.lang, 'close')))
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self._prepare_close)
        self._close_timer.start(5000)

    def _prepare_close(self):
        self.label.setPixmap(self.pet_happy)
        self.label.setWindowOpacity(1.0)
        self.animation_timer.stop()
        self.startup_timer.stop()
        self.clear_dialog_timer()
        if hasattr(self, "note_repeat_timer"):
            self.note_repeat_timer.stop()
        QTimer.singleShot(3000, self._really_quit)

    def _really_quit(self):
        if self.control_panel:
            self.control_panel.close()
        if self.news_window:
            self.news_window.close()
        if self.midnight_window:
            self.midnight_window.close()
        if self.note_window:
            self.note_window.close()
        if hasattr(self, "note_repeat_timer"):
            self.note_repeat_timer.stop()
        self.close()
        QApplication.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    pet = DesktopPet()
    pet.show()
    sys.exit(app.exec_())