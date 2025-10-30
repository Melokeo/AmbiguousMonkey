'''
An event marker that allows you to preview frames much smoother than
previous MATLAB code.

Requirements: PyQt6

Playback controls:
    - ←→ steps STEP numbers of frame (default STEP = 1 frame)
    - ↑↓ steps LARGE_STEP_MULTIPLIER*STEP of frame
    - space for play/pause
    - numpad +- adjust playback speed by 1.1x/0.9x
    - numpad Enter reset speed to 1x
        **speed changes sometimes have latency**
    - timeline is draggable

Marking controls:
    - 1~5 (above qwerty) sets marker at current timepoint
    - markers will appear above timeline, left click will jump
    - CTRL+Z undo, CTRL+SHIFT+Z redo
    - Marked events will be printed when the window closes

Constants
    - MARKER_COLORS set color of markers above timeline
    - FPS sets playback fps
    - FPS_ORIG should be set to actual video fps
    - STEP determines step length when hitting arrow keys.
        x * 1000 // FPS_ORIG means each step is x frame(s)
    - PAIRING is boolean; T is to draw pairing line between markers
    - PAIRING_RULES is dict that determines what events are paired
    - TIMELINE_OFFSET is two magic (not really) numbers that refines
        marker alignment to timeline slider. First element shifts
        markers' start position to the right; second element reduces
        total drawing region's length
    - MAGIC compensates for QMediaPlayer's inaccuracy. Set to 0 and
        see there will be duplicate frames per 25 frames. Use 0.041
        because of magic.
    
Attention: QMediaPlayer lacks support of frame level control. The
displayed and recorded frame number are calculated by time/fps (1 ms
accuracy). But given that even under 120fps, each frame is 8.34 ms,
it should result in correct frame number even if not control by frames

If you have doubt on accuracy, just open Premier Pro and check it.

Contributed by: deepseek-r1, chatgpt-4o, Mel
Feb 2025
'''

import sys, os, re, ast 
import platform, subprocess
from PyQt6.QtCore import (
    Qt, QUrl, QTime, QTimer, QEvent, QRectF, QPointF,
    QSettings, QSize, QPoint
)
from PyQt6.QtGui import QAction, QKeyEvent, QPainter, QColor, QTransform
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSlider,
    QPushButton,
    QLabel,
    QLineEdit,
    QFileDialog,
    QSizePolicy,
    QMenu,
    QStyle,
    # QStatusBar,
    QComboBox,
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from collections import defaultdict
from datetime import datetime
from functools import partial
import numpy as np, csv

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

MARKER_COLORS = [
            QColor(172, 157, 147), 
            QColor(199, 184, 164),  
            QColor(147, 155, 144),  
            QColor(180, 166, 169), 
            QColor(158, 170, 177)   
]
FPS = 30
FPS_ORIG = 119.88
LARGE_STEP_MULTIPLIER = 6 
STEP = 1
PAIRING = True
PAIRING_RULES = {'1':'4'}
TIMELINE_OFFSET = [5, 15]
MAGIC = 3   # yes, magic.
WIN_TITLE = "Event Marker (N'amløpau ver.)"
DEFAULT_WRKPATH = r'P:\projects\monkeys\Chronic_VLL\DATA\Pici'
MARKER_KEY = [Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4, Qt.Key.Key_5]

