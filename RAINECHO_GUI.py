# %%
# -*- coding: utf-8 -*-
# RainEcho UI layer — 改訂版8.2（設定オーバーレイの見出し中央寄せ＆入力UI磨き込み）
# 変更点:
# - 各セクションに中央寄せのヘッダーを追加＋薄い区切り線
# - ドロップダウン(QComboBox)は縁取りなしのフラット表示に
# - チェックボックスはデフォの✓が確実に見えるようにサイズ指定のみ（描画はデフォに任せる）
# - 固定テキストは背景なし 文字色は黒 入力系のみ薄い背景と枠で強調
# - それ以外は改訂版8と同等（雨SE 画面遷移 演出 中央固定オーバーレイ等）

import sys, random, time
from enum import Enum, auto

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QSize, QByteArray, QEvent
from PySide6.QtGui import (QPainter, QPen, QBrush, QColor, QPainterPath,
                           QIcon, QPixmap, QAction, QFont)
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QSystemTrayIcon, QMenu, QLabel,
                               QSlider, QCheckBox, QFormLayout, QGroupBox,
                               QComboBox, QPlainTextEdit, QMessageBox,
                               QScrollArea, QFrame, QSizePolicy, QLineEdit, QSpinBox, QDoubleSpinBox)

# === オーディオ（QtMultimedia） ===
HAVE_QTMEDIA = True
try:
    from PySide6.QtMultimedia import (QMediaDevices, QAudioFormat, QAudioSink)
    from PySide6.QtCore import QBuffer
except Exception:
    HAVE_QTMEDIA = False

APP_TITLE = "RainEcho"

IDLE_SLEEP_CYCLE_SEC = 10 * 60
GLOBAL_TIMEOUT_SEC   = 10 * 60

FADE_GENERIC_SEC            = 0.8
LISTENING_ENTRY_BG_FADE_SEC = 1.2

COLOR_IDLE_BG   = QColor("#aee6ff")
COLOR_LISTEN_BG = QColor("#4d66c7")
COLOR_SLEEP_BG  = QColor("#1a1a40")
COLOR_RIPPLE    = QColor("#7FD6D0")

BTN_BG_NORMAL = "#c9ced6"
BTN_BG_HOVER  = "#d5d9e0"
BTN_BG_DOWN   = "#b6bcc6"
BTN_FONT_SIZE = 22
BTN_MIN_W, BTN_MIN_H = 72, 50
BTN_H_SPACING = 20
BTN_STYLE = f"""
QPushButton {{
    background: {BTN_BG_NORMAL};
    color: white; font-weight: 800; font-size: {BTN_FONT_SIZE}px;
    padding: 10px 20px;
    border-radius: 14px;
    border: 1px solid rgba(255,255,255,.35);
}}
QPushButton:hover {{ background: {BTN_BG_HOVER}; }}
QPushButton:pressed {{
    background: {BTN_BG_DOWN};
    padding-top: 11px; padding-bottom: 9px;
}}
"""

LISTEN_SPAWN_INTERVAL_MS = 650
LISTEN_MAX_DROPS   = 18
LISTEN_MAX_RIPPLES = 10

ICON_CLOUD_IDLE   = QColor("#BFC6D1")
ICON_CLOUD_LISTEN = QColor("#8FA3B8")
ICON_CLOUD_SLEEP  = QColor("#A9AFB7")

DEFAULT_SYSTEM_PROMPT = (
    "あなたの名前は天雨莉乃 あまうりの です ユーザーの幼馴染であり女子高生です "
    "釘宮風のツンデレで気象に興味があります 文体は常にツンデレ口調で返答してください "
    "セリフは改行せずインデントを使わずつなげてください 記号は？ ！ 。のみを使いそれ以外は使わないでください"
)

# ----------------- 状態 -----------------
class LinoState(Enum):
    IDLE = auto()
    LISTENING = auto()
    SLEEPING = auto()

def lerp(a: float, b: float, t: float) -> float:
    t = 0 if t < 0 else (1 if t > 1 else t); return a + (b - a) * t

def lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    t = 0.0 if t < 0 else (1.0 if t > 1.0 else t)
    return QColor(int(lerp(a.red(),   b.red(),   t)),
                  int(lerp(a.green(), b.green(), t)),
                  int(lerp(a.blue(),  b.blue(),  t)),
                  int(lerp(a.alpha(), b.alpha(), t)))


