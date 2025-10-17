import sys, os, json, signal, math, time, random
from functools import partial
from datetime import datetime, timezone

from PySide2 import QtCore, QtGui, QtWidgets
from PySide2.QtGui import QFontDatabase, QFont
from PySide2.QtMultimedia import QMediaPlayer, QMediaContent, QMediaPlaylist
from shiboken2 import wrapInstance, isValid

IN_MAYA = False
try:
    import maya.OpenMayaUI as omui  # type: ignore
    IN_MAYA = True
except Exception:
    omui = None

PALETTE_BG = "#FFF4E6"
PALETTE_PINK = "#FAD0EB"
PALETTE_PURPLE = "#F2D4FF"
PALETTE_TEXT = "#6B5B53"
PALETTE_BORDER = "#F5C7E3"
HILITE = "#7A6C8F"

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
IMG_DIR   = os.path.join(BASE_DIR, "assets", "images")
SND_PATH  = os.path.join(BASE_DIR, "assets", "sound", "soundtrack.mp3")
DATA_DIR  = os.path.join(BASE_DIR, "assets", "data")
SAVE_PATH = os.path.join(DATA_DIR, "save.json")
FONT_PATH = os.path.join(BASE_DIR, "assets", "font", "TA 8 bit.ttf")

PREFERRED_IMAGES = ["novvel.png", "tama.png"]


def ensure_dirs():
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)

def clamp(v, a, b):
    return max(a, min(b, v))

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def parse_iso(s):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s)
        except Exception:
            return datetime.now(timezone.utc)

def hours_between(iso_then, iso_now=None):
    if not iso_then:
        return 0.0
    dt_then = parse_iso(iso_then)
    dt_now = parse_iso(iso_now) if iso_now else datetime.now(timezone.utc)
    return max(0.0, (dt_now - dt_then).total_seconds() / 3600.0)

def load_save():
    try:
        if os.path.exists(SAVE_PATH):
            with open(SAVE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_save(data: dict):
    ensure_dirs()
    tmp = SAVE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SAVE_PATH)

def list_pet_images():
    items = []
    if os.path.isdir(IMG_DIR):
        for name in PREFERRED_IMAGES:
            fp = os.path.join(IMG_DIR, name)
            if os.path.exists(fp):
                items.append((os.path.splitext(name)[0], fp))
        for fn in sorted(os.listdir(IMG_DIR)):
            if fn.lower().endswith(".png"):
                fp = os.path.join(IMG_DIR, fn)
                base = os.path.splitext(fn)[0]
                if all(fp != p for _, p in items):
                    items.append((base, fp))
    return items


class BackgroundMusic(QtCore.QObject):
    """ควบคุมเพลงพื้นหลังด้วย QMediaPlayer/QMediaPlaylist"""
    def __init__(self, parent=None, volume=10):
        super().__init__(parent)
        self.player = QMediaPlayer(parent)
        self.playlist = QMediaPlaylist(parent)
        self.playlist.setPlaybackMode(QMediaPlaylist.Loop)
        if os.path.exists(SND_PATH):
            url = QtCore.QUrl.fromLocalFile(SND_PATH)
            self.playlist.addMedia(QMediaContent(url))
        else:
            print("[Warning] เพลงไม่พบที่:", SND_PATH)
        self.player.setPlaylist(self.playlist)
        self.player.setVolume(int(volume))

    def start(self):
        if self.playlist.mediaCount() > 0:
            self.player.play()

    def stop(self): self.player.stop()
    def set_volume(self, v:int): self.player.setVolume(int(v))
    def volume(self): return self.player.volume()
    def toggle_mute(self)->bool:
        self.player.setMuted(not self.player.isMuted())
        return self.player.isMuted()


class PixelLabel(QtWidgets.QLabel):
    """QLabel ปรับขนาด/หนา พร้อมโทนสีธีม"""
    def __init__(self, text="", size=14, bold=False, parent=None):
        super().__init__(text, parent)
        f = self.font(); f.setPointSize(size); f.setBold(bold)
        self.setFont(f)
        self.setStyleSheet(f"color:{PALETTE_TEXT}")


