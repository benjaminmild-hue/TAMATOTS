from PySide2 import QtCore, QtGui, QtWidgets
from shiboken2 import wrapInstance, isValid
import maya.OpenMayaUI as omui

PALETTE_BG = "#FFF4E6"
PALETTE_PINK = "#FAD0EB"
PALETTE_PURPLE = "#F2D4FF"
PALETTE_TEXT = "#6B5B53"
PALETTE_BORDER = "#F5C7E3"

class PixelLabel(QtWidgets.QLabel):
    def __init__(self, text="", size=14, bold=False, parent=None):
        super(PixelLabel, self).__init__(text, parent)
        f = self.font()
        f.setPointSize(size)
        f.setBold(bold)
        self.setFont(f)
        self.setStyleSheet("color:%s" % PALETTE_TEXT)

class StarButton(QtWidgets.QPushButton):
    def __init__(self, text="", parent=None):
        super(StarButton, self).__init__(text, parent)
        self.setFixedSize(96, 96)
        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.setText(text)
        self.setStyleSheet("""
            QPushButton {
                border: 0px;
                background-color: %s;
                border-radius: 20px;
                font-size: 22px;
            }
            QPushButton:hover { background-color: #FFD6F0; }
        """ % PALETTE_PINK)

# ---------- วิวตัวละคร (QGraphicsView) ----------
class GameView(QtWidgets.QGraphicsView):
    # พื้นที่ตัวละคร + แอนิเมชันเด้งๆ
    def __init__(self, pet_pix_path=None, parent=None):
        super(GameView, self).__init__(parent)

        # ปิดสกอร์บาร์ทั้งหมด
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        # scene
        scn = QtWidgets.QGraphicsScene(self)
        self.setScene(scn)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        self.setStyleSheet("background:#FFFFFF; border:0px;")
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        scn.setSceneRect(0, 0, 640, 420)

        if pet_pix_path:
            pix = QtGui.QPixmap(pet_pix_path)
            if pix.isNull():
                pix = self._make_placeholder()
        else:
            pix = self._make_placeholder()

        self.item = scn.addPixmap(pix)
        self.item.setOffset(210, 140) 

        self.anim = QtCore.QVariantAnimation(self)
        self.anim.setDuration(1200)
        self.anim.setStartValue(140.0)
        self.anim.setEndValue(150.0)
        self.anim.setEasingCurve(QtCore.QEasingCurve.InOutSine)
        self.anim.setLoopCount(-1)
        self.anim.valueChanged.connect(self._on_anim_value)
        self.anim.start()

    def _make_placeholder(self):
        pix = QtGui.QPixmap(220, 220)
        pix.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setBrush(QtGui.QColor("#FFC0D9"))
        p.setPen(QtGui.QPen(QtGui.QColor("#333"), 3))
        p.drawEllipse(10, 10, 200, 200)
        p.end()
        return pix

    def _on_anim_value(self, v):
        if getattr(self, "item", None) is None:
            if self.anim.state() == QtCore.QAbstractAnimation.Running:
                self.anim.stop()
            return
        if not isValid(self.item):
            if self.anim.state() == QtCore.QAbstractAnimation.Running:
                self.anim.stop()
            try:
                self.anim.valueChanged.disconnect(self._on_anim_value)
            except Exception:
                pass
            self.item = None
            return
        self.item.setY(float(v))

    def shutdown(self):
        try:
            if self.anim.state() == QtCore.QAbstractAnimation.Running:
                self.anim.stop()
            try:
                self.anim.valueChanged.disconnect(self._on_anim_value)
            except Exception:
                pass
        except Exception:
            pass
        try:
            if self.scene():
                self.scene().clear()
        except Exception:
            pass
        self.item = None

    def closeEvent(self, e):
        self.shutdown()
        super(GameView, self).closeEvent(e)

# ---------- ชิ้นส่วน UI อื่นๆ ----------
class TopBar(QtWidgets.QWidget):
    def __init__(self):
        super(TopBar, self).__init__()
        self.setStyleSheet("background:%s" % PALETTE_BG)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(12)

        self.btnSetting = QtWidgets.QPushButton("⚙  setting")
        self.btnSetting.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.btnSetting.setStyleSheet("""
            QPushButton { background: #FFE3F5; border: 2px solid #F2C3E2; border-radius: 12px; padding: 6px 12px; color:#6B5B53; }
            QPushButton:hover { background: #FFD6F0; }
        """)
        lay.addWidget(self.btnSetting, 0, QtCore.Qt.AlignLeft)
        lay.addStretch()

        coinWrap = QtWidgets.QFrame()
        coinWrap.setStyleSheet("QFrame { background:#FFF; border:2px solid #F2C3E2; border-radius:12px; }")
        h = QtWidgets.QHBoxLayout(coinWrap)
        h.setContentsMargins(10, 4, 10, 4)
        h.setSpacing(6)
        h.addWidget(PixelLabel("🪙", size=18))
        h.addWidget(PixelLabel("bb13100", size=16, bold=True))
        lay.addWidget(coinWrap, 0, QtCore.Qt.AlignRight)

class StatusBar(QtWidgets.QWidget):
    def __init__(self):
        super(StatusBar, self).__init__()
        self.setStyleSheet("background:%s; border:2px solid %s; border-radius:12px;" % (PALETTE_PINK, PALETTE_BORDER))
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)
        hearts = PixelLabel("❤❤❤❤❤")
        hearts.setStyleSheet("color:#E26693;")
        lay.addWidget(hearts)
        lay.addStretch()
        for emoji in ["🍽️", "🔥", "⚡"]:
            box = QtWidgets.QLabel(emoji)
            box.setAlignment(QtCore.Qt.AlignCenter)
            box.setFixedSize(42, 42)
            box.setStyleSheet("background:#FFFFFF; border:2px solid %s; border-radius:8px;" % PALETTE_BORDER)
            lay.addWidget(box)