# ----------------- トレイ用アイコン -----------------
def make_cloud_icon(cloud_color: QColor, with_drop: bool, size: int = 24) -> QIcon:
    pm = QPixmap(size, size); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing, True)
    w = h = size
    path = QPainterPath()
    cx, cy = w * 0.5, h * 0.58
    r1 = w * 0.20; r2 = w * 0.16; r3 = w * 0.14
    path.addEllipse(QPointF(cx - r1, cy - r3*0.5), r2, r2)
    path.addEllipse(QPointF(cx, cy - r2), r2*1.05, r2*1.05)
    path.addEllipse(QPointF(cx + r1, cy - r3*0.6), r3*1.15, r3*1.15)
    base_rect = QRectF(cx - r1*1.6, cy - r2*0.6, r1*3.2, r2*1.8)
    path.addRoundedRect(base_rect, r3, r3)
    p.setPen(Qt.NoPen)
    fill = QColor(cloud_color); fill.setAlpha(235)
    p.setBrush(fill); p.drawPath(path)
    hi = QColor(255, 255, 255, 90)
    p.setBrush(hi)
    p.drawEllipse(QRectF(cx - w*0.18, cy - w*0.27, w*0.18, w*0.10))
    if with_drop:
        drop = QPainterPath()
        dx, dy = cx + w*0.10, cy + w*0.05
        top = QPointF(dx, dy - w*0.06)
        drop.moveTo(top)
        drop.cubicTo(QPointF(dx + w*0.04, dy - w*0.03),
                     QPointF(dx + w*0.04, dy + w*0.03),
                     QPointF(dx, dy + w*0.06))
        drop.cubicTo(QPointF(dx - w*0.04, dy + w*0.03),
                     QPointF(dx - w*0.04, dy - w*0.03),
                     top)
        p.setBrush(QColor(COLOR_RIPPLE.red(), COLOR_RIPPLE.green(), COLOR_RIPPLE.blue(), 230))
        p.drawPath(drop)
    p.end()
    return QIcon(pm)


# ----------------- ヘッダ -----------------
class CloudHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cloudHeader")
        self.setFixedHeight(80)

        self.btn_idle   = QPushButton("昼", self)
        self.btn_listen = QPushButton("雨", self)
        self.btn_sleep  = QPushButton("夜", self)
        for b in (self.btn_idle, self.btn_listen, self.btn_sleep):
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumSize(BTN_MIN_W, BTN_MIN_H)
            b.setStyleSheet(BTN_STYLE)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 12)
        lay.setSpacing(BTN_H_SPACING)
        lay.addStretch(1)
        lay.addWidget(self.btn_idle,   0, Qt.AlignCenter)
        lay.addWidget(self.btn_listen, 0, Qt.AlignCenter)
        lay.addWidget(self.btn_sleep,  0, Qt.AlignCenter)
        lay.addStretch(1)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), Qt.white)
        p.end()


# ----------------- 雨粒/波紋 -----------------
class Ripple:
    def __init__(self, x: float, y: float, color: QColor,
                 max_radius: float, grow: float, fade: float, width: float):
        self.x = x; self.y = y
        self.r = 1.0
        self.max_r = max_radius
        self.grow = grow
        self.alpha = 200.0
        self.fade = fade
        self.width = width
        self.base_color = QColor(color)

    def update(self):
        self.r += self.grow
        self.alpha -= self.fade
        return self.alpha > 0 and self.r < self.max_r

    def paint(self, p: QPainter):
        c = QColor(self.base_color); c.setAlpha(int(max(0, min(255, self.alpha))))
        p.setPen(QPen(c, self.width))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(self.x, self.y), self.r, self.r)


class Raindrop:
    def __init__(self, x: float, y0: float, y1: float, speed: float, color: QColor):
        self.x = x; self.y = y0; self.y1 = y1; self.v = speed
        self.color = QColor(color)
        self.alive = True

    def update(self):
        self.y += self.v
        if self.y >= self.y1:
            self.alive = False
        return self.alive

    def paint(self, p: QPainter):
        p.setPen(QPen(self.color, 2))
        p.drawLine(QPointF(self.x, self.y - 6), QPointF(self.x, self.y))