class CSVPlotWindow(QWidget):
    def __init__(self, player):
        super().__init__(player, Qt.WindowType.Window | Qt.WindowType.Tool)
        self.player:VideoPlayer = player
        self.setWindowTitle("CSV Plot")
        self.setFixedSize(1500, 200)              # wide & short
        layout = QVBoxLayout(self)

        # top: load button + column selector
        hl = QHBoxLayout()
        self.load_btn = QPushButton("Load CSV")
        self.combo    = QComboBox()
        hl.addWidget(self.load_btn)
        hl.addWidget(self.combo)
        layout.addLayout(hl)

        # bottom: horizontal matplotlib canvas
        self.fig = Figure(figsize=(8,1.5))
        self.ax  = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        self.line, = self.ax.plot([], [], lw=1)
        self.ax2 = self.ax.twinx()
        self.diff_line, = self.ax2.plot([], [], lw=1, linestyle='--')
        self.cursor_line = self.ax.axvline(0, color='red')
        layout.addWidget(self.canvas)

        self.data = {}
        self.data_diff = {}
        self.win_size = 1200

        # signals
        self.load_btn.clicked.connect(self._load_csv)
        self.combo.currentTextChanged.connect(self._update_plot)
        player.media_player.positionChanged.connect(self._on_position)

        # allow clicks on the plot
        self.canvas.mpl_connect("button_press_event", self._on_click)

    def _load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV", "", "CSV Files (*.csv)")
        if not path: return
        with open(path) as f:
            reader = csv.reader(f)
            headers = next(reader)
            cols = list(zip(*reader))

        self.data.clear()
        self.combo.blockSignals(True)
        self.combo.clear()
        for h, col in zip(headers, cols):
            try:
                arr = np.array(col, float)
                self.data[h] = arr
                self.data_diff[h] = np.diff(arr, prepend=arr[0])
                # self.data_diff[h] = np.diff(self.data_diff[h], prepend=self.data_diff[h][0])
                self.combo.addItem(h)
            except ValueError:
                pass
        self.combo.blockSignals(False)
        if self.combo.count(): 
            self.combo.setCurrentIndex(0)
            self._update_plot()

    def _on_position(self, ms):
        frame = int(round(ms * FPS_ORIG / 1000))
        self._draw(frame)

    def _update_plot(self, name=None):
        self.cur_name = self.combo.currentText()
        arr = self.data[self.cur_name]
        diff = self.data_diff[self.cur_name]
        self.ax.set_ylim(arr.min(), arr.max())
        self.ax2.set_ylim(diff.min(), diff.max())
        frame = int(round(self.player.media_player.position() * FPS_ORIG / 1000))
        self._draw(frame)

    def _draw(self, frame):
        if not hasattr(self, 'cur_name'): return
        arr  = self.data[self.cur_name]
        diff = self.data_diff[self.cur_name]
        half = self.win_size // 2
        lo   = max(frame - half, 0)
        hi   = min(frame + half, len(arr))

        # update data
        x = np.arange(lo, hi)
        y = arr[lo:hi]
        self.line.set_data(x, y)
        self.cursor_line.set_xdata(frame)

        ydiff = diff[lo:hi]
        self.diff_line.set_data(x, ydiff)

        # slide x-window
        self.ax.set_xlim(lo, hi)
        # (y-limits already locked in _update_plot)

        # lightweight redraw
        self.canvas.draw_idle()

    def _on_click(self, ev):
        if ev.xdata is None: return
        tgt = int(round(ev.xdata))
        pos = int(round(tgt * 1000 / FPS_ORIG))
        self.player.media_player.setPosition(pos)

