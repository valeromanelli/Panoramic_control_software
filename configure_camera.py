import os
import numpy as np
import pyqtgraph
from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QTransform
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QGridLayout, \
    QGroupBox, QSizePolicy, QLabel, QFormLayout, QMessageBox, QToolButton, QSpacerItem, QLineEdit, QGraphicsRectItem, \
    QGraphicsLineItem, QSpinBox, QFileDialog, QGraphicsTextItem
from pyqtgraph import ImageView
import support_functions as sf
import support_classes as sc
from threads import AcquireThread, CheckExposureTimeValueThread, LiveThread
import style_sheet as ss
from datetime import datetime
import tifffile as tiff


class ConfigureCamera(QMainWindow):
    stop_live_thread = pyqtSignal()
    new_info_signal = pyqtSignal(str, object, str)
    update_stop_number_signal = pyqtSignal(int)
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("ORCA-Flash4.0 V3 Device Manager")
        #self.setGeometry(2000, -1000, 1600, 980)
        self.setGeometry(100, 100, 1600, 980)

        # VARIABLES
        self.parent = parent
        self.cam1 = self.parent.cam1
        self.cam2 = self.parent.cam2
        self.cam3 = self.parent.cam3
        self.cam4 = self.parent.cam4

        self.live = False
        self.n_frames = 0
        self.opt_roi_value = 192
        self.start_done = False

        self.acquire_thread = AcquireThread(parent=self)
        self.check_exp_value_thread = CheckExposureTimeValueThread(parent=self)
        self.live_thread = LiveThread(parent=self)

        # Widget layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)

        # Image Display
        v_layout = QVBoxLayout()

        image_view_group = QGroupBox("Image Display")
        image_view_layout = QGridLayout()

        self.image_view1 = ImageView()
        self.image_view2 = ImageView()
        self.image_view3 = ImageView()
        self.image_view4 = ImageView()

        camera_labels = ["CAM 1", "CAM 2", "CAM 3", "CAM 4"]
        center_x, center_y = 256, 256
        cross_size = 15
        tick_size = 10
        for i, image_view in enumerate([self.image_view1, self.image_view2, self.image_view3, self.image_view4]):
            image_view.ui.roiBtn.hide()
            image_view.ui.menuBtn.hide()

            border = QGraphicsRectItem(0, 0, 512, 512)
            border.setPen(pyqtgraph.mkPen('y', width=0.75))
            vertical_line = QGraphicsLineItem(
                center_x, center_y - cross_size, center_x, center_y + cross_size
            )
            vertical_line.setPen(pyqtgraph.mkPen(color='y', width=0.75))
            horizontal_line = QGraphicsLineItem(
                center_x - cross_size, center_y, center_x + cross_size, center_y
            )
            horizontal_line.setPen(pyqtgraph.mkPen(color='y', width=0.75))

            top_tick = QGraphicsLineItem(center_x, 0, center_x, tick_size)
            bottom_tick = QGraphicsLineItem(center_x, 512 - tick_size, center_x, 512)
            left_tick = QGraphicsLineItem(0, center_y, tick_size, center_y)
            right_tick = QGraphicsLineItem(512 - tick_size, center_y, 512, center_y)

            for tick in [top_tick, bottom_tick, left_tick, right_tick]:
                tick.setPen(pyqtgraph.mkPen(color='y', width=0.75))

            label = QGraphicsTextItem(camera_labels[i])
            label.setDefaultTextColor(pyqtgraph.mkColor('y'))
            font = QFont()
            font.setPointSize(20)
            label.setFont(font)
            transform = QTransform()
            transform.rotate(-90)
            label.setTransform(transform)
            label.setPos(-70, 295)

            view = image_view.getView()
            for item in [border, vertical_line, horizontal_line, top_tick, bottom_tick, left_tick, right_tick, label]:
                view.addItem(item)

        image_view_layout.addWidget(self.image_view1, 0, 0)
        image_view_layout.addWidget(self.image_view2, 0, 1)
        image_view_layout.addWidget(self.image_view3, 1, 0)
        image_view_layout.addWidget(self.image_view4, 1, 1)

        image_view_group.setLayout(image_view_layout)
        image_view_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        v_layout.addWidget(image_view_group)

        #SETTINGS
        settings_group = QGroupBox("Settings")
        settings_group.setFixedWidth(240)
        settings_layout = QVBoxLayout()

        # Experimental Setup
        experimental_setup_group = QGroupBox("Experimental Setup")
        ss.update_groupbox_style(experimental_setup_group, 'subgroup')
        experimental_setup_layout = QVBoxLayout()

        switch_roi_layout = QHBoxLayout()
        switch_roi_label = QLabel("ROI 192x192")
        self.switch_subarray_mode = sc.QToggleSwitch()
        self.switch_roi_label = QLabel("OFF")
        roi_selection_layout = QFormLayout()
        self.roi_value = QSpinBox()
        self.roi_value.setRange(4, 2048)
        self.roi_value.setValue(192)
        self.roi_value.setSingleStep(4)
        self.set_roi_button = QPushButton("Set ROI")
        roi_selection_layout.addRow("ROI Value (Optional):", self.roi_value)
        switch_roi_layout.addWidget(self.switch_subarray_mode)
        switch_roi_layout.addWidget(self.switch_roi_label)

        switch_trigger_layout = QHBoxLayout()
        switch_trigger_label = QLabel("Acquisition Mode")
        self.switch_trigger_mode = sc.QToggleSwitch()
        self.switch_trigger_label = QLabel("OFF")
        switch_trigger_layout.addWidget(self.switch_trigger_mode)
        switch_trigger_layout.addWidget(self.switch_trigger_label)

        experimental_setup_layout.addWidget(switch_roi_label)
        experimental_setup_layout.addLayout(switch_roi_layout)
        experimental_setup_layout.addLayout(roi_selection_layout)
        experimental_setup_layout.addWidget(self.set_roi_button, alignment=Qt.AlignmentFlag.AlignCenter)
        experimental_setup_layout.addWidget(switch_trigger_label)
        experimental_setup_layout.addLayout(switch_trigger_layout)
        experimental_setup_group.setLayout(experimental_setup_layout)

        # Commands Display
        validation_group = QGroupBox("Commands Display")
        ss.update_groupbox_style(validation_group, 'subgroup')
        validation_layout = QVBoxLayout()

        cams_layout = QGridLayout()
        icon = QIcon("Icons/camera.png")

        self.cam1_icon = QToolButton()
        self.cam1_icon.setText("CAM 1")
        self.cam1_icon.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.cam1_icon.setIcon(icon)
        self.cam1_icon.setIconSize(QSize(40, 40))
        cams_layout.addWidget(self.cam1_icon, 0, 0)

        self.cam2_icon = QToolButton()
        self.cam2_icon.setText("CAM 2")
        self.cam2_icon.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.cam2_icon.setIcon(icon)
        self.cam2_icon.setIconSize(QSize(40, 40))
        cams_layout.addWidget(self.cam2_icon, 0, 1)

        self.cam3_icon = QToolButton()
        self.cam3_icon.setText("CAM 3")
        self.cam3_icon.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.cam3_icon.setIcon(icon)
        self.cam3_icon.setIconSize(QSize(40, 40))
        cams_layout.addWidget(self.cam3_icon, 1, 0)

        self.cam4_icon = QToolButton()
        self.cam4_icon.setText("CAM 4")
        self.cam4_icon.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.cam4_icon.setIcon(icon)
        self.cam4_icon.setIconSize(QSize(40, 40))
        cams_layout.addWidget(self.cam4_icon, 1, 1)

        green_icon = QIcon("Icons/led_green.png")
        red_icon = QIcon("Icons/led_red.png")
        spacer = QSpacerItem(50, 20, QSizePolicy.Policy.Minimum)
        red_button = QPushButton()
        red_button.setIcon(red_icon)
        green_button = QPushButton()
        green_button.setIcon(green_icon)

        info_status_layout = QGridLayout()
        green_label = QLabel("Camera is Acquiring")
        red_label = QLabel("Camera is Stopped")
        info_status_layout.addWidget(green_button, 0, 0)
        info_status_layout.addWidget(green_label, 0, 1)
        info_status_layout.addItem(spacer, 0, 2)
        info_status_layout.addWidget(red_button, 1, 0)
        info_status_layout.addWidget(red_label, 1, 1)
        info_status_layout.addItem(spacer, 1, 2)

        validation_layout.addLayout(cams_layout)
        validation_layout.addLayout(info_status_layout)
        validation_group.setLayout(validation_layout)

        # Start/Stop Recording
        start_rec_icon = QIcon("Icons/start_record.png")
        self.start_record_button = QPushButton("Start Recording")
        self.start_record_button.setIcon(start_rec_icon)
        self.start_record_button.setFixedHeight(50)
        self.start_record_button.setFont(QFont("Arial", 14))
        self.start_record_button.setIconSize(QSize(30, 30))
        self.start_record_button.setEnabled(False)

        # Acquisition Infos
        acquisition_infos_group = QGroupBox("Acquisition Infos")
        ss.update_groupbox_style(acquisition_infos_group, 'subgroup')

        acquisition_infos_layout = QFormLayout()

        self.exposure_time_value = QLineEdit()
        self.frame_rate_label = QLabel("N/A")
        self.frames_acquired_label = QLabel("0")

        acquisition_infos_layout.addRow("Exposure Time (s):", self.exposure_time_value)
        acquisition_infos_layout.addRow("Frame Rate (Hz):", self.frame_rate_label)
        acquisition_infos_layout.addRow("Frames Acquired:", self.frames_acquired_label)

        self.exposure_time_value.setText(str(round(self.cam1.getExposure(), 8)))
        self.frame_rate_label.setText(str(round(self.cam1.getFrameRate(), 8)))

        acquisition_infos_group.setLayout(acquisition_infos_layout)

        # ZOOM TO FIT
        zoom_icon = QIcon("Icons/zoom_to_fit.png")
        self.zoom_to_fit_button = QPushButton("Zoom to Fit")
        self.zoom_to_fit_button.setFixedHeight(50)
        self.zoom_to_fit_button.setFont(QFont("Arial", 14))
        self.zoom_to_fit_button.setIcon(zoom_icon)
        self.zoom_to_fit_button.setIconSize(QSize(25, 25))

        # ADJUST
        adjust_icon = QIcon("Icons/adjust.png")
        self.adjust_button = QPushButton("Adjust")
        self.adjust_button.setFixedHeight(50)
        self.adjust_button.setFont(QFont("Arial", 14))
        self.adjust_button.setIcon(adjust_icon)
        self.adjust_button.setIconSize(QSize(40, 40))

        # TAKE A SNAP
        snap_icon = QIcon("Icons/snapshot.png")
        self.snap = QPushButton("Snap")
        self.snap.setFixedHeight(50)
        self.snap.setFont(QFont("Arial", 14))
        self.snap.setIcon(snap_icon)
        self.snap.setIconSize(QSize(30, 30))

        settings_layout.addWidget(experimental_setup_group)
        settings_layout.addWidget(validation_group)
        settings_layout.addWidget(acquisition_infos_group)
        settings_layout.addWidget(self.zoom_to_fit_button)
        settings_layout.addWidget(self.adjust_button)
        settings_layout.addWidget(self.snap)
        settings_layout.addWidget(self.start_record_button)
        settings_layout.addStretch()

        settings_group.setLayout(settings_layout)

        ss.style(widget=self)

        self.layout.addWidget(settings_group)
        self.layout.addLayout(v_layout)

        self.central_widget.setLayout(self.layout)

        # CONNECTIONS
        self.adjust_button.clicked.connect(self.adjust_histogram)
        self.acquire_thread.acquisition_finished.connect(self.stop_recording)
        self.acquire_thread.black_screen_signal.connect(self.black_screen)
        self.acquire_thread.update_image_view_signal.connect(self.update_image_views)
        self.check_exp_value_thread.error_signal.connect(self.generate_error)
        self.exposure_time_value.returnPressed.connect(self.check_exposure_time_value)
        self.live_thread.black_screen_signal.connect(self.black_screen)
        self.live_thread.update_image_view_signal.connect(self.update_image_views)
        self.parent.stop_condition_signal.connect(self.update_stop_condition_value)
        self.set_roi_button.clicked.connect(self.set_roi_value)
        self.snap.clicked.connect(self.take_a_snap)
        self.start_record_button.clicked.connect(self.start_recording)
        self.switch_subarray_mode.toggled.connect(self.subarray_mode)
        self.switch_trigger_mode.toggled.connect(self.trigger_mode)
        self.zoom_to_fit_button.clicked.connect(self.fit_image)

    # METHODS
    def adjust_histogram(self):
        sf.set_levels_histogram(self.image_view1)
        sf.set_levels_histogram(self.image_view2)
        sf.set_levels_histogram(self.image_view3)
        sf.set_levels_histogram(self.image_view4)

    def black_screen(self):
        black_frame = np.zeros((512, 512), dtype=np.uint16)
        self.image_view1.setImage(black_frame, autoLevels=False, autoRange=False, autoHistogramRange=False)
        self.image_view2.setImage(black_frame, autoLevels=False, autoRange=False, autoHistogramRange=False)
        self.image_view3.setImage(black_frame, autoLevels=False, autoRange=False, autoHistogramRange=False)
        self.image_view4.setImage(black_frame, autoLevels=False, autoRange=False, autoHistogramRange=False)

    def check_exposure_time_value(self):
        self.check_exp_value_thread.start()

    def fit_image(self):
        padding_value = 0.046
        self.image_view1.getView().autoRange(padding=padding_value)
        self.image_view2.getView().autoRange(padding=padding_value)
        self.image_view3.getView().autoRange(padding=padding_value)
        self.image_view4.getView().autoRange(padding=padding_value)

    def generate_error(self, exp_range):
        QMessageBox.critical(self, "Error", f"Exposure Time value must be between the following values:<br>"
                                            f"- {round(exp_range[0], 8)}<br>"
                                            f"- {round(exp_range[1], 8)}<br>")

    def set_roi_value(self):
        if self.live:
            self.roi_value.setValue(self.opt_roi_value)
            QMessageBox.critical(self, "Error", "Cannot change ROI while live is running.")
            return

        value = int(self.roi_value.value())
        try:
            self.cam1.ableROI(value, value)
            self.cam2.ableROI(value, value)
            self.cam3.ableROI(value, value)
            self.cam4.ableROI(value, value)
        except Exception:
            self.roi_value.setValue(self.opt_roi_value)
            QMessageBox.critical(self, "Error", f"Error setting ROI: Invalid Parameter!")
            return
        self.opt_roi_value = value

        self.exposure_time_value.setText(str(round(self.cam1.getExposure(), 8)))
        self.frame_rate_label.setText(str(round(self.cam1.getFrameRate(), 8)))
        self.check_exposure_time_value()

    def start_live(self):
        if not self.cam1 or not self.cam2 or not self.cam3 or not self.cam4:
            QMessageBox.critical(self, "Error", "No all devices found. Please scan devices first.")
            return

        if not self.live:
            self.live = True
            self.n_frames = 0

            self.live_thread.start()

        else:
            QMessageBox.critical(self, "Error", "Live is already running.")
            return

    def start_recording(self):
        if self.live:
            self.stop_live()

        if self.switch_roi_label.text() == "OFF" or self.switch_trigger_label.text() == "OFF":
            reply = QMessageBox.question(self, 'Confirmation',
                                         'ROI or Trigger Mode is OFF. Are you sure you want to continue?',
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return

        self.start_done = True
        ss.update_toolbutton_style(self.cam1_icon, 'on')
        ss.update_toolbutton_style(self.cam2_icon, 'on')
        ss.update_toolbutton_style(self.cam3_icon, 'on')
        ss.update_toolbutton_style(self.cam4_icon, 'on')

        self.live = True

        device_index = [0, 1, 4, 5, 8, 9, 12, 13]
        for idx in device_index:
            self.parent.current_image = self.parent.gi8.draw(idx, self.parent.current_image)

        self.parent.platform_status_label.setPixmap(self.parent.current_image)

        self.cam1_acquisition = []
        self.cam2_acquisition = []
        self.cam3_acquisition = []
        self.cam4_acquisition = []
        self.acquire_thread.start()

    def stop_live(self):
        if not self.live:
            QMessageBox.critical(self, "Error", "Live is not running.")
            return

        self.live = False

    def stop_recording(self, n_frames_acquired):
        self.live = False

        device_index = [0, 1, 4, 5, 8, 9, 12, 13]
        for idx in device_index:
            self.parent.current_image = self.parent.gi8.draw(idx, self.parent.current_image)

        self.parent.platform_status_label.setPixmap(self.parent.current_image)

        end_time = datetime.now().strftime("%H:%M:%S")
        self.parent.experiment_info["end_time"] = end_time
        ss.update_toolbutton_style(self.cam1_icon, 'off')
        ss.update_toolbutton_style(self.cam2_icon, 'off')
        ss.update_toolbutton_style(self.cam3_icon, 'off')
        ss.update_toolbutton_style(self.cam4_icon, 'off')
        self.frames_acquired_label.setText(str(n_frames_acquired))

    def subarray_mode(self, checked, alignment=False):
        if checked:
            if not alignment:
                self.switch_roi_label.setText("ON")

            self.cam1.ableROI(192, 192)
            self.cam2.ableROI(192, 192)
            self.cam3.ableROI(192, 192)
            self.cam4.ableROI(192, 192)

            self.roi_value.setValue(192)

            self.cam1.setExposure(0.001)
            self.cam2.setExposure(0.001)
            self.cam3.setExposure(0.001)
            self.cam4.setExposure(0.001)

            if self.switch_trigger_mode.checked:
                self.frame_rate_label.setText("Set by External")
            else:
                self.exposure_time_value.setText(str(round(self.cam1.getExposure(), 8)))
                self.frame_rate_label.setText(str(round(self.cam1.getFrameRate(), 8)))

            self.new_info_signal.emit("cam_info", (192, 192), "roi")
            self.parent.cam_info.setText(f"""
                <b>Cameras:</b>
                <ul>
                    <li>ROI: 192 x 192</li>
                    <li>Trigger Source: {"External" if self.switch_trigger_mode.checked else "Internal"}</li>
                    <li>Trigger Mode: Normal</li>
                    <li>Trigger Active: {"SYNCREADOUT" if self.switch_trigger_mode.checked else "Edge"}</li>
                    <li>Trigger Polarity: Positive</li>
                    <li>Frame Bundle: {"2" if self.switch_trigger_mode.checked else "OFF"}</li>
                    </ul>
                """)

        else:
            self.switch_roi_label.setText("OFF")

            self.cam1.disableROI()
            self.cam2.disableROI()
            self.cam3.disableROI()
            self.cam4.disableROI()

            self.cam1.setExposure(0.01)
            self.cam2.setExposure(0.01)
            self.cam3.setExposure(0.01)
            self.cam4.setExposure(0.01)

            if self.switch_trigger_mode.checked:
                self.frame_rate_label.setText("Set by External")
            else:
                self.exposure_time_value.setText(str(round(self.cam1.getExposure(), 8)))
                self.frame_rate_label.setText(str(round(self.cam1.getFrameRate(), 8)))

            self.new_info_signal.emit("cam_info", (2048, 2048), "roi")
            self.parent.cam_info.setText(f"""
                            <b>Cameras:</b>
                            <ul>
                                <li>ROI: 2048 x 2048</li>
                                <li>Trigger Source: {"External" if self.switch_trigger_mode.checked else "Internal"}</li>
                                <li>Trigger Mode: Normal</li>
                                <li>Trigger Active: {"SYNCREADOUT" if self.switch_trigger_mode.checked else "Edge"}</li>
                                <li>Trigger Polarity: Positive</li>
                                <li>Frame Bundle: {"2" if self.switch_trigger_mode.checked else "OFF"}</li>
                                </ul>
                            """)

    def take_a_snap(self):
        directory = QFileDialog.getExistingDirectory(None, "Select the Destination Folder")
        if not directory:
            QMessageBox.warning(self, "Warning", "No directory selected.")
            return

        for i, image_view in enumerate([self.image_view1, self.image_view2, self.image_view3, self.image_view4]):
            image_data = image_view.image
            image_data = np.rot90(image_data)
            if image_data is None:
                QMessageBox.warning(self, "Warning", f"No image data available for CAM {i + 1}.")
                continue

            file_path = os.path.join(directory, f"SNAP CAM {i+1}.tif")
            tiff.imwrite(file_path, image_data.astype(np.uint16))

        QMessageBox.information(self, "Success", "Snapshot saved successfully.")

    def trigger_mode(self, checked, alignment=False):
        if checked:
            if not alignment:
                self.switch_trigger_label.setText("ON")

            sf.able_trig_mode_camera(self.cam1)
            sf.able_trig_mode_camera(self.cam2)
            sf.able_trig_mode_camera(self.cam3)
            sf.able_trig_mode_camera(self.cam4)

            self.exposure_time_value.setEnabled(False)
            self.frame_rate_label.setText("Set by External")

            self.new_info_signal.emit("cam_info", ("External", "Normal", "SYNCREADOUT", "Positive", ["on", "2"]), "trigger")
            self.parent.cam_info.setText(f"""
                            <b>Cameras:</b>
                            <ul>
                                <li>ROI: {"192 x 192" if self.switch_subarray_mode.checked else "2048 x 2048"}</li>
                                <li>Trigger Source: External</li>
                                <li>Trigger Mode: Normal</li>
                                <li>Trigger Active: SYNCREADOUT</li>
                                <li>Trigger Polarity: Positive</li>
                                <li>Frame Bundle: 2</li>
                                </ul>
                            """)

        else:
            self.switch_trigger_label.setText("OFF")

            sf.disable_trig_mode_camera(self.cam1)
            sf.disable_trig_mode_camera(self.cam2)
            sf.disable_trig_mode_camera(self.cam3)
            sf.disable_trig_mode_camera(self.cam4)

            self.exposure_time_value.setEnabled(True)
            self.frame_rate_label.setText(str(round(self.cam1.getFrameRate(), 8)))

            self.new_info_signal.emit("cam_info", ("Internal", "Normal", "Edge", "Positive", ["off", ""]), "trigger")
            self.parent.cam_info.setText(f"""
                                        <b>Cameras:</b>
                                        <ul>
                                            <li>ROI: {"192 x 192" if self.switch_subarray_mode.checked else "2048 x 2048"}</li>
                                            <li>Trigger Source: Internal</li>
                                            <li>Trigger Mode: Normal</li>
                                            <li>Trigger Active: Edge</li>
                                            <li>Trigger Polarity: Positive</li>
                                            <li>Frame Bundle: OFF</li>
                                            </ul>
                                        """)

    def update_image_views(self, frame1, frame2, frame3, frame4):
        self.image_view1.setImage(frame1, autoLevels=False, autoRange=False, autoHistogramRange=False)
        self.image_view2.setImage(frame2, autoLevels=False, autoRange=False, autoHistogramRange=False)
        self.image_view3.setImage(frame3, autoLevels=False, autoRange=False, autoHistogramRange=False)
        self.image_view4.setImage(frame4, autoLevels=False, autoRange=False, autoHistogramRange=False)

    def update_stop_condition_value(self, value):
        if value <= 0:
            self.start_record_button.setEnabled(False)
            return

        value = value - 2 if value % 2 == 0 else value - 1
        self.stop_number = value
        self.parent.experiment_info["stop_condition"] = self.stop_number
        self.update_stop_number_signal.emit(self.stop_number)
        self.start_record_button.setEnabled(True)

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Are you sure you want to close the window?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.live:
                self.stop_live_thread.emit()

            event.accept()

        else:
            event.ignore()