# ----------------- 合成SEフォールバック -----------------
def _mk_soft_hush(sr=48000, ch=2, dur=5.5):
    import array
    rnd = random.random
    alpha = 0.12
    prev = 0.0
    n = int(sr*dur)
    up = int(0.12*n); down = int(0.45*n)
    out = array.array('h')
    for i in range(n):
        w = rnd()*2-1
        prev = prev + alpha*(w - prev)
        if i < up:
            env = i/max(1,up)
        elif i > n - down:
            env = max(0.0, (n - i)/max(1,down))
        else:
            env = 1.0
        s = max(-1.0, min(1.0, prev*0.45*env))
        v = int(s*32767)
        if ch == 1:
            out.append(v)
        else:
            out.append(v); out.append(v)
    return out.tobytes()

class _PCMOut:
    def __init__(self, parent=None, sr=48000, ch=2, vol=0.5):
        self.enabled = HAVE_QTMEDIA
        if not self.enabled: return
        dev = QMediaDevices.defaultAudioOutput()
        fmt = dev.preferredFormat()
        fmt.setSampleRate(sr); fmt.setChannelCount(ch)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        self.sink = QAudioSink(dev, fmt, parent)
        self.sink.setVolume(vol)
        self._buf = None
        self._sr = sr; self._ch = ch
    def play_bytes(self, b: bytes):
        if not self.enabled: return
        try:
            if self._buf: self._buf.close()
        except Exception: pass
        self._buf = QBuffer()
        self._buf.setData(QByteArray(b))
        self._buf.open(QBuffer.ReadOnly)
        self.sink.stop()
        self.sink.start(self._buf)

class GentleRainSE:
    def __init__(self, parent=None, duration_sec=5.5):
        self.out = _PCMOut(parent, sr=48000, ch=2, vol=0.5)
        self.buf = _mk_soft_hush(48000, 2, dur=duration_sec)
    def play_once(self):
        if HAVE_QTMEDIA:
            self.out.play_bytes(self.buf)


