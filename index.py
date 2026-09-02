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
import base64
import re
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QMenu,
                             QPushButton, QGridLayout, QGroupBox,
                             QSpinBox, QCheckBox, QHBoxLayout, QAction,
                             QFrame, QVBoxLayout, QSystemTrayIcon,
                             QScrollArea, QPlainTextEdit)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QTime, QEasingCurve, QDateTime, QEvent
from PyQt5.QtGui import QPixmap, QPainter, QFont, QColor, QPalette, QIcon, QImage

# 导入对话配置
try:
    from dialogues import get_dialogues
except ImportError:
    def get_dialogues(lang, key):
        default = {
            'zh': {
                'start': ['你好呀！今天想做什么呢？'],
                'click': ['哎呀，别戳我！', '好痒！'],
                'flirt': ['讨厌啦~', '你好坏哦~'],
                'drink': ['该喝水了！', '喝点水吧~'],
                'lunch': ['该吃午饭了！', '午饭时间到！'],
                'dinner': ['该吃晚饭了！', '晚饭时间到！'],
                'sleep': ['该睡觉了！', '晚安~'],
                'random': ['今天天气真好~', '你在看什么呢？'],
                'note_saved': ['便签已保存！', '笔记已存好~'],
                'note_error': ['便签保存失败...', '出错了...'],
                'note_repeat': ['我记得你写过这个！', '这句话真有意思~'],
                'close': ['真的要走了吗？', '拜拜~下次见！']
            },
            'en': {
                'start': ['Hello! What do you want to do today?'],
                'click': ['Hey, stop poking me!', 'That tickles!'],
                'flirt': ['Oh stop~', 'You are so naughty~'],
                'drink': ['Time to drink water!', 'Have some water~'],
                'lunch': ['Time for lunch!', 'Lunch time!'],
                'dinner': ['Time for dinner!', 'Dinner time!'],
                'sleep': ['Time to sleep!', 'Good night~'],
                'random': ['Nice weather today~', 'What are you looking at?'],
                'note_saved': ['Note saved!', 'Note stored~'],
                'note_error': ['Failed to save note...', 'Error...'],
                'note_repeat': ['I remember you wrote this!', 'That is interesting~'],
                'close': ['Are you really leaving?', 'Bye~ See you next time!']
            }
        }
        return default.get(lang, default['zh']).get(key, ['...'])

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
_news_cache_zh = None
_news_cache_en = None
_cache_time_zh = 0
_cache_time_en = 0
CACHE_DURATION = 600
_midnight_cache_zh = None
_midnight_cache_en = None
_midnight_cache_time_zh = 0
_midnight_cache_time_en = 0

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
    """获取中文今日新闻，并使用独立中文缓存。"""
    global _news_cache_zh, _cache_time_zh
    current_time = time.time()
    if _news_cache_zh is not None and (current_time - _cache_time_zh) < CACHE_DURATION:
        return _news_cache_zh.copy()

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
                    print(f"成功从 {api['url']} 获取中文新闻，共 {len(news_list)} 条")
                    raw_news = news_list
                    break
        except Exception as e:
            print(f"API {api['url']} 失败: {e}")
            continue

    if not raw_news:
        return None

    _news_cache_zh = raw_news
    _cache_time_zh = current_time
    return raw_news.copy()

# ---------- 英文新闻API (APITube - 使用urllib) ----------
def fetch_news_en():
    """获取英文今日新闻；英文缓存与中文完全分离。"""
    global _news_cache_en, _cache_time_en
    current_time = time.time()
    if _news_cache_en is not None and (current_time - _cache_time_en) < CACHE_DURATION:
        return _news_cache_en.copy()

    try:
        url = f"{APITUBE_BASE_URL}?api_key={APITUBE_KEY}&language.code=en&per_page=10"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data.get("status") == "ok":
                articles = data.get("results", [])
                if articles:
                    news = [
                        {"title": article.get("title", ""), "url": article.get("href", "#")}
                        for article in articles if article.get("title")
                    ]
                    if news:
                        _news_cache_en = news
                        _cache_time_en = current_time
                        print(f"APITube 获取英文新闻，共 {len(news)} 条")
                        return news.copy()
    except Exception as e:
        print(f"英文新闻获取失败: {e}")
    return None

# ---------- 午夜新闻（统一接口，支持中英文 - 纯urllib） ----------
def fetch_midnight_news(lang='zh'):
    """
    获取午夜新闻。
    中文和英文使用完全独立的缓存：
    - 英文：直接显示 APITube 英文犯罪新闻
    - 中文：对筛选后的英文犯罪新闻逐条翻译
    同一种语言首次得到有效结果后，本次运行内保持该语言自己的结果。
    """
    global _midnight_cache_zh, _midnight_cache_en
    global _midnight_cache_time_zh, _midnight_cache_time_en

    is_en = (lang == 'en')
    if is_en and _midnight_cache_en is not None:
        return _midnight_cache_en.copy()
    if not is_en and _midnight_cache_zh is not None:
        return _midnight_cache_zh.copy()

    current_time = time.time()
    try:
        url = f"{APITUBE_BASE_URL}?api_key={APITUBE_KEY}&language.code=en&per_page=10"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data.get("status") == "ok":
                articles = data.get("results", [])
                if articles:
                    filtered_news = []
                    for article in articles:
                        title = article.get("title", "")
                        if any(keyword.lower() in title.lower() for keyword in MIDNIGHT_KEYWORDS):
                            filtered_news.append({
                                "title": title,
                                "url": article.get("href", "#")
                            })

                    print(f"APITube 获取到 {len(articles)} 条新闻，筛选后保留 {len(filtered_news)} 条犯罪新闻")

                    if filtered_news:
                        if is_en:
                            result = filtered_news
                            _midnight_cache_en = result
                            _midnight_cache_time_en = current_time
                            return result.copy()

                        print("正在翻译中文午夜新闻标题...")
                        translated_news = []
                        for item in filtered_news:
                            translated_news.append({
                                "title": translate_to_chinese(item["title"]),
                                "url": item["url"]
                            })
                        _midnight_cache_zh = translated_news
                        _midnight_cache_time_zh = current_time
                        return translated_news.copy()

                    print("没有找到匹配的犯罪新闻，将使用默认午夜新闻")
                else:
                    print("APITube 返回空结果，将使用默认午夜新闻")
            else:
                print(f"APITube 返回错误: {data.get('message', '未知错误')}")
    except Exception as e:
        print(f"午夜新闻获取失败: {e}")

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
    return os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "note.txt")

def load_notes():
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
        self.label.setGeometry(int(130 * scale), int(85 * scale), int(340 * scale), int(160 * scale))
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.label.setStyleSheet("background: transparent; color: #2c3e50;")
        # Keep the original visual size while compensating for Windows/Qt DPI scaling.
        # The pet's own screen-resolution scale is preserved; only the font's logical
        # point size is adjusted so 125%/150%/200% Windows scaling does not enlarge
        # the bubble text unexpectedly.
        dpi_scale = 1.0
        try:
            screen = QApplication.primaryScreen()
            if screen is not None:
                dpi = float(screen.logicalDotsPerInch())
                if dpi > 0:
                    dpi_scale = max(1.0, dpi / 96.0)
        except Exception:
            dpi_scale = 1.0

        normal_point_size = max(1.0, (18.0 * scale) / dpi_scale)
        big_point_size = max(1.0, (72.0 * scale) / dpi_scale)

        self.normal_font = QFont("Microsoft YaHei")
        self.normal_font.setPointSizeF(normal_point_size)
        self.big_font = QFont("Microsoft YaHei")
        self.big_font.setPointSizeF(big_point_size)
        self.label.setFont(self.normal_font)

        self.full_text = ""
        self.char_index = 0
        self.typing_timer = QTimer(self)
        self.typing_timer.timeout.connect(self.type_char)
        self.typing_interval = 50

        self.is_typing = False
        self.is_complete = False

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
            self.width() - int(248 * scale),
            self.height() - int(105 * scale),
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
        # 提醒超过1分钟未确认：先消失，稍后再次提醒。
        self.hide_confirmation_button()
        if self.parent() is not None:
            self.parent().reminder_dialog_timeout()

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

    def _text_height(self, text):
        fm = self.label.fontMetrics()
        rect = fm.boundingRect(0, 0, self.label.width(), 10000, Qt.TextWordWrap, text)
        return rect.height()

    def _split_for_bubble(self, text):
        max_height = int(160 * getattr(self.parent(), "scale", 1.0))
        if self._text_height(text) <= max_height:
            return text, ""

        low, high = 1, len(text)
        best = 1
        while low <= high:
            mid = (low + high) // 2
            part = text[:mid].rstrip()
            if self._text_height(part) <= max_height:
                best = mid
                low = mid + 1
            else:
                high = mid - 1

        cut = best
        prefix = text[:best]
        if " " in prefix:
            space_pos = prefix.rfind(" ")
            if space_pos >= max(1, best - 40):
                cut = space_pos

        first = text[:cut].rstrip()
        rest = text[cut:].lstrip()
        if not first:
            first = text[:best]
            rest = text[best:]
        return first, rest

    def type_char(self):
        if self.char_index < len(self.full_text):
            self.char_index += 1
            current_text = self.full_text[:self.char_index]
            if self._text_height(current_text) > int(160 * getattr(self.parent(), "scale", 1.0)):
                visible_text, remaining = self._split_for_bubble(self.full_text)
                self.typing_timer.stop()
                self.label.setText(visible_text)
                self.full_text = visible_text
                self.char_index = len(visible_text)
                self.is_typing = False
                self.is_complete = True
                if remaining:
                    parent = self.parent()
                    if parent is not None:
                        parent.start_dialog_continuation(
                            remaining,
                            getattr(self, "current_requires_confirmation", False)
                        )
                else:
                    parent = self.parent()
                    if parent is not None:
                        parent.on_dialog_complete()
            else:
                self.label.setText(current_text)
        else:
            self.typing_timer.stop()
            self.is_typing = False
            self.is_complete = True
            parent = self.parent()
            if parent is not None:
                parent.on_dialog_complete()

    def start_typing(self, text, requires_confirmation=False):
        self.label.setFont(self.normal_font)
        self.current_requires_confirmation = bool(requires_confirmation)
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
        global _news_cache_zh, _news_cache_en, _cache_time_zh, _cache_time_en
        _news_cache_zh = None
        _news_cache_en = None
        _cache_time_zh = 0
        _cache_time_en = 0
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
        global _midnight_cache_zh, _midnight_cache_en
        global _midnight_cache_time_zh, _midnight_cache_time_en
        _midnight_cache_zh = None
        _midnight_cache_en = None
        _midnight_cache_time_zh = 0
        _midnight_cache_time_en = 0
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
        self.sleep_time_label = QLabel("Time:" if (parent and parent.lang == 'en') else "时间：")
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
            self.sleep_time_label.setText("Time:")
            self.tomato_label.setText("")
            self.tomato_spin_label.setText("Set Duration:")
            self.tomato_btn.setText("▶ Start")
            self.tomato_reset_btn.setText("⟳ Reset")
            self.drink_check.setText("Drink")
            self.sleep_check.setText("Sleep")
            self.eat_label.setText("Lunch: 12:00  |  Dinner: 18:00")
            group1 = self.findChild(QGroupBox)
            if group1:
                group1.setTitle("Focus")
            groups = self.findChildren(QGroupBox)
            if len(groups) > 1:
                groups[1].setTitle("Reminders")
        else:
            self.title_label.setText("控制面板")
            self.sleep_time_label.setText("时间：")
            self.tomato_label.setText("")
            self.tomato_spin_label.setText("设置时长：")
            self.tomato_btn.setText("▶ 开始")
            self.tomato_reset_btn.setText("⟳ 重置")
            self.drink_check.setText("喝水")
            self.sleep_check.setText("睡觉")
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
            self.parent_pet.add_reminder_dialog('drink', 'drink')
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
            if (self.reminder_elapsed['喝水'] >= self.drink_spin.value() and
                    not self.parent_pet.is_reminder_pending('drink')):
                self.parent_pet.add_reminder_dialog('drink', 'drink')
                self.reminder_elapsed['喝水'] = 0

        if hour == 12 and minute == 0 and not self.lunch_triggered and not self.parent_pet.is_reminder_pending('lunch'):
            self.parent_pet.add_reminder_dialog('lunch', 'lunch')
            self.lunch_triggered = True
        if hour != 12:
            self.lunch_triggered = False

        if hour == 18 and minute == 0 and not self.parent_pet.is_reminder_pending('dinner') and not self.dinner_triggered:
            self.parent_pet.add_reminder_dialog('dinner', 'dinner')
            self.dinner_triggered = True
        if hour != 18:
            self.dinner_triggered = False

        if self.sleep_check.isChecked():
            set_h = self.sleep_hour.value()
            set_m = self.sleep_min.value()
            if hour == set_h and minute == set_m and not self.sleep_triggered and not self.parent_pet.is_reminder_pending('sleep'):
                self.parent_pet.add_reminder_dialog('sleep', 'sleep')
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


