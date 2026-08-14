"""系统托盘后台 + 右键菜单。"""
import logging

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt

from config.settings import get, set, get_run_mode, set_run_mode
from config.app_const import RunMode

logger = logging.getLogger(__name__)


def _create_icon() -> QIcon:
    """生成一个简单的蓝色方形托盘图标（无外部资源依赖）。"""
    pix = QPixmap(32, 32)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#4a90d9"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, 28, 28, 6, 6)
    painter.setPen(QColor("white"))
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "A")
    painter.end()
    return QIcon(pix)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setIcon(_create_icon())
        self.setToolTip("桌面智能助手")
        self._build_menu()
        self.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()
        menu.setStyleSheet("QMenu { font-size: 13px; }")

        open_action = QAction("打开主界面", menu)
        open_action.triggered.connect(self._show_main)
        menu.addAction(open_action)

        menu.addSeparator()

        new_todo = QAction("快速新建待办", menu)
        new_todo.triggered.connect(self._quick_todo)
        menu.addAction(new_todo)

        menu.addSeparator()

        # 模式切换
        mode_menu = menu.addMenu("运行模式")
        self.mode_online = QAction("联网模式", mode_menu, checkable=True)
        self.mode_online.setChecked(get_run_mode() == RunMode.ONLINE)
        self.mode_online.triggered.connect(lambda: self._switch_mode(RunMode.ONLINE))
        self.mode_offline = QAction("离线模式", mode_menu, checkable=True)
        self.mode_offline.setChecked(get_run_mode() == RunMode.OFFLINE)
        self.mode_offline.triggered.connect(lambda: self._switch_mode(RunMode.OFFLINE))
        mode_menu.addAction(self.mode_online)
        mode_menu.addAction(self.mode_offline)

        # 开机自启
        menu.addSeparator()
        self.auto_start_action = QAction("开机自启", menu, checkable=True)
        self.auto_start_action.setChecked(bool(get("auto_start", False)))
        self.auto_start_action.triggered.connect(self._toggle_auto_start)
        menu.addAction(self.auto_start_action)

        menu.addSeparator()

        quit_action = QAction("退出程序", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_main()

    def _show_main(self):
        self.main_window.showNormal()
        self.main_window.activateWindow()

    def _quick_todo(self):
        self._show_main()
        self.trayIcon.showMessage("快速待办", "待办已新建（骨架）", QSystemTrayIcon.MessageIcon.Information, 2000)

    def _switch_mode(self, mode: RunMode):
        set_run_mode(mode)
        self.mode_online.setChecked(mode == RunMode.ONLINE)
        self.mode_offline.setChecked(mode == RunMode.OFFLINE)
        self.showMessage("模式切换", f"已切换到{mode.value}模式", QSystemTrayIcon.MessageIcon.Information, 2000)

    def _toggle_auto_start(self):
        new_val = not bool(get("auto_start", False))
        set("auto_start", new_val)
        self.auto_start_action.setChecked(new_val)

    def _quit(self):
        logger.info("用户退出程序")
        QApplication.quit()