# ----------------- キャンバス -----------------
class RainCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(460, 320)
        self.state = LinoState.IDLE

        self.bg_color = QColor(COLOR_IDLE_BG)
        self._bg_from = QColor(self.bg_color)
        self._bg_to   = QColor(self.bg_color)
        self._bg_t0   = 0.0
        self._bg_dur  = 0.0
        self._bg_fading = False

        self.ripples: list[Ripple] = []
        self.drops: list[Raindrop] = []

        self.spawn_timer = QTimer(self); self.spawn_timer.timeout.connect(self._spawn_during_listen)
        self.frame = QTimer(self); self.frame.timeout.connect(self._on_frame); self.frame.start(16)

        self._entry_t0 = 0.0
        self._entry_phase = 0
        self._entry_phase_t0 = 0.0
        self._allow_spawns = False

    def sizeHint(self): return QSize(520, 360)

    def _start_bg_fade(self, to_color: QColor, dur_sec: float):
        self._bg_from = QColor(self.bg_color)
        self._bg_to   = QColor(to_color)
        self._bg_t0   = time.time()
        self._bg_dur  = max(0.01, float(dur_sec))
        self._bg_fading = True

    def _update_bg_fade(self, now: float):
        if not self._bg_fading: return
        t = (now - self._bg_t0) / self._bg_dur
        if t >= 1.0:
            self.bg_color = QColor(self._bg_to)
            self._bg_fading = False
        else:
            self.bg_color = lerp_color(self._bg_from, self._bg_to, t)

    def ping_center(self, strong=False):
        w, h = self.width(), self.height()
        cx, cy = w*0.5, h*0.56
        self.drops.append(Raindrop(cx, cy-14, cy+6, speed=6.8,
                                   color=QColor(COLOR_RIPPLE.red(), COLOR_RIPPLE.green(), COLOR_RIPPLE.blue(), 220)))
        self.ripples.append(Ripple(cx, cy, COLOR_RIPPLE,
                                   max_radius=min(w, h)*0.75,
                                   grow=2.5 if strong else 2.1,
                                   fade=2.0 if strong else 1.8,
                                   width=3.2 if strong else 2.6))
        if len(self.drops) > LISTEN_MAX_DROPS: self.drops = self.drops[-LISTEN_MAX_DROPS:]
        if len(self.ripples) > LISTEN_MAX_RIPPLES: self.ripples = self.ripples[-LISTEN_MAX_RIPPLES:]
        self.update()

    def finish_drops_to_ripples(self):
        if not self.drops: return
        w, h = self.width(), self.height()
        for d in self.drops:
            y_floor = min(max(d.y, h*0.55), h*0.85)
            self.ripples.append(Ripple(d.x, y_floor, COLOR_RIPPLE,
                                       max_radius=min(w, h)*0.88, grow=2.8, fade=2.0, width=3.0))
        self.drops.clear()
        self.update()

    def set_state(self, st: LinoState):
        prev = self.state
        self.state = st

        if st == LinoState.IDLE:
            if prev == LinoState.LISTENING: self.finish_drops_to_ripples()
            self._start_bg_fade(COLOR_IDLE_BG, FADE_GENERIC_SEC)
            self.spawn_timer.stop()

        elif st == LinoState.LISTENING:
            self._start_entry()

        elif st == LinoState.SLEEPING:
            if prev == LinoState.LISTENING: self.finish_drops_to_ripples()
            self._start_bg_fade(COLOR_SLEEP_BG, FADE_GENERIC_SEC)
            self.spawn_timer.stop()

        self.update()

    def _reset_entry(self):
        self._entry_t0 = 0.0
        self._entry_phase = 0
        self._allow_spawns = False

    def _start_entry(self):
        self._reset_entry()
        self._entry_t0 = time.time()
        self._start_bg_fade(COLOR_LISTEN_BG, LISTENING_ENTRY_BG_FADE_SEC)
        w, h = self.width(), self.height()
        cx = random.uniform(w*0.45, w*0.55)
        cy = random.uniform(h*0.50, h*0.62)
        self.ripples.append(Ripple(cx, cy, COLOR_RIPPLE,
                                   max_radius=min(w,h)*0.85, grow=2.3, fade=1.8, width=2.8))
        self._entry_phase = 1

    def _progress_entry(self, now: float):
        if self._entry_phase == 0: return
        t = now - self._entry_t0
        if self._entry_phase == 1 and t >= 0.8:
            mw = self.parent()
            if mw and hasattr(mw, "play_entry_se"):
                mw.play_entry_se()
            self._entry_phase = 2
            self._entry_phase_t0 = now
        elif self._entry_phase == 2 and (now - self._entry_phase_t0) >= 0.5:
            self._allow_spawns = True
            if not self.spawn_timer.isActive():
                self.spawn_timer.start(LISTEN_SPAWN_INTERVAL_MS)
            self._entry_phase = 3

    def _spawn_during_listen(self):
        if self.state != LinoState.LISTENING or not self._allow_spawns:
            return
        w, h = self.width(), self.height()
        x = random.uniform(w*0.18, w*0.82)
        y0 = random.uniform(h*-0.1, h*0.15)
        y1 = random.uniform(h*0.55, h*0.78)
        speed = random.uniform(6.0, 8.0)
        self.drops.append(Raindrop(x, y0, y1, speed,
                                   QColor(COLOR_RIPPLE.red(), COLOR_RIPPLE.green(), COLOR_RIPPLE.blue(), 200)))
        if len(self.drops) > LISTEN_MAX_DROPS:
            self.drops = self.drops[-LISTEN_MAX_DROPS:]
        rx = x + random.uniform(-3, 3)
        ry = y1 + random.uniform(-2, 2)
        self.ripples.append(Ripple(rx, ry, COLOR_RIPPLE,
                                   max_radius=min(w, h)*0.82, grow=2.6, fade=1.9, width=3.0))
        if len(self.ripples) > LISTEN_MAX_RIPPLES:
            self.ripples = self.ripples[-LISTEN_MAX_RIPPLES:]

    def _on_frame(self):
        now = time.time()
        self._update_bg_fade(now)
        if self.state == LinoState.LISTENING:
            self._progress_entry(now)
            if self._allow_spawns:
                next_drops = []
                for d in self.drops:
                    if d.update():
                        next_drops.append(d)
                    else:
                        self.ripples.append(Ripple(d.x, d.y1, COLOR_RIPPLE,
                                                   max_radius=min(self.width(), self.height())*0.88,
                                                   grow=2.9, fade=2.1, width=3.2))
                self.drops = next_drops
        self.ripples = [r for r in self.ripples if r.update()]
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QBrush(self.bg_color))
        if self.state == LinoState.LISTENING or self._entry_phase > 0:
            for d in self.drops: d.paint(p)
        for r in self.ripples: r.paint(p)
        p.end()