# ---------- DNT .save 角色系统 ----------
_DNT_RENDERER = None
_DNT_BOUNCE_CONFIG = {}

# 第7套服装专用图层标识
OUTFIT7_HEAD_ANTENNA_KEYWORDS = ['脑袋+天线', 'dnt-脑袋+天线', 'dnt-脑袋+天线.png']
OUTFIT7_MOUTH_KEYWORDS = ['嘴巴闭合2', 'dnt-嘴巴闭合2', 'spritesheet红']
OUTFIT7_BLACK_SCREEN_KEYWORDS = ['黑屏红', 'dnt-黑屏红']
OUTFIT1_6_BLACK_SCREEN_KEYWORDS = ['黑屏蓝', 'dnt-黑屏蓝']


class DNTRoleRenderer:
    def __init__(self):
        self.objects = []
        self.outfits = {}
        self.outfit_count = 7
        self.canvas_size = None

    def get_outfit_sprites(self, outfit_no):
        """获取指定服装的所有原始精灵数据"""
        result = []
        for obj in self.objects:
            if self._belongs_to_outfit(obj, outfit_no):
                result.append(obj)
        return result

    @staticmethod
    def _parse_layers(value):
        if isinstance(value, (list, tuple)):
            return list(value)
        if isinstance(value, str):
            try:
                value = json.loads(value)
                if isinstance(value, list):
                    return value
            except Exception:
                pass
            try:
                import ast
                value = ast.literal_eval(value)
                if isinstance(value, (list, tuple)):
                    return list(value)
            except Exception:
                pass
        return []

    @staticmethod
    def _truthy_layer(value):
        try:
            return int(value or 0) != 0
        except Exception:
            return str(value).strip().lower() not in ('', '0', '0.0', 'false', 'none', 'null')

    @staticmethod
    def _decode(data):
        try:
            if not data:
                return QPixmap()
            if ',' in data:
                data = data.split(',', 1)[1]
            raw = base64.b64decode(data)
            image = QImage.fromData(raw, 'PNG')
            if image.isNull():
                return QPixmap()
            return QPixmap.fromImage(image)
        except Exception:
            return QPixmap()

    @staticmethod
    def _frame(pixmap, index, count):
        if pixmap is None or pixmap.isNull():
            return QPixmap()
        count = max(1, int(count or 1))
        if count == 1:
            return pixmap
        fw = pixmap.width() // count
        if fw <= 0:
            return pixmap
        index %= count
        return pixmap.copy(index * fw, 0, fw, pixmap.height())

    @staticmethod
    def _vector(value):
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                return float(value[0]), float(value[1])
            except Exception:
                return 0.0, 0.0
        if isinstance(value, str):
            m = re.search(r'Vector2\(([-+0-9.eE]+),\s*([-+0-9.eE]+)\)', value)
            if m:
                return float(m.group(1)), float(m.group(2))
        return 0.0, 0.0

    def _path_text(self, obj):
        return (str(obj.get('path', '')) + ' ' + str(obj.get('name', '')) + ' ' + str(obj.get('title', ''))).lower()

    def _talk_mode(self, obj):
        try:
            return int(obj.get('showTalk', 0) or 0)
        except Exception:
            s = str(obj.get('showTalk', '')).strip().lower()
            if s in ('1', 'closed', 'close', 'mouth_closed'):
                return 1
            if s in ('2', 'open', 'talk', 'mouth_open'):
                return 2
            return 0

    def _is_head(self, obj):
        p = self._path_text(obj)
        return any(k in p for k in ('脑袋', '脑', '头部', '头.png', 'head.png', 'head_', '_head', '/head', '\\head'))

    def _is_antenna(self, obj):
        p = self._path_text(obj)
        return any(k in p for k in ('天线', 'antenna', 'antennae'))

    def _is_mouth(self, obj):
        p = self._path_text(obj)
        return self._talk_mode(obj) in (1, 2) or any(k in p for k in ('嘴巴', '嘴', 'mouth', 'lip', 'lips'))

    def _is_base_character(self, obj):
        return self._is_head(obj) or self._is_antenna(obj) or self._is_mouth(obj)

    def _is_cloak(self, obj):
        p = self._path_text(obj)
        return '斗篷' in p or 'cloak' in p

    def _is_outfit7_head_antenna(self, obj):
        """检查是否是第7套的'脑袋+天线'组合图层"""
        p = self._path_text(obj)
        for keyword in OUTFIT7_HEAD_ANTENNA_KEYWORDS:
            if keyword.lower() in p:
                return True
        return False

    def _is_outfit7_mouth(self, obj):
        """检查是否是第7套的嘴巴图层（包含spritesheet红）"""
        p = self._path_text(obj)
        for keyword in OUTFIT7_MOUTH_KEYWORDS:
            if keyword.lower() in p:
                return True
        return False

    def _is_outfit7_black_screen(self, obj):
        """检查是否是第7套的黑屏图层"""
        p = self._path_text(obj)
        for keyword in OUTFIT7_BLACK_SCREEN_KEYWORDS:
            if keyword.lower() in p:
                return True
        return False

    def _is_outfit1_6_black_screen(self, obj):
        """检查是否是1-6套的黑屏图层"""
        p = self._path_text(obj)
        for keyword in OUTFIT1_6_BLACK_SCREEN_KEYWORDS:
            if keyword.lower() in p:
                return True
        return False

    def _explicit_outfit(self, obj):
        p = self._path_text(obj)
        if any(k in p for k in ('帽子', 'hat', 'headwear')):
            return 5
        if self._is_cloak(obj):
            return 4
        patterns = (
            r'(?:服装|衣服|身体|outfit|costume|body)[\s_\-\[\]\(\)]*(?:第)?([1-7])(?:套)?',
            r'(?:第)([1-7])(?:套)?',
        )
        for pattern in patterns:
            m = re.search(pattern, p)
            if m:
                n = int(m.group(1))
                if 1 <= n <= 7:
                    return n
        return None

    def _belongs_to_outfit(self, obj, outfit_no):
        p = self._path_text(obj)

        # 黑屏是“独立叠加层”，不能参与普通闭嘴/张嘴合成。
        # 黑屏显示时会在 DesktopPet 中叠加到已经完整合成的角色上。
        if self._is_outfit7_black_screen(obj) or self._is_outfit1_6_black_screen(obj):
            return False

        # 第7套的“脑袋+天线”组合图层只属于第7套
        if self._is_outfit7_head_antenna(obj):
            return outfit_no == 7

        # 第7套专属嘴巴只属于第7套
        if self._is_outfit7_mouth(obj):
            return outfit_no == 7

        # 普通嘴巴属于1-6套。
        # dnt.save 中1-6套各自保存了一份相同的“嘴巴闭合”图片，
        # 但它们的 showTalk / pos 并不完全一致；不能把其中任意一份
        # 同时当成所有1-6套的 normal layer，否则 open[1]/open[2]
        # 合成时会把闭嘴图层一起留在张嘴图层下面，形成“最后一帧叠加”。
        if '嘴巴闭合' in p and '嘴巴闭合2' not in p:
            regular_mouths = [
                item for item in self.objects
                if '嘴巴闭合' in self._path_text(item)
                and '嘴巴闭合2' not in self._path_text(item)
                and not self._is_outfit7_mouth(item)
            ]
            if 1 <= outfit_no <= 6:
                try:
                    return obj is regular_mouths[outfit_no - 1]
                except IndexError:
                    return False
            return False

        # 基础角色部件（脑袋、天线）
        if self._is_head(obj) or self._is_antenna(obj):
            # 第7套使用组合图层，不使用独立的脑袋和天线
            if outfit_no == 7:
                return False
            return True

        explicit = self._explicit_outfit(obj)
        if explicit is not None:
            return explicit == outfit_no

        # 张嘴图层有些 save 版本没有写正确的 costumeLayers / outfit 标记。
        # 1-6 套的张嘴素材本身相同，因此在没有显式套装信息时，
        # 按 save 中1-6套张嘴图层的出现顺序进行对应。
        if self._talk_mode(obj) == 2 and 1 <= outfit_no <= 6:
            open_mouths = [
                item for item in self.objects
                if self._talk_mode(item) == 2
                and not self._is_outfit7_mouth(item)
            ]
            try:
                return obj is open_mouths[outfit_no - 1]
            except IndexError:
                pass

        layers = self._parse_layers(obj.get('costumeLayers'))
        if not layers:
            return False
        active = [i for i, value in enumerate(layers) if self._truthy_layer(value)]
        if not active:
            return True
        if outfit_no == 7:
            return any(slot >= 12 for slot in active)
        if outfit_no == 6:
            return any(slot >= 10 for slot in active)
        return any((slot // 2) + 1 == outfit_no for slot in active)

    def _get_black_screen_obj(self, outfit_no):
        """
        返回当前套装真正对应的黑屏对象。

        dnt.save 中1-6套的蓝色黑屏各自保存了不同的 pos：
        它们不能再像旧代码一样“找到第一个黑屏就使用”，否则
        第2-6套会全部错误使用第1套的定位。
        当前 save 的对象顺序正好对应：
            蓝色黑屏第1个 -> outfit 1
            蓝色黑屏第2个 -> outfit 2
            ...
            蓝色黑屏第6个 -> outfit 6
            红色黑屏 -> outfit 7
        """
        try:
            outfit_no = int(outfit_no)
        except Exception:
            return None

        if 1 <= outfit_no <= 6:
            blue = [
                obj for obj in self.objects
                if self._is_outfit1_6_black_screen(obj)
            ]
            return blue[outfit_no - 1] if outfit_no - 1 < len(blue) else None

        if outfit_no == 7:
            red = [
                obj for obj in self.objects
                if self._is_outfit7_black_screen(obj)
            ]
            return red[0] if red else None

        return None

    def _layer_sort_key(self, obj):
        p = self._path_text(obj)
        # 第7套的"脑袋+天线"组合图层放在较高层级
        if self._is_outfit7_head_antenna(obj):
            return (1000, int(obj.get('zindex', 0) or 0), obj.get('_order', 0))
        if self._is_head(obj) or self._is_antenna(obj):
            return (1000, int(obj.get('zindex', 0) or 0), obj.get('_order', 0))
        if self._is_mouth(obj):
            return (1100, int(obj.get('zindex', 0) or 0), obj.get('_order', 0))
        if self._is_cloak(obj):
            return (-2000, int(obj.get('zindex', 0) or 0), obj.get('_order', 0))
        return (0, int(obj.get('zindex', 0) or 0), obj.get('_order', 0))

    def _make_canvas_size(self):
        w = h = 1
        for obj in self.objects:
            pm = obj.get('pixmap')
            if pm is not None and not pm.isNull():
                w = max(w, pm.width())
                h = max(h, pm.height())
        self.canvas_size = (w, h)

    def _dedupe_layers(self, layers):
        result = []
        seen = set()
        for obj in layers:
            data = obj.get('imageData', '')
            if data:
                key = data
            else:
                key = (obj.get('_order'), obj.get('path'), obj.get('name'))
            if key in seen:
                continue
            seen.add(key)
            result.append(obj)
        return sorted(result, key=self._layer_sort_key)

    def _compose(self, layers, frame_index):
        w, h = self.canvas_size
        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        for obj in self._dedupe_layers(layers):
            pm = obj.get('pixmap')
            if pm is None or pm.isNull():
                continue
            frame = self._frame(pm, frame_index, max(1, int(obj.get('frames', 1) or 1)))
            painter.drawPixmap(0, 0, frame)
        painter.end()
        return QPixmap.fromImage(image)

    def _build_outfit(self, outfit_no):
        selected = [obj for obj in self.objects if self._belongs_to_outfit(obj, outfit_no)]
        if not selected:
            return None

        # 黑屏已经被明确排除在 selected 之外。
        # 这样正常状态下不会一直带着黑屏；黑屏触发时单独叠加。
        # 1-6套的“嘴巴闭合”是闭嘴专用层，即使 save 中某一份
        # 的 showTalk 被写成 0，也绝不能把它放进 normal；否则
        # open_sources = normal + opened 时，闭嘴嘴巴会留在 open[1]/open[2]
        # 的底下，最终看起来像“第三帧叠加了前一帧”。
        def is_regular_mouth(obj):
            p = self._path_text(obj)
            return (
                '嘴巴闭合' in p
                and '嘴巴闭合2' not in p
                and not self._is_outfit7_mouth(obj)
            )

        normal = [
            obj for obj in selected
            if self._talk_mode(obj) == 0 and not is_regular_mouth(obj)
        ]
        closed = [
            obj for obj in selected
            if self._talk_mode(obj) == 1 or is_regular_mouth(obj)
        ]
        opened = [obj for obj in selected if self._talk_mode(obj) == 2]

        closed_sources = normal + closed
        if not closed_sources:
            closed_sources = selected
        open_sources = normal + opened

        closed_count = max(
            [int(obj.get('frames', 1) or 1) for obj in closed_sources] or [1]
        )
        mouth_count = max(
            [int(obj.get('frames', 1) or 1) for obj in opened] or [0]
        )

        closed_frames = [
            self._compose(closed_sources, i) for i in range(closed_count)
        ]

        open_frames = []
        if opened:
            open_frames = [
                self._compose(open_sources, i) for i in range(mouth_count)
            ]

        speed_candidates = [
            float(obj.get('animSpeed', 0) or 0)
            for obj in normal
            if float(obj.get('animSpeed', 0) or 0) > 0
        ]
        anim_speed = max(speed_candidates) if speed_candidates else 0.0

        bounce_layers = normal

        def max_abs(field):
            return max(
                [abs(float(obj.get(field, 0) or 0)) for obj in bounce_layers]
                or [0.0]
            )

        def first_nonzero(field):
            for obj in bounce_layers:
                v = float(obj.get(field, 0) or 0)
                if v:
                    return v
            return 0.0

        black_obj = self._get_black_screen_obj(outfit_no)
        black_pixmap = black_obj.get('pixmap') if black_obj else None
        black_pos = black_obj.get('pos', (0.0, 0.0)) if black_obj else (0.0, 0.0)
        black_offset = black_obj.get('offset', (0.0, 0.0)) if black_obj else (0.0, 0.0)

        return {
            'closed_frames': closed_frames,
            'open_frames': open_frames,
            'animSpeed': anim_speed,
            'bounce': {
                'xAmp': max_abs('xAmp'),
                'yAmp': max_abs('yAmp'),
                'xFrq': first_nonzero('xFrq'),
                'yFrq': first_nonzero('yFrq'),
                'stretchAmount': max_abs('stretchAmount')
            },
            # 黑屏作为独立覆盖层保存，绝不替换角色本体。
            'black_screen': black_pixmap,
            'black_screen_pos': black_pos,
            'black_screen_offset': black_offset
        }

    def load(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            a = content.find('{')
            b = content.rfind('}') + 1
            if a < 0 or b <= a:
                raise ValueError('无法找到 JSON 数据')
            data = json.loads(content[a:b])
            self.objects = []
            for order, (key, obj) in enumerate(data.items()):
                if not str(key).isdigit() or not isinstance(obj, dict):
                    continue
                pm = self._decode(obj.get('imageData'))
                if pm.isNull():
                    continue
                item = dict(obj)
                item['pixmap'] = pm
                item['frames'] = max(1, int(obj.get('frames', 1) or 1))
                item['showTalk'] = self._talk_mode(obj)
                item['zindex'] = int(obj.get('zindex', 0) or 0)
                item['pos'] = self._vector(obj.get('pos', 'Vector2(0, 0)'))
                item['offset'] = self._vector(obj.get('offset', 'Vector2(0, 0)'))
                item['_order'] = order
                self.objects.append(item)

            if not self.objects:
                raise ValueError('没有可读取的 Base64 PNG 图层')
            self._make_canvas_size()
            self.outfits = {}
            self.outfit_count = 7
            for n in range(1, 8):
                built = self._build_outfit(n)
                if built and built.get('closed_frames'):
                    self.outfits[n] = built

            # 第6套如果 save 内没有被正确识别到 open 图层，
            # 使用1-5套共用的同款张嘴素材，保证第6套对话动画仍可正常播放。
            if 6 in self.outfits and not self.outfits[6].get('open_frames'):
                for fallback_no in (1, 2, 3, 4, 5):
                    fallback = self.outfits.get(fallback_no)
                    if fallback and fallback.get('open_frames'):
                        self.outfits[6]['open_frames'] = list(fallback['open_frames'])
                        print(f'Outfit 6: open frames fallback to outfit {fallback_no}')
                        break

            print(f'DNT save loaded: {file_path}')
            print('Available outfits:', sorted(self.outfits.keys()))
            for n in range(1, 8):
                o = self.outfits.get(n)
                if o:
                    print(f'Outfit {n}: closed={len(o["closed_frames"])}, open={len(o["open_frames"])}, animSpeed={o["animSpeed"]}')
                else:
                    print(f'Outfit {n}: EMPTY')
            return True
        except Exception as e:
            print(f'读取 DNT save 失败: {e}')
            import traceback
            traceback.print_exc()
            return False


def _find_dnt_save():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, 'dnt.save')
    return path if os.path.isfile(path) else None


def _load_dnt_save_layers():
    global _DNT_RENDERER, _DNT_BOUNCE_CONFIG
    path = _find_dnt_save()
    if not path:
        return None, None
    renderer = DNTRoleRenderer()
    if not renderer.load(path):
        return None, None
    _DNT_RENDERER = renderer
    first = min(renderer.outfits.keys())
    outfit = renderer.outfits[first]
    _DNT_BOUNCE_CONFIG = outfit['bounce']
    return outfit['closed_frames'][0], outfit['open_frames'][0]


# ============================================================
# 主窗口 DesktopPet
# ============================================================
class DesktopPet(QWidget):
    def __init__(self):
        super().__init__()
        set_windows_autostart(True)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        screen_w, screen_h = get_screen_size()
        self.setFixedSize(screen_w, screen_h)
        self.move(0, 0)

        self.scale = min(screen_w / 1920, screen_h / 1080)
        self.lang = 'zh'

        # 桌宠形态：dnt = 07版完整DNT动画；classic = 原index的pet1~pet9动画。
        self.pet_form = 'dnt'
        self._happy_transition_active = False
        self.legacy_pet_frames = []
        self.legacy_pet_happy = QPixmap()
        self.legacy_frame_index = 0
        self.legacy_bounce_time = 0.0
        self._form_switch_timer = None

        # 加载原 index 的 pet1~pet9 / pet-happy 资源。
        for i in range(1, 10):
            pm = QPixmap(resource_path(f"pet{i}.png"))
            if not pm.isNull():
                self.legacy_pet_frames.append(pm.scaled(
                    int(pm.width() * self.scale),
                    int(pm.height() * self.scale),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                ))
        if not self.legacy_pet_frames:
            fallback = QPixmap(resource_path("pet.png"))
            if not fallback.isNull():
                self.legacy_pet_frames = [fallback.scaled(
                    int(fallback.width() * self.scale),
                    int(fallback.height() * self.scale),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )]
        happy = QPixmap(resource_path("pet-happy.png"))
        if not happy.isNull():
            self.legacy_pet_happy = happy.scaled(
                int(happy.width() * self.scale),
                int(happy.height() * self.scale),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

        # 初始化对话队列
        self.dialog_queue = []
        self.is_displaying = False
        self.dialog_timer = None
        self.current_dialog_requires_confirmation = False
        self.current_reminder_key = None
        self._reminder_retry_timers = {}
        self._pending_reminders = set()

        # 番茄钟相关
        self.tomato_display_active = False
        self.tomato_update_timer = QTimer(self)

        # 动画相关
        self.animation_paused = False
        self.auto_dialog_enabled = True
        self.animation_timer_started = False

        # 弹跳相关
        self.idle_bounce_active = True
        self.idle_bounce_time = 0.0
        self.idle_x_amp = 0.0
        self.idle_y_amp = 0.0
        self.idle_x_frq = 0.0
        self.idle_y_frq = 0.0
        self.idle_stretch = 0.0

        # 嘴巴动画相关 - 必须在_load_current_outfit之前初始化
        self._mouth_phase = 0  # 0=闭嘴, 1=张嘴
        self._stop_after_play = False
        self._mouth_animation_active = False
        self._mouth_end_animation = False

        # 黑屏相关 - 用于记录黑屏是否正在显示
        self._black_screen_active = False
        # 保存黑屏显示前的帧，用于恢复
        self._black_screen_previous_pixmap = None

        # 创建系统托盘图标（先创建，避免后面报错）
        self.create_tray_icon()

        # 加载 DNT .save 角色系统
        self.pet_static, self.pet_talking = _load_dnt_save_layers()
        self.role_renderer = globals().get("_DNT_RENDERER")

        if self.pet_static is None or self.role_renderer is None:
            raise FileNotFoundError(
                "未找到可用的 dnt.save，请将 dnt.save 放在 "
                "index.py / DesktopPet.exe 同目录。"
            )

        self.available_outfits = sorted(self.role_renderer.outfits.keys())
        self.current_outfit = self.available_outfits[0]
        self.outfit_count = 7

        self.pet_closed_frames = []
        self.pet_open_frames = []

        # 黑屏定时器（在_load_current_outfit之前创建）
        self.black_screen_timer = QTimer(self)
        self.black_screen_timer.setSingleShot(True)
        self.black_screen_timer.timeout.connect(self._show_black_screen)

        self.black_screen_hide_timer = QTimer(self)
        self.black_screen_hide_timer.setSingleShot(True)
        self.black_screen_hide_timer.timeout.connect(self._hide_black_screen)

        # 桌宠缩放：Ctrl + 鼠标滚轮，仅在鼠标位于桌宠上时生效。
        self.pet_zoom = 1.0
        self.pet_zoom_min = 0.5
        self.pet_zoom_max = 2.0
        self.pet_zoom_step = 0.1

        self._load_current_outfit(self.current_outfit)

        self.pet_frames = list(self.pet_closed_frames)
        self.pet_static = self.pet_frames[0] if self.pet_frames else QPixmap()
        self.pet_talking = self.pet_open_frames[0] if self.pet_open_frames else self.pet_static
        self.pet_happy = self.pet_static

        self.current_frame_index = 0
        self._talking_one_shot = False
        self.current_pixmap = self.pet_frames[0] if self.pet_frames else QPixmap()

        # 闲置动画参数 - 从save中读取
        self.idle_bounce_active = True
        self.idle_bounce_time = 0.0
        self.idle_x_amp = 0.0
        self.idle_y_amp = 0.0
        self.idle_x_frq = 0.0
        self.idle_y_frq = 0.0
        self.idle_stretch = 0.0
        self._idle_last_tick = time.monotonic()
        self._load_idle_bounce_params()

        pet_w = self.pet_frames[0].width() if self.pet_frames else 200
        pet_h = self.pet_frames[0].height() if self.pet_frames else 200

        self.label = FadeLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWindowOpacity(1.0)
        self.label.installEventFilter(self)
        self._show_pet_frame_fixed(self.pet_static)

        self.bubble = BubbleWidget(self)

        # 对话张嘴定时器 - 0.1秒切换闭嘴和开口
        self.mouth_timer = QTimer(self)
        self.mouth_timer.setInterval(100)  # 0.1秒
        self.mouth_timer.timeout.connect(self._toggle_talking_mouth)
        self.is_talking_mouth_open = False
        self._talk_open_one_shot = False
        self.current_mouth_frame_index = 0

        # 对话弹跳状态
        self.dialogue_bounce_active = False
        self.dialogue_bounce_elapsed = 0.0
        self.dialogue_session_active = False
        self._talk_open_session_started = False

        # 闲置弹跳定时器
        self.idle_bounce_timer = QTimer(self)
        self.idle_bounce_timer.timeout.connect(self._update_idle_bounce)
        self.idle_bounce_timer.start(50)

        self.control_panel = None
        self.news_window = None
        self.midnight_window = None
        self.note_window = None

        self.animation_paused = False
        self.auto_dialog_enabled = True

        self.startup_frames = [self.pet_happy] + self.pet_frames if self.pet_frames else [self.pet_happy]
        self._happy_transition_active = True
        self.startup_index = 0
        self.startup_timer = QTimer(self)
        self.startup_timer.timeout.connect(self._startup_animation)
        self.startup_timer.start(1000)

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._next_frame)
        self.animation_timer_started = False

        # 对话弹跳定时器 - 独立驱动
        self.dialogue_bounce_timer = QTimer(self)
        self.dialogue_bounce_timer.timeout.connect(self._update_dialogue_bounce)
        self.dialogue_bounce_timer.setInterval(50)

        self.drag_pos = None
        self.is_dragging = False

        self.random_timer = QTimer(self)
        self.random_timer.timeout.connect(self._random_dialog)
        self.random_timer.start(30 * 60 * 1000)

        self.note_repeat_timer = QTimer(self)
        self.note_repeat_timer.timeout.connect(self._repeat_random_note)
        self.note_repeat_timer.start(60 * 1000)
        self.note_repeat_elapsed = 0

        # 创建菜单
        self.create_menu()

        self.add_dialog(random.choice(get_dialogues(self.lang, 'start')))

        # 启动时必须先强制显示文件夹中的 pet-happy.png 1 秒。
        # 不能依赖 startup_frames = [happy] + pet_frames，
        # 因为初始化过程中前面的 pet_static / 对话 / 黑屏逻辑可能覆盖首帧。
        self._start_happy_transition()

    def _load_idle_bounce_params(self):
        """读取当前套装在 dnt.save 中保存的 DuangDuang 参数。

        不再给所有套装强行使用同一组参数。尤其第7套在 save 中
        的 xAmp/yAmp/xFrq/yFrq/stretchAmount 与 1-6 套不同，统一
        使用固定的大参数会把第7套的 Squash 放大成明显抖动。
        """
        outfit = getattr(self, 'role_renderer', None)
        outfit = outfit.outfits.get(self.current_outfit, {}) if outfit else {}
        cfg = outfit.get('bounce', {}) or {}

        self.idle_x_amp = float(cfg.get('xAmp', 3.0) or 3.0)
        self.idle_y_amp = float(cfg.get('yAmp', 6.0) or 6.0)
        self.idle_x_frq = float(cfg.get('xFrq', 0.02) or 0.02)
        self.idle_y_frq = float(cfg.get('yFrq', 0.025) or 0.025)
        self.idle_stretch = abs(float(cfg.get('stretchAmount', 4.25) or 4.25))

        print(f"Outfit {self.current_outfit} bounce - "
              f"xAmp: {self.idle_x_amp}, yAmp: {self.idle_y_amp}, "
              f"xFrq: {self.idle_x_frq}, yFrq: {self.idle_y_frq}, "
              f"stretch: {self.idle_stretch}")
        
    def _load_current_outfit(self, outfit_no):
        outfit = self.role_renderer.outfits.get(outfit_no)
        if not outfit:
            return False

        self.current_outfit = outfit_no

        def scale_frames(frames):
            result = []
            for pixmap in frames:
                if pixmap is None or pixmap.isNull():
                    continue
                zoom = float(getattr(self, "pet_zoom", 1.0))
                result.append(pixmap.scaled(
                    max(1, int(round(pixmap.width() * self.scale * zoom))),
                    max(1, int(round(pixmap.height() * self.scale * zoom))),
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                ))
            return result

        self.pet_closed_frames = scale_frames(outfit.get('closed_frames', []))
        self.pet_open_frames = scale_frames(outfit.get('open_frames', []))

        if not self.pet_closed_frames:
            return False

        self.pet_frames = list(self.pet_closed_frames)
        self.pet_static = self.pet_closed_frames[0]
        self.pet_talking = self.pet_open_frames[0] if self.pet_open_frames else self.pet_static
        self.pet_happy = self.pet_static

        self.current_frame_index = 0
        self.current_mouth_frame_index = 0
        self._talk_open_one_shot = False

        # 更新闲置弹跳参数
        self._load_idle_bounce_params()

        # 更新动画速度
        self.save_anim_speed = float(outfit.get('animSpeed', 0) or 0)
        if self.save_anim_speed > 0:
            self.save_animation_interval = max(30, int(1000 / self.save_anim_speed))
        else:
            self.save_animation_interval = 300

        self.current_pixmap = self.pet_static
        self._idle_last_tick = time.monotonic()

        # 切换套装时保持同一个渲染画布尺寸。
        # 不让 QLabel 在套装之间从 400x400 / 448x448 来回变化，
        # 否则 Qt 的重排和整数取整会表现成“抖动”。
        if hasattr(self, 'label'):
            self._show_pet_frame_fixed(self.pet_static)

        if hasattr(self, 'animation_timer'):
            if self.animation_timer.isActive():
                self.animation_timer.stop()
            if getattr(self, 'animation_timer_started', False) and not getattr(self, 'animation_paused', False):
                self.animation_timer.start(self.save_animation_interval)

        return True

    def change_outfit(self, outfit_no):
        if getattr(self, 'pet_form', 'dnt') != 'dnt':
            return
        try:
            outfit_no = int(outfit_no)
        except Exception:
            return
        if outfit_no not in self.role_renderer.outfits:
            return
        was_talking = self.is_displaying
        if getattr(self, "_black_screen_active", False):
            self._hide_black_screen()
        if hasattr(self, "mouth_timer"):
            self.mouth_timer.stop()
        if self._load_current_outfit(outfit_no):
            for i, action in enumerate(getattr(self, 'costume_actions', []), start=1):
                action.setChecked(i == outfit_no)
            if was_talking:
                if self.pet_open_frames:
                    self._show_pet_frame_fixed(self.pet_open_frames[0])
                else:
                    self._show_pet_frame_fixed(self.pet_static)
            else:
                if self.pet_closed_frames:
                    self._show_pet_frame_fixed(self.pet_closed_frames[self.current_frame_index % len(self.pet_closed_frames)])
                else:
                    self._show_pet_frame_fixed(self.pet_static)

        # 切换服装后立即用当前动画相位重绘一次固定画布，避免
        # 新旧套装的 QLabel / pixmap 尺寸在两个定时器之间来回跳变。
        if self.pet_frames and not self.is_displaying and not self._mouth_animation_active:
            self._update_idle_bounce()

        # 切换服装后重新启动黑屏计时器
        self._start_black_screen_timer()

    # ==================== 黑屏图层功能 ====================
    def _start_black_screen_timer(self):
        """启动黑屏计时器（闲置5秒后显示）"""
        if not hasattr(self, 'black_screen_timer'):
            return
        self.black_screen_timer.stop()
        if getattr(self, 'pet_form', 'dnt') == 'classic':
            return
        if getattr(self, '_happy_transition_active', False):
            return
        # 条件：没有对话、没有番茄钟、没有嘴部动画、没有黑屏正在显示、没有拖拽
        if (not self.is_displaying and 
            not self.tomato_display_active and
            not self._mouth_animation_active and
            not self._black_screen_active and
            not self.is_dragging):
            self.black_screen_timer.start(900000)  # 900秒后显示

    def _show_black_screen(self):
        """显示黑屏覆盖层：仅 DNT 形态允许显示。"""
        if getattr(self, 'pet_form', 'dnt') == 'classic' or getattr(self, '_happy_transition_active', False):
            return
        if (self.is_displaying or
            self.tomato_display_active or
            self._mouth_animation_active or
            self._black_screen_active or
            self.is_dragging):
            return

        outfit = self.role_renderer.outfits.get(self.current_outfit, {})
        black_screen = outfit.get('black_screen')

        if black_screen is None or black_screen.isNull():
            return

        # 保存黑屏前的完整角色帧。
        # 注意：这里保存的是“角色本体”，不是黑屏替代图。
        self._black_screen_previous_pixmap = self.current_pixmap

        # 当前角色画布已经是完整的400x400合成图；
        # 黑屏也放到同一画布上，再按照 dnt.save 中该套装自己的
        # pos + offset 放置，最后一次性显示。
        combined = self._compose_black_screen_overlay(
            self.current_pixmap,
            outfit
        )

        if combined is None or combined.isNull():
            return

        self._black_screen_active = True
        self._set_mouth_frame_centered(combined)

        self.black_screen_hide_timer.stop()
        self.black_screen_hide_timer.start(3000)

    def _compose_black_screen_overlay(self, base_pixmap, outfit):
        """把黑屏叠加到完整角色上，而不是替换完整角色。"""
        if base_pixmap is None or base_pixmap.isNull():
            return QPixmap()

        black = outfit.get('black_screen')
        if black is None or black.isNull():
            return base_pixmap

        # 角色本体与黑屏保持同一个原始画布尺寸。
        canvas_w = base_pixmap.width()
        canvas_h = base_pixmap.height()

        image = QImage(
            canvas_w,
            canvas_h,
            QImage.Format_ARGB32_Premultiplied
        )
        image.fill(Qt.transparent)

        painter = QPainter(image)
        painter.drawPixmap(0, 0, base_pixmap)

        try:
            px, py = outfit.get('black_screen_pos', (0.0, 0.0))
            ox, oy = outfit.get('black_screen_offset', (0.0, 0.0))
            px = float(px) + float(ox)
            py = float(py) + float(oy)
        except Exception:
            px, py = 0.0, 0.0

        # base_pixmap 同时已经按 self.scale 和当前 pet_zoom 缩放。
        # 黑屏覆盖层必须使用完全相同的缩放倍率，否则桌宠放大/缩小时，
        # 黑屏的位置和尺寸会停留在原来的倍率。
        zoom = float(getattr(self, "pet_zoom", 1.0))
        effective_scale = self.scale * zoom

        x = int(round(px * effective_scale))
        y = int(round(py * effective_scale))

        scaled_black = black.scaled(
            max(1, int(round(black.width() * effective_scale))),
            max(1, int(round(black.height() * effective_scale))),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
        )

        # 黑屏的 z-order 固定高于头、身体、嘴巴、服装。
        painter.drawPixmap(x, y, scaled_black)
        painter.end()

        return QPixmap.fromImage(image)

    def _hide_black_screen(self):
        """隐藏黑屏覆盖层，恢复完整角色帧。"""
        self._black_screen_active = False
        self.black_screen_hide_timer.stop()

        if self._black_screen_previous_pixmap and not self._black_screen_previous_pixmap.isNull():
            self._set_mouth_frame_centered(self._black_screen_previous_pixmap)
            self.current_pixmap = self._black_screen_previous_pixmap
        elif self.pet_closed_frames:
            idx = self.current_frame_index % len(self.pet_closed_frames)
            pixmap = self.pet_closed_frames[idx]
            self._set_mouth_frame_centered(pixmap)
            self.current_pixmap = pixmap
        else:
            self._set_mouth_frame_centered(self.pet_static)
            self.current_pixmap = self.pet_static

        self._black_screen_previous_pixmap = None
        self._start_black_screen_timer()

    def _reset_black_screen_timer(self):
        """重置黑屏计时器（用户交互时调用）。"""
        if self._black_screen_active:
            self._hide_black_screen()

        if hasattr(self, 'black_screen_timer'):
            self.black_screen_timer.stop()

            # 对话/嘴部动画/番茄钟期间不启动黑屏。
            if (not self.is_displaying and
                not self.tomato_display_active and
                not self._mouth_animation_active and
                not self.is_dragging):
                self.black_screen_timer.start(5000)

    # ==================== 稳定角色渲染 ====================
    def _get_pet_render_size(self):
        """返回所有套装共用的固定渲染画布尺寸。"""
        if getattr(self, 'pet_static', None) is not None and not self.pet_static.isNull():
            base_w = self.pet_static.width()
            base_h = self.pet_static.height()
        elif getattr(self, 'pet_frames', None):
            base_w = self.pet_frames[0].width()
            base_h = self.pet_frames[0].height()
        else:
            base_w = base_h = max(1, int(round(400 * getattr(self, 'scale', 1.0))))

        # dnt.save 的普通角色帧都是同一 400x400 画布。
        # 留出固定透明边距给 Squash/Stretch，整个程序生命周期内不改变。
        pad = 1.12
        return (max(1, int(round(base_w * pad))),
                max(1, int(round(base_h * pad))))

    def _render_pet_to_fixed_canvas(self, pixmap, scale_x=1.0, scale_y=1.0):
        """把角色帧绘制到固定画布，避免 QLabel 尺寸变化造成抖动。"""
        if pixmap is None or pixmap.isNull():
            return QPixmap()

        canvas_w, canvas_h = self._get_pet_render_size()
        canvas = QPixmap(canvas_w, canvas_h)
        canvas.fill(Qt.transparent)

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.translate(canvas_w / 2.0, canvas_h / 2.0)
        painter.scale(float(scale_x), float(scale_y))
        painter.drawPixmap(
            int(round(-pixmap.width() / 2.0)),
            int(round(-pixmap.height() / 2.0)),
            pixmap
        )
        painter.end()
        return canvas

    def _show_pet_frame_fixed(self, pixmap, x_offset=0.0, y_offset=0.0,
                              scale_x=1.0, scale_y=1.0):
        """统一显示角色帧：永远使用同一 QLabel 尺寸。"""
        if pixmap is None or pixmap.isNull() or not hasattr(self, 'label'):
            return

        canvas = self._render_pet_to_fixed_canvas(
            pixmap, scale_x=scale_x, scale_y=scale_y
        )
        if canvas.isNull():
            return

        canvas_w = canvas.width()
        canvas_h = canvas.height()
        center_x = self.width() / 2.0 + float(x_offset)
        center_y = self.height() / 2.0 + float(y_offset)
        x = int(round(center_x - canvas_w / 2.0))
        y = int(round(center_y - canvas_h / 2.0))

        self.label.setGeometry(x, y, canvas_w, canvas_h)
        self.label.setPixmap(canvas)
        self.label.setWindowOpacity(1.0)
        self.label.update()

    # ==================== 闲置弹跳动画 ====================
    def _update_idle_bounce(self):
        """闲置弹跳 + Squash/Stretch。

        关键修复：角色永远绘制到同一个固定画布，动画只改变画布内部
        的缩放和整个画布的位置，不再改变 QLabel 的宽高。
        """
        if getattr(self, '_happy_transition_active', False):
            return
        if self._black_screen_active:
            return
        if getattr(self, "_mouth_end_animation", False):
            return
        if self.pet_form == 'classic':
            self._update_classic_bounce()
            return
        if self.tomato_display_active:
            return
        if self.dialogue_bounce_active:
            return
        if self.is_dragging:
            return
        if not self.pet_frames:
            return

        now = time.monotonic()
        last = getattr(self, "_idle_last_tick", None)
        if last is None:
            dt = 0.05
        else:
            dt = max(0.001, min(0.10, now - last))
        self._idle_last_tick = now
        self.idle_bounce_time += dt
        t = self.idle_bounce_time

        x_amp = float(getattr(self, "idle_x_amp", 3.0))
        y_amp = float(getattr(self, "idle_y_amp", 6.0))
        x_frq = float(getattr(self, "idle_x_frq", 0.02))
        y_frq = float(getattr(self, "idle_y_frq", 0.025))

        phase_x = t * x_frq * 2.0 * math.pi
        phase_y = t * y_frq * 2.0 * math.pi
        bounce_x = math.sin(phase_x) * x_amp
        bounce_y = math.sin(phase_y) * y_amp

        squash_amount = float(getattr(self, "idle_stretch", 4.25))
        squash_speed = 5.0
        squash = math.cos(phase_y * squash_speed) * squash_amount / 100.0

        # Squash/Stretch 只改变上下高度。
        # X 方向始终保持 100%，绝不左右拉伸或压缩。
        scale_x = 1.0
        scale_y = max(0.90, min(1.10, 1.0 + squash))

        if self.is_talking_mouth_open and self.pet_open_frames:
            source_pixmap = self.pet_open_frames[
                self.current_mouth_frame_index % len(self.pet_open_frames)
            ]
        else:
            source_pixmap = self.current_pixmap

        if source_pixmap is None or source_pixmap.isNull():
            return

        # 固定画布 + 浮点缩放。QLabel 尺寸和角色中心始终不变。
        self._show_pet_frame_fixed(
            source_pixmap,
            x_offset=bounce_x,
            y_offset=bounce_y,
            scale_x=scale_x,
            scale_y=scale_y
        )

    # ==================== 对话弹跳动画 ====================
    def _start_dialogue_bounce(self):
        """对话开始时播放一次弹跳动画"""
        if self.tomato_display_active:
            return

        # 重置黑屏计时器
        self._reset_black_screen_timer()

        outfit = self.role_renderer.outfits.get(self.current_outfit, {})
        self._dialogue_bounce_cfg = outfit.get('bounce', {})
        
        self.dialogue_bounce_active = True
        self.dialogue_bounce_elapsed = 0.0
        self.dialogue_bounce_timer.start(50)

    def _update_dialogue_bounce(self):
        """对话弹跳动画：只移动固定渲染画布，不改变其尺寸。"""
        if self.tomato_display_active or not self.dialogue_bounce_active:
            return

        cfg = self._dialogue_bounce_cfg if hasattr(self, '_dialogue_bounce_cfg') else {}
        duration = 0.55
        self.dialogue_bounce_elapsed += 0.05
        progress = self.dialogue_bounce_elapsed / duration

        if progress >= 1.0:
            self.dialogue_bounce_active = False
            self.dialogue_bounce_elapsed = 0.0
            self.dialogue_bounce_timer.stop()
            # 结束时回到固定画布中心；不要恢复成 400x400 QLabel。
            if not self._black_screen_active:
                if self.pet_closed_frames:
                    pixmap = self.pet_closed_frames[self.current_frame_index % len(self.pet_closed_frames)]
                else:
                    pixmap = self.pet_static
                self._show_pet_frame_fixed(pixmap)
            return

        x_amp = float(cfg.get('xAmp', 0) or 0)
        y_amp = float(cfg.get('yAmp', 0) or 0)
        x_frq = float(cfg.get('xFrq', 0) or 0)
        y_frq = float(cfg.get('yFrq', 0) or 0)
        if x_amp == 0:
            x_amp = 4.0
        if y_amp == 0:
            y_amp = 8.0
        if x_frq == 0:
            x_frq = 0.06
        if y_frq == 0:
            y_frq = 0.06

        decay = 1.0 - progress * progress
        t = self.dialogue_bounce_elapsed
        bounce_x = math.sin(t * x_frq * 2 * math.pi) * x_amp * decay
        bounce_y = math.sin(t * y_frq * 2 * math.pi) * y_amp * decay

        # 对话期间保留当前嘴部帧，只移动固定画布。
        if self.is_talking_mouth_open and self.pet_open_frames:
            pixmap = self.pet_open_frames[self.current_mouth_frame_index % len(self.pet_open_frames)]
        else:
            pixmap = self.current_pixmap
        self._show_pet_frame_fixed(pixmap, x_offset=bounce_x, y_offset=bounce_y)

    # ==================== 对话张嘴动画 ====================
    def _set_mouth_frame_centered(self, pixmap):
        """显示嘴部帧，但始终保持固定 QLabel 画布尺寸。"""
        if pixmap is None or pixmap.isNull() or not hasattr(self, 'label'):
            return

        try:
            self.label.opacity_effect.stop()
            self.label._is_fading = False
            self.label._pending_pixmap = None
            self.label._fade_in_pixmap = None
        except Exception:
            pass

        self._show_pet_frame_fixed(pixmap)
        self.label.update()
        self.label.repaint()

    def _start_talking_mouth(self):
        """开始张嘴动画"""
        # pet-happy 过渡期间绝对不能被对话嘴部动画覆盖。
        if getattr(self, '_happy_transition_active', False):
            return
        if self.pet_form == 'classic':
            return

        # 重置黑屏计时器
        self._reset_black_screen_timer()

        if not self.pet_open_frames:
            return

        # 先完全恢复到闭嘴状态，清理所有残留
        self._mouth_end_animation = False
        self._mouth_animation_active = False
        self.is_talking_mouth_open = False
        self._talk_open_one_shot = False
        self.current_mouth_frame_index = 0
        self._mouth_phase = 0

        # 停止所有相关定时器
        if hasattr(self, "mouth_timer"):
            self.mouth_timer.stop()
        try:
            self._stop_timer.stop()
        except Exception:
            pass
        try:
            self._restore_timer.stop()
        except Exception:
            pass
        self.dialogue_bounce_active = False
        if hasattr(self, "dialogue_bounce_timer"):
            self.dialogue_bounce_timer.stop()

        # 先恢复闭嘴帧
        if self.pet_closed_frames:
            idx = self.current_frame_index % len(self.pet_closed_frames)
            pixmap = self.pet_closed_frames[idx]
            self._set_mouth_frame_centered(pixmap)
            self.current_pixmap = pixmap

        # 开启嘴部动画锁
        self._mouth_animation_active = True
        self._mouth_end_animation = False

        # 停止普通动画计时器
        if hasattr(self, "animation_timer"):
            self.animation_timer.stop()

        # 初始化张嘴状态
        self._talk_open_one_shot = True
        self.is_talking_mouth_open = True
        self.current_mouth_frame_index = 0
        self._mouth_phase = 1

        # 立即显示 open[0]
        if self.pet_open_frames:
            pixmap = self.pet_open_frames[0]
            self._set_mouth_frame_centered(pixmap)
            self.current_pixmap = pixmap

        # 对话弹跳
        self._start_dialogue_bounce()

        # 0.1秒切换
        if hasattr(self, "mouth_timer"):
            self.mouth_timer.start(100)

    def _toggle_talking_mouth(self):
        """对话过程中闭嘴 ↔ 张嘴"""

        if self.pet_form == 'classic':
            return
        if not getattr(self, "_mouth_animation_active", False):
            if hasattr(self, "mouth_timer"):
                self.mouth_timer.stop()
            return

        if getattr(self, "_mouth_end_animation", False):
            if hasattr(self, "mouth_timer"):
                self.mouth_timer.stop()
            return

        if not getattr(self, "_talk_open_one_shot", False):
            if hasattr(self, "mouth_timer"):
                self.mouth_timer.stop()
            return

        if not self.pet_open_frames:
            self._restore_normal_frame()
            return

        if self._mouth_phase == 0:
            # 闭嘴 -> 张嘴
            self._mouth_phase = 1
            self.is_talking_mouth_open = True
            self.current_mouth_frame_index = 0
            pixmap = self.pet_open_frames[0]
            self._set_mouth_frame_centered(pixmap)
            self.current_pixmap = pixmap
        else:
            # 张嘴 -> 闭嘴
            self._mouth_phase = 0
            self.is_talking_mouth_open = False
            if self.pet_closed_frames:
                idx = self.current_frame_index % len(self.pet_closed_frames)
                pixmap = self.pet_closed_frames[idx]
                self._set_mouth_frame_centered(pixmap)
                self.current_pixmap = pixmap
            else:
                self._set_mouth_frame_centered(self.pet_static)
                self.current_pixmap = self.pet_static

        if hasattr(self, "mouth_timer"):
            self.mouth_timer.start(100)

    def _stop_talking_mouth(self):
        """对话结束，进入结束嘴部动画。经典pet1~pet9形态不使用DNT嘴部帧。"""

        if self.pet_form == 'classic':
            if hasattr(self, "mouth_timer"):
                self.mouth_timer.stop()
            self._mouth_animation_active = False
            self._mouth_end_animation = False
            self.is_talking_mouth_open = False
            self._mouth_phase = 0
            if self.legacy_pet_frames:
                idx = self.legacy_frame_index % len(self.legacy_pet_frames)
                self.current_pixmap = self.legacy_pet_frames[idx]
                self._show_pet_frame_fixed(self.current_pixmap)
            return

        if hasattr(self, "mouth_timer"):
            self.mouth_timer.stop()

        self._talk_open_one_shot = False
        self.is_talking_mouth_open = False
        self._mouth_phase = 0

        self._mouth_animation_active = True
        self._mouth_end_animation = True

        try:
            self._stop_timer.stop()
        except Exception:
            pass

        try:
            self._restore_timer.stop()
        except Exception:
            pass

        if hasattr(self, "animation_timer"):
            self.animation_timer.stop()

        if len(self.pet_open_frames) < 2:
            self._restore_normal_frame()
            return

        self.current_mouth_frame_index = 1
        pixmap = self.pet_open_frames[1]
        self._set_mouth_frame_centered(pixmap)
        self.current_pixmap = pixmap

        self._stop_timer = QTimer(self)
        self._stop_timer.setSingleShot(True)
        self._stop_timer.timeout.connect(self._play_second_mouth_frame)
        self._stop_timer.start(500)

    def _play_second_mouth_frame(self):
        """第二阶段：open[2] -> 0.5秒 -> 恢复闭嘴"""

        if not getattr(self, "_mouth_end_animation", False):
            return

        if len(self.pet_open_frames) < 3:
            self._restore_normal_frame()
            return

        # 先停止旧的恢复定时器
        try:
            self._restore_timer.stop()
        except Exception:
            pass

        self.current_mouth_frame_index = 2
        pixmap = self.pet_open_frames[2]
        # 直接设置图片
        self._set_mouth_frame_centered(pixmap)
        self.current_pixmap = pixmap

        # 创建新的恢复定时器
        self._restore_timer = QTimer(self)
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(self._restore_normal_frame)
        self._restore_timer.start(500)

    def _restore_normal_frame(self):
        """恢复普通闭嘴动画"""

        # 先重置所有状态
        self._mouth_end_animation = False
        self._mouth_animation_active = False
        self.is_talking_mouth_open = False
        self._talk_open_one_shot = False
        self.current_mouth_frame_index = 0
        self._mouth_phase = 0

        # 停止所有定时器
        if hasattr(self, "mouth_timer"):
            self.mouth_timer.stop()
        try:
            self._stop_timer.stop()
        except Exception:
            pass
        try:
            self._restore_timer.stop()
        except Exception:
            pass

        self.dialogue_bounce_active = False
        if hasattr(self, "dialogue_bounce_timer"):
            self.dialogue_bounce_timer.stop()

        # 如果黑屏正在显示，不要覆盖它
        if not self._black_screen_active:
            # 恢复到闭嘴帧
            if self.pet_closed_frames:
                idx = self.current_frame_index % len(self.pet_closed_frames)
                pixmap = self.pet_closed_frames[idx]
                self._set_mouth_frame_centered(pixmap)
                self.current_pixmap = pixmap
            else:
                self._set_mouth_frame_centered(self.pet_static)
                self.current_pixmap = self.pet_static

        self.label.setWindowOpacity(1.0)

        # 恢复普通动画
        if (hasattr(self, "animation_timer") and
            getattr(self, "animation_timer_started", False) and
            not getattr(self, "animation_paused", False)):
            self.animation_timer.start(getattr(self, "save_animation_interval", 300))

        # 重新启动黑屏计时器
        self._start_black_screen_timer()

    # ==================== 原有方法 ====================
    def switch_language(self):
        if self.lang == 'zh':
            self.lang = 'en'
        else:
            self.lang = 'zh'
        self._update_menu_language()
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

    def _update_menu_language(self):
        if self.lang == 'en':
            self.control_action.setText("Control Panel")
            self.note_action.setText("Notes")
            self.costume_menu.setTitle("Outfit")
            self.costume_menu.setEnabled(self.pet_form == 'dnt')
            self.toggle_animation_action.setEnabled(self.pet_form == 'classic')
            self.flirt_action.setText("Flirt")
            self.news_action.setText("Today's News")
            self.midnight_action.setText("Midnight News")
            self.pet_form_action.setText("Switch to Classic Pet" if self.pet_form == 'dnt' else "Switch to DNT Pet")
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
            self.costume_menu.setTitle("换装")
            self.costume_menu.setEnabled(self.pet_form == 'dnt')
            self.toggle_animation_action.setEnabled(self.pet_form == 'classic')
            self.flirt_action.setText("调情")
            self.news_action.setText("今日新闻")
            self.midnight_action.setText("午夜新闻")
            self.pet_form_action.setText("切换到桌宠1" if self.pet_form == 'dnt' else "切换到桌宠2")
            self.toggle_animation_action.setText("暂停动画" if not self.animation_paused else "开始动画")
            self.toggle_visibility_action.setText("显示/隐藏" if self.isVisible() else "显示/隐藏")
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
        show_action.triggered.connect(self._toggle_visibility)
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
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _get_form_happy_pixmap(self):
        """所有打开、关闭、切换形态的过渡统一使用程序文件夹中的 pet-happy.png。

        不区分 DNT / 普通桌宠，也不使用 DNT 当前形态的首帧代替。
        """
        happy = getattr(self, 'legacy_pet_happy', QPixmap())
        if happy is not None and not happy.isNull():
            return happy
        # 仅作为文件不存在时的安全回退；正常情况下应始终使用文件夹中的 pet-happy.png。
        return QPixmap()

    def _start_happy_transition(self):
        """显示 pet-happy 1 秒，期间禁止黑屏和闲置动画覆盖。"""
        happy = self._get_form_happy_pixmap()
        if happy is None or happy.isNull():
            return
        self._happy_transition_active = True
        if hasattr(self, 'black_screen_timer'):
            self.black_screen_timer.stop()
        if hasattr(self, 'black_screen_hide_timer'):
            self.black_screen_hide_timer.stop()
        self._black_screen_active = False
        if hasattr(self, 'animation_timer'):
            self.animation_timer.stop()
        # 过渡期间禁止嘴巴动画和对话弹跳抢占 pet-happy.png。
        if hasattr(self, 'mouth_timer'):
            self.mouth_timer.stop()
        self._mouth_animation_active = False
        self._mouth_end_animation = False
        if hasattr(self, 'dialogue_bounce_timer'):
            self.dialogue_bounce_timer.stop()
        self.dialogue_bounce_active = False
        self.animation_timer_started = False
        self.startup_timer.stop()
        self.startup_frames = [happy]
        self.startup_index = 0
        # 立即绘制并置顶，确保 1 秒 happy 真正可见。
        self.current_pixmap = happy
        self._show_pet_frame_fixed(happy)
        self.label.raise_()
        self.show()
        self.raise_()
        self.startup_timer.start(1000)

    def _toggle_visibility_from_menu(self):
        if self.isVisible():
            # 隐藏前也先显示文件夹中的 pet-happy 1 秒。
            if hasattr(self, 'black_screen_timer'):
                self.black_screen_timer.stop()
            if hasattr(self, 'black_screen_hide_timer'):
                self.black_screen_hide_timer.stop()
            self._black_screen_active = False
            self._start_happy_transition()
            self.toggle_visibility_action.setText("显示桌宠" if self.lang == 'zh' else "Show Pet")
            QTimer.singleShot(1000, self._hide_after_happy)
        else:
            self.show()
            self.raise_()
            self._start_happy_transition()
            self.toggle_visibility_action.setText("隐藏桌宠" if self.lang == 'zh' else "Hide Pet")

    def _hide_after_happy(self):
        if self._happy_transition_active:
            self._happy_transition_active = False
        self.hide()

    def _toggle_auto_dialog(self):
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

    def _toggle_visibility(self):
        if self.isVisible():
            if hasattr(self, 'black_screen_timer'):
                self.black_screen_timer.stop()
            if hasattr(self, 'black_screen_hide_timer'):
                self.black_screen_hide_timer.stop()
            self._black_screen_active = False
            self._start_happy_transition()
            QTimer.singleShot(1000, self._hide_after_happy)
        else:
            self.show()
            self.raise_()
            self._start_happy_transition()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._toggle_visibility()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.showMessage("桌宠" if self.lang == 'zh' else "Desk Pet",
                                       "程序已最小化到系统托盘" if self.lang == 'zh' else "Program minimized to system tray",
                                       QSystemTrayIcon.Information, 2000)

    def _startup_animation(self):
        # happy 已经在启动/打开/切换时立即显示；1000ms 后才进入正常动画。
        self.startup_timer.stop()
        self._happy_transition_active = False
        self.startup_index = 0
        if self.pet_form == 'classic':
            self.current_frame_index = 0
            if self.legacy_pet_frames:
                self.current_pixmap = self.legacy_pet_frames[0]
                self._show_pet_frame_fixed(self.legacy_pet_frames[0])
            self.animation_timer.start(300)
        else:
            self.current_frame_index = 0
            if self.pet_frames:
                self.current_pixmap = self.pet_frames[0]
                self._show_pet_frame_fixed(self.pet_frames[0])
            self.animation_timer.start(getattr(self, 'save_animation_interval', 300))
        self.animation_timer_started = True
        if self.pet_form == 'dnt':
            self._start_black_screen_timer()

    def _toggle_animation(self):
        # DNT 完整动画不提供暂停按钮；仅普通 pet1~9 形态可暂停。
        if getattr(self, 'pet_form', 'dnt') != 'classic':
            return
        self.animation_paused = not self.animation_paused
        if self.animation_paused:
            self.animation_timer.stop()
            happy_or_static = self.pet_static
            if self.pet_form == 'classic' and self.legacy_pet_frames:
                happy_or_static = self.legacy_pet_frames[0]
            self._show_pet_frame_fixed(happy_or_static)
            self.toggle_animation_action.setText("开始动画" if self.lang == 'zh' else "Start Animation")
        else:
            self.animation_timer.start(300 if self.pet_form == 'classic' else getattr(self, 'save_animation_interval', 300))
            self.current_frame_index = 0
            if self.pet_form == 'classic':
                self.current_pixmap = self.legacy_pet_frames[0] if self.legacy_pet_frames else self.legacy_pet_happy
            else:
                self.current_pixmap = self.pet_frames[0] if self.pet_frames else QPixmap()
            self._show_pet_frame_fixed(self.current_pixmap)
            self.toggle_animation_action.setText("暂停动画" if self.lang == 'zh' else "Pause Animation")

    def _next_frame(self):
        if self.animation_paused or not self.animation_timer_started:
            return
        if self.is_displaying or self.is_dragging or self.tomato_display_active:
            return
        if getattr(self, "_mouth_animation_active", False) or self._black_screen_active:
            return

        if self.pet_form == 'classic':
            if not self.legacy_pet_frames:
                return
            self.legacy_frame_index = (self.legacy_frame_index + 1) % len(self.legacy_pet_frames)
            self.current_frame_index = self.legacy_frame_index
            self.current_pixmap = self.legacy_pet_frames[self.legacy_frame_index]
            return

        if not self.pet_frames:
            return
        self.current_frame_index = (self.current_frame_index + 1) % len(self.pet_frames)
        self.current_pixmap = self.pet_frames[self.current_frame_index]

    def switch_pet_form(self):
        """在07版DNT完整动画与原index的pet1~pet9动画之间切换。"""
        target = 'classic' if self.pet_form == 'dnt' else 'dnt'

        if hasattr(self, 'black_screen_timer'):
            self.black_screen_timer.stop()
        if hasattr(self, 'black_screen_hide_timer'):
            self.black_screen_hide_timer.stop()
        if hasattr(self, 'mouth_timer'):
            self.mouth_timer.stop()
        if hasattr(self, 'dialogue_bounce_timer'):
            self.dialogue_bounce_timer.stop()
        self._mouth_animation_active = False
        self._mouth_end_animation = False
        self.dialogue_bounce_active = False
        self._black_screen_active = False
        self._happy_transition_active = True

        self.animation_timer.stop()
        self.startup_timer.stop()
        self.animation_timer_started = False
        self.pet_form = target

        if target == 'classic':
            if not self.legacy_pet_frames:
                self.pet_form = 'dnt'
                return
            self.current_frame_index = 0
            self.legacy_frame_index = 0
            self.legacy_bounce_time = 0.0
            self.pet_frames = list(self.legacy_pet_frames)
            self.pet_static = self.legacy_pet_frames[0]
            self.pet_happy = self.legacy_pet_happy if not self.legacy_pet_happy.isNull() else self.pet_static
            self.current_pixmap = self.pet_frames[0]
            self.startup_frames = [self.pet_happy]
            self.startup_index = 0
            self._show_pet_frame_fixed(self.pet_happy)
        else:
            if not self._load_current_outfit(self.current_outfit):
                self.pet_form = 'classic'
                return
            self.pet_frames = list(self.pet_closed_frames)
            self.pet_static = self.pet_frames[0] if self.pet_frames else QPixmap()
            self.pet_talking = self.pet_open_frames[0] if self.pet_open_frames else self.pet_static
            # DNT 本身仍然使用自己的动画首帧作为正常静态帧，
            # 但“切换形态”的 1 秒过渡画面统一使用文件夹 pet-happy.png。
            self.pet_happy = self.pet_static
            self.current_frame_index = 0
            self.current_pixmap = self.pet_static
            self._load_idle_bounce_params()
            self.startup_frames = [self._get_form_happy_pixmap()]
            self.startup_index = 0
            self._show_pet_frame_fixed(self._get_form_happy_pixmap())

        self._update_menu_language()
        # 与原index一致：打开/切换形态后先显示pet-happy约0.5秒。
        self.startup_timer.start(1000)

    def _update_classic_bounce(self):
        if not self.legacy_pet_frames or self.tomato_display_active or self.is_dragging:
            return
        self.legacy_bounce_time += 0.15
        bounce_y = math.sin(self.legacy_bounce_time * 2.5) * 3 * self.scale
        bounce_x = math.sin(self.legacy_bounce_time * 1.8) * 2 * self.scale
        self._show_pet_frame_fixed(
            self.current_pixmap if self.current_pixmap and not self.current_pixmap.isNull() else self.legacy_pet_frames[0],
            x_offset=bounce_x, y_offset=bounce_y
        )

    def start_tomato_display(self, seconds):
        self.tomato_display_active = True
        # 暂停黑屏计时器
        if hasattr(self, 'black_screen_timer'):
            self.black_screen_timer.stop()
        if self._black_screen_active:
            self._hide_black_screen()
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
        # 重新启动黑屏计时器
        self._start_black_screen_timer()
        if self.dialog_queue:
            self.bubble.hide()
            self.show_next_dialog()
        else:
            self.bubble.fade_out()

    def _format_time(self, seconds):
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

    def _rescale_classic_pet(self):
        """按当前 pet_zoom 重新缩放普通桌宠资源。"""
        zoom = float(getattr(self, "pet_zoom", 1.0))
        frames = []
        for i in range(1, 10):
            pm = QPixmap(resource_path(f"pet{i}.png"))
            if not pm.isNull():
                frames.append(pm.scaled(
                    max(1, int(round(pm.width() * self.scale * zoom))),
                    max(1, int(round(pm.height() * self.scale * zoom))),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                ))
        if not frames:
            fallback = QPixmap(resource_path("pet.png"))
            if not fallback.isNull():
                frames = [fallback.scaled(
                    max(1, int(round(fallback.width() * self.scale * zoom))),
                    max(1, int(round(fallback.height() * self.scale * zoom))),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )]
        happy = QPixmap(resource_path("pet-happy.png"))
        if not happy.isNull():
            self.legacy_pet_happy = happy.scaled(
                max(1, int(round(happy.width() * self.scale * zoom))),
                max(1, int(round(happy.height() * self.scale * zoom))),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        if frames:
            self.legacy_pet_frames = frames
            self.legacy_frame_index %= len(frames)
            self.current_pixmap = frames[self.legacy_frame_index]

    def _set_pet_zoom(self, zoom):
        """改变桌宠显示倍率，保持桌宠中心位置不变。"""
        zoom = max(
            float(getattr(self, "pet_zoom_min", 0.5)),
            min(float(getattr(self, "pet_zoom_max", 2.0)), float(zoom))
        )
        old_zoom = float(getattr(self, "pet_zoom", 1.0))
        if abs(zoom - old_zoom) < 0.0001:
            return

        old_frame_index = getattr(self, "current_frame_index", 0)
        old_mouth_index = getattr(self, "current_mouth_frame_index", 0)
        old_legacy_index = getattr(self, "legacy_frame_index", 0)
        was_talking = bool(getattr(self, "is_talking_mouth_open", False))
        self.pet_zoom = zoom

        if getattr(self, "pet_form", "dnt") == "classic":
            self._rescale_classic_pet()
            if self.legacy_pet_frames:
                self.current_pixmap = self.legacy_pet_frames[
                    old_legacy_index % len(self.legacy_pet_frames)
                ]
        else:
            current_outfit = getattr(self, "current_outfit", None)
            if current_outfit is not None:
                self._load_current_outfit(current_outfit)
                if self.pet_closed_frames:
                    self.current_frame_index = old_frame_index % len(self.pet_closed_frames)
                if self.pet_open_frames:
                    self.current_mouth_frame_index = old_mouth_index % len(self.pet_open_frames)

        if self.pet_form == "classic":
            self._show_pet_frame_fixed(self.current_pixmap)
        elif was_talking and self.pet_open_frames:
            self.is_talking_mouth_open = True
            self._show_pet_frame_fixed(
                self.pet_open_frames[
                    self.current_mouth_frame_index % len(self.pet_open_frames)
                ]
            )
        elif self.pet_closed_frames:
            self.is_talking_mouth_open = False
            self._show_pet_frame_fixed(
                self.pet_closed_frames[
                    self.current_frame_index % len(self.pet_closed_frames)
                ]
            )
        else:
            self._show_pet_frame_fixed(self.pet_static)

        # 如果缩放桌宠时正处于黑屏状态，黑屏覆盖层也必须按照新的
        # 桌宠倍率重新合成，否则黑屏会继续停留在缩放前的位置和尺寸。
        if getattr(self, "_black_screen_active", False) and self.pet_form == "dnt":
            outfit = self.role_renderer.outfits.get(self.current_outfit, {})
            combined = self._compose_black_screen_overlay(self.current_pixmap, outfit)
            if combined is not None and not combined.isNull():
                self._set_mouth_frame_centered(combined)

    def eventFilter(self, obj, event):
        if obj is getattr(self, "label", None) and event.type() == QEvent.Wheel:
            if event.modifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                if delta:
                    steps = 1 if delta > 0 else -1
                    self._set_pet_zoom(
                        getattr(self, "pet_zoom", 1.0)
                        + steps * getattr(self, "pet_zoom_step", 0.1)
                    )
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            self.is_dragging = False
            # 重置黑屏计时器
            self._reset_black_screen_timer()
            self._show_pet_frame_fixed(self.legacy_pet_happy if self.pet_form == 'classic' and not self.legacy_pet_happy.isNull() else self.pet_happy)
            if self.animation_timer_started:
                self.animation_timer.stop()
        elif event.button() == Qt.RightButton:
            # 重置黑屏计时器
            self._reset_black_screen_timer()
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

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                steps = 1 if delta > 0 else -1
                self._set_pet_zoom(
                    getattr(self, "pet_zoom", 1.0)
                    + steps * getattr(self, "pet_zoom_step", 0.1)
                )
                event.accept()
                return
        event.ignore()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos is not None:
            distance = (event.globalPos() - self.frameGeometry().topLeft() - self.drag_pos).manhattanLength()
            if distance > 5:
                self.is_dragging = True
                self.move(event.globalPos() - self.drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.animation_paused:
                self._show_pet_frame_fixed(self.pet_static)
            elif self.animation_timer_started:
                self._show_pet_frame_fixed(self.current_pixmap)
            else:
                self._show_pet_frame_fixed(self.pet_frames[0] if self.pet_frames else QPixmap())
            if not self.animation_paused and self.animation_timer_started:
                self.animation_timer.start(300 if self.pet_form == 'classic' else getattr(self, 'save_animation_interval', 300))
            if not self.is_dragging:
                pos = event.pos()
                pet_rect = self.label.geometry()
                if pet_rect.contains(pos):
                    self._on_pet_click()
            self.drag_pos = None
            self.is_dragging = False

    def clear_dialog_timer(self):
        if self.dialog_timer is not None:
            self.dialog_timer.stop()
            self.dialog_timer = None

    def add_dialog(self, text, requires_confirmation=False, priority=False, reminder_key=None):
        dialog_item = (text, requires_confirmation, reminder_key)
        if priority:
            self.dialog_queue.insert(0, dialog_item)
        else:
            self.dialog_queue.append(dialog_item)

        # 重置黑屏计时器
        self._reset_black_screen_timer()

        if self.tomato_display_active:
            return

        if not self.is_displaying:
            self.show_next_dialog()

    def show_next_dialog(self):
        # 整组对话第一次开始时播放张嘴和弹跳
        if not self.dialogue_session_active:
            self.dialogue_session_active = True
            self._start_talking_mouth()

        if self.tomato_display_active:
            return
        self.clear_dialog_timer()
        if self.dialog_queue:
            self.is_displaying = True
            text, requires_confirmation, reminder_key = self.dialog_queue.pop(0)
            self.current_dialog_requires_confirmation = requires_confirmation
            self.current_reminder_key = reminder_key
            self.bubble.start_typing(text, requires_confirmation)
        else:
            self.is_displaying = False
            self.current_dialog_requires_confirmation = False
            self.current_reminder_key = None
            self.dialogue_session_active = False
            self._stop_talking_mouth()
            self.dialogue_bounce_active = False

    def start_dialog_continuation(self, remaining, requires_confirmation=False):
        if self.tomato_display_active:
            return
        self.clear_dialog_timer()
        self.is_displaying = True
        self.current_dialog_requires_confirmation = requires_confirmation
        self.bubble.start_typing(remaining, requires_confirmation)

    def on_dialog_complete(self):
        self.clear_dialog_timer()
        if self.dialog_queue:
            self.dialog_timer = QTimer(self)
            self.dialog_timer.setSingleShot(True)
            self.dialog_timer.timeout.connect(self.show_next_dialog)
            self.dialog_timer.start(3000)
        else:
            self._stop_talking_mouth()
            self.dialogue_session_active = False
            self.dialogue_bounce_active = False
            # 需要确认的提醒由 Bubble 自己的60秒确认计时器控制消失。
            # 未确认时会进入 reminder_dialog_timeout()，1分钟后重新出现。
            if self.current_dialog_requires_confirmation:
                return
            self.dialog_timer = QTimer(self)
            self.dialog_timer.setSingleShot(True)
            self.dialog_timer.timeout.connect(self._fade_and_reset)
            self.dialog_timer.start(3000)

    def confirm_dialog(self):
        # 用户点击 Confirm：取消当前提醒的再次提醒计时。
        reminder_key = self.current_reminder_key
        if reminder_key:
            self._pending_reminders.discard(reminder_key)
            timer = self._reminder_retry_timers.pop(reminder_key, None)
            if timer is not None:
                timer.stop()
                timer.deleteLater()

        self.clear_dialog_timer()
        self.bubble.dismiss()
        self.is_displaying = False
        self.current_dialog_requires_confirmation = False
        self.current_reminder_key = None
        self.dialogue_bounce_active = False
        if self.dialog_queue and not self.tomato_display_active:
            self.show_next_dialog()
        else:
            self.dialogue_session_active = False
            self._stop_talking_mouth()

    def add_reminder_dialog(self, reminder_key, dialogue_key):
        """添加喝水/吃饭/睡觉提醒，并记录为待确认提醒。"""
        self._pending_reminders.add(reminder_key)
        self.add_dialog(
            random.choice(get_dialogues(self.lang, dialogue_key)),
            requires_confirmation=True,
            priority=True,
            reminder_key=reminder_key
        )

    def is_reminder_pending(self, reminder_key):
        return reminder_key in self._pending_reminders

    def reminder_dialog_timeout(self):
        """提醒显示1分钟仍未确认：消失，空1分钟后再次出现。"""
        reminder_key = self.current_reminder_key
        self.bubble.dismiss()
        self.is_displaying = False
        self.current_dialog_requires_confirmation = False
        self.current_reminder_key = None
        self.dialogue_bounce_active = False
        self.dialogue_session_active = False
        self._stop_talking_mouth()

        if not reminder_key or reminder_key not in self._pending_reminders:
            return

        old_timer = self._reminder_retry_timers.pop(reminder_key, None)
        if old_timer is not None:
            old_timer.stop()
            old_timer.deleteLater()

        retry_timer = QTimer(self)
        retry_timer.setSingleShot(True)
        retry_timer.timeout.connect(lambda key=reminder_key: self._retry_reminder(key))
        self._reminder_retry_timers[reminder_key] = retry_timer
        retry_timer.start(60000)

    def _retry_reminder(self, reminder_key):
        timer = self._reminder_retry_timers.pop(reminder_key, None)
        if timer is not None:
            timer.deleteLater()
        if reminder_key not in self._pending_reminders:
            return
        dialogue_map = {
            'drink': 'drink',
            'lunch': 'lunch',
            'dinner': 'dinner',
            'sleep': 'sleep'
        }
        dialogue_key = dialogue_map.get(reminder_key)
        if dialogue_key:
            self.add_reminder_dialog(reminder_key, dialogue_key)

    def _fade_and_reset(self):
        self.bubble.fade_out()
        self.is_displaying = False
        self.current_dialog_requires_confirmation = False
        self.dialog_timer = None
        # 重新启动黑屏计时器
        self._start_black_screen_timer()

    def _on_pet_click(self):
        if self.auto_dialog_enabled:
            self.add_dialog(random.choice(get_dialogues(self.lang, 'click')))

    def flirt(self):
        self.add_dialog(random.choice(get_dialogues(self.lang, 'flirt')))

    def _random_dialog(self):
        if (self.auto_dialog_enabled and not self.tomato_display_active and
            not self.is_displaying and not self.current_dialog_requires_confirmation):
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

    def _repeat_random_note(self):
        self.note_repeat_elapsed += 1
        if self.note_repeat_elapsed < 60:
            return
        self.note_repeat_elapsed = 0

        note_text = load_notes()
        if not note_text.strip():
            return

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
        # 仅 DNT 桌宠：打开今日新闻时显示黑屏 5 秒；普通桌宠不受影响。
        self._show_news_black_screen()

    def show_midnight_news(self):
        if self.midnight_window is None:
            self.midnight_window = MidnightNewsWindow(self)
        self.midnight_window.update_position()
        self.midnight_window.show()
        self.midnight_window.raise_()
        # 仅 DNT 桌宠：打开午夜新闻时显示黑屏 5 秒；普通桌宠不受影响。
        self._show_news_black_screen()

    def _show_news_black_screen(self):
        """打开新闻面板时，仅 DNT 桌宠额外黑屏 5 秒。"""
        if getattr(self, 'pet_form', 'dnt') == 'classic':
            return
        if getattr(self, '_happy_transition_active', False):
            return
        # 新闻打开不应打断正在进行的对话、番茄钟、嘴巴动画或拖拽。
        if (getattr(self, 'is_displaying', False) or
            getattr(self, 'tomato_display_active', False) or
            getattr(self, '_mouth_animation_active', False) or
            getattr(self, 'is_dragging', False)):
            return
        if hasattr(self, 'black_screen_timer'):
            self.black_screen_timer.stop()
        self._show_black_screen()
        if getattr(self, '_black_screen_active', False):
            self.black_screen_hide_timer.stop()
            self.black_screen_hide_timer.start(5000)

    def create_menu(self):
        self.menu = QMenu(self)
        self.control_action = QAction(self)
        self.control_action.triggered.connect(self.show_control_panel)
        self.note_action = QAction(self)
        self.note_action.triggered.connect(self.show_note)
        self.flirt_action = QAction(self)
        self.flirt_action.triggered.connect(self.flirt)
        self.news_action = QAction(self)
        self.news_action.triggered.connect(self.show_news)
        self.midnight_action = QAction(self)
        self.midnight_action.triggered.connect(self.show_midnight_news)

        self.costume_menu = QMenu(self)
        self.costume_actions = []
        for outfit_no in range(1, 8):  # 1-7套服装
            action = QAction(str(outfit_no), self)
            action.setCheckable(True)
            action.setEnabled(outfit_no in self.available_outfits)
            action.triggered.connect(lambda checked=False, n=outfit_no: self.change_outfit(n))
            self.costume_menu.addAction(action)
            self.costume_actions.append(action)
        if self.costume_actions and self.current_outfit <= len(self.costume_actions):
            self.costume_actions[self.current_outfit - 1].setChecked(True)

        self.toggle_animation_action = QAction(self)
        self.toggle_animation_action.triggered.connect(self._toggle_animation)
        self.toggle_visibility_action = QAction(self)
        self.toggle_visibility_action.triggered.connect(self._toggle_visibility_from_menu)
        self.toggle_auto_dialog_action = QAction(self)
        self.toggle_auto_dialog_action.triggered.connect(self._toggle_auto_dialog)
        self.lang_action = QAction(self)
        self.lang_action.triggered.connect(self.switch_language)
        self.quit_action = QAction(self)
        self.quit_action.triggered.connect(self.quit_app)

        self.menu.addAction(self.control_action)
        self.menu.addAction(self.note_action)
        self.menu.addMenu(self.costume_menu)
        self.menu.addAction(self.flirt_action)
        self.menu.addAction(self.news_action)
        self.menu.addAction(self.midnight_action)
        self.pet_form_action = QAction(self)
        self.pet_form_action.triggered.connect(self.switch_pet_form)
        self.menu.addAction(self.pet_form_action)
        self.menu.addAction(self.toggle_animation_action)
        self.menu.addAction(self.toggle_visibility_action)
        self.menu.addAction(self.toggle_auto_dialog_action)
        self.menu.addSeparator()
        self.menu.addAction(self.lang_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)

        self._update_menu_language()

    def quit_app(self):
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        self.add_dialog(random.choice(get_dialogues(self.lang, 'close')))
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self._prepare_close)
        self._close_timer.start(5000)

    def _prepare_close(self):
        # 关闭时彻底关闭黑屏，并统一显示文件夹中的 pet-happy.png 1 秒。
        if hasattr(self, 'black_screen_timer'):
            self.black_screen_timer.stop()
        if hasattr(self, 'black_screen_hide_timer'):
            self.black_screen_hide_timer.stop()
        self._black_screen_active = False
        self._happy_transition_active = True
        happy = self._get_form_happy_pixmap()
        if happy is not None and not happy.isNull():
            self.current_pixmap = happy
            self._show_pet_frame_fixed(happy)
            self.label.raise_()
            self.show()
            self.raise_()
        self.animation_timer.stop()
        self.startup_timer.stop()
        self.clear_dialog_timer()
        if hasattr(self, "note_repeat_timer"):
            self.note_repeat_timer.stop()
        QTimer.singleShot(1000, self._really_quit)

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
    # 程序首次启动：强制先显示文件夹中的 pet-happy.png 1 秒。
    QTimer.singleShot(0, pet._start_happy_transition)
    sys.exit(app.exec_())