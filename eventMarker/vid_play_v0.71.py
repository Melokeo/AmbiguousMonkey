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

import sys, os, re
import configparser as cfgp
from PyQt6.QtCore import Qt, QUrl, QTime, QTimer, QEvent, QRectF, QPointF
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
    QStyle
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

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
PAIRING_RULES = {1:2}
TIMELINE_OFFSET = [5, 15]
MAGIC = 3   # yes, magic.

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
        self.player = parent
        self.setMinimumHeight(20)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        # 获取进度条尺寸信息
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
            marker_map = {event_type: [] for event_type in range(1, 6)}
            for event_type in range(1, 6):
                color = MARKER_COLORS[event_type-1]
                for frame in self.player.event_markers[event_type]:
                    # 将帧转换为时间位置
                    time_pos = frame * (1000 / FPS_ORIG)
                    # 计算标记位置
                    x_pos = int(time_pos * duration_ratio)+TIMELINE_OFFSET[0]
                    self.marker_positions.append((x_pos, frame))
                    marker_map[event_type].append((frame, x_pos))
                    
                    marker_rect = QRectF(x_pos, 5+event_type*0.8, 3.5, 3.5)  
                    painter.setBrush(color)
                    painter.drawEllipse(marker_rect)

            if PAIRING:
                # Match and draw multiple pairings
                for start_type, end_type in PAIRING_RULES.items():
                    if start_type in marker_map and end_type in marker_map:
                        start_markers = sorted(marker_map[start_type])  # Sorted list of (frame, x_pos)
                        end_markers = sorted(marker_map[end_type])  # Sorted list of (frame, x_pos)

                        i, j = 0, 0
                        while i < len(start_markers) and j < len(end_markers):
                            start_frame, start_x = start_markers[i]
                            end_frame, end_x = end_markers[j]

                            if start_frame < end_frame:
                                paired_positions.append((start_x, end_x))
                                i += 1  # Move to the next start marker
                            j += 1  # Always move to the next end marker
                        
                painter.setPen(QColor(100, 100, 100))  # Gray lines for connection
                for x1, x2 in paired_positions:
                    painter.drawLine(x1, 13, x2, 13)
        except Exception as e:
            print(f"Error in marker painting: {e}")

    def mousePressEvent(self, event):
        """ Detects clicks on markers and jumps to the corresponding frame """
        if not hasattr(self, "marker_positions"):
            return
        try:
            click_x = event.position().x()  # Get clicked x-coordinate
            threshold = 5  # Click tolerance in pixels

            for x_pos, frame in self.marker_positions:
                if abs(click_x - x_pos) <= threshold:
                    # Jump to frame when marker is clicked
                    new_position = int(round(frame * (1000 / FPS_ORIG)))
                    self.player.media_player.setPosition(new_position)
                    break  # Exit loop after first match
        except Exception as e:
            print(f"Error in mark mouse event: {e}")