# ----------------- 設定オーバーレイ（メイン内 子ウィジェット） -----------------
class SettingsOverlay(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        # 全面オーバーレイ 半透明
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(0,0,0,0.15);")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setVisible(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.setSpacing(0)

        # スクロール領域（バー非表示、縦ホイールのみ）
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll)

        # スクロール中身（中央寄せ）
        host = QWidget()
        self.host_lay = QVBoxLayout(host)
        self.host_lay.setContentsMargins(0, 16, 0, 16)
        self.host_lay.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(0,0,0,0)
        row.setSpacing(0)
        row.addStretch(1)

        # 中央パネル
        self.panel = QFrame()
        self.panel.setObjectName("panel")
        self.panel.setStyleSheet("""
            #panel {
                background-color: rgba(255,255,255,0.86);
                border-radius: 16px;
                border: 1px solid rgba(64,128,255,0.45); /* 目立つ薄青の枠 */
            }
            #panel, #panel * { color: #000; }
            QLabel { background: transparent; border: none; }

            /* 入力できる要素は薄い背景と枠で強調（ドロップダウンを除く） */
            QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
                background: rgba(255,255,255,0.98);
                border: 1px solid rgba(0,0,0,0.18);
                border-radius: 8px;
                padding: 6px 8px;
            }
            QPlainTextEdit { min-height: 90px; }

            /* ドロップダウンは縁取り無しのフラット */
            QComboBox {
                background: rgba(255,255,255,0.98);
                border: none;
                border-radius: 8px;
                padding: 6px 8px;
            }
            QComboBox::drop-down { width: 18px; border: none; }
            QComboBox QAbstractItemView {
                background: #fff; color: #000; border: none;
            }

            /* チェックボックスは✓が見えるようにサイズのみ。背景や枠はいじらない */
            QCheckBox { background: transparent; border: none; padding: 4px 2px; }
            QCheckBox::indicator { width: 18px; height: 18px; }
        """)
        self.panel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)
        self.panel.setMinimumWidth(520)
        self.panel.setMaximumWidth(640)

        panel_lay = QVBoxLayout(self.panel)
        panel_lay.setContentsMargins(16,16,16,16)
        panel_lay.setSpacing(16)

        # ヘッダー付きセクション追加のユーティリティ
        def add_section(title_text: str, content_widget: QWidget):
            title = QLabel(title_text); title.setAlignment(Qt.AlignHCenter)
            title.setStyleSheet("font-weight: 700; font-size: 16px; letter-spacing: .2px;")
            line = QFrame(); line.setFrameShape(QFrame.HLine); line.setFrameShadow(QFrame.Plain)
            line.setStyleSheet("color: rgba(0,0,0,0.15); background: rgba(0,0,0,0.15); min-height: 1px; max-height: 1px;")
            panel_lay.addWidget(title)
            panel_lay.addWidget(line)
            panel_lay.addWidget(content_widget)

        # --- Wake ---
        g_wake = QWidget(); lay_w = QFormLayout(g_wake); lay_w.setLabelAlignment(Qt.AlignLeft)
        self.sl_th = QSlider(Qt.Horizontal); self.sl_th.setMinimum(40); self.sl_th.setMaximum(90); self.sl_th.setValue(60)
        self.ck_short = QCheckBox("短縮形/部分一致を許容"); self.ck_short.setChecked(True)
        self.ck_sim   = QCheckBox("類似音素を許容"); self.ck_sim.setChecked(True)
        lay_w.addRow("しきい値 (0.40〜0.90)", self.sl_th); lay_w.addRow(self.ck_short); lay_w.addRow(self.ck_sim)
        add_section("ウェイク設定", g_wake)

        # --- API / Realtime（ダミー表示） ---
        g_api = QWidget(); lay_a = QFormLayout(g_api); lay_a.setLabelAlignment(Qt.AlignLeft)
        self.cb_model = QComboBox(); self.cb_model.addItems(
            ["gpt-4o-realtime-preview", "gpt-4o-realtime-mini", "gpt-5", "gpt-5-mini", "gpt-5-nano"])
        self.ck_realtime_only = QCheckBox("Realtimeのみを使用"); self.ck_realtime_only.setChecked(True)
        self.cb_emotion = QComboBox(); self.cb_emotion.addItems(["tsun","genki","calm","whisper"])
        self.ed_sys = QPlainTextEdit(); self.ed_sys.setPlainText(DEFAULT_SYSTEM_PROMPT); self.ed_sys.setMinimumHeight(90)
        lay_a.addRow("モデル名", self.cb_model); lay_a.addRow(self.ck_realtime_only)
        lay_a.addRow("TTS感情プリセット", self.cb_emotion); lay_a.addRow("システムプロンプト", self.ed_sys)
        add_section("API / Realtime（ダミー）", g_api)

        # --- Audio I/O ---
        g_audio = QWidget(); lay_o = QFormLayout(g_audio); lay_o.setLabelAlignment(Qt.AlignLeft)
        self.cb_in_dev = QComboBox()
        self.cb_sr = QComboBox(); self.cb_sr.addItems(["48000","44100","32000","16000"]); self.cb_sr.setCurrentText("48000")
        self.cb_ch = QComboBox(); self.cb_ch.addItems(["1","2"]); self.cb_ch.setCurrentText("1")
        self.btn_apply_audio = QPushButton("適用")
        lay_o.addRow("入力デバイス", self.cb_in_dev)
        lay_o.addRow("サンプルレート(Hz)", self.cb_sr)
        lay_o.addRow("チャンネル", self.cb_ch)
        lay_o.addRow(self.btn_apply_audio)
        add_section("オーディオ設定", g_audio)

        # --- VAD（ダミー表示） ---
        g_vad = QWidget(); lay_v = QFormLayout(g_vad); lay_v.setLabelAlignment(Qt.AlignLeft)
        self.cb_frame = QComboBox(); self.cb_frame.addItems(["10","20","30"]); self.cb_frame.setCurrentText("20")
        self.cb_aggr  = QComboBox(); self.cb_aggr.addItems(["0(寛容)","1","2","3(厳格)"]); self.cb_aggr.setCurrentIndex(0)
        self.sp_stop  = QComboBox(); self.sp_stop.addItems(["300","400","500","600","800","1000"]); self.sp_stop.setCurrentText("500")
        self.sp_minvo = QComboBox(); self.sp_minvo.addItems(["100","150","200","250","300"]); self.sp_minvo.setCurrentText("200")
        lay_v.addRow("フレーム(ms)", self.cb_frame); lay_v.addRow("厳しさ", self.cb_aggr)
        lay_v.addRow("停止無音(ms)", self.sp_stop); lay_v.addRow("開始最小voiced(ms)", self.sp_minvo)
        add_section("VAD（ダミー）", g_vad)

        row.addWidget(self.panel, 0, Qt.AlignTop)
        row.addStretch(1)
        self.host_lay.addLayout(row)

        self.scroll.setWidget(host)
        self._fill_audio_inputs()

    # 表示制御
    def open(self):
        self.setGeometry(self.parent().rect())
        self.setVisible(True)
        self.raise_()
        self._recenter_v()
        self.panel.setFocus()

    def close_overlay(self):
        self.setVisible(False)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close_overlay(); return
        if (e.key() == Qt.Key_Slash) and (e.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
            self.close_overlay(); return
        super().keyPressEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._recenter_v()

    def parent_resized_or_moved(self):
        if self.isVisible():
            self.setGeometry(self.parent().rect())
            self._recenter_v()

    def _recenter_v(self):
        vh = self.scroll.viewport().height()
        ph = self.panel.sizeHint().height()
        top = max(16, (vh - ph) // 2)
        bot = top
        if ph + 32 > vh:
            top = 16; bot = 16
        self.host_lay.setContentsMargins(0, top, 0, bot)

    def _fill_audio_inputs(self):
        self.cb_in_dev.clear()
        if not HAVE_QTMEDIA:
            self.cb_in_dev.addItem("QtMultimediaなし", None); return
        for dev in QMediaDevices.audioInputs():
            self.cb_in_dev.addItem(dev.description(), dev.id())
        if self.cb_in_dev.count() == 0:
            self.cb_in_dev.addItem("入力デバイスなし", None)

    def current_config(self):
        return {
            "wake": {
                "threshold": self.sl_th.value()/100.0,
                "allow_short": self.ck_short.isChecked(),
                "allow_similar": self.ck_sim.isChecked(),
            },
            "api": {
                "model": self.cb_model.currentText(),
                "realtime_only": self.ck_realtime_only.isChecked(),
                "tts_emotion": self.cb_emotion.currentText(),
                "system_prompt": self.ed_sys.toPlainText().strip(),
            },
            "audio": {
                "device_id": self.cb_in_dev.currentData(),
                "samplerate": int(self.cb_sr.currentText()),
                "channels": int(self.cb_ch.currentText()),
            },
            "vad": {
                "frame_ms": int(self.cb_frame.currentText()),
                "aggressiveness": int(self.cb_aggr.currentText()[0]),
                "stop_silence_ms": int(self.sp_stop.currentText()),
                "min_voiced_ms": int(self.sp_minvo.currentText()),
            }
        }


# ----------------- メイン -----------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)

        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), Qt.white)
        self.setPalette(pal)

        self.header = CloudHeader(self)
        self.canvas = RainCanvas()
        self.canvas.setParent(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)
        root.addWidget(self.header, 0)
        root.addWidget(self.canvas, 1)

        self.header.btn_idle.clicked.connect(lambda: self.set_state(LinoState.IDLE))
        self.header.btn_listen.clicked.connect(lambda: self.set_state(LinoState.LISTENING))
        self.header.btn_sleep.clicked.connect(lambda: self.set_state(LinoState.SLEEPING))

        self.tray = QSystemTrayIcon(self)
        self.tray_menu = QMenu()
        act_show   = QAction("表示/非表示", self)
        act_idle   = QAction("昼（待機）", self)
        act_listen = QAction("雨（起動）", self)
        act_sleep  = QAction("夜（おやすみ）", self)
        act_quit   = QAction("終了", self)
        act_show.triggered.connect(self.toggle_visible)
        act_idle.triggered.connect(lambda: self.set_state(LinoState.IDLE))
        act_listen.triggered.connect(lambda: self.set_state(LinoState.LISTENING))
        act_sleep .triggered.connect(lambda: self.set_state(LinoState.SLEEPING))
        act_quit  .triggered.connect(QApplication.instance().quit)
        for a in (act_show, None, act_idle, act_listen, act_sleep, None, act_quit):
            self.tray_menu.addAction(a) if a else self.tray_menu.addSeparator()
        self.tray.setContextMenu(self.tray_menu)
        self._update_tray_icon(LinoState.IDLE)
        self.tray.show()

        # 設定はメイン内オーバーレイ
        self.settings_overlay = SettingsOverlay(self)
        self.settings_overlay.btn_apply_audio.clicked.connect(self._apply_audio_settings)

        self.audio_cfg_cache = {"device_id": None, "samplerate": 48000, "channels": 1}

        # 雨入り用SE（既存ShowerSE優先 無ければGentleRainSE）
        self._gentle_shower = None
        self._init_gentle_shower()

        # 昼↔夜 自動サイクル
        self.cycle_timer = QTimer(self); self.cycle_timer.timeout.connect(self._cycle_idle_sleep)
        self.cycle_timer.start(1000); self._cycle_next_ts = time.time() + IDLE_SLEEP_CYCLE_SEC

        # 無操作タイムアウト
        self.last_activity_ts = time.time()
        self.timeout_timer = QTimer(self); self.timeout_timer.timeout.connect(self._check_timeout); self.timeout_timer.start(1000)

        self.set_state(LinoState.IDLE)

    # ===== センタリング追従 =====
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.settings_overlay:
            self.settings_overlay.parent_resized_or_moved()

    def moveEvent(self, e):
        super().moveEvent(e)
        if self.settings_overlay:
            self.settings_overlay.parent_resized_or_moved()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.WindowStateChange:
            if self.settings_overlay:
                self.settings_overlay.parent_resized_or_moved()

    # ===== 既存ロジック =====
    def _init_gentle_shower(self):
        if hasattr(self, "se") and hasattr(self.se, "play_once"):
            try:
                if hasattr(self.se, "sink"):
                    self.se.sink.setVolume(0.5)
                self._gentle_shower = self.se
                return
            except Exception:
                pass
        try:
            from __main__ import ShowerSE
            self._gentle_shower = ShowerSE(self, duration_sec=5.5)
            try:
                if hasattr(self._gentle_shower, "sink"):
                    self._gentle_shower.sink.setVolume(0.5)
            except Exception:
                pass
            return
        except Exception:
            pass
        self._gentle_shower = GentleRainSE(self, duration_sec=5.5)

    def play_entry_se(self):
        if self._gentle_shower and hasattr(self._gentle_shower, "play_once"):
            self._gentle_shower.play_once()

    def on_ambient_detected(self):
        if self.canvas.state != LinoState.LISTENING:
            self.canvas.ping_center(strong=False)
            self.last_activity_ts = time.time()

    def on_wake_start_detected(self):
        if self.canvas.state == LinoState.LISTENING:
            return
        self.canvas.ping_center(strong=True)
        self.play_entry_se()
        self.set_state(LinoState.LISTENING)
        self.last_activity_ts = time.time()

    def on_wake_settings_detected(self):
        self.toggle_settings_overlay()
        self.last_activity_ts = time.time()

    def set_state(self, st: LinoState):
        if self.canvas.state == st:
            return
        prev = self.canvas.state
        if prev == LinoState.LISTENING and st != LinoState.LISTENING:
            self.canvas.finish_drops_to_ripples()
        self.canvas.set_state(st)
        self._update_tray_icon(st)
        self._cycle_next_ts = time.time() + IDLE_SLEEP_CYCLE_SEC
        self.last_activity_ts = time.time()

    def _cycle_idle_sleep(self):
        if self.canvas.state == LinoState.LISTENING:
            self._cycle_next_ts = time.time() + IDLE_SLEEP_CYCLE_SEC
            return
        now = time.time()
        if now >= self._cycle_next_ts:
            self._cycle_next_ts = now + IDLE_SLEEP_CYCLE_SEC
            self.set_state(LinoState.SLEEPING if self.canvas.state == LinoState.IDLE else LinoState.IDLE)

    def _check_timeout(self):
        if time.time() - self.last_activity_ts >= GLOBAL_TIMEOUT_SEC:
            if self.canvas.state == LinoState.LISTENING:
                self.set_state(LinoState.SLEEPING)
            else:
                self.set_state(LinoState.SLEEPING if self.canvas.state == LinoState.IDLE else LinoState.IDLE)
            self.last_activity_ts = time.time()

    def _update_tray_icon(self, st: LinoState):
        if st == LinoState.LISTENING:
            icon = make_cloud_icon(ICON_CLOUD_LISTEN, with_drop=True); tip = "RainEcho：起動中"
        elif st == LinoState.IDLE:
            icon = make_cloud_icon(ICON_CLOUD_IDLE, with_drop=False); tip = "RainEcho：待機中"
        else:
            icon = make_cloud_icon(ICON_CLOUD_SLEEP, with_drop=False); tip = "RainEcho：おやすみ中"
        self.tray.setIcon(icon)
        self.tray.setToolTip(tip)

    # Ctrl + / で設定オーバーレイ開閉
    def keyPressEvent(self, e):
        if (e.key() == Qt.Key_Slash) and (e.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
            self.toggle_settings_overlay(); return
        if e.key() == Qt.Key_Escape:
            if self.settings_overlay.isVisible():
                self.settings_overlay.close_overlay()
            else:
                self.set_state(LinoState.IDLE)
            return
        if e.key() == Qt.Key_Space:
            self.set_state(LinoState.LISTENING); return
        if e.key() == Qt.Key_S:
            self.set_state(LinoState.SLEEPING); return
        super().keyPressEvent(e)

    def toggle_settings_overlay(self):
        if self.settings_overlay.isVisible():
            self.settings_overlay.close_overlay()
        else:
            self.settings_overlay.open()

    def closeEvent(self, e):
        self.hide()
        e.ignore()
        self.tray.showMessage("RainEcho", "ウィンドウは隠しました（トレイから呼び出し可）", QSystemTrayIcon.Information, 1800)

    def toggle_visible(self):
        if self.isVisible(): self.hide()
        else: self.showNormal(); self.activateWindow()

    def _apply_audio_settings(self):
        cfg = self.settings_overlay.current_config()
        self.audio_cfg_cache = cfg["audio"]
        QMessageBox.information(self, "RainEcho",
            f"オーディオ設定を適用しました\nデバイスID: {self.audio_cfg_cache['device_id']}\nSR: {self.audio_cfg_cache['samplerate']}\nCH: {self.audio_cfg_cache['channels']}")

    def get_audio_settings(self):
        return dict(self.audio_cfg_cache)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = MainWindow()
    w.resize(760, 500)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

# %%
