"""右侧覆盖式设置抽屉（需求第 25 节）。

真实设置项：导出默认目录、主题（第一版仅浅色，深色/跟随系统预留）；
壁纸、强调色、整库迁移按项目惯例以禁用控件 + “后续开放”提示呈现。
抽屉的覆盖/滑入/关闭/外部点击/Esc/减少动画行为由公共基类
``SlideDrawer`` 提供。
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from hyacinth.ui.drawer_base import SlideDrawer, animations_enabled  # noqa: F401


class SettingsDrawer(SlideDrawer):
    """覆盖在主窗口右侧的设置抽屉，不挤压四个主面板。"""

    export_directory_selected = Signal(str)
    export_directory_reset_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, width=380, object_name="settings-drawer")

        header = QFrame(self)
        header.setObjectName("settings-drawer-header")
        header.setFixedHeight(44)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 10, 0)
        title = QLabel("设置", header)
        title.setObjectName("settings-drawer-title")
        close_button = QPushButton("✕", header)
        close_button.setObjectName("settings-close-button")
        close_button.setFixedSize(30, 26)
        close_button.setToolTip("关闭设置 (Esc)")
        close_button.clicked.connect(self.close_drawer)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(close_button)

        # ── 通用：导出默认目录 ────────────────────────────────────────
        general = QGroupBox("通用", self)
        general.setObjectName("settings-group")
        general_layout = QVBoxLayout(general)
        general_layout.setContentsMargins(10, 8, 10, 10)
        export_label = QLabel("导出默认目录", general)
        export_label.setToolTip("导出版本时不选“另存为”时的默认保存位置")
        self._export_input = QLineEdit(general)
        self._export_input.setObjectName("settings-export-input")
        self._export_input.setReadOnly(True)
        self._export_input.setPlaceholderText("默认：下载目录")
        browse_button = QPushButton("浏览…", general)
        browse_button.clicked.connect(self._browse_export_directory)
        reset_button = QPushButton("恢复默认", general)
        reset_button.setToolTip("恢复为系统下载目录")
        reset_button.clicked.connect(self.export_directory_reset_requested.emit)
        export_row = QHBoxLayout()
        export_row.addWidget(self._export_input, 1)
        export_row.addWidget(browse_button)
        export_row.addWidget(reset_button)
        general_layout.addWidget(export_label)
        general_layout.addLayout(export_row)

        # ── 外观：主题（第一版仅浅色）────────────────────────────────
        appearance = QGroupBox("外观", self)
        appearance.setObjectName("settings-group")
        appearance_layout = QVBoxLayout(appearance)
        appearance_layout.setContentsMargins(10, 8, 10, 10)
        light = QRadioButton("浅色（当前）", appearance)
        light.setChecked(True)
        light.setEnabled(False)
        light.setToolTip("浅色主题为第一版唯一主题")
        dark = QRadioButton("深色（后续开放）", appearance)
        dark.setEnabled(False)
        dark.setToolTip("深色主题将在后续版本开放")
        system = QRadioButton("跟随系统（后续开放）", appearance)
        system.setEnabled(False)
        system.setToolTip("跟随系统主题将在后续版本开放")
        for radio in (light, dark, system):
            appearance_layout.addWidget(radio)

        # ── 个性化：壁纸 / 强调色（预留）─────────────────────────────
        personal = QGroupBox("个性化", self)
        personal.setObjectName("settings-group")
        personal_layout = QVBoxLayout(personal)
        personal_layout.setContentsMargins(10, 8, 10, 10)
        wallpaper = QPushButton("桌面壁纸…", personal)
        wallpaper.setEnabled(False)
        wallpaper.setToolTip("桌面壁纸将在后续版本开放")
        accent = QPushButton("自定义强调色…", personal)
        accent.setEnabled(False)
        accent.setToolTip("自定义强调色将在后续版本开放")
        personal_layout.addWidget(wallpaper)
        personal_layout.addWidget(accent)

        # ── 存储：整库迁移（预留）────────────────────────────────────
        storage = QGroupBox("存储", self)
        storage.setObjectName("settings-group")
        storage_layout = QVBoxLayout(storage)
        storage_layout.setContentsMargins(10, 8, 10, 10)
        migrate = QPushButton("迁移存储目录…", storage)
        migrate.setEnabled(False)
        migrate.setToolTip("整库迁移将在后续版本开放")
        storage_layout.addWidget(migrate)

        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 8, 12, 12)
        content_layout.addWidget(general)
        content_layout.addWidget(appearance)
        content_layout.addWidget(personal)
        content_layout.addWidget(storage)
        content_layout.addStretch()
        scroll = QScrollArea(self)
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(scroll, 1)

    def set_export_directory(self, directory: str) -> None:
        self._export_input.setText(directory)

    def _browse_export_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择导出默认目录",
            self._export_input.text() or "",
        )
        if directory:
            self.export_directory_selected.emit(directory)