class StarButton(QtWidgets.QPushButton):
    """ปุ่มทรงสี่เหลี่ยมมุมมนขนาดใหญ่สำหรับ action หลัก"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFixedSize(96, 96)
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.setText(text)
        self.setStyleSheet(f"""
            QPushButton {{
                border: 0px; background-color: {PALETTE_PINK};
                border-radius: 20px; font-size: 22px;
            }}
            QPushButton:hover {{ background-color: #FFD6F0; }}
        """)


class PoopItem(QtWidgets.QGraphicsTextItem):
    """อีโม่จิ 💩 ในฉาก คลิกเพื่อเก็บ"""
    def __init__(self, pid: str, x: float, y: float, on_clicked, parent=None):
        super().__init__("💩", parent)
        self.setDefaultTextColor(QtGui.QColor("#6B4E16"))
        f = QtGui.QFont(); f.setPointSize(22)
        self.setFont(f)
        self.setPos(x, y)
        self.setZValue(5)
        self.pid = pid
        self.on_clicked = on_clicked
        self.setAcceptHoverEvents(True)
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

    def hoverEnterEvent(self, e):
        self.setDefaultTextColor(QtGui.QColor("#4E3A10"))
        super().hoverEnterEvent(e)

    def hoverLeaveEvent(self, e):
        self.setDefaultTextColor(QtGui.QColor("#6B4E16"))
        super().hoverLeaveEvent(e)

    def mousePressEvent(self, e):
        if self.on_clicked:
            self.on_clicked(self.pid)
        super().mousePressEvent(e)


class GameView(QtWidgets.QGraphicsView):
    """พื้นที่ฉาก: ตัวสัตว์เดินซ้าย-ขวา บ๊อบขึ้นลง พลิกทิศ และมีระบบวาง/เก็บ 💩"""
    def __init__(self, pet_pix_path=None, parent=None):
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        scn = QtWidgets.QGraphicsScene(self)
        self.setScene(scn)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        self.setStyleSheet("background:#FFFFFF; border:0px;")
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        scn.setSceneRect(0, 0, 640, 420)

        pix = None
        if pet_pix_path:
            pm = QtGui.QPixmap(pet_pix_path)
            if not pm.isNull():
                pix = pm
            else:
                print("[PetGame] ไม่สามารถโหลดรูปได้:", pet_pix_path)
        if pix is None:
            pix = self._make_placeholder()
            print("[PetGame] ใช้ placeholder")

        max_side = 120
        if pix.width() > max_side or pix.height() > max_side:
            pix = pix.scaled(max_side, max_side, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

        self.item = scn.addPixmap(pix)
        self.speed = 1.6
        self.amp = 6.0
        self.t = 0.0
        self.facing_right = True
        self.margin = 12
        self._place_on_ground(center=True)

        self.walkTimer = QtCore.QTimer(self)
        self.walkTimer.timeout.connect(self._tick)
        self.walkTimer.start(16)

        self.poop_items = {}
        self._poop_click_cb = None

    def _make_placeholder(self):
        pix = QtGui.QPixmap(120, 120)
        pix.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setBrush(QtGui.QColor("#FFC0D9"))
        p.setPen(QtGui.QPen(QtGui.QColor("#333"), 3))
        p.drawEllipse(10, 10, 100, 100)
        p.end()
        return pix

    def _scene_bounds_for_item(self):
        s = self.sceneRect()
        pm = self.item.pixmap()
        ground_y = s.bottom() - pm.height() - 20
        left_x = s.left() + self.margin
        right_x = s.right() - self.margin - pm.width()
        return left_x, right_x, ground_y

    def _place_on_ground(self, center=False):
        left_x, right_x, ground_y = self._scene_bounds_for_item()
        x = (left_x + right_x) * 0.5 if center else left_x
        self.base_pos = QtCore.QPointF(x, ground_y)
        self.item.setPos(self.base_pos)

    def _flip_if_needed(self, moving_right: bool):
        if moving_right and not self.facing_right:
            self.item.setTransform(QtGui.QTransform())
            self.facing_right = True
        elif (not moving_right) and self.facing_right:
            w = self.item.pixmap().width()
            self.item.setTransform(QtGui.QTransform(-1, 0, 0, 1, w, 0))
            self.facing_right = False

    def _tick(self):
        if not self.item:
            return
        left_x, right_x, ground_y = self._scene_bounds_for_item()
        pos = self.item.pos()
        x = pos.x() + self.speed
        if x < left_x:
            x = left_x
            self.speed = abs(self.speed)
        elif x > right_x:
            x = right_x
            self.speed = -abs(self.speed)
        self.t += 0.12
        y = ground_y - (self.amp * (0.5 + 0.5 * math.sin(self.t)))
        self._flip_if_needed(self.speed > 0)
        self.item.setPos(x, y)

    def set_poop_click_callback(self, cb):
        self._poop_click_cb = cb

    def random_ground_pos(self):
        s = self.sceneRect()
        y = s.bottom() - 28
        x = random.uniform(s.left() + 20, s.right() - 20)
        return x, y

    def spawn_poop(self, pid: str, x: float, y: float):
        if pid in self.poop_items:
            return
        item = PoopItem(pid, x, y, self._poop_click_cb)
        self.scene().addItem(item)
        self.poop_items[pid] = item

    def remove_poop(self, pid: str):
        it = self.poop_items.pop(pid, None)
        if it is not None:
            self.scene().removeItem(it)
            del it

    def clear_all_poops(self):
        for pid in list(self.poop_items.keys()):
            self.remove_poop(pid)

    def resizeEvent(self, e):
        self.scene().setSceneRect(0, 0, self.viewport().width(), self.viewport().height())
        self._place_on_ground(center=False)
        super().resizeEvent(e)


class TopBar(QtWidgets.QWidget):
    """ท็อปบาร์: ปุ่ม Settings และเหรียญ"""
    settingClicked = QtCore.Signal()
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{PALETTE_BG}")
        lay = QtWidgets.QHBoxLayout(self); lay.setContentsMargins(6,6,6,6); lay.setSpacing(12)

        self.btnSetting = QtWidgets.QPushButton("⚙ setting")
        self.btnSetting.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.btnSetting.setStyleSheet("""
            QPushButton { background:#FFE3F5; border:2px solid #F2C3E2; border-radius:12px; padding:6px 12px; color:#6B5B53; }
            QPushButton:hover { background:#FFD6F0; }
        """)
        self.btnSetting.clicked.connect(self.settingClicked.emit)
        lay.addWidget(self.btnSetting, 0, QtCore.Qt.AlignLeft)
        lay.addStretch()

        coinWrap = QtWidgets.QFrame()
        coinWrap.setStyleSheet("QFrame { background:#FFF; border:2px solid #F2C3E2; border-radius:12px; }")
        h = QtWidgets.QHBoxLayout(coinWrap); h.setContentsMargins(10,4,10,4); h.setSpacing(6)
        h.addWidget(PixelLabel("🪙", size=18)); h.addWidget(PixelLabel("bb13100", size=16, bold=True))
        lay.addWidget(coinWrap, 0, QtCore.Qt.AlignRight)


class GamePanel(QtWidgets.QFrame):
    """กรอบเกม: ชื่อสัตว์และ GameView"""
    def __init__(self, pet_pix_path=None, pet_name=""):
        super().__init__()
        self.setStyleSheet(f"QFrame {{ background:#FFFFFF; border:3px solid {PALETTE_BORDER}; border-radius:14px; }}")
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(10,10,10,10); v.setSpacing(8)

        top = QtWidgets.QHBoxLayout()
        self.title = PixelLabel(pet_name or "Your Pet", size=18, bold=True)
        self.title.setStyleSheet("color:#7A6C8F")
        top.addWidget(self.title); top.addStretch()
        home = QtWidgets.QLabel("🏠"); home.setFixedSize(36,36); home.setAlignment(QtCore.Qt.AlignCenter)
        home.setStyleSheet(f"background:#FFF1FC; border:2px solid {PALETTE_BORDER}; border-radius:8px;")
        top.addWidget(home); v.addLayout(top)

        self.view = GameView(pet_pix_path); v.addWidget(self.view, 1)


class BottomBar(QtWidgets.QWidget):
    """ปุ่มคำสั่งหลัก: Wash/Eat/Water/Heal"""
    def __init__(self):
        super().__init__()
        lay = QtWidgets.QHBoxLayout(self); lay.setContentsMargins(0,8,0,0); lay.setSpacing(20)
        lay.addStretch()
        self.btnWash = StarButton("🫧"); self.btnEat = StarButton("🍽️")
        self.btnWater = StarButton("💧"); self.btnHeal = StarButton("✚")
        for b in (self.btnWash, self.btnEat, self.btnWater, self.btnHeal): lay.addWidget(b)
        lay.addStretch()


class StartPage(QtWidgets.QWidget):
    """หน้าเริ่มต้น พร้อมปุ่ม Start Game"""
    startClicked = QtCore.Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{PALETTE_BG}")
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(24,24,24,24); v.setSpacing(12)
        title = PixelLabel("TAMATOTS", size=28, bold=True); title.setAlignment(QtCore.Qt.AlignCenter); v.addWidget(title)
        v.addStretch()
        btn = QtWidgets.QPushButton("Start Game")
        btn.setFixedHeight(70); btn.setFixedWidth(250)
        btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        btn.setStyleSheet(f"""
            QPushButton {{ background:#FFFFFF; border:3px solid {PALETTE_BORDER}; border-radius:14px; font-size:20px; color:{PALETTE_TEXT}; }}
            QPushButton:hover {{ background:#FFEFFC; }}
        """)
        btn.clicked.connect(self.startClicked.emit)
        v.addWidget(btn, 0, QtCore.Qt.AlignCenter); v.addStretch()


class GamePage(QtWidgets.QWidget):
    """หน้าหลักของเกม: สถานะ (bars/หัวใจ), ฉาก, ปุ่มล่าง"""
    def __init__(self, pet_pix_path=None, pet_name=""):
        super().__init__()
        self.setStyleSheet(f"background:{PALETTE_BG}")
        outer = QtWidgets.QVBoxLayout(self); outer.setContentsMargins(16,16,16,16); outer.setSpacing(12)

        self.topbar = TopBar(); outer.addWidget(self.topbar)

        panel = QtWidgets.QFrame()
        panel.setStyleSheet(f"QFrame {{ background:{PALETTE_PURPLE}; border:3px solid {PALETTE_BORDER}; border-radius:14px; }}")
        pv = QtWidgets.QVBoxLayout(panel); pv.setContentsMargins(12,12,12,12); pv.setSpacing(10)

        status = QtWidgets.QWidget()
        status.setStyleSheet(f"background:{PALETTE_PINK}; border:2px solid {PALETTE_BORDER}; border-radius:12px;")
        sh = QtWidgets.QVBoxLayout(status); sh.setContentsMargins(12,8,12,8); sh.setSpacing(6)

        heartRow = QtWidgets.QHBoxLayout(); heartRow.setSpacing(8)
        self.hearts = PixelLabel("❤❤❤❤❤")
        self.hearts.setStyleSheet("color:#E26693;")
        heartRow.addWidget(self.hearts); heartRow.addStretch()
        sh.addLayout(heartRow)

        def make_bar(color="#7A6C8F"):
            bar = QtWidgets.QProgressBar()
            bar.setRange(0,100); bar.setValue(80)
            bar.setTextVisible(True)
            bar.setStyleSheet(f"""
                QProgressBar {{
                    background:#FFFFFF; border:2px solid {PALETTE_BORDER};
                    border-radius:8px; padding:2px; color:{PALETTE_TEXT};
                }}
                QProgressBar::chunk {{
                    background:{color}; border-radius:6px;
                }}
            """)
            return bar

        grid = QtWidgets.QGridLayout(); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(8)
        grid.addWidget(PixelLabel("Hunger", size=12), 0, 0); self.barHunger = make_bar("#9B8CF2"); grid.addWidget(self.barHunger, 0, 1)
        grid.addWidget(PixelLabel("Clean", size=12), 1, 0); self.barClean  = make_bar("#F289C0"); grid.addWidget(self.barClean, 1, 1)
        grid.addWidget(PixelLabel("Fun", size=12),   2, 0); self.barFun    = make_bar("#7BC6A4"); grid.addWidget(self.barFun, 2, 1)
        grid.addWidget(PixelLabel("Health", size=12),3, 0); self.barHealth = make_bar("#F2C879"); grid.addWidget(self.barHealth, 3, 1)

        sh.addLayout(grid)
        pv.addWidget(status)

        self.gamePanel = GamePanel(pet_pix_path, pet_name); pv.addWidget(self.gamePanel, 1)
        outer.addWidget(panel, 1)

        self.bottom = BottomBar(); outer.addWidget(self.bottom)
        self.bottom.btnEat.clicked.connect(lambda: self.flash_message("อร่อยยย!"))
        self.bottom.btnWash.clicked.connect(lambda: self.flash_message("ล้างสะอาดแล้ว!"))
        self.bottom.btnWater.clicked.connect(lambda: self.flash_message("อึก อึก"))
        self.bottom.btnHeal.clicked.connect(lambda: self.flash_message("รู้สึกดีมากกก!"))

    def flash_message(self, text):
        m = QtWidgets.QLabel(text, self.gamePanel)
        m.setStyleSheet("background:#000000AA; color:white; padding:6px 10px; border-radius:8px;")
        m.adjustSize(); m.move(200, 20); m.show()
        QtCore.QTimer.singleShot(800, m.deleteLater)

    def set_pet_title(self, name: str):
        self.gamePanel.title.setText(name or "Your Pet")


class SelectPetDialog(QtWidgets.QDialog):
    """ไดอะล็อกเลือกสัตว์ (ปุ่มเล็กด้านล่าง) + ตั้งชื่อ"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose your pet")
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{ background: #FFFFFF; }}
            QLabel#Thumb {{ background:#ECECEC; border:2px solid #CFCFCF; border-radius:12px; }}
            QLabel#Thumb[selected="true"] {{ background:#F3ECFF; border:3px solid {HILITE}; }}
            QPushButton {{ min-width:60px; font-size:13px; padding:4px 10px; }}
            QLineEdit {{ border:1px solid #CFCFCF; border-radius:6px; padding:3px 6px; }}
        """)
        self.setMinimumWidth(680)

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16); v.setSpacing(10)
        v.addWidget(PixelLabel("Select your pet", size=18, bold=True))

        self.pets = list_pet_images()
        self.selected_index = 0 if self.pets else None

        self.imgRow = QtWidgets.QHBoxLayout(); self.imgRow.setSpacing(16)
        v.addLayout(self.imgRow)
        self.imgLabels = []
        for _, path in self.pets:
            lab = QtWidgets.QLabel(); lab.setObjectName("Thumb")
            lab.setAlignment(QtCore.Qt.AlignCenter); lab.setFixedSize(200, 200)
            px = QtGui.QPixmap(path)
            if px.isNull(): lab.setText("(missing)")
            else: lab.setPixmap(px.scaled(180, 180, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            self.imgRow.addWidget(lab, 1); self.imgLabels.append(lab)

        self.btnRow = QtWidgets.QHBoxLayout(); self.btnRow.setSpacing(16)
        v.addLayout(self.btnRow)
        self.selectButtons = []
        for idx, (_name, _path) in enumerate(self.pets):
            btn = QtWidgets.QPushButton(f"pet {idx+1}")
            btn.setFixedSize(80, 32)
            btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            btn.setStyleSheet("QPushButton { background:#FFFFFF; border:2px solid %s; border-radius:8px; }"
                              "QPushButton:hover { background:#F2F2F2; }" % PALETTE_BORDER)
            btn.clicked.connect(partial(self._select_index, idx))
            self.btnRow.addWidget(btn, 1); self.selectButtons.append(btn)

        form = QtWidgets.QHBoxLayout()
        form.addWidget(PixelLabel("Name:", size=14))
        self.nameEdit = QtWidgets.QLineEdit(); self.nameEdit.setPlaceholderText("ตั้งชื่อสัตว์เลี้ยงของคุณ")
        form.addWidget(self.nameEdit, 1); v.addLayout(form)

        btns = QtWidgets.QHBoxLayout(); btns.addStretch()
        self.btnCancel = QtWidgets.QPushButton("Cancel")
        self.btnOk = QtWidgets.QPushButton("Select"); self.btnOk.setEnabled(False)
        btns.addWidget(self.btnCancel); btns.addWidget(self.btnOk); v.addLayout(btns)

        self.btnCancel.clicked.connect(self.reject)
        self.btnOk.clicked.connect(self._accept_if_valid)
        self.nameEdit.textChanged.connect(self._update_ok_state)

        self._refresh_highlight(); self._update_ok_state()

    def _select_index(self, i:int):
        self.selected_index = i
        self._refresh_highlight(); self._update_ok_state()

    def _refresh_highlight(self):
        for j, lab in enumerate(self.imgLabels):
            sel = (j == self.selected_index)
            lab.setProperty("selected", sel)
            lab.style().unpolish(lab); lab.style().polish(lab); lab.update()

    def _update_ok_state(self):
        has_name = bool(self.nameEdit.text().strip())
        has_sel = self.selected_index is not None and 0 <= self.selected_index < len(self.pets)
        self.btnOk.setEnabled(has_name and has_sel)

    def _accept_if_valid(self):
        if not self.btnOk.isEnabled(): return
        super().accept()

    def get_result(self):
        if self.selected_index is None or not self.pets: return {}
        _, path = self.pets[self.selected_index]
        return {"pet_name": self.nameEdit.text().strip(), "pet_image": path}


class SettingsDialog(QtWidgets.QDialog):
    """ตั้งค่าเสียง + ปุ่ม Back to Start (modal)"""
    backToStart = QtCore.Signal()
    def __init__(self, parent=None, current_volume=10):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{ background:#FFFFFF; }}
            QPushButton {{ min-width:60px; font-size:13px; padding:4px 10px; }}
            QSlider::groove:horizontal {{ height:6px; background:#E8E8E8; border-radius:3px; }}
            QSlider::handle:horizontal {{ width:14px; background:{HILITE}; border-radius:7px; margin:-4px 0; }}
        """)
        self.setMinimumWidth(380)

        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(16,16,16,16); v.setSpacing(12)
        v.addWidget(PixelLabel("Audio", size=16, bold=True))
        hv = QtWidgets.QHBoxLayout()
        hv.addWidget(PixelLabel("Volume:", size=14))
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal); self.slider.setRange(0,100); self.slider.setValue(int(current_volume))
        hv.addWidget(self.slider, 1); v.addLayout(hv)

        v.addSpacing(10); v.addWidget(PixelLabel("Navigation", size=16, bold=True))
        self.btnBack = QtWidgets.QPushButton("↩ Back to Start")
        self.btnBack.setStyleSheet("QPushButton { background:#FFFFFF; border:2px solid %s; border-radius:10px; }" % PALETTE_BORDER)
        v.addWidget(self.btnBack, 0, QtCore.Qt.AlignLeft)

        btns = QtWidgets.QHBoxLayout(); btns.addStretch()
        self.btnClose = QtWidgets.QPushButton("Close"); btns.addWidget(self.btnClose); v.addLayout(btns)

        self.btnBack.clicked.connect(self._on_back)
        self.btnClose.clicked.connect(self.accept)

    def _on_back(self):
        self.backToStart.emit()
        self.accept()


class MainWindow(QtWidgets.QMainWindow):
    """หน้าต่างหลัก: จัดการ state, เพลง, หน้าต่างย่อย, สถานะ และตัวจับเวลา"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pet Game UI")
        self.resize(560, 840)
        self.setStyleSheet(f"QMainWindow {{ background:{PALETTE_BG}; }}")

        self.state = load_save() or {}
        self.state.setdefault("volume", 10)
        self.state.setdefault("stats", {"hunger":80, "clean":80, "fun":80, "health":80})
        self.state.setdefault("cfg", {
            "decay_per_hour": {"hunger":6, "clean":5, "fun":7, "health":2},
            "min_tick_secs": 2,
            "autosave_secs": 12
        })
        self.state.setdefault("poops", [])
        self.state.setdefault("poop_cfg", {
            "spawn_min_sec": 90,
            "spawn_max_sec": 240,
            "max_on_field": 5,
            "decay_clean_per_min": 2,
            "offline_spawn_per_hour": 1,
            "offline_spawn_cap": 6,
            "clean_reward": 8,
            "coin_reward": 0
        })
        self.state.setdefault("last_seen", now_iso())

        self.apply_offline_decay()
        self.apply_offline_poops()

        self.music = BackgroundMusic(parent=self, volume=self.state.get("volume", 10))
        self.music.start()

        self.stacked = QtWidgets.QStackedWidget(); self.setCentralWidget(self.stacked)
        self.startPage = StartPage(); self.stacked.addWidget(self.startPage)
        self.gamePage = None

        self.startPage.startClicked.connect(self.on_start_clicked)
        QtWidgets.QShortcut(QtGui.QKeySequence("Esc"), self, activated=self.close)

        self.last_tick = time.time()
        self.tickTimer = QtCore.QTimer(self)
        self.tickTimer.timeout.connect(self._on_tick)
        self.tickTimer.start(int(self.state["cfg"]["min_tick_secs"]*1000))

        self.autoSaveTimer = QtCore.QTimer(self)
        self.autoSaveTimer.timeout.connect(lambda: save_save(self.state))
        self.autoSaveTimer.start(int(self.state["cfg"]["autosave_secs"]*1000))

        self.poopSpawnTimer = QtCore.QTimer(self)
        self.poopSpawnTimer.timeout.connect(self._on_poop_spawn_time)
        self._schedule_next_poop()

        self.poopDecayTimer = QtCore.QTimer(self)
        self.poopDecayTimer.timeout.connect(self._on_poop_decay_minute)
        self.poopDecayTimer.start(60_000)

    def apply_offline_decay(self):
        hrs = hours_between(self.state.get("last_seen"))
        if hrs <= 0:
            self.state["last_seen"] = now_iso()
            return
        decay = self.state["cfg"]["decay_per_hour"]
        s = self.state["stats"]
        for k, rate in decay.items():
            s[k] = clamp(s.get(k, 80) - rate*hrs, 0, 100)
        self.state["last_seen"] = now_iso()

    def apply_offline_poops(self):
        hrs = hours_between(self.state.get("last_seen"))
        cfg = self.state["poop_cfg"]
        n_new = min(int(hrs * cfg["offline_spawn_per_hour"]), cfg["offline_spawn_cap"])
        self.state["stats"]["clean"] = clamp(
            self.state["stats"]["clean"] - n_new * cfg["decay_clean_per_min"] * min(hrs, 1),
            0, 100
        )
        self._offline_poop_to_place = n_new

    def on_start_clicked(self):
        has_pet = bool(self.state.get("pet_name")) and bool(self.state.get("pet_image")) and os.path.exists(self.state.get("pet_image",""))
        if not has_pet:
            dlg = SelectPetDialog(self)
            if dlg.exec_() == QtWidgets.QDialog.Accepted:
                res = dlg.get_result()
                if not res: return
                self.state["pet_name"]  = res["pet_name"]
                self.state["pet_image"] = res["pet_image"]
                save_save(self.state)
            else:
                return
        self.enter_game()

    def enter_game(self):
        if self.gamePage:
            idx = self.stacked.indexOf(self.gamePage)
            if idx >= 0:
                w = self.stacked.widget(idx); self.stacked.removeWidget(w); w.deleteLater()
            self.gamePage = None

        pet_img = self.state.get("pet_image")
        pet_name= self.state.get("pet_name","Your Pet")
        self.gamePage = GamePage(pet_pix_path=pet_img, pet_name=pet_name)
        self.gamePage.topbar.settingClicked.connect(self.open_settings)
        self.stacked.addWidget(self.gamePage); self.stacked.setCurrentWidget(self.gamePage)

        self.gamePage.bottom.btnEat.clicked.connect(self.do_eat)
        self.gamePage.bottom.btnWash.clicked.connect(self.do_wash)
        self.gamePage.bottom.btnWater.clicked.connect(self.do_water)
        self.gamePage.bottom.btnHeal.clicked.connect(self.do_heal)

        self.gamePage.gamePanel.view.set_poop_click_callback(self.on_poop_clicked)

        self.reload_poops_into_view()

        n_off = getattr(self, "_offline_poop_to_place", 0) or 0
        if n_off > 0:
            for _ in range(min(n_off, self.state["poop_cfg"]["max_on_field"] - len(self.state["poops"]))):
                x, y = self.gamePage.gamePanel.view.random_ground_pos()
                pid = f"p_{int(time.time()*1000)}_{random.randint(100,999)}"
                spawn_ts = time.time() - random.uniform(0, 3600)
                self.state["poops"].append({"id": pid, "spawn_ts": spawn_ts, "x": x, "y": y})
                self.gamePage.gamePanel.view.spawn_poop(pid, x, y)
            self._offline_poop_to_place = 0
            save_save(self.state)

        self.refresh_ui()

    def reload_poops_into_view(self):
        v = self.gamePage.gamePanel.view
        v.clear_all_poops()
        for p in self.state["poops"]:
            x = p.get("x"); y = p.get("y")
            if x is None or y is None:
                x,y = v.random_ground_pos()
                p["x"], p["y"] = x, y
            v.spawn_poop(p["id"], x, y)

    def open_settings(self):
        dlg = SettingsDialog(self, current_volume=self.music.volume())
        dlg.slider.valueChanged.connect(self.on_volume_changed)
        dlg.backToStart.connect(self.back_to_start)
        dlg.exec_()

    def on_volume_changed(self, v:int):
        self.music.set_volume(int(v))
        self.state["volume"] = int(v); save_save(self.state)

    def back_to_start(self):
        save_save(self.state)
        self.stacked.setCurrentWidget(self.startPage)

    def add_stat(self, key, delta):
        s = self.state["stats"]
        s[key] = clamp(s.get(key, 80) + delta, 0, 100)

    _cooldowns = {"eat":0.0}
    def cooldown_ok(self, key, sec):
        t = time.time()
        if t >= self._cooldowns.get(key, 0.0):
            self._cooldowns[key] = t + sec
            return True
        return False

    def do_eat(self):
        if not self.cooldown_ok("eat", 8):
            self.gamePage.flash_message("ยังไม่หิว เดี๋ยวก่อนน!")
            return
        self.add_stat("hunger", +30)
        self.add_stat("health", +5)
        self.refresh_ui(); save_save(self.state)

    def do_wash(self):
        cfg = self.state["poop_cfg"]
        count = len(self.state["poops"])
        if count > 0:
            if self.gamePage:
                self.gamePage.gamePanel.view.clear_all_poops()
            self.state["poops"].clear()
            self.add_stat("clean", +cfg["clean_reward"] * count)
        else:
            self.add_stat("clean", +10)
        self.refresh_ui(); save_save(self.state)

    def do_water(self):
        self.add_stat("hunger", +10)
        self.add_stat("health", +5)
        self.refresh_ui(); save_save(self.state)

    def do_heal(self):
        h = self.state["stats"]["hunger"]
        c = self.state["stats"]["clean"]
        if h < 30 or c < 30:
            self.add_stat("health", +10)
        else:
            self.add_stat("health", +20)
        self.refresh_ui(); save_save(self.state)

    def _schedule_next_poop(self):
        cfg = self.state["poop_cfg"]
        sec = random.randint(cfg["spawn_min_sec"], cfg["spawn_max_sec"])
        self.poopSpawnTimer.start(sec * 1000)

    def _on_poop_spawn_time(self):
        cfg = self.state["poop_cfg"]
        if len(self.state["poops"]) >= cfg["max_on_field"]:
            return self._schedule_next_poop()
        if not self.gamePage:
            return self._schedule_next_poop()
        x, y = self.gamePage.gamePanel.view.random_ground_pos()
        pid = f"p_{int(time.time()*1000)}_{random.randint(100,999)}"
        self.state["poops"].append({"id": pid, "spawn_ts": time.time(), "x": x, "y": y})
        self.gamePage.gamePanel.view.spawn_poop(pid, x, y)
        save_save(self.state)
        self._schedule_next_poop()

    def _on_poop_decay_minute(self):
        n = len(self.state["poops"])
        if n <= 0:
            return
        dec = self.state["poop_cfg"]["decay_clean_per_min"] * n
        self.add_stat("clean", -dec)
        self.refresh_ui(); save_save(self.state)

    def on_poop_clicked(self, pid):
        if self.gamePage:
            self.gamePage.gamePanel.view.remove_poop(pid)
        before = len(self.state["poops"])
        self.state["poops"] = [p for p in self.state["poops"] if p["id"] != pid]
        if len(self.state["poops"]) < before:
            self.add_stat("clean", +self.state["poop_cfg"]["clean_reward"])
            self.refresh_ui(); save_save(self.state)

    def _on_tick(self):
        now = time.time()
        dt = now - self.last_tick
        self.last_tick = now
        decay = self.state["cfg"]["decay_per_hour"]
        s = self.state["stats"]
        for k, rate in decay.items():
            s[k] = clamp(s[k] - (rate * dt / 3600.0), 0, 100)
        self.refresh_ui()

    def refresh_ui(self):
        if not self.gamePage:
            return
        s = self.state["stats"]
        self.gamePage.barHunger.setValue(int(s["hunger"]))
        self.gamePage.barClean.setValue(int(s["clean"]))
        self.gamePage.barFun.setValue(int(s["fun"]))
        self.gamePage.barHealth.setValue(int(s["health"]))
        mood = (0.4*s["hunger"] + 0.3*s["clean"] + 0.3*s["fun"] + 0.2*s["health"]) / 1.2
        hearts = int(round(mood / 20.0))
        hearts = clamp(hearts, 0, 5)
        self.gamePage.hearts.setText("❤"*hearts + "♡"*(5-hearts))

    def closeEvent(self, e):
        try:
            self.state["last_seen"] = now_iso()
            save_save(self.state); self.music.stop()
        except Exception: pass
        super().closeEvent(e)


def _maya_main_window():
    if IN_MAYA and omui is not None:
        ptr = omui.MQtUtil.mainWindow()
        return wrapInstance(int(ptr), QtWidgets.QWidget)
    return None


def run():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    if os.path.exists(FONT_PATH):
        fid = QFontDatabase.addApplicationFont(FONT_PATH)
        fams = QFontDatabase.applicationFontFamilies(fid)
        if fams:
            QtWidgets.QApplication.setFont(QFont(fams[0], 11))
            print("[Font] Loaded:", fams[0])
        else:
            print("[Font] Font loaded but no family:", FONT_PATH)
    else:
        print("[Font] Not found:", FONT_PATH)
    parent = _maya_main_window()
    win = MainWindow(parent=parent); win.show()
    return app if IN_MAYA else app.exec_()

def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    if os.path.exists(FONT_PATH):
        fid = QFontDatabase.addApplicationFont(FONT_PATH)
        fams = QFontDatabase.applicationFontFamilies(fid)
        if fams:
            QtWidgets.QApplication.setFont(QFont(fams[0], 11))
            print("[Font] Loaded:", fams[0])
        else:
            print("[Font] Font loaded but no family:", FONT_PATH)
    else:
        print("[Font] Not found:", FONT_PATH)
    tick = QtCore.QTimer(); tick.start(250); tick.timeout.connect(lambda: None)
    win = MainWindow(parent=None); win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