class GamePanel(QtWidgets.QFrame):
    def __init__(self, pet_pix_path=None):
        super(GamePanel, self).__init__()
        self.setStyleSheet("QFrame { background:#FFFFFF; border:3px solid %s; border-radius:14px; }" % PALETTE_BORDER)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)

        top = QtWidgets.QHBoxLayout()
        title = PixelLabel("Chipmunk", size=18, bold=True)
        title.setStyleSheet("color:#7A6C8F")
        top.addWidget(title)
        top.addStretch()
        home = QtWidgets.QLabel("🏠")
        home.setFixedSize(36, 36)
        home.setAlignment(QtCore.Qt.AlignCenter)
        home.setStyleSheet("background:#FFF1FC; border:2px solid %s; border-radius:8px;" % PALETTE_BORDER)
        top.addWidget(home)
        v.addLayout(top)

        self.view = GameView(pet_pix_path)
        v.addWidget(self.view, 1)

class BottomBar(QtWidgets.QWidget):
    def __init__(self):
        super(BottomBar, self).__init__()
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(20)
        lay.addStretch()
        self.btnWash = StarButton("🫧")
        self.btnEat = StarButton("🍽️")
        self.btnWater = StarButton("💧")
        self.btnHeal = StarButton("✚")
        for b in (self.btnWash, self.btnEat, self.btnWater, self.btnHeal):
            lay.addWidget(b)
        lay.addStretch()

# ---------- หน้าเริ่มเกม ----------
class StartPage(QtWidgets.QWidget):
    startClicked = QtCore.Signal() 

    def __init__(self, parent=None):
        super(StartPage, self).__init__(parent)
        self.setStyleSheet("background:%s" % PALETTE_BG)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)

        title = PixelLabel("TAMATOTS", size=28, bold=True)
        title.setAlignment(QtCore.Qt.AlignCenter)
        v.addWidget(title)

        v.addStretch()

        startBtn = QtWidgets.QPushButton("Start")
        startBtn.setFixedHeight(70)
        startBtn.setFixedWidth(250)
        startBtn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        startBtn.setStyleSheet("""
            QPushButton { background:#FFFFFF; border:3px solid %s; border-radius:14px; font-size:20px; color:%s; }
            QPushButton:hover { background:#FFEFFC; }
        """ % (PALETTE_BORDER, PALETTE_TEXT))
        startBtn.clicked.connect(self.startClicked.emit)
        v.addWidget(startBtn, 0, QtCore.Qt.AlignCenter)

        v.addStretch()

# ---------- หน้าเกมหลัก ----------
class GamePage(QtWidgets.QWidget):
    def __init__(self, pet_pix_path=None, parent=None):
        super(GamePage, self).__init__(parent)
        self.setStyleSheet("background:%s" % PALETTE_BG)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        self.topbar = TopBar()
        outer.addWidget(self.topbar)

        panel = QtWidgets.QFrame()
        panel.setStyleSheet("QFrame { background:%s; border:3px solid %s; border-radius:14px; }" % (PALETTE_PURPLE, PALETTE_BORDER))
        pv = QtWidgets.QVBoxLayout(panel)
        pv.setContentsMargins(12, 12, 12, 12)
        pv.setSpacing(10)

        self.status = StatusBar()
        pv.addWidget(self.status)

        self.gamePanel = GamePanel(pet_pix_path)
        pv.addWidget(self.gamePanel, 1)

        outer.addWidget(panel, 1)

        self.bottom = BottomBar()
        outer.addWidget(self.bottom)

        self.bottom.btnEat.clicked.connect(lambda: self.flash_message("อร่อยยย!"))
        self.bottom.btnWash.clicked.connect(lambda: self.flash_message("สดชื่นนนน!"))
        self.bottom.btnWater.clicked.connect(lambda: self.flash_message("อึก อึก"))
        self.bottom.btnHeal.clicked.connect(lambda: self.flash_message("รู้สึกดีมากกก!"))

    def flash_message(self, text):
        m = QtWidgets.QLabel(text, self.gamePanel)
        m.setStyleSheet("background:#000000AA; color:black; padding:6px 10px; border-radius:8px;")
        m.adjustSize()
        m.move(200, 20)
        m.show()
        QtCore.QTimer.singleShot(800, m.deleteLater)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None, pet_pix_path=None):
        super(MainWindow, self).__init__(parent)
        self.setWindowTitle("Pet Game UI - Maya")
        self.resize(540, 820)
        self.setStyleSheet("QMainWindow { background:%s; }" % PALETTE_BG)

        self.stacked = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.stacked)

        self.startPage = StartPage()
        self.gamePage = GamePage(pet_pix_path=pet_pix_path)

        self.stacked.addWidget(self.startPage) 
        self.stacked.addWidget(self.gamePage)  

        self.startPage.startClicked.connect(lambda: self.stacked.setCurrentIndex(1))

    def closeEvent(self, e):
        try:
            self.gamePage.gamePanel.view.shutdown()
        except Exception:
            pass
        super(MainWindow, self).closeEvent(e)

def _maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)

_window = None

def run(pet_pix_path=None):
    """
    เรียกจาก Maya:
        import pet_game
        pet_game.run('C:/path/to/pet.png')
    ถ้าไม่ส่ง path มาก็มี placeholder ให้
    """
    global _window
    try:
        if _window:
            _window.close()
            _window.deleteLater()
    except Exception:
        pass

    parent = _maya_main_window()
    _window = MainWindow(parent=parent, pet_pix_path=pet_pix_path)
    _window.show()
    return _window