class QIVideoWidget(QVideoWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.zoom_factor = 1.0
        self.pan_offset = QPointF(0, 0)
        self._last_mouse_pos = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Force custom painting by disabling native window rendering
        self.setAttribute(Qt.WidgetAttribute.WA_PaintOnScreen, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, False)

    def wheelEvent(self, event):
        # Zoom in/out with mouse wheel
        factor = 1.1 if event.angleDelta().y() > 0 else 1/1.1
        self.zoom_factor *= factor
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_mouse_pos = event.position()

    def mouseMoveEvent(self, event):
        if self._last_mouse_pos:
            delta = event.position() - self._last_mouse_pos
            self.pan_offset += delta
            self._last_mouse_pos = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        self._last_mouse_pos = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        transform = QTransform()
        transform.translate(self.pan_offset.x(), self.pan_offset.y())
        transform.scale(self.zoom_factor, self.zoom_factor)
        painter.setTransform(transform)
        super().paintEvent(event)

class MarkersWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.player:VideoPlayer = parent
        self.setMinimumHeight(16)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        # 获取进度条尺寸
        slider = self.player.time_slider
        total_duration = self.player.media_player.duration()
        if total_duration <= 0:
            return

        # 计算比例因子
        slider_width = slider.width()
        duration_ratio = (
            slider_width-TIMELINE_OFFSET[1]) / total_duration if total_duration else 0

        self.marker_positions = []  # Store positions for click detection
        paired_positions = []
        
        # 绘制所有标记
        try:
            # Build map for whatever keys are in event_markers
            marker_map = {evt: [] for evt in self.player.event_markers}
            for evt, frames in self.player.event_markers.items():
                # Derive base index (1–5) from the first digit of evt
                idx = int(str(evt)[0])
                color = MARKER_COLORS[idx-1]
                for frame in frames:
                    # frame → time → x-pos
                    time_pos = frame * (1000 / FPS_ORIG)
                    x_pos = int(time_pos * duration_ratio) + TIMELINE_OFFSET[0]
                    self.marker_positions.append((x_pos, frame))
                    marker_map[evt].append((frame, x_pos))
                    painter.setBrush(color)
                    painter.drawEllipse(QRectF(x_pos, 5 + idx*0.8, 3.5, 3.5))

            # Draw any pairing lines if enabled
            if PAIRING:
                paired_positions = []
                for start_type, end_type in PAIRING_RULES.items():
                    starts = sorted(marker_map.get(start_type, []))
                    ends   = sorted(marker_map.get(end_type,   []))
                    i = j = 0
                    while i < len(starts) and j < len(ends):
                        sf, sx = starts[i]
                        ef, ex = ends[j]
                        if sf < ef:
                            paired_positions.append((sx, ex))
                            i += 1
                        j += 1
                painter.setPen(QColor(100, 100, 100))
                for x1, x2 in paired_positions:
                    painter.drawLine(x1, 13, x2, 13)
        except Exception as e:
            print(f"Error in marker painting: {e}")

    def mousePressEvent(self, event):
        """ Detects clicks on markers and jumps to the corresponding frame """
        if not hasattr(self, "marker_positions"):
            return
        try:
            click_x = event.position().x()  # clicked x-coord
            threshold = 5  # Click tolerance in pixels

            for x_pos, frame in self.marker_positions:
                if abs(click_x - x_pos) <= threshold:
                    # Jump to marker frame when clicked
                    new_position = int(round(frame * (1000 / FPS_ORIG)))
                    self.player.media_player.setPosition(new_position)
                    break  
        except Exception as e:
            print(f"Error in mark mouse event: {e}")

class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WIN_TITLE)
        self.setGeometry(100, 100, 1420, 750)

        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.video_widget = QIVideoWidget()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        
        self.frame_timer = QTimer()
        self.frame_timer.timeout.connect(self.update_position)
        self.markers_widget = MarkersWidget(self)
        self.markers_widget.setFixedHeight(16)
        
        self.init_ui()
        self.connect_signals()
        self.is_slider_pressed = False

        # status for 'delicate mode'
        self.delicate = False
        self.pending_num = None
        self.pending_frame = None
        
        # Event markers storage
        self.event_markers = {}
        self.undo_stack = []
        self.redo_stack = []

        self.save_status = True

        self.settings = QSettings('mel.rnel', 'EventMarker')
        self.resize(self.settings.value("window/size", QSize(1420, 750), type=QSize))
        self.move(self.settings.value("window/pos",  QPoint(100, 100), type=QPoint))

        self.fname = self.settings.value('Path/last_vid_path', None, type=str)
     
        self.csv_plot_win = CSVPlotWindow(self)
        self.csv_plot_win.move(self.x()+20, self.y()+self.height()-170)
        self.csv_plot_win.show()
        
        app.installEventFilter(self)

    
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(0)
        main_widget.setLayout(layout)

        layout.addWidget(self.video_widget)
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(5)

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(30, 30)
        # control_layout.addWidget(self.play_btn)

        # 创建垂直布局包含标记组件和进度条
        slider_container = QWidget()
        slider_layout = QVBoxLayout()
        slider_container.setLayout(slider_layout)
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        # self.time_slider.setStyleSheet("QSlider::handle:horizontal { border-radius: 8px; width: 16px; height: 16px; }")
        self.time_slider.setMinimumHeight(25)
        
        slider_layout.addWidget(self.markers_widget)
        slider_layout.addWidget(self.time_slider)

        # then build control layout
        control_layout.addWidget(self.play_btn)
        slider_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        control_layout.addWidget(slider_container, 1)  

        info_container = QWidget()
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        info_container.setLayout(info_layout)

        # info - top row: time, frame, input, speed
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.frame_label = QLabel("Frame: 0")
        self.frame_label.mouseDoubleClickEvent = self.enable_frame_edit

        self.frame_input = QLineEdit()
        self.frame_input.setFixedWidth(100)
        self.frame_input.setVisible(False)
        self.frame_input.returnPressed.connect(self.jump_to_frame)
        self.frame_editing = False

        self.speed_label = QLabel("1.0x")
        self.speed_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(5)
        top_row.addWidget(self.time_label)
        top_row.addWidget(self.frame_label)
        top_row.addWidget(self.frame_input)
        top_row.addWidget(self.speed_label)
        info_layout.addLayout(top_row)

        # bottom row: delicate + marker
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(5)
        self.delicate_label = QLabel("Combo Mark: OFF")
        bottom_row.addWidget(self.delicate_label)
        self.marker_label   = QLabel("Marker: –")
        bottom_row.addWidget(self.marker_label)
        info_layout.addLayout(bottom_row)

        h = self.time_label.sizeHint().height()
        for lbl in (self.delicate_label, self.marker_label):
            lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            lbl.setFixedHeight(h)

        info_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        control_layout.addWidget(info_container, 0)

        layout.addLayout(control_layout)
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        open_action = QAction("Open new video", self)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        open_events_action = QAction("Read saved events", self)
        open_events_action.triggered.connect(self.loadEvents)
        file_menu.addAction(open_events_action)

        save_as_action = QAction('&Save events as', self)
        save_as_action.triggered.connect(self.saveEventAs)
        file_menu.addAction(save_as_action)

        # uncomment the following if u want it to scan for videos
        '''
        workpath = self.cfg['Path'].get('workpath',
                                         os.path.join(DEFAULT_WRKPATH,
                                                      datetime.today().strftime('%Y'),
                                                      datetime.today().strftime('%m')))
        if os.path.exists(workpath):
            self.add_video_menu(workpath) 
        else:
            print('Warning: video path not exist. Menu is not updated')
        '''

        '''
        sb = QStatusBar(self)
        sb.setStyleSheet(
            "QStatusBar::item { margin-left:4px; margin-right:10px; }"
        )
        self.setStatusBar(sb)
        self._sb_delicate = QLabel("Delicate: OFF")
        sb.addWidget(self._sb_delicate)
        self._sb_marker   = QLabel("Marker: –")
        sb.addWidget(self._sb_marker)

        self.setFocus()
        '''
    def add_video_menu(self, base_path: str):
        """Build a menu of all .mp4 files in base_path, grouped by top-two folders."""
        video_menu = self.menuBar().addMenu("Videos")
        structure = defaultdict(lambda: defaultdict(list))

        # Collect .mp4 files in a nested dict {folder1: {folder2: [file_paths]}}
        for root, dirs, files in os.walk(base_path):
            for f in files:
                if f.lower().endswith('.mp4'):
                    full_path = os.path.join(root, f)
                    rel_parts = os.path.relpath(full_path, base_path).split(os.sep)
                    folder1 = rel_parts[0] if len(rel_parts) > 0 else "Unknown1"
                    folder2 = rel_parts[1] if len(rel_parts) > 1 else "Unknown2"
                    structure[folder1][folder2].append(full_path)

        # Build submenus:
        self.menuBar().setUpdatesEnabled(False)

        for folder1 in sorted(structure):
            sub_menu1 = QMenu(folder1, self)
            video_menu.addMenu(sub_menu1)
            for folder2 in sorted(structure[folder1]):
                sub_menu2 = QMenu(folder2, self)
                sub_menu1.addMenu(sub_menu2)
                for fpath in sorted(structure[folder1][folder2]):
                    action = sub_menu2.addAction(os.path.basename(fpath))
                    action.triggered.connect(partial(self.on_file_chosen, fpath))

        self.menuBar().setUpdatesEnabled(True)

    def on_file_chosen(self, file_path: str):
        """Handle clicking on a file from the Videos menu."""
        if hasattr(self, 'fname'):
            self.saveEventToFile()       # in case you open another file after marking one
            # Event markers storage
            self.event_markers = {}
            self.undo_stack = []
            self.redo_stack = []

        if file_path:
            self.media_player.setSource(QUrl.fromLocalFile(file_path))
            self.fname = file_path
            self.setWindowTitle(' - '.join([WIN_TITLE, os.path.basename(file_path)]))
            self.play_btn.setEnabled(True)
            self.play_btn.setText("▶")


    def eventFilter(self, obj, event):
        try:
            if event.type() == QEvent.Type.KeyPress and not self.frame_editing:
                self.keyPressEvent(event)
                return True
            return super().eventFilter(obj, event)
        except Exception as e:
            raise RuntimeError(f"Error in eventFilter: {e}")
            return super().eventFilter(obj, event)

    def enable_frame_edit(self, event):
        self.frame_label.setVisible(False)
        self.frame_input.setVisible(True)
        self.frame_editing = True
        self.frame_input.setText(self.frame_label.text().replace("Frame: ", ""))
        self.frame_input.setFocus()
        self.media_player.pause()
        self.play_btn.setText("▶")
        self.frame_timer.stop()

    def jump_to_frame(self):
        frame_number = self.frame_input.text()
        try:
            if frame_number == '':
                pass
                self.media_player.play()
                self.play_btn.setText("⏸")
                self.frame_timer.start(int(round(1000 / FPS)))
            else:
                frame_number = int(frame_number)
                position = int(round(frame_number * 1000 / FPS_ORIG))
                self.media_player.setPosition(position)
        except Exception as e:
            print(f'Error handling frame input: {e}')
        self.frame_input.setVisible(False)
        self.frame_label.setVisible(True)
        self.setFocus()
        self.frame_editing = False

    def update_frame_number(self):
        if FPS:
            frame = round((self.media_player.position()+MAGIC) / (1000 / FPS_ORIG))
            self.frame_label.setText(f"Frame: {frame}")

    def connect_signals(self):
        self.play_btn.clicked.connect(self.toggle_play)
        self.time_slider.sliderPressed.connect(self.slider_pressed)
        self.time_slider.sliderReleased.connect(self.slider_released)
        self.time_slider.sliderMoved.connect(self.set_position)
        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)
        self.media_player.positionChanged.connect(self._update_current_marker)

    def open_file(self):
        try:
            file_name, _ = QFileDialog.getOpenFileName(
                self, "Select video file", 
                self.settings.value('Path/last_vid_path', self.fname, type=str),
                "Video (*.mp4 *.avi *.mkv *.mov)"
                )
        except Exception as e:
            raise RuntimeError(f'Error in QFileDialog: {e}')
        
        if file_name:           
            if hasattr(self, 'fname'):
                self.saveEventToFile()       # in case you open another file after marking one     
            self.event_markers = {}
            self.undo_stack = []
            self.redo_stack = []

            self.settings.setValue('Path/last_vid_path', os.path.dirname(file_name))
            self.settings.sync()
            self.media_player.setSource(QUrl.fromLocalFile(file_name))
            self.fname = file_name
            self.setWindowTitle(' - '.join([WIN_TITLE, os.path.basename(file_name)]))
            self.play_btn.setEnabled(True)
            self.play_btn.setText("▶")
            
    def loadEvents(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select event file", 
            self.settings.value('Path/last_evt_path', self.fname, type=str), "Text file (*.txt)")
        if file_name:
            self.settings.setValue('Path/last_evt_path', os.path.dirname(file_name))
            self.settings.sync()
            # if os.path.basename(file_name).split('.')[-1] == 'txt':
            try:
                with open(file_name, 'r') as f:
                    self.event_markers = ast.literal_eval(f.read())
            except Exception as e:
                pass
            else:
                self.undo_stack.clear()
                self.redo_stack.clear()
                self.markers_widget.update()
                self.save_status = True    

    def toggle_play(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_btn.setText("▶")
            self.frame_timer.stop()
        else:
            self.media_player.play()
            self.play_btn.setText("⏸")
            self.frame_timer.start(int(round(1000 / FPS)))

    def update_position(self, position=None):
        if not self.is_slider_pressed:
            self.time_slider.setValue(self.media_player.position())
        
        current_time = QTime(0, 0, 0).addMSecs(self.media_player.position()).toString("HH:mm:ss")
        duration = QTime(0, 0, 0).addMSecs(self.media_player.duration()).toString("HH:mm:ss")
        self.time_label.setText(f"{current_time} / {duration}")
        self.update_frame_number()

    def update_duration(self, duration):
        self.time_slider.setRange(0, duration)

    def set_position(self, position):
        self.media_player.setPosition(int(round(position)))

    def slider_pressed(self):
        self.is_slider_pressed = True

    def slider_released(self):
        self.is_slider_pressed = False
        target_frame = round(self.time_slider.value() * FPS_ORIG / 1000)
        new_pos = int(target_frame * (1000 / FPS_ORIG))
        self.set_position(new_pos)

    def update_frame_number(self):
        if FPS:
            # print(f'{self.media_player.position()} // (1000 // {FPS})')
            frame = round(self.media_player.position() * FPS_ORIG / 1000)
            self.frame_label.setText(f"Frame: {frame}")
    
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Z and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.undo_event()
        elif event.key() == Qt.Key.Key_Z and event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            self.redo_event()
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            frame = round(self.media_player.position() * FPS_ORIG / 1000)
            # marker at this frame
            for mtype, frames in self.event_markers.items():
                if frame in frames:
                    self.undo_stack.append((mtype, frame))
                    self.redo_stack.clear()
                    frames.remove(frame)
                    self.markers_widget.update()
                    print(f"Deleted marker {mtype} @ frame {frame}")
        elif event.key() in MARKER_KEY:
            num = event.key() - Qt.Key.Key_1 + 1
            frame = round(self.media_player.position() * FPS_ORIG / 1000)
            if self.delicate:
                self.pending_num = num
                self.pending_frame = frame
                print(f'Pending num {num} at frame {frame}')
            else:
                self.mark_event(num)
        elif (self.delicate
            and self.pending_num 
            and (event.text().isalpha())):  #  or event.text().isnumeric()
                letter = event.text().lower()
                markerId = f"{self.pending_num}{letter}"
                self.mark_event(markerId)
                self.pending_num = None
                self.pending_frame = None

        # Ctrl+←: jump to the previous marker
        elif event.key() == Qt.Key.Key_Left and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # collect & sort all marker frames
            all_frames = sorted(f for frames in self.event_markers.values() for f in frames)
            if not all_frames:
                return
            # current playhead frame
            cur = round(self.media_player.position() * FPS_ORIG / 1000)
            # find the last frame < cur
            prevs = [f for f in all_frames if f < cur]
            if prevs:
                target = max(prevs)
                self.media_player.setPosition(int(target * (1000 / FPS_ORIG)))
                self.update_position()

        # Ctrl+→: jump to the next marker
        elif event.key() == Qt.Key.Key_Right and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            all_frames = sorted(f for frames in self.event_markers.values() for f in frames)
            if not all_frames:
                return
            cur = round(self.media_player.position() * FPS_ORIG / 1000)
            nexts = [f for f in all_frames if f > cur]
            if nexts:
                target = min(nexts)
                self.media_player.setPosition(int(target * (1000 / FPS_ORIG)))
                self.update_position()    

        elif event.key() == Qt.Key.Key_Left:
            '''# self.media_player.setPosition(self.media_player.position() - int(round(STEP)))
            frame = self.media_player.position() / (1000 / FPS_ORIG)
            print(frame, self.media_player.position())
            new_frame = frame + MAGIC - STEP
            new_pos = int(round(new_frame * (1000 / FPS_ORIG)))
            print(new_frame, new_pos, self.media_player.position() - int(round(1000/FPS_ORIG)))
            self.media_player.setPosition(max(new_pos,1))'''
            try:
                frame = round(self.media_player.position() * FPS_ORIG / 1000)
                #print(f'\n{self.media_player.position() * FPS_ORIG / 1000}')
                new_frame = max(frame - STEP, 0)
                new_pos = int(new_frame * (1000 / FPS_ORIG))
                self.media_player.setPosition(new_pos-MAGIC)
                #print(frame, self.media_player.position())
                #print(new_frame, new_pos, self.media_player.position() - int(round(1000/FPS_ORIG)))
                #print(self.media_player.position())
            except Exception as e:
                print(e)
                
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                for mtype, frames in self.event_markers.items():
                    if frame in frames:
                        i = frames.index(frame)
                        delta = -STEP
                        candidate = frame + delta
                        # prevent crossing its neighbors
                        s = sorted(frames)
                        pos = s.index(frame)
                        lower = (s[pos-1] + 1) if pos > 0 else 0
                        upper = (s[pos+1] - 1) if pos < len(s)-1 else candidate
                        new_frame = max(lower, min(candidate, upper))
                        # update the list and repaint
                        frames[i] = new_frame

                        for uidx, (etype, uframe) in enumerate(self.undo_stack):
                            if etype == mtype and uframe == frame:
                                self.undo_stack[uidx] = (etype, new_frame)

                        self.markers_widget.update()
                        break

        elif event.key() == Qt.Key.Key_Right:
            try:
                frame = round(self.media_player.position() * FPS_ORIG / 1000)
                #print(f'\n{self.media_player.position() * FPS_ORIG / 1000}')
                new_frame = frame + STEP
                new_pos = int(new_frame * (1000 / FPS_ORIG))
                self.media_player.setPosition(new_pos-MAGIC)
                #print(frame, self.media_player.position())
                #print(new_frame, new_pos, self.media_player.position() - int(round(1000/FPS_ORIG)))
                #print(self.media_player.position())
            except Exception as e:
                print(e)

            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                for mtype, frames in self.event_markers.items():
                    if frame in frames:
                        i = frames.index(frame)
                        delta = STEP
                        candidate = frame + delta
                        # prevent crossing its neighbors
                        s = sorted(frames)
                        pos = s.index(frame)
                        lower = (s[pos-1] + 1) if pos > 0 else 0
                        upper = (s[pos+1] - 1) if pos < len(s)-1 else candidate
                        new_frame = max(lower, min(candidate, upper))
                        # update the list and repaint
                        frames[i] = new_frame

                        for uidx, (etype, uframe) in enumerate(self.undo_stack):
                            if etype == mtype and uframe == frame:
                                self.undo_stack[uidx] = (etype, new_frame)

                        self.markers_widget.update()
                        break
        elif event.key() == Qt.Key.Key_Up:
            frame = round(self.media_player.position() * FPS_ORIG / 1000)
            new_frame = max(frame - STEP * LARGE_STEP_MULTIPLIER, 0)
            new_pos = int(new_frame * (1000 / FPS_ORIG))
            self.media_player.setPosition(new_pos)

            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                for mtype, frames in self.event_markers.items():
                    if frame in frames:
                        i = frames.index(frame)
                        delta = - STEP * LARGE_STEP_MULTIPLIER
                        candidate = frame + delta
                        # prevent crossing its neighbors
                        s = sorted(frames)
                        pos = s.index(frame)
                        lower = (s[pos-1] + 1) if pos > 0 else 0
                        upper = (s[pos+1] - 1) if pos < len(s)-1 else candidate
                        new_frame = max(lower, min(candidate, upper))
                        # update the list and repaint
                        frames[i] = new_frame

                        for uidx, (etype, uframe) in enumerate(self.undo_stack):
                            if etype == mtype and uframe == frame:
                                self.undo_stack[uidx] = (etype, new_frame)

                        self.markers_widget.update()
                        break
        elif event.key() == Qt.Key.Key_Down:
            frame = round(self.media_player.position() * FPS_ORIG / 1000)
            new_frame = frame + STEP * LARGE_STEP_MULTIPLIER
            new_pos = int(new_frame * (1000 / FPS_ORIG))
            self.media_player.setPosition(new_pos)
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                for mtype, frames in self.event_markers.items():
                    if frame in frames:
                        i = frames.index(frame)
                        delta = STEP * LARGE_STEP_MULTIPLIER
                        candidate = frame + delta
                        # prevent crossing its neighbors
                        s = sorted(frames)
                        pos = s.index(frame)
                        lower = (s[pos-1] + 1) if pos > 0 else 0
                        upper = (s[pos+1] - 1) if pos < len(s)-1 else candidate
                        new_frame = max(lower, min(candidate, upper))
                        # update the list and repaint
                        frames[i] = new_frame

                        for uidx, (etype, uframe) in enumerate(self.undo_stack):
                            if etype == mtype and uframe == frame:
                                self.undo_stack[uidx] = (etype, new_frame)

                        self.markers_widget.update()
                        break
        elif event.key() in [Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4, Qt.Key.Key_5]:
            self.mark_event(event.key() - Qt.Key.Key_1 + 1)
        elif event.key() == Qt.Key.Key_Space:
            self.toggle_play()
        elif event.key() == Qt.Key.Key_Minus:
            self.change_playback_rate(0.9)
        elif event.key() == Qt.Key.Key_Plus:
            self.change_playback_rate(1.1)
        elif event.key() == Qt.Key.Key_Enter:
            self.change_playback_rate(-1)
        elif event.key() == Qt.Key.Key_S \
            and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self.saveEventToFile()
        elif event.key() == Qt.Key.Key_D \
            and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self.delicate = not self.delicate
                print(f"Combo marking mode {'ON' if self.delicate else 'OFF'}")
                self.pending_num = None
                self.pending_frame = None
                self._update_delicate_label()
        else:
            super().keyPressEvent(event)

    def change_playback_rate(self, factor):
        current_rate = self.media_player.playbackRate()
        if factor == -1:
            new_rate = 1
        else: 
            new_rate = round(current_rate * factor, 1)
        self.media_player.setPlaybackRate(new_rate)
        #self.speed_combo.setCurrentText(f"{new_rate}x")
        self.speed_label.setText(f"{new_rate}x")
    
    def mark_event(self, event_type):
        try:
            if self.pending_frame is None:
                frame = round((self.media_player.position()+MAGIC) / (1000 / FPS_ORIG))
            else:
                frame = self.pending_frame
            key = str(event_type)
            if not key in self.event_markers:
                self.event_markers[key] = []
            if frame not in self.event_markers[key]:
                self.event_markers[key].append(frame)
                self.undo_stack.append((key, frame))
                self.redo_stack.clear()
                self.markers_widget.update() # refresh mkrs
                self.save_status = False
            print(f"Marked event {key} at frame {frame}")
        except Exception as e:
            print(f"Error in mark_event: {e}")
    
    def undo_event(self):
        if self.undo_stack:
            event_type, frame = self.undo_stack.pop()
            if frame in self.event_markers[event_type]:
                # undo was an “add” -> remove it
                self.event_markers[event_type].remove(frame)
                print(f"Undid add {event_type} @ {frame}")
            else:
                # undo was a “del” -> re-add it
                self.event_markers[event_type].append(frame)
                print(f"Undid del {event_type} @ {frame}")
            self.redo_stack.append((event_type, frame))
            self.markers_widget.update()
    
    def redo_event(self):
        if self.redo_stack:
            event_type, frame = self.redo_stack.pop()
            if frame in self.event_markers[event_type]:
                # redo was a del -> remove
                self.event_markers[event_type].remove(frame)
                print(f"Redid del {event_type} @ {frame}")
            else:
                # redo was an add -> re-add
                self.event_markers[event_type].append(frame)
                print(f"Redid add {event_type} @ {frame}")
            self.undo_stack.append((event_type, frame))
            self.markers_widget.update()


    def resizeEvent(self, event):
        self.markers_widget.update()
        super().resizeEvent(event)
    
    def closeEvent(self, event):
        self.media_player.stop()
        print("Recorded Events:", self.event_markers)
        print(self.redo_stack)
        self.saveEventToFile()
        if hasattr(self, 'fname'):
            p = os.path.dirname(self.fname) if '.' in os.path.basename(self.fname) else self.fname
            self.settings.setValue('Path/last_vid_path', p)

        self.settings.setValue("window/size", self.size())
        self.settings.setValue("window/pos", self.pos())
        self.settings.sync()

        super().closeEvent(event)
    
    def saveEventToFile(self):
        # return
        # skip it if nothing marked
        if any(self.event_markers.values()) and len(self.redo_stack)+len(self.undo_stack)>0 \
            and not self.save_status:
            assert hasattr(self, 'fname')
            try:
                # if not os.path.exists('Marked Events'):
                    # os.makedirs('Marked Events', exist_ok=True)
                m = re.search(r'2025\d{4}-(Pici|Fusillo)-(TS|BBT|Brinkman|Pull).*?-\d{1,2}', self.fname, re.IGNORECASE)
                if m:
                    fnm = m.group()
                else:
                    fnm = os.path.basename(self.fname)
                    fnm = fnm.split('.')[0]
                
                base_path = self.settings.value(
                    'Path/save_path', 
                    os.path.join(
                        os.path.dirname(os.path.abspath(__file__)), 
                        'Marked Events'
                        ), 
                    type=str,
                    )
                file_path = os.path.join(base_path, f'event-{fnm}.txt')
                # print(base_path, file_path)

                if not os.path.exists(base_path):
                    os.makedirs(base_path)
                    print('Target path does not exist, created new')

                suffix = ''
                while os.path.exists(os.path.join(base_path, f'event-{fnm}{suffix}.txt')):
                    suffix += ' (new)'
                file_path = os.path.join(
                    base_path,
                    f'event-{fnm}{suffix}.txt'
                    )
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(str(self.event_markers))

                print(f'Successfully saved events to {file_path}')

                system = platform.system()
                if system == 'Windows':
                    os.startfile(file_path)
                elif system == 'Darwin':  # macOS
                    subprocess.call(['open', file_path])
                else:                     # Linux, etc.
                    subprocess.call(['xdg-open', file_path])
            except Exception as e:
                print(self.event_markers)
                raise RuntimeError(f'Error when saving events; plz copy it yourself!!\n{e}')

            self.save_status = True

        else:
            print('Nothing to save.')
            
    def saveEventAs(self):
        if any(self.event_markers.values()):
            assert hasattr(self, 'fname')
            try:
                base_path = self.settings.value(
                    'Path/save_path', 
                    os.path.join(
                        os.path.dirname(self.fname), 
                        'Marked Events'
                        ), 
                    type=str,
                    )
                path, _ = QFileDialog.getSaveFileName(
                    self, "Save events as", base_path, "Text Files (*.txt);;All Files (*)"
                )
                if path:
                    self.settings.setValue('Path/save_path', os.path.dirname(path))
                    self.settings.sync()
                    m = re.search(r'2025\d{4}-(Pici|Fusillo)-(TS|BBT|Brinkman|Pull).*?-\d{1,2}', self.fname, re.IGNORECASE)
                    if m:
                        fnm = m.group()
                    else:
                        fnm = os.path.basename(self.fname)
                        fnm = fnm.split('.')[0]
                    file_path = os.path.join(base_path, f'event-{fnm}.txt')
                    '''
                    suffix = ''
                    while os.path.exists(os.path.join(base_path, f'event-{fnm}{suffix}.txt')):
                        suffix += ' (new)'
                    file_path = os.path.join(
                        base_path,
                        f'event-{fnm}{suffix}.txt'
                        )
                    '''
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(str(self.event_markers))
                    print(f'Successfully saved events to {file_path}')

            except Exception as e:
                print(self.event_markers)
                raise RuntimeError(f'Error when saving events as new file; plz copy it yourself!!\n{e}')
            
        else:
            print('Nothing to save.')

    def _update_delicate_label(self):
        txt = f"Combo mark: {'ON' if self.delicate else 'OFF'}"
        if self.delicate_label.text() != txt:
            self.delicate_label.setText(txt)

    def _update_current_marker(self):
        # cheap: only repaint text when name actually changes
        frame = round(self.media_player.position() * FPS_ORIG / 1000)
        name = None
        for key, frames in self.event_markers.items():
            if frame in frames:
                name = key
                break
        txt = f"Marker: {name}" if name else "Marker: –"
        if self.marker_label.text() != txt:
            self.marker_label.setText(txt)

                
if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    sys.exit(app.exec())