class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Event Marker (WTH ver.)")
        self.setGeometry(100, 100, 1420, 750)

        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.video_widget = QIVideoWidget()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        
        self.frame_timer = QTimer()
        self.frame_timer.timeout.connect(self.update_position)
        self.markers_widget = MarkersWidget(self)
        
        self.init_ui()
        self.connect_signals()
        self.is_slider_pressed = False
        
        # Event markers storage
        self.event_markers = {i: [] for i in range(1, 6)}
        self.undo_stack = []
        self.redo_stack = []

        self.cfg = cfgp.ConfigParser()
        try:
            self.cfg.read('vidPlayerConfig.ini')
            self.fname = self.cfg['Path'].get('last_path', r'C:\Users')
        except Exception as e:
            print(f'Warning: cannot read ini file when starting: {e}')
            self.fname = 'C:/Users'
        
        app.installEventFilter(self)

    
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        main_widget.setLayout(layout)

        layout.addWidget(self.video_widget)
        control_layout = QHBoxLayout()

        self.play_btn = QPushButton("▶")
        control_layout.addWidget(self.play_btn)

        # 创建垂直布局包含标记组件和进度条
        slider_container = QWidget()
        slider_layout = QVBoxLayout()
        slider_container.setLayout(slider_layout)
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setStyleSheet("QSlider::handle:horizontal { border-radius: 8px; width: 16px; height: 16px; }")
        
        slider_layout.addWidget(self.markers_widget)
        slider_layout.addWidget(self.time_slider)
        
        control_layout.addWidget(self.play_btn)
        control_layout.addWidget(slider_container)  

        self.time_label = QLabel("00:00:00 / 00:00:00")
        control_layout.addWidget(self.time_label)

        self.frame_label = QLabel("Frame: 0")
        self.frame_label.mouseDoubleClickEvent = self.enable_frame_edit
        control_layout.addWidget(self.frame_label)

        self.frame_input = QLineEdit()
        self.frame_input.setFixedWidth(100)
        self.frame_input.setVisible(False)
        self.frame_input.returnPressed.connect(self.jump_to_frame)
        self.frame_editing = False
        control_layout.addWidget(self.frame_input)

        self.speed_label = QLabel("1.0x")
        self.speed_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        control_layout.addWidget(self.speed_label, 0)

        layout.addLayout(control_layout)
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        open_action = QAction("Open new video", self)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        self.setFocus()

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

    def open_file(self):
        if hasattr(self, 'fname'):
            self.saveEventToFile()       # in case you open another file after marking one
            # Event markers storage
            self.event_markers = {i: [] for i in range(1, 6)}
            self.undo_stack = []
            self.redo_stack = []

        try:
            file_name, _ = QFileDialog.getOpenFileName(self, "Select video file", 
                os.path.dirname(self.fname), "Video (*.mp4 *.avi *.mkv *.mov)")
        except Exception as e:
            raise RuntimeError(f'Error in QFileDialog: {e}')
        if file_name:
            self.media_player.setSource(QUrl.fromLocalFile(file_name))
            self.fname = file_name
            self.play_btn.setEnabled(True)
            self.play_btn.setText("▶")

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
        elif event.key() in [Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4, Qt.Key.Key_5]:
            self.mark_event(event.key() - Qt.Key.Key_1 + 1)
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
        elif event.key() == Qt.Key.Key_Right:
            '''frame = self.media_player.position() / (1000 / FPS_ORIG)
            # print(frame, self.media_player.position())
            new_frame = frame + MAGIC + STEP
            new_pos = int(round(new_frame * (1000 / FPS_ORIG)))
            # print(new_frame, new_pos, self.media_player.position() - int(round(1000/FPS_ORIG)))
            self.media_player.setPosition(max(new_pos,1))
            # adding STEP directly leads to still frames occasionally '''
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
        elif event.key() == Qt.Key.Key_Up:
            frame = round(self.media_player.position() * FPS_ORIG / 1000)
            new_frame = max(frame - STEP * LARGE_STEP_MULTIPLIER, 0)
            new_pos = int(new_frame * (1000 / FPS_ORIG))
            self.media_player.setPosition(new_pos)
        elif event.key() == Qt.Key.Key_Down:
            frame = round(self.media_player.position() * FPS_ORIG / 1000)
            new_frame = frame + STEP * LARGE_STEP_MULTIPLIER
            new_pos = int(new_frame * (1000 / FPS_ORIG))
            self.media_player.setPosition(new_pos)
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
            frame = round((self.media_player.position()+MAGIC) / (1000 / FPS_ORIG))
            if frame not in self.event_markers[event_type]:
                self.event_markers[event_type].append(frame)
                self.undo_stack.append((event_type, frame))
                self.redo_stack.clear()
                self.markers_widget.update()  # 触发重绘
            print(f"Marked event {event_type} at frame {frame}")
        except Exception as e:
            print(f"Error in mark_event: {e}")
    
    def undo_event(self):
        if self.undo_stack:
            event_type, frame = self.undo_stack.pop()
            self.event_markers[event_type].remove(frame)
            self.redo_stack.append((event_type, frame))
            self.markers_widget.update()
            print(f"Undid event {event_type} at frame {frame}")
    
    def redo_event(self):
        if self.redo_stack:
            event_type, frame = self.redo_stack.pop()
            self.event_markers[event_type].append(frame)
            self.undo_stack.append((event_type, frame))
            self.markers_widget.update()
            print(f"Redid event {event_type} at frame {frame}")

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
            self.cfg['Path'] = {'last_path': p}
            with open('vidPlayerConfig.ini', 'w') as c:
                self.cfg.write(c) # save last browsed path
        super().closeEvent(event)
    
    def saveEventToFile(self):
        # skip it if nothing marked
        if any(self.event_markers.values()):
            assert hasattr(self, 'fname')
            try:
                if not os.path.exists('Marked Events'):
                    os.makedirs('Marked Events', exist_ok=True)
                m = re.search(r'2025\d{4}-(Pici|Fusillo)-(TS|BBT|Brinkman|Pull)-\d{1,2}', self.fname, re.IGNORECASE)
                if m:
                    fnm = m.group()
                else:
                    fnm = os.path.basename(self.fname)
                    fnm = fnm.split('.')[0]

                with open(f'Marked Events/event-{fnm}.txt', 'w', encoding='utf-8') as f:
                    f.write(str(self.event_markers))
                print(f'Successfully saved events to Marked Events/{fnm}.txt')
            except Exception as e:
                raise RuntimeError(f'Error when saving events, plz copy it yourself!!\n{e}')
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    sys.exit(app.exec())
