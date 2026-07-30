"""Graphical interface for configuring and controlling the DMD subsystem.

The window manages LightCrafter firmware images, pattern upload and preview,
pattern lookup tables, LED-current commands, and synchronized control of up to
four digital micromirror devices (DMDs).

Hardware operations are delegated to the command and worker-thread modules so
that long-running USB, firmware, and camera operations do not block the Qt user
interface.
"""

import runtime_config as cfg
import os
import shutil
import nidaqmx
from PyQt6.QtCore import Qt, QIODevice, QFile, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QImage, QPixmap, QFont
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QGroupBox, QPushButton, QFormLayout, QLabel, \
    QWidget, QHBoxLayout, QGridLayout, QToolButton, QLineEdit, QFileDialog, QScrollArea, QSpinBox, \
    QProgressBar, QRadioButton, QCheckBox, QMessageBox, QSpacerItem, QSizePolicy, QDoubleSpinBox
from pyqtgraph import ImageView
import support_functions as sf
import dlpc350_commands as comm
from threads import UploadPatternsThread, ShowUploadedImagesThread, AddAndValidateSequenceThreadDMD1, \
    AddAndValidateSequenceThreadDMD2, AddAndValidateSequenceThreadDMD3, AddAndValidateSequenceThreadDMD4, \
    AcquireSingleThread, ModifyFirmwareThread
import style_sheet as ss
import firmware_commands as fc


class ConfigureDMD(QMainWindow):
    """Provide the DMD configuration and pattern-management window.

    The window coordinates four LightCrafter controllers, firmware image editing,
    pattern LUT validation, optical-stimulation presets, camera previews, and LED
    current configuration. The parent platform window supplies the connected-device
    state and shared experiment metadata.
    """
    new_info_signal = pyqtSignal(str, object, str)
    def __init__(self, parent=None):
        """Initialize the DMD manager and construct its Qt interface.

        Parameters
        ----------
        parent : QMainWindow, optional
            Parent platform window. It must expose the connected DMD list, camera
            controls, experiment metadata, and platform-status widgets used here.
        """
        super().__init__(parent)

        self.setWindowTitle("DMD Device Manager")
        self.setGeometry(2000, 50, 1650, 800)

        # VARIABLES
        self.parent = parent
        self.local_system = nidaqmx.system.System.local()
        self.daq_board = None
        self.dmd_uploaded = 0
        self.m_added_splash_images = []
        self.command_dict = {
            '0': 0.6,
            '1': 0.6,
            '4': 0.6,
            '5': 0.6,
            '8': 0.6,
            '9': 0.6,
            '12': 0.6,
            '13': 0.6,
        }
        self.m_splash_image_add_index = 0
        self.m_splash_image_original = 0
        self.m_splash_image_count = 0
        self.m_splash_image_added = 0
        self.m_splash_image_removed = 0
        self.all_together = False
        self.start_done = False
        self.actual_firmware = None

        self.update_dmd_connection()

        self.dmd1 = comm.DMD()
        self.dmd2 = comm.DMD()
        self.dmd3 = comm.DMD()
        self.dmd4 = comm.DMD()

        self.show_images_thread = ShowUploadedImagesThread(parent=self)
        self.add_to_lut_dmd1_thread = AddAndValidateSequenceThreadDMD1(parent=self)
        self.add_to_lut_dmd2_thread = AddAndValidateSequenceThreadDMD2(parent=self)
        self.add_to_lut_dmd3_thread = AddAndValidateSequenceThreadDMD3(parent=self)
        self.add_to_lut_dmd4_thread = AddAndValidateSequenceThreadDMD4(parent=self)
        self.modify_firmware_thread = ModifyFirmwareThread(parent=self)

        # Widget Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # UPPER LAYOUT
        upper_layout = QHBoxLayout()

        # Pattern File Upload
        pattern_file_group = QGroupBox("Pattern File Upload")
        pattern_file_group.setFixedWidth(460)
        pattern_file_layout = QVBoxLayout()

        browse_file_layout = QFormLayout()
        self.pattern_file_path = QLineEdit()
        browse_file_layout.addRow("Pattern File:", self.pattern_file_path)

        buttons_layout = QHBoxLayout()
        self.show_patterns_button = QPushButton("Show")
        self.browse_button = QPushButton("Browse")
        buttons_layout.addWidget(self.show_patterns_button)
        buttons_layout.addWidget(self.browse_button)

        self.upload_button = QPushButton("Upload")
        self.upload_button.setEnabled(False)

        uploading_layout = QGridLayout()

        self.info_labels1 = QLabel("Not Started")
        self.info_labels2 = QLabel("Not Started")
        self.info_labels3 = QLabel("Not Started")
        self.info_labels4 = QLabel("Not Started")

        icon = QIcon("Icons/dmd_icon.ico")
        self.dmd1_icon_upload = QToolButton()
        self.dmd1_icon_upload.setText("DMD 1")
        self.dmd1_icon_upload.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.dmd1_icon_upload.setIcon(icon)
        self.progress_bar_dmd1 = QProgressBar()
        self.progress_bar_dmd1.setFixedWidth(150)
        self.progress_bar_dmd1.setValue(0)

        self.dmd2_icon_upload = QToolButton()
        self.dmd2_icon_upload.setText("DMD 2")
        self.dmd2_icon_upload.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.dmd2_icon_upload.setIcon(icon)
        self.progress_bar_dmd2 = QProgressBar()
        self.progress_bar_dmd2.setFixedWidth(150)
        self.progress_bar_dmd2.setValue(0)

        self.dmd3_icon_upload = QToolButton()
        self.dmd3_icon_upload.setText("DMD 3")
        self.dmd3_icon_upload.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.dmd3_icon_upload.setIcon(icon)
        self.progress_bar_dmd3 = QProgressBar()
        self.progress_bar_dmd3.setFixedWidth(150)
        self.progress_bar_dmd3.setValue(0)

        self.dmd4_icon_upload = QToolButton()
        self.dmd4_icon_upload.setText("DMD 4")
        self.dmd4_icon_upload.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.dmd4_icon_upload.setIcon(icon)
        self.progress_bar_dmd4 = QProgressBar()
        self.progress_bar_dmd4.setFixedWidth(150)
        self.progress_bar_dmd4.setValue(0)

        uploading_layout.addWidget(self.dmd1_icon_upload, 0, 0)
        uploading_layout.addWidget(self.progress_bar_dmd1, 0, 1)
        uploading_layout.addWidget(self.info_labels1, 0, 2)

        uploading_layout.addWidget(self.dmd2_icon_upload, 1, 0)
        uploading_layout.addWidget(self.progress_bar_dmd2, 1, 1)
        uploading_layout.addWidget(self.info_labels2, 1, 2)

        uploading_layout.addWidget(self.dmd3_icon_upload, 2, 0)
        uploading_layout.addWidget(self.progress_bar_dmd3, 2, 1)
        uploading_layout.addWidget(self.info_labels3, 2, 2)

        uploading_layout.addWidget(self.dmd4_icon_upload, 3, 0)
        uploading_layout.addWidget(self.progress_bar_dmd4, 3, 1)
        uploading_layout.addWidget(self.info_labels4, 3, 2)

        pattern_file_layout.addLayout(browse_file_layout)
        pattern_file_layout.addLayout(buttons_layout)
        pattern_file_layout.addWidget(self.upload_button)
        pattern_file_layout.addLayout(uploading_layout)
        pattern_file_layout.addStretch()

        pattern_file_group.setLayout(pattern_file_layout)

        # Patterns Uploaded
        patterns_uploaded_group = QGroupBox("Patterns Uploaded")
        patterns_uploaded_group.setFixedHeight(420)
        patterns_uploaded_layout = QVBoxLayout()

        modify_file_layout = QHBoxLayout()

        images_infos_layout = QFormLayout()
        self.original_images_label = QLabel(str(self.m_splash_image_original))
        self.images_added_label = QLabel(str(self.m_splash_image_added))
        self.images_removed_label = QLabel(str(self.m_splash_image_removed))
        self.total_images_label = QLabel(str(self.m_splash_image_count))
        images_infos_layout.addRow("<b>- Original Images:</b>", self.original_images_label)
        images_infos_layout.addRow("<b>- Images Added:</b>", self.images_added_label)
        images_infos_layout.addRow("<b>- Images Removed:</b>", self.images_removed_label)
        images_infos_layout.addRow("<b>- Total Images:</b>", self.total_images_label)

        file_browse_layout = QHBoxLayout()
        label = QLabel("Firmware File:")
        self.firm_file_line = QLineEdit()
        self.firm_file_line.setFixedWidth(220)
        self.browse_firm_file = QPushButton("Browse")
        self.browse_firm_file.setFixedWidth(150)
        file_browse_layout.addWidget(label)
        file_browse_layout.addWidget(self.firm_file_line)
        file_browse_layout.addWidget(self.browse_firm_file)

        index_modify_layout = QGridLayout()
        self.select_index_spinbox = QSpinBox()
        self.select_index_spinbox.setFixedWidth(70)
        self.change_pattern_button = QPushButton("Change")
        self.remove_pattern_button = QPushButton("Remove")
        self.add_file_button = QPushButton("Add")
        for button in [self.change_pattern_button, self.remove_pattern_button, self.add_file_button]:
            button.setFixedWidth(80)
        index_modify_layout.addWidget(self.select_index_spinbox, 0, 1)
        index_modify_layout.addWidget(self.change_pattern_button, 1, 0)
        index_modify_layout.addWidget(self.remove_pattern_button, 1, 1)
        index_modify_layout.addWidget(self.add_file_button, 1, 2)

        self.save_updates_button = QPushButton("SAVE\nUPDATES")
        self.save_updates_button.setStyleSheet("""
            QPushButton {
                qproperty-alignment: AlignCenter;
                font-size: 14px;
                font-name: 'Arial';
            }
        """)
        self.save_updates_button.setFixedSize(100, 80)

        spacer = QSpacerItem(30, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        modify_file_layout.addLayout(images_infos_layout)
        modify_file_layout.addItem(spacer)
        modify_file_layout.addLayout(file_browse_layout)
        modify_file_layout.addItem(spacer)
        modify_file_layout.addLayout(index_modify_layout)
        modify_file_layout.addItem(spacer)
        modify_file_layout.addWidget(self.save_updates_button)
        modify_file_layout.addStretch()

        self.show_patterns_area = QScrollArea()
        self.show_patterns_area.setFixedHeight(290)
        self.show_patterns_area.setWidgetResizable(True)
        container = QWidget()
        self.show_pattern_layout = QHBoxLayout(container)

        self.show_patterns_area.setWidget(container)

        patterns_uploaded_layout.addLayout(modify_file_layout)
        patterns_uploaded_layout.addWidget(self.show_patterns_area)

        patterns_uploaded_group.setLayout(patterns_uploaded_layout)

        upper_layout.addWidget(pattern_file_group)
        upper_layout.addWidget(patterns_uploaded_group)

        # LOWER LAYOUT
        lower_layout = QHBoxLayout()

        # Pattern Sequence Settings
        pattern_sequence_group = QGroupBox("Pattern Sequence Settings")
        pattern_sequence_group.setFixedWidth(460)
        pattern_sequence_layout = QVBoxLayout()

        dmd1_group = QGroupBox("DMD 1")
        ss.update_groupbox_style(dmd1_group, mode='subgroup')
        dmd1_layout = QHBoxLayout()

        power_settings_layout = QFormLayout()
        self.red_led_power_dmd1 = QDoubleSpinBox()
        self.red_led_power_dmd1.setRange(0.6, 12.0)
        self.red_led_power_dmd1.setValue(5.0)
        self.red_led_power_dmd1.setFixedWidth(70)
        self.blue_led_power_dmd1 = QDoubleSpinBox()
        self.blue_led_power_dmd1.setRange(0.6, 12.0)
        self.blue_led_power_dmd1.setValue(10.0)
        self.blue_led_power_dmd1.setFixedWidth(70)
        power_settings_layout.addRow("Red LED Current (A):", self.red_led_power_dmd1)
        power_settings_layout.addRow("Blue LED Current (A):", self.blue_led_power_dmd1)

        pattern_choice_layout = QFormLayout()
        self.red_pattern_dmd1 = QSpinBox()
        self.blue_pattern_dmd1 = QSpinBox()
        pattern_choice_layout.addRow("Pattern Index:", self.red_pattern_dmd1)
        pattern_choice_layout.addRow("Pattern Index:", self.blue_pattern_dmd1)

        add_dmd1_layout = QVBoxLayout()
        self.preview_dmd1_button = QPushButton("View Patterns")
        self.set_led_dmd1_currents_button = QPushButton("Set LED Currents")
        add_dmd1_layout.addWidget(self.set_led_dmd1_currents_button)
        add_dmd1_layout.addWidget(self.preview_dmd1_button)

        power_settings_wrapper = QVBoxLayout()
        power_settings_wrapper.addLayout(power_settings_layout)
        power_settings_wrapper.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pattern_choice_wrapper = QVBoxLayout()
        pattern_choice_wrapper.addLayout(pattern_choice_layout)
        pattern_choice_wrapper.setAlignment(Qt.AlignmentFlag.AlignCenter)

        dmd1_layout.addLayout(power_settings_wrapper)
        dmd1_layout.addLayout(pattern_choice_wrapper)
        dmd1_layout.addLayout(add_dmd1_layout)
        dmd1_group.setLayout(dmd1_layout)

        dmd2_group = QGroupBox("DMD 2")
        ss.update_groupbox_style(dmd2_group, mode='subgroup')
        dmd2_layout = QHBoxLayout()

        power_settings_layout = QFormLayout()
        self.red_led_power_dmd2 = QDoubleSpinBox()
        self.red_led_power_dmd2.setRange(0.6, 12.0)
        self.red_led_power_dmd2.setValue(4.9)
        self.red_led_power_dmd2.setFixedWidth(70)
        self.blue_led_power_dmd2 = QDoubleSpinBox()
        self.blue_led_power_dmd2.setRange(0.6, 12.0)
        self.blue_led_power_dmd2.setValue(10.0)
        self.blue_led_power_dmd2.setFixedWidth(70)
        power_settings_layout.addRow("Red LED Current (A):", self.red_led_power_dmd2)
        power_settings_layout.addRow("Blue LED Current (A):", self.blue_led_power_dmd2)

        pattern_choice_layout = QFormLayout()
        self.red_pattern_dmd2 = QSpinBox()
        self.blue_pattern_dmd2 = QSpinBox()
        pattern_choice_layout.addRow("Pattern Index:", self.red_pattern_dmd2)
        pattern_choice_layout.addRow("Pattern Index:", self.blue_pattern_dmd2)

        add_dmd2_layout = QVBoxLayout()
        self.preview_dmd2_button = QPushButton("View Patterns")
        self.set_led_dmd2_currents_button = QPushButton("Set LED Currents")
        add_dmd2_layout.addWidget(self.set_led_dmd2_currents_button)
        add_dmd2_layout.addWidget(self.preview_dmd2_button)

        power_settings_wrapper = QVBoxLayout()
        power_settings_wrapper.addLayout(power_settings_layout)
        power_settings_wrapper.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pattern_choice_wrapper = QVBoxLayout()
        pattern_choice_wrapper.addLayout(pattern_choice_layout)
        pattern_choice_wrapper.setAlignment(Qt.AlignmentFlag.AlignCenter)

        dmd2_layout.addLayout(power_settings_wrapper)
        dmd2_layout.addLayout(pattern_choice_wrapper)
        dmd2_layout.addLayout(add_dmd2_layout)
        dmd2_group.setLayout(dmd2_layout)

        dmd3_group = QGroupBox("DMD 3")
        ss.update_groupbox_style(dmd3_group, mode='subgroup')
        dmd3_layout = QHBoxLayout()

        power_settings_layout = QFormLayout()
        self.red_led_power_dmd3 = QDoubleSpinBox()
        self.red_led_power_dmd3.setRange(0.6, 12.0)
        self.red_led_power_dmd3.setValue(4.9)
        self.red_led_power_dmd3.setFixedWidth(70)
        self.blue_led_power_dmd3 = QDoubleSpinBox()
        self.blue_led_power_dmd3.setRange(0.6, 12.0)
        self.blue_led_power_dmd3.setValue(12.0)
        self.blue_led_power_dmd3.setFixedWidth(70)
        power_settings_layout.addRow("Red LED Current (A):", self.red_led_power_dmd3)
        power_settings_layout.addRow("Blue LED Current (A):", self.blue_led_power_dmd3)

        pattern_choice_layout = QFormLayout()
        self.red_pattern_dmd3 = QSpinBox()
        self.blue_pattern_dmd3 = QSpinBox()
        pattern_choice_layout.addRow("Pattern Index:", self.red_pattern_dmd3)
        pattern_choice_layout.addRow("Pattern Index:", self.blue_pattern_dmd3)

        add_dmd3_layout = QVBoxLayout()
        self.preview_dmd3_button = QPushButton("View Patterns")
        self.set_led_dmd3_currents_button = QPushButton("Set LED Currents")
        add_dmd3_layout.addWidget(self.set_led_dmd3_currents_button)
        add_dmd3_layout.addWidget(self.preview_dmd3_button)

        power_settings_wrapper = QVBoxLayout()
        power_settings_wrapper.addLayout(power_settings_layout)
        power_settings_wrapper.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pattern_choice_wrapper = QVBoxLayout()
        pattern_choice_wrapper.addLayout(pattern_choice_layout)
        pattern_choice_wrapper.setAlignment(Qt.AlignmentFlag.AlignCenter)

        dmd3_layout.addLayout(power_settings_wrapper)
        dmd3_layout.addLayout(pattern_choice_wrapper)
        dmd3_layout.addLayout(add_dmd3_layout)
        dmd3_group.setLayout(dmd3_layout)

        dmd4_group = QGroupBox("DMD 4")
        ss.update_groupbox_style(dmd4_group, mode='subgroup')
        dmd4_layout = QHBoxLayout()

        power_settings_layout = QFormLayout()
        self.red_led_power_dmd4 = QDoubleSpinBox()
        self.red_led_power_dmd4.setRange(0.6, 12.0)
        self.red_led_power_dmd4.setValue(4.9)
        self.red_led_power_dmd4.setFixedWidth(70)
        self.blue_led_power_dmd4 = QDoubleSpinBox()
        self.blue_led_power_dmd4.setRange(0.6, 12.0)
        self.blue_led_power_dmd4.setValue(11.0)
        self.blue_led_power_dmd4.setFixedWidth(70)
        power_settings_layout.addRow("Red LED Current (A):", self.red_led_power_dmd4)
        power_settings_layout.addRow("Blue LED Current (A):", self.blue_led_power_dmd4)

        for i in range(1, 5):
            self.send_command_to_dac(dmd=i)
        #self.experiment_info[key].update({value[0]: {priv_key: [value[1], value[2]]}})
        self.parent.experiment_info['dmd_info'].update({"DMD 1": {"led_currents": [round(self.red_led_power_dmd1.value(), 1), round(self.blue_led_power_dmd1.value(), 1)]}})
        self.parent.experiment_info['dmd_info'].update({"DMD 2": {"led_currents": [round(self.red_led_power_dmd2.value(), 1), round(self.blue_led_power_dmd2.value(), 1)]}})
        self.parent.experiment_info['dmd_info'].update({"DMD 3": {"led_currents": [round(self.red_led_power_dmd3.value(), 1), round(self.blue_led_power_dmd3.value(), 1)]}})
        self.parent.experiment_info['dmd_info'].update({"DMD 4": {"led_currents": [round(self.red_led_power_dmd4.value(), 1), round(self.blue_led_power_dmd4.value(), 1)]}})

        pattern_choice_layout = QFormLayout()
        self.red_pattern_dmd4 = QSpinBox()
        self.blue_pattern_dmd4 = QSpinBox()
        pattern_choice_layout.addRow("Pattern Index:", self.red_pattern_dmd4)
        pattern_choice_layout.addRow("Pattern Index:", self.blue_pattern_dmd4)

        add_dmd4_layout = QVBoxLayout()
        self.preview_dmd4_button = QPushButton("View Patterns")
        self.set_led_dmd4_currents_button = QPushButton("Set LED Currents")
        add_dmd4_layout.addWidget(self.set_led_dmd4_currents_button)
        add_dmd4_layout.addWidget(self.preview_dmd4_button)

        self.preview_dmd1_button.setEnabled(True)
        self.preview_dmd2_button.setEnabled(True)
        self.preview_dmd3_button.setEnabled(True)
        self.preview_dmd4_button.setEnabled(True)

        power_settings_wrapper = QVBoxLayout()
        power_settings_wrapper.addLayout(power_settings_layout)
        power_settings_wrapper.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pattern_choice_wrapper = QVBoxLayout()
        pattern_choice_wrapper.addLayout(pattern_choice_layout)
        pattern_choice_wrapper.setAlignment(Qt.AlignmentFlag.AlignCenter)

        dmd4_layout.addLayout(power_settings_wrapper)
        dmd4_layout.addLayout(pattern_choice_wrapper)
        dmd4_layout.addLayout(add_dmd4_layout)
        dmd4_group.setLayout(dmd4_layout)

        self.update_image_index()

        define_sequence_layout = QHBoxLayout()
        self.add_all_pattern_to_lut_button = QPushButton("Add All Patterns to Sequence")
        self.clear_all_button = QPushButton("Clear All")

        define_sequence_layout.addWidget(self.add_all_pattern_to_lut_button)
        define_sequence_layout.addWidget(self.clear_all_button)

        pattern_sequence_layout.addWidget(dmd1_group)
        pattern_sequence_layout.addWidget(dmd2_group)
        pattern_sequence_layout.addWidget(dmd3_group)
        pattern_sequence_layout.addWidget(dmd4_group)
        pattern_sequence_layout.addLayout(define_sequence_layout)

        pattern_sequence_group.setLayout(pattern_sequence_layout)

        # Pattern Preview
        pattern_preview_group = QGroupBox("Pattern Preview")
        pattern_preview_group.setFixedWidth(595)
        pattern_preview_layout = QVBoxLayout()

        self.enable_preview = QPushButton("Enable Preview")
        self.enable_preview.setEnabled(False)

        image_preview_layout = QGridLayout()

        cam1_gb = QGroupBox("CAM 1")
        cam1_layout = QVBoxLayout()
        self.preview_cam1 = ImageView()
        self.preview_cam1.setFixedSize(QSize(192, 192))
        cam1_layout.addWidget(self.preview_cam1, alignment=Qt.AlignmentFlag.AlignCenter)
        cam1_gb.setLayout(cam1_layout)

        cam2_gb = QGroupBox("CAM 2")
        cam2_layout = QVBoxLayout()
        self.preview_cam2 = ImageView()
        self.preview_cam2.setFixedSize(QSize(192, 192))
        cam2_layout.addWidget(self.preview_cam2, alignment=Qt.AlignmentFlag.AlignCenter)
        cam2_gb.setLayout(cam2_layout)

        cam3_gb = QGroupBox("CAM 3")
        cam3_layout = QVBoxLayout()
        self.preview_cam3 = ImageView()
        self.preview_cam3.setFixedSize(QSize(192, 192))
        cam3_layout.addWidget(self.preview_cam3, alignment=Qt.AlignmentFlag.AlignCenter)
        cam3_gb.setLayout(cam3_layout)

        cam4_gb = QGroupBox("CAM 4")
        cam4_layout = QVBoxLayout()
        self.preview_cam4 = ImageView()
        self.preview_cam4.setFixedSize(QSize(192, 192))
        cam4_layout.addWidget(self.preview_cam4, alignment=Qt.AlignmentFlag.AlignCenter)
        cam4_gb.setLayout(cam4_layout)

        for groupbox in [cam1_gb, cam2_gb, cam3_gb, cam4_gb]:
            ss.update_groupbox_style(groupbox, mode='subgroup')
            groupbox.setFixedSize(220, 240)

        self.preview_cam1.ui.roiBtn.hide()
        self.preview_cam1.ui.menuBtn.hide()
        self.preview_cam1.ui.histogram.hide()
        self.preview_cam2.ui.roiBtn.hide()
        self.preview_cam2.ui.menuBtn.hide()
        self.preview_cam2.ui.histogram.hide()
        self.preview_cam3.ui.roiBtn.hide()
        self.preview_cam3.ui.menuBtn.hide()
        self.preview_cam3.ui.histogram.hide()
        self.preview_cam4.ui.roiBtn.hide()
        self.preview_cam4.ui.menuBtn.hide()
        self.preview_cam4.ui.histogram.hide()

        image_preview_layout.addWidget(cam1_gb, 0, 0)
        image_preview_layout.addWidget(cam2_gb, 0, 1)
        image_preview_layout.addWidget(cam3_gb, 1, 0)
        image_preview_layout.addWidget(cam4_gb, 1, 1)

        pattern_preview_layout.addWidget(self.enable_preview)
        pattern_preview_layout.addLayout(image_preview_layout)
        pattern_preview_group.setLayout(pattern_preview_layout)

        lower_dx_layout = QVBoxLayout()

        # Optical Stimulation Presets
        stimulation_preset_group = QGroupBox("Optical Stimulation Pre-Sets")
        stimulation_preset_group.setFixedWidth(595)
        stimulation_layout = QGridLayout()

        heart_all_icon = QIcon("Icons/heart_all.png")
        heart_apex_icon = QIcon("Icons/heart_apex.png")
        heart_base_icon = QIcon("Icons/heart_base.png")
        heart_sx_icon = QIcon("Icons/heart_sx.png")
        heart_dx_icon = QIcon("Icons/heart_dx.png")
        heart_line_icon = QIcon("Icons/heart_line.png")
        self.heart_all_button = QToolButton()
        self.heart_all_button.setIcon(heart_all_icon)
        self.heart_all_button.setText("Wide")
        self.heart_all_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.heart_apex_button = QToolButton()
        self.heart_apex_button.setIcon(heart_apex_icon)
        self.heart_apex_button.setText("Apex")
        self.heart_apex_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.heart_base_button = QToolButton()
        self.heart_base_button.setIcon(heart_base_icon)
        self.heart_base_button.setText("Base")
        self.heart_base_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.heart_sx_button = QToolButton()
        self.heart_sx_button.setIcon(heart_sx_icon)
        self.heart_sx_button.setText("Left")
        self.heart_sx_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.heart_dx_button = QToolButton()
        self.heart_dx_button.setIcon(heart_dx_icon)
        self.heart_dx_button.setText("Right")
        self.heart_dx_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

        for tool_button in [self.heart_all_button, self.heart_apex_button, self.heart_base_button, self.heart_sx_button, self.heart_dx_button]:
            tool_button.setIconSize(QSize(50, 50))
            tool_button.setFixedSize(100, 100)
            ss.update_toolbutton_style(tool_button, mode="on", clickable=True)

        line_settings_layout = QVBoxLayout()
        self.heart_line_button = QToolButton()
        self.heart_line_button.setIcon(heart_line_icon)
        self.heart_line_button.setText("Line")
        self.heart_line_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.heart_line_button.setIconSize(QSize(45, 45))
        self.heart_line_button.setFixedSize(90, 90)
        ss.update_toolbutton_style(self.heart_line_button, mode="on", clickable=True)
        self.line_width = QSpinBox()
        self.line_width.setFixedWidth(40)
        self.line_width.setRange(1, 5)
        line_settings_layout.addWidget(self.heart_line_button, alignment=Qt.AlignmentFlag.AlignCenter)
        line_settings_layout.addWidget(self.line_width, alignment=Qt.AlignmentFlag.AlignCenter)

        stimulation_layout.addWidget(self.heart_apex_button, 0, 0)
        stimulation_layout.addWidget(self.heart_all_button, 0, 1)
        stimulation_layout.addWidget(self.heart_base_button, 0, 2)
        stimulation_layout.addWidget(self.heart_sx_button, 1, 0)
        stimulation_layout.addLayout(line_settings_layout, 1, 1)
        stimulation_layout.addWidget(self.heart_dx_button, 1, 2)
        stimulation_preset_group.setLayout(stimulation_layout)

        validation_control_layout = QHBoxLayout()
        # Sequence Validation
        lut_infos_group = QGroupBox("Sequence Validation")
        lut_infos_group.setFixedWidth(298)
        lut_infos_layout = QVBoxLayout()

        self.lut_infos_labels = QLabel("No Process in Progress")
        self.lut_infos_labels.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar_lut = QProgressBar()
        self.progress_bar_lut.setValue(0)

        icon = QIcon("Icons/led_gray.png")
        h_layout = QHBoxLayout()
        states_layout = QGridLayout()

        self.state_dmd1_button = QPushButton()
        self.state_dmd1_button.setIcon(icon)
        self.state_dmd1_label = QLabel("<b>DMD 1:</b> No patterns in LUT ")

        self.state_dmd2_button = QPushButton()
        self.state_dmd2_button.setIcon(icon)
        self.state_dmd2_label = QLabel("<b>DMD 2:</b> No patterns in LUT ")

        self.state_dmd3_button = QPushButton()
        self.state_dmd3_button.setIcon(icon)
        self.state_dmd3_label = QLabel("<b>DMD 3:</b> No patterns in LUT ")

        self.state_dmd4_button = QPushButton()
        self.state_dmd4_button.setIcon(icon)
        self.state_dmd4_label = QLabel("<b>DMD 4:</b> No patterns in LUT ")

        states_layout.addWidget(self.state_dmd1_button, 0, 0)
        states_layout.addWidget(self.state_dmd1_label, 0, 1)
        states_layout.addWidget(self.state_dmd2_button, 1, 0)
        states_layout.addWidget(self.state_dmd2_label, 1, 1)
        states_layout.addWidget(self.state_dmd3_button, 2, 0)
        states_layout.addWidget(self.state_dmd3_label, 2, 1)
        states_layout.addWidget(self.state_dmd4_button, 3, 0)
        states_layout.addWidget(self.state_dmd4_label, 3, 1)

        h_layout.addLayout(states_layout)
        h_layout.addStretch()

        lut_infos_layout.addWidget(self.lut_infos_labels)
        lut_infos_layout.addWidget(self.progress_bar_lut)
        lut_infos_layout.addLayout(h_layout)

        lut_infos_group.setLayout(lut_infos_layout)

        # Sequence Control
        sequence_control_group = QGroupBox("Sequence Control")
        sequence_control_group.setFixedWidth(297)
        sequence_control_layout = QVBoxLayout()

        v_layout = QVBoxLayout()
        select_dmd_layout = QGridLayout()
        self.dmd1_radiobutton = QCheckBox("DMD 1")
        self.dmd2_radiobutton = QCheckBox("DMD 2")
        self.dmd3_radiobutton = QCheckBox("DMD 3")
        self.dmd4_radiobutton = QCheckBox("DMD 4")
        select_dmd_layout.addWidget(self.dmd1_radiobutton, 0, 0)
        select_dmd_layout.addWidget(self.dmd2_radiobutton, 0, 1)
        select_dmd_layout.addWidget(self.dmd3_radiobutton, 1, 0)
        select_dmd_layout.addWidget(self.dmd4_radiobutton, 1, 1)

        for checkbox in [self.dmd1_radiobutton, self.dmd2_radiobutton, self.dmd3_radiobutton, self.dmd4_radiobutton]:
            ss.update_checkbox_style(checkbox, dmd_selection=True)

        self.dmd1_radiobutton.setEnabled(False)
        self.dmd2_radiobutton.setEnabled(False)
        self.dmd3_radiobutton.setEnabled(False)
        self.dmd4_radiobutton.setEnabled(False)

        self.use_selection_dmd = QRadioButton("Allow DMDs Selection")

        buttons_layout = QVBoxLayout()
        buttons2_layout = QHBoxLayout()

        self.start_button = QPushButton("Start")
        self.pause_button = QPushButton("Pause")
        buttons2_layout.addWidget(self.start_button)
        buttons2_layout.addWidget(self.pause_button)

        self.stop_button = QPushButton("Stop")

        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)

        buttons_layout.addLayout(buttons2_layout)
        buttons_layout.addWidget(self.stop_button)

        v_layout.addLayout(select_dmd_layout)
        v_layout.addWidget(self.use_selection_dmd)

        sequence_control_layout.addLayout(v_layout)
        sequence_control_layout.addLayout(buttons_layout)
        sequence_control_group.setLayout(sequence_control_layout)

        validation_control_layout.addWidget(lut_infos_group)
        validation_control_layout.addWidget(sequence_control_group)

        lower_dx_layout.addWidget(stimulation_preset_group)
        lower_dx_layout.addLayout(validation_control_layout)

        lower_layout.addWidget(pattern_sequence_group)
        lower_layout.addWidget(pattern_preview_group)
        lower_layout.addLayout(lower_dx_layout)

        # DEFINE LAYOUT
        ss.style(widget=self)

        self.layout.addLayout(upper_layout)
        self.layout.addLayout(lower_layout)

        self.setLayout(self.layout)

        # CONNECTIONS
        self.add_all_pattern_to_lut_button.clicked.connect(self.prepare_all_patterns_to_lut)
        self.add_to_lut_dmd1_thread.finished_signal.connect(self.update_gui)
        self.add_to_lut_dmd2_thread.finished_signal.connect(self.update_gui)
        self.add_to_lut_dmd3_thread.finished_signal.connect(self.update_gui)
        self.add_to_lut_dmd4_thread.finished_signal.connect(self.update_gui)
        self.add_to_lut_dmd1_thread.progress_signal.connect(self.update_progress_bar_lut)
        self.add_to_lut_dmd2_thread.progress_signal.connect(self.update_progress_bar_lut)
        self.add_to_lut_dmd3_thread.progress_signal.connect(self.update_progress_bar_lut)
        self.add_to_lut_dmd4_thread.progress_signal.connect(self.update_progress_bar_lut)
        self.add_file_button.clicked.connect(self.add_pattern)
        self.browse_button.clicked.connect(self.browse_pattern_file)
        self.browse_firm_file.clicked.connect(self.browse_firmware_file)
        self.change_pattern_button.clicked.connect(self.change_pattern)
        self.clear_all_button.clicked.connect(self.clear_all)
        self.enable_preview.clicked.connect(self.acquire_single_frame)
        self.heart_apex_button.clicked.connect(self.define_heart_apex_sequence)
        self.heart_all_button.clicked.connect(self.define_heart_all_sequence)
        self.heart_base_button.clicked.connect(self.define_heart_base_sequence)
        self.heart_sx_button.clicked.connect(self.define_heart_sx_sequence)
        self.heart_dx_button.clicked.connect(self.define_heart_dx_sequence)
        self.heart_line_button.clicked.connect(self.define_heart_line_sequence)
        self.modify_firmware_thread.finished_signal.connect(self.update_build)
        self.parent.dmd_connected_signal.connect(self.update_dmd_connection)
        self.parent.enable_preview_signal.connect(self.enable_preview_button)
        self.pause_button.clicked.connect(self.pause_sequence)
        self.remove_pattern_button.clicked.connect(self.remove_splash_image)
        self.save_updates_button.clicked.connect(self.save_firmware_updates)
        self.set_led_dmd1_currents_button.clicked.connect(lambda: self.send_command_to_dac(dmd=1))
        self.set_led_dmd2_currents_button.clicked.connect(lambda: self.send_command_to_dac(dmd=2))
        self.set_led_dmd3_currents_button.clicked.connect(lambda: self.send_command_to_dac(dmd=3))
        self.set_led_dmd4_currents_button.clicked.connect(lambda: self.send_command_to_dac(dmd=4))
        self.preview_dmd1_button.clicked.connect(self.add_dmd1_patterns_to_lut)
        self.preview_dmd2_button.clicked.connect(self.add_dmd2_patterns_to_lut)
        self.preview_dmd3_button.clicked.connect(self.add_dmd3_patterns_to_lut)
        self.preview_dmd4_button.clicked.connect(self.add_dmd4_patterns_to_lut)
        self.show_images_thread.finished_signal.connect(self.update_scroll_area)
        self.show_patterns_button.clicked.connect(self.show_patterns)
        self.start_button.clicked.connect(self.start_sequence)
        self.stop_button.clicked.connect(self.stop_sequence)
        self.upload_button.clicked.connect(self.upload_patterns_dmd1)
        self.use_selection_dmd.toggled.connect(self.allow_dmd_selection)

    # METHODS
    def add_pattern(self):
        """Append a 912 x 1140 BMP image to the editable firmware image list.

        The method updates the splash-image counters and refreshes the preview area.
        A warning is shown when the firmware limit is reached or the selected image has
        an unsupported resolution.
        """
        if self.m_splash_image_add_index == fc.MAX_SPLASH_IMAGES:
            QMessageBox.warning(self, "Warning", "Only 256 images can be added.")
            return

        file_path = str(cfg.PATTERN_OUTPUT_DIRECTORY)
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Splash Image", file_path, "BMP Files (*.bmp)")
        if file_name:
            img = QImage(file_name)
            if img.width() != 912 or img.height() != 1140:
                QMessageBox.warning(self, "Warning", "Only images of resolution 912x1140 are supported.")
                return

            self.m_added_splash_images[self.m_splash_image_add_index] = file_name
            self.select_index_spinbox.setRange(0, self.m_splash_image_add_index)
            self.select_index_spinbox.setValue(self.m_splash_image_add_index)

            self.m_splash_image_add_index += 1
            self.m_splash_image_count += 1
            self.m_splash_image_added += 1
            self.images_added_label.setText(str(self.m_splash_image_added))

            sf.clear_layout(self.show_pattern_layout)
            self.update_scroll_area()

    def acquire_single_frame(self):
        """Acquire one preview frame from each configured camera.

        Camera subarray mode is enabled before starting the asynchronous acquisition
        thread. The resulting frames are handled by :meth:`enable_preview_buttons`.
        """
        self.parent.control_camera_gui.subarray_mode(True)

        self.acquire_single_frame_thread.start()

    def add_all_patterns_to_lut(self):
        """Continue LUT configuration for the currently selected DMD.

        This method dispatches to the device-specific LUT routine identified by
        ``self.dmd_selected``. It is also used while configuring all connected DMDs in
        sequence.
        """
        if self.dmd_selected == 1:
            self.add_dmd1_patterns_to_lut()

        elif self.dmd_selected == 2:
            self.add_dmd2_patterns_to_lut()

        elif self.dmd_selected == 3:
            self.add_dmd3_patterns_to_lut()

        elif self.dmd_selected == 4:
            self.all_together = False
            self.index_dmd_selected = 1
            self.add_dmd4_patterns_to_lut()

    def add_dmd1_patterns_to_lut(self, warning=True):
        """Build and validate the selected red/blue pattern LUT for DMD 1.

        Parameters
        ----------
        warning : bool, default=True
            Show a warning when DMD 1 is not connected.
        """
        if self.parent.avoid_overray:
            QMessageBox.warning(self, "Warning", "Please turn off the DMDs before sending this command. Risk of command overload to the PCIe-6612!")
            return

        if 1 in self.dmd_connected:
            self.start_done = False

            for i in [10, 11]:
                self.parent.current_image = self.parent.gi8.draw(i, self.parent.current_image, True, 1)
            self.parent.platform_status_label.setPixmap(self.parent.current_image)

            self.new_info_signal.emit("dmd_info",("DMD 1", self.red_pattern_dmd1.value(), self.blue_pattern_dmd1.value()), "pattern_index")
            self.progress_bar_lut.setValue(0)
            sf.select_channel(1)

            self.lut_infos_labels.setText("Validating DMD 1 pattern LUT...")
            self.add_to_lut_dmd1_thread.start()

        elif warning:
            QMessageBox.warning(self, "Warning", "DMD 1 is not connected to the system!", QMessageBox.StandardButton.Ok)

    def add_dmd2_patterns_to_lut(self, warning=True):
        """Build and validate the selected red/blue pattern LUT for DMD 2.

        Parameters
        ----------
        warning : bool, default=True
            Show a warning when DMD 2 is not connected.
        """
        if self.parent.avoid_overray:
            QMessageBox.warning(self, "Warning", "Please turn off the DMDs before sending this command. Risk of command overload to the PCIe-6612!")
            return

        if 2 in self.dmd_connected:
            self.start_done = False

            self.parent.current_image = self.parent.gi8.draw(7, self.parent.current_image, True, 2)
            self.parent.platform_status_label.setPixmap(self.parent.current_image)

            self.new_info_signal.emit("dmd_info", ("DMD 2", self.red_pattern_dmd2.value(), self.blue_pattern_dmd2.value()), "pattern_index")
            self.progress_bar_lut.setValue(0)
            sf.select_channel(2)

            self.lut_infos_labels.setText("Validating DMD 2 pattern LUT...")
            self.add_to_lut_dmd2_thread.start()

        elif warning:
            QMessageBox.warning(self, "Warning", "DMD 2 is not connected to the system!", QMessageBox.StandardButton.Ok)

    def add_dmd3_patterns_to_lut(self, warning=True):
        """Build and validate the selected red/blue pattern LUT for DMD 3.

        Parameters
        ----------
        warning : bool, default=True
            Show a warning when DMD 3 is not connected.
        """
        if self.parent.avoid_overray:
            QMessageBox.warning(self, "Warning", "Please turn off the DMDs before sending this command. Risk of command overload to the PCIe-6612!")
            return

        if 3 in self.dmd_connected:
            self.start_done = False

            for i in [2, 3]:
                self.parent.current_image = self.parent.gi8.draw(i, self.parent.current_image, True, 3)
            self.parent.platform_status_label.setPixmap(self.parent.current_image)

            self.new_info_signal.emit("dmd_info", ("DMD 3", self.red_pattern_dmd3.value(), self.blue_pattern_dmd3.value()), "pattern_index")
            self.progress_bar_lut.setValue(0)
            sf.select_channel(3)

            self.lut_infos_labels.setText("Validating DMD 3 pattern LUT...")
            self.add_to_lut_dmd3_thread.start()

        elif warning:
            QMessageBox.warning(self, "Warning", "DMD 3 is not connected to the system!", QMessageBox.StandardButton.Ok)

    def add_dmd4_patterns_to_lut(self, warning=True):
        """Build and validate the selected red/blue pattern LUT for DMD 4.

        Parameters
        ----------
        warning : bool, default=True
            Show a warning when DMD 4 is not connected.
        """
        if self.parent.avoid_overray:
            QMessageBox.warning(self, "Warning", "Please turn off the DMDs before sending this command. Risk of command overload to the PCIe-6612!")
            return

        if 4 in self.dmd_connected:
            self.start_done = False


            self.parent.current_image = self.parent.gi8.draw(6, self.parent.current_image, True, 4)
            self.parent.platform_status_label.setPixmap(self.parent.current_image)

            self.new_info_signal.emit("dmd_info", ("DMD 4", self.red_pattern_dmd4.value(), self.blue_pattern_dmd4.value()), "pattern_index")
            self.progress_bar_lut.setValue(0)
            sf.select_channel(4)

            self.lut_infos_labels.setText("Validating DMD 4 pattern LUT...")
            self.add_to_lut_dmd4_thread.start()

        elif warning:
            QMessageBox.warning(self, "Warning", "DMD 4 is not connected to the system!", QMessageBox.StandardButton.Ok)

    def allow_dmd_selection(self):
        """Enable or disable individual DMD selection controls.

        The radio buttons are available only when selective DMD control is enabled by
        the corresponding checkbox.
        """
        if self.use_selection_dmd.isChecked():
            self.dmd1_radiobutton.setEnabled(True)
            self.dmd2_radiobutton.setEnabled(True)
            self.dmd3_radiobutton.setEnabled(True)
            self.dmd4_radiobutton.setEnabled(True)
        else:
            self.dmd1_radiobutton.setEnabled(False)
            self.dmd2_radiobutton.setEnabled(False)
            self.dmd3_radiobutton.setEnabled(False)
            self.dmd4_radiobutton.setEnabled(False)

    def browse_pattern_file(self):
        """Select a firmware binary containing patterns for upload.

        The selected file is assigned to the upload worker, displayed in the path
        field, and parsed asynchronously to populate the pattern preview.
        """
        self.file_path, _ = QFileDialog.getOpenFileName(self, "Select BIN File", str(cfg.PATTERN_REPOSITORY), "BIN Files (*.bin)")
        if self.file_path:
            self.clear_all()
            if self.firm_file_line.text() != "":
                self.firm_file_line.clear()

            self.upload_patterns_thread = UploadPatternsThread(parent=self, upload_file=self.file_path)
            self.upload_patterns_thread.finished_signal.connect(self.upload_patterns_other_dmds)
            self.upload_patterns_thread.progress_signal.connect(self.update_progress_bar_upload)
            self.pattern_file_path.setText(self.file_path)
            self.show_patterns(True)

    def browse_firmware_file(self):
        """Select an existing firmware binary for inspection or modification.

        Current splash-image counters and previews are reset before the selected
        firmware is parsed by the background worker.
        """
        self.file_path_modified, _ = QFileDialog.getOpenFileName(self, "Select BIN File", str(cfg.PATTERN_REPOSITORY), "BIN Files (*.bin)")
        if self.file_path_modified:
            self.clear_all()

            self.m_splash_image_add_index = 0
            self.m_splash_image_original = 0
            self.m_splash_image_count = 0
            self.m_splash_image_added = 0
            self.m_splash_image_removed = 0
            if self.pattern_file_path.text() != "":
                self.pattern_file_path.clear()

            self.upload_patterns_thread = UploadPatternsThread(parent=self, upload_file=self.file_path_modified)
            self.upload_patterns_thread.finished_signal.connect(self.upload_patterns_other_dmds)
            self.upload_patterns_thread.progress_signal.connect(self.update_progress_bar_upload)
            self.firm_file_line.setText(self.file_path_modified)

            sf.clear_layout(self.show_pattern_layout)
            self.file_to_show = self.file_path_modified
            self.show_images_thread.start()

    def change_pattern(self):
        """Replace the currently selected splash image with another BMP file.

        Only 912 x 1140 images are accepted. The firmware preview is refreshed after a
        successful replacement.
        """
        index = self.select_index_spinbox.value()

        if not self.m_added_splash_images[index]:
            QMessageBox.warning(self, "Warning", "Use Add Button to add patterns in sequence.")
            return

        file_path = str(cfg.PATTERN_OUTPUT_DIRECTORY)
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Splash Image", file_path, "BMP Files (*.bmp)")
        if file_name:
            img = QImage(file_name)
            if img.width() != 912 or img.height() != 1140:
                QMessageBox.warning(self, "Warning", "Only images of resolution 912x1140 are supported.")
                return

            self.m_added_splash_images[index] = file_name

            sf.clear_layout(self.show_pattern_layout)
            self.update_scroll_area()

    def clear_all(self):
        """Clear the pattern LUTs and reset DMD status indicators.

        This operation clears the in-memory LUT objects for all four DMDs and updates
        the platform diagram to show that no DMD sequence is configured.
        """
        self.dmd1.clear_pat_lut()
        self.dmd2.clear_pat_lut()
        self.dmd3.clear_pat_lut()
        self.dmd4.clear_pat_lut()

        icon = QIcon("Icons/led_gray.png")
        self.state_dmd1_button.setIcon(icon)
        self.state_dmd2_button.setIcon(icon)
        self.state_dmd3_button.setIcon(icon)
        self.state_dmd4_button.setIcon(icon)
        self.state_dmd1_label.setText("<b>DMD 1:</b> No patterns in LUT ")
        self.state_dmd2_label.setText("<b>DMD 2:</b> No patterns in LUT ")
        self.state_dmd3_label.setText("<b>DMD 3:</b> No patterns in LUT ")
        self.state_dmd4_label.setText("<b>DMD 4:</b> No patterns in LUT ")

        device_index = [2, 3, 6, 7, 10, 11]
        for idx in device_index:
            if self.parent.gi8.platform_states[idx]:
                self.parent.current_image = self.parent.gi8.draw(idx, self.parent.current_image)
        self.parent.platform_status_label.setPixmap(self.parent.current_image)

    def define_heart_all_sequence(self):
        """Select the wide-field optical-stimulation preset for all DMDs."""
        for spinbox in [self.blue_pattern_dmd1, self.blue_pattern_dmd2, self.blue_pattern_dmd3, self.blue_pattern_dmd4]:
            spinbox.setValue(1)
        for spinbox in [self.red_pattern_dmd1, self.red_pattern_dmd2, self.red_pattern_dmd3, self.red_pattern_dmd4]:
            spinbox.setValue(1)

    def define_heart_apex_sequence(self):
        """Select the heart-apex optical-stimulation preset for all DMDs."""
        for spinbox in [self.blue_pattern_dmd1, self.blue_pattern_dmd2, self.blue_pattern_dmd3, self.blue_pattern_dmd4]:
            spinbox.setValue(6)
        for spinbox in [self.red_pattern_dmd1, self.red_pattern_dmd2, self.red_pattern_dmd3, self.red_pattern_dmd4]:
            spinbox.setValue(1)

    def define_heart_base_sequence(self):
        """Select the heart-base optical-stimulation preset for all DMDs."""
        for spinbox in [self.blue_pattern_dmd1, self.blue_pattern_dmd2, self.blue_pattern_dmd3, self.blue_pattern_dmd4]:
            spinbox.setValue(5)
        for spinbox in [self.red_pattern_dmd1, self.red_pattern_dmd2, self.red_pattern_dmd3, self.red_pattern_dmd4]:
            spinbox.setValue(1)

    def define_heart_dx_sequence(self):
        """Select the right-side optical-stimulation pattern combination."""
        self.blue_pattern_dmd1.setValue(3)
        self.blue_pattern_dmd2.setValue(1)
        self.blue_pattern_dmd3.setValue(4)
        self.blue_pattern_dmd4.setValue(2)
        for spinbox in [self.red_pattern_dmd1, self.red_pattern_dmd2, self.red_pattern_dmd3, self.red_pattern_dmd4]:
            spinbox.setValue(1)

    def define_heart_sx_sequence(self):
        """Select the left-side optical-stimulation pattern combination."""
        self.blue_pattern_dmd1.setValue(4)
        self.blue_pattern_dmd2.setValue(2)
        self.blue_pattern_dmd3.setValue(3)
        self.blue_pattern_dmd4.setValue(1)
        for spinbox in [self.red_pattern_dmd1, self.red_pattern_dmd2, self.red_pattern_dmd3, self.red_pattern_dmd4]:
            spinbox.setValue(1)

    def define_heart_line_sequence(self):
        """Select a line-stimulation preset using the configured line width."""
        for spinbox in [self.blue_pattern_dmd1, self.blue_pattern_dmd2, self.blue_pattern_dmd3, self.blue_pattern_dmd4]:
            spinbox.setValue(9 + self.line_width.value())
        for spinbox in [self.red_pattern_dmd1, self.red_pattern_dmd2, self.red_pattern_dmd3, self.red_pattern_dmd4]:
            spinbox.setValue(1)

    def enable_preview_button(self, cam1, cam2, cam3, cam4):
        """Initialize single-frame preview acquisition for four cameras.

        Parameters
        ----------
        cam1, cam2, cam3, cam4 : camera
            Camera-controller objects used by the asynchronous preview thread.
        """
        self.enable_preview.setEnabled(True)

        self.acquire_single_frame_thread = AcquireSingleThread(cam1, cam2, cam3, cam4, parent=self)
        self.acquire_single_frame_thread.finished_signal.connect(self.enable_preview_buttons)

    def enable_preview_buttons(self, frame1, frame2, frame3, frame4):
        """Display newly acquired preview frames and enable LUT controls.

        Parameters
        ----------
        frame1, frame2, frame3, frame4 : object
            Frame objects acquired from the four cameras.
        """
        sf.show_frame_x_thread(frame1, self.preview_cam1)
        sf.show_frame_x_thread(frame2, self.preview_cam2)
        sf.show_frame_x_thread(frame3, self.preview_cam3)
        sf.show_frame_x_thread(frame4, self.preview_cam4)

        sf.set_levels_histogram(self.preview_cam1)
        sf.set_levels_histogram(self.preview_cam2)
        sf.set_levels_histogram(self.preview_cam3)
        sf.set_levels_histogram(self.preview_cam4)

        self.parent.control_camera_gui.subarray_mode(False)

        self.preview_dmd1_button.setEnabled(True)
        self.preview_dmd2_button.setEnabled(True)
        self.preview_dmd3_button.setEnabled(True)
        self.preview_dmd4_button.setEnabled(True)

        self.frame_cam1 = frame1
        self.frame_cam2 = frame2
        self.frame_cam3 = frame3
        self.frame_cam4 = frame4

    def pause_sequence(self):
        """Pause pattern display on the selected or all connected DMDs.

        The method also restores the relevant selection controls and updates the
        platform-status diagram. The command is blocked while the parent window marks
        the PCIe command path as busy.
        """
        if self.parent.avoid_overray:
            QMessageBox.warning(self, "Warning", "Please turn off the DMDs before sending this command. Risk of command overload to the PCIe-6612!")
            return

        self.start_done = False

        if self.use_selection_dmd.isChecked():
            if self.dmd1_radiobutton.isChecked():
                sf.select_channel(1)
                comm.pause_display()

                device_index = [10, 11]
                for idx in device_index:
                    self.parent.current_image = self.parent.gi8.draw(idx, self.parent.current_image)
                self.parent.platform_status_label.setPixmap(self.parent.current_image)
            if self.dmd2_radiobutton.isChecked():
                sf.select_channel(2)
                comm.pause_display()

                self.parent.current_image = self.parent.gi8.draw(7, self.parent.current_image)
                self.parent.platform_status_label.setPixmap(self.parent.current_image)
            if self.dmd3_radiobutton.isChecked():
                sf.select_channel(3)
                comm.pause_display()

                device_index = [2, 3]
                for idx in device_index:
                    self.parent.current_image = self.parent.gi8.draw(idx, self.parent.current_image)
                self.parent.platform_status_label.setPixmap(self.parent.current_image)
            if self.dmd4_radiobutton.isChecked():
                sf.select_channel(4)
                comm.pause_display()

                self.parent.current_image = self.parent.gi8.draw(6, self.parent.current_image)
                self.parent.platform_status_label.setPixmap(self.parent.current_image)

            self.dmd1_radiobutton.setEnabled(True)
            self.dmd2_radiobutton.setEnabled(True)
            self.dmd3_radiobutton.setEnabled(True)
            self.dmd4_radiobutton.setEnabled(True)

        else:
            for i in self.dmd_connected:
                sf.select_channel(i)
                comm.pause_display()

            device_index = [2, 3, 6, 7, 10, 11]
            for idx in device_index:
                self.parent.current_image = self.parent.gi8.draw(idx, self.parent.current_image)
            self.parent.platform_status_label.setPixmap(self.parent.current_image)

        sf.select_channel(0)
        self.start_button.setEnabled(True)

    def prepare_all_patterns_to_lut(self):
        """Start sequential LUT configuration for every connected DMD."""
        if self.parent.avoid_overray:
            QMessageBox.warning(self, "Warning", "Please turn off the DMDs before sending this command. Risk of command overload to the PCIe-6612!")
            return

        self.index_dmd_selected = 0
        self.dmd_selected = self.dmd_connected[self.index_dmd_selected]
        self.all_together = True
        self.wait = True
        self.warnings_lut = []
        self.add_all_patterns_to_lut()

    def remove_splash_image(self):
        """Remove the selected splash image from the editable firmware list.

        Image counters, index limits, and the preview area are updated after removal.
        """
        index = self.select_index_spinbox.value()
        del self.m_added_splash_images[index]

        self.m_splash_image_count -= 1
        sf.clear_layout(self.show_pattern_layout)
        self.update_scroll_area()

        self.m_splash_image_add_index -= 1
        self.m_splash_image_removed += 1
        self.select_index_spinbox.setRange(0, self.m_splash_image_add_index)
        self.total_images_label.setText(str(self.m_splash_image_count))
        self.images_removed_label.setText(str(self.m_splash_image_removed))

    def save_firmware_updates(self):
        """Choose an output file and start rebuilding the modified firmware."""
        self.file_name, _ = QFileDialog.getSaveFileName(
            parent=self,
            caption="Enter name of new Image to be built",
            directory=str(cfg.PATTERN_REPOSITORY),
            filter="*.img *.bin"
        )
        if not self.file_name:
            return

        self.modify_firmware_thread.start()

    def send_command_to_dac(self, dmd):
        """Send the selected DMD LED-current settings to the DAC controller.

        Parameters
        ----------
        dmd : int
            DMD identifier in the range 1--4.

        Notes
        -----
        The GUI values are expressed in amperes. They are scaled by ``0.125`` before
        being inserted into the command dictionary sent to the external DAC service.
        """
        if dmd == 1:
            red_current = self.red_led_power_dmd1.value()
            blue_current = self.blue_led_power_dmd1.value()
            #self.new_info_signal.emit("dmd_info", ("DMD 1", red_current, blue_current), "led_currents")
            self.parent.dmd1_info.setText(f"""
                                            <b>DMD 1:</b>
                                            <ul>
                                                <li>Red LED Current: {self.red_led_power_dmd1.value()} A</li>
                                                <li>Blue LED Current: {self.blue_led_power_dmd1.value()} A</li>
                                                </ul>
                                        """)

            self.command_dict['0'] = 0.125 * red_current
            self.command_dict['1'] = 0.125 * blue_current

        elif dmd == 2:
            red_current = self.red_led_power_dmd2.value()
            blue_current = self.blue_led_power_dmd2.value()
            self.parent.dmd2_info.setText(f"""
                                <b>DMD 2:</b>
                                <ul>
                                    <li>Red LED Current: {self.red_led_power_dmd2.value()} A</li>
                                    <li>Blue LED Current: {self.blue_led_power_dmd2.value()} A</li>
                                    </ul>
                            """)

            self.command_dict['4'] = 0.125 * red_current
            self.command_dict['5'] = 0.125 * blue_current

        elif dmd == 3:
            red_current = self.red_led_power_dmd3.value()
            blue_current = self.blue_led_power_dmd3.value()
            self.parent.dmd3_info.setText(f"""
                                <b>DMD 3:</b>
                                <ul>
                                    <li>Red LED Current: {self.red_led_power_dmd3.value()} A</li>
                                    <li>Blue LED Current: {self.blue_led_power_dmd3.value()} A</li>
                                    </ul>
                            """)

            self.command_dict['8'] = 0.125 * red_current
            self.command_dict['9'] = 0.125 * blue_current

        elif dmd == 4:
            red_current = self.red_led_power_dmd4.value()
            blue_current = self.blue_led_power_dmd4.value()
            self.parent.dmd4_info.setText(f"""
                                            <b>DMD 4:</b>
                                            <ul>
                                                <li>Red LED Current: {self.red_led_power_dmd4.value()} A</li>
                                                <li>Blue LED Current: {self.blue_led_power_dmd4.value()} A</li>
                                                </ul>
                                        """)

            self.command_dict['12'] = 0.125 * red_current
            self.command_dict['13'] = 0.125 * blue_current

        sf.run_server_32bit()
        sf.send_command_to_board(self.command_dict)

    def show_patterns(self, browse):
        """Load firmware patterns into the scrollable preview area.

        Parameters
        ----------
        browse : bool
            When ``True``, display the firmware selected through the file browser.
            When ``False``, display the first firmware file in ``flash_firmware``.
        """

        sf.clear_layout(self.show_pattern_layout)

        if browse and self.pattern_file_path.text() and self.file_path:
            self.file_to_show = self.file_path
            self.show_images_thread.start()

        elif not browse:
            file = os.listdir("flash_firmware")[0]

            self.file_to_show = os.path.join("flash_firmware", file)
            self.show_images_thread.start()

    def start_sequence(self, warning=True, draw=True):
        """Start pattern display on the selected or all connected DMDs.

        Parameters
        ----------
        warning : bool, default=True
            Show a summary warning for DMDs that could not be started.
        draw : bool, default=True
            Update the platform-status diagram when all connected DMDs are started.

        The operation is rejected if no LUT is configured or if the parent window has
        blocked additional PCIe commands.
        """
        if self.parent.avoid_overray:
            QMessageBox.warning(self, "Warning", "Please turn off the DMDs before sending this command. Risk of command overload to the PCIe-6612!")
            return

        for label in [self.state_dmd1_label, self.state_dmd2_label, self.state_dmd3_label, self.state_dmd4_label]:
            if label.text() == "<b>DMD 1:</b> No patterns in LUT " or label.text() == "<b>DMD 2:</b> No patterns in LUT " or label.text() == "<b>DMD 3:</b> No patterns in LUT " or label.text() == "<b>DMD 4:</b> No patterns in LUT ":
                QMessageBox.warning(self, "Warning", "Please add patterns to the LUT before starting the sequence!")
                return

        warnings = []
        self.start_done = True
        self.start_button.setEnabled(False)

        if self.use_selection_dmd.isChecked():
            self.dmd1_radiobutton.setEnabled(False)
            self.dmd2_radiobutton.setEnabled(False)
            self.dmd3_radiobutton.setEnabled(False)
            self.dmd4_radiobutton.setEnabled(False)

            if self.dmd1_radiobutton.isChecked():
                if 1 in self.dmd_connected:
                    sf.select_channel(1)
                    comm.pattern_display(2)

                    device_index = [10, 11]
                    for idx in device_index:
                        self.parent.current_image = self.parent.gi8.draw(idx, self.parent.current_image)
                    self.parent.platform_status_label.setPixmap(self.parent.current_image)
                else:
                    self.dmd1_radiobutton.setChecked(False)
                    warnings.append("DMD 1")

            if self.dmd2_radiobutton.isChecked():
                if 2 in self.dmd_connected:
                    sf.select_channel(2)
                    comm.pattern_display(2)

                    self.parent.current_image = self.parent.gi8.draw(7, self.parent.current_image)
                    self.parent.platform_status_label.setPixmap(self.parent.current_image)
                else:
                    self.dmd2_radiobutton.setChecked(False)
                    warnings.append("DMD 2")

            if self.dmd3_radiobutton.isChecked():
                if 3 in self.dmd_connected:
                    sf.select_channel(3)
                    comm.pattern_display(2)

                    device_index = [2, 3]
                    for idx in device_index:
                        self.parent.current_image = self.parent.gi8.draw(idx, self.parent.current_image)
                    self.parent.platform_status_label.setPixmap(self.parent.current_image)
                else:
                    self.dmd3_radiobutton.setChecked(False)
                    warnings.append("DMD 3")

            if self.dmd4_radiobutton.isChecked():
                if 4 in self.dmd_connected:
                    sf.select_channel(4)
                    comm.pattern_display(2)

                    self.parent.current_image = self.parent.gi8.draw(6, self.parent.current_image)
                    self.parent.platform_status_label.setPixmap(self.parent.current_image)
                else:
                    self.dmd4_radiobutton.setChecked(False)
                    warnings.append("DMD 4")

        else:
            if 1 in self.dmd_connected:
                sf.select_channel(1)
                comm.pattern_display(2)

                if draw:
                    device_index = [10, 11]
                    for idx in device_index:
                        self.parent.current_image = self.parent.gi8.draw(idx, self.parent.current_image)
                    self.parent.platform_status_label.setPixmap(self.parent.current_image)
            else:
                warnings.append("DMD 1")
            if 2 in self.dmd_connected:
                sf.select_channel(2)
                comm.pattern_display(2)

                if draw:
                    self.parent.current_image = self.parent.gi8.draw(7, self.parent.current_image)
                    self.parent.platform_status_label.setPixmap(self.parent.current_image)
            else:
                warnings.append("DMD 2")
            if 3 in self.dmd_connected:
                sf.select_channel(3)
                comm.pattern_display(2)

                if draw:
                    device_index = [2, 3]
                    for idx in device_index:
                        self.parent.current_image = self.parent.gi8.draw(idx, self.parent.current_image)
                    self.parent.platform_status_label.setPixmap(self.parent.current_image)
            else:
                warnings.append("DMD 3")
            if 4 in self.dmd_connected:
                sf.select_channel(4)
                comm.pattern_display(2)

                if draw:
                    self.parent.current_image = self.parent.gi8.draw(6, self.parent.current_image)
                    self.parent.platform_status_label.setPixmap(self.parent.current_image)
            else:
                warnings.append("DMD 4")

        if warning and warnings:
            QMessageBox.warning(self, "Warning", f"The following DMDs are not connected: {', '.join(warnings)}")

        sf.select_channel(0)

    def stop_sequence(self):
        """Stop pattern display on the selected or all connected DMDs.

        The method restores the GUI controls, resets the active DMD channel, and updates
        the platform-status diagram.
        """
        if self.parent.avoid_overray:
            QMessageBox.warning(self, "Warning", "Please turn off the DMDs before sending this command. Risk of command overload to the PCIe-6612!")
            return

        self.start_done = False

        if self.use_selection_dmd.isChecked():
            if self.dmd1_radiobutton.isChecked():
                sf.select_channel(1)
                comm.stop_display()

                device_index = [10, 11]
                for idx in device_index:
                    self.parent.current_image = self.parent.gi8.draw(idx, self.parent.current_image)
                self.parent.platform_status_label.setPixmap(self.parent.current_image)
            if self.dmd2_radiobutton.isChecked():
                sf.select_channel(2)
                comm.stop_display()

                self.parent.current_image = self.parent.gi8.draw(7, self.parent.current_image)
                self.parent.platform_status_label.setPixmap(self.parent.current_image)
            if self.dmd3_radiobutton.isChecked():
                sf.select_channel(3)
                comm.stop_display()

                device_index = [2, 3]
                for idx in device_index:
                    self.parent.current_image = self.parent.gi8.draw(idx, self.parent.current_image)
                self.parent.platform_status_label.setPixmap(self.parent.current_image)
            if self.dmd4_radiobutton.isChecked():
                sf.select_channel(4)
                comm.stop_display()

                self.parent.current_image = self.parent.gi8.draw(6, self.parent.current_image)
                self.parent.platform_status_label.setPixmap(self.parent.current_image)

            self.dmd1_radiobutton.setEnabled(True)
            self.dmd2_radiobutton.setEnabled(True)
            self.dmd3_radiobutton.setEnabled(True)
            self.dmd4_radiobutton.setEnabled(True)

        else:
            for i in self.dmd_connected:
                sf.select_channel(i)
                comm.stop_display()

            device_index = [2, 3, 6, 7, 10, 11]
            for idx in device_index:
                self.parent.current_image = self.parent.gi8.draw(idx, self.parent.current_image)
            self.parent.platform_status_label.setPixmap(self.parent.current_image)

        sf.select_channel(0)
        self.start_button.setEnabled(True)

    def update_build(self, new_frmw_image):
        """Write a rebuilt firmware image to disk and reset editing controls.

        Parameters
        ----------
        new_frmw_image : bytes or bytearray
            Complete firmware image produced by the firmware-modification worker.
        """
        try:
            with open(self.file_name, "wb+") as out_file:
                out_file.write(new_frmw_image)
        except IOError:
            QMessageBox.critical(self, "Error", "Cannot open output file for writing.")
            return

        sf.clear_layout(self.show_pattern_layout)
        self.original_images_label.setText("0")
        self.total_images_label.setText("0")
        self.images_added_label.setText("0")
        self.images_removed_label.setText("0")
        self.select_index_spinbox.setRange(0, 0)
        self.firm_file_line.clear()
        QMessageBox.information(self, "Success", "Build Complete.")

    def update_dmd_connection(self):
        """Refresh the local list of connected DMD identifiers from the parent."""
        self.dmd_connected = self.parent.dmd_connected

    def update_gui(self, success):
        """Handle completion of a pattern-LUT validation operation.

        Parameters
        ----------
        success : bool
            Whether LUT creation and validation completed successfully.

        When configuring all DMDs, this method advances to the next connected device.
        Otherwise, it restores the idle GUI state.
        """
        if self.all_together:
            self.index_dmd_selected += 1
            if self.index_dmd_selected < len(self.dmd_connected):
                self.dmd_selected = self.dmd_connected[self.index_dmd_selected]
            if success:
                self.start_button.setEnabled(True)
                self.pause_button.setEnabled(True)
                self.stop_button.setEnabled(True)
                self.add_all_patterns_to_lut()
            else:
                self.add_all_patterns_to_lut()

        else:
            sf.select_channel(0)

            self.lut_infos_labels.setText("No Process in Progress")
            self.progress_bar_lut.setValue(0)

            if success:
                self.start_button.setEnabled(True)
                self.pause_button.setEnabled(True)
                self.stop_button.setEnabled(True)
                self.wait = False
            else:
                return

    def update_image_index(self):
        """Read the number of stored patterns and update all index selectors."""
        if len(self.dmd_connected) > 0:
            sf.select_channel(self.dmd_connected[0])

            num_images_in_flash = comm.get_num_images_in_flash()
            self.parent.experiment_info["numb_pattern_file"] = num_images_in_flash
            self.red_pattern_dmd1.setRange(0, num_images_in_flash - 1)
            self.blue_pattern_dmd1.setRange(0, num_images_in_flash - 1)
            self.red_pattern_dmd2.setRange(0, num_images_in_flash - 1)
            self.blue_pattern_dmd2.setRange(0, num_images_in_flash - 1)
            self.red_pattern_dmd3.setRange(0, num_images_in_flash - 1)
            self.blue_pattern_dmd3.setRange(0, num_images_in_flash - 1)
            self.red_pattern_dmd4.setRange(0, num_images_in_flash - 1)
            self.blue_pattern_dmd4.setRange(0, num_images_in_flash - 1)

            sf.select_channel(0)

    def upload_patterns_dmd1(self):
        """Prepare the selected firmware and begin upload to the first DMD.

        A copy of the selected file is stored in ``flash_firmware`` for local reuse.
        Uploads then proceed through the connected DMD list asynchronously.
        """
        directory = 'flash_firmware'
        files = os.listdir(directory)

        if files:
            for filename in files:
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)

        file_name = os.path.basename(self.file_path)
        destination_file = os.path.join(directory, file_name)
        shutil.copy(self.file_path, destination_file)

        self.index_to_upload = 0
        sf.select_channel(self.dmd_connected[self.index_to_upload])
        self.dmd_selected = self.dmd_connected[self.index_to_upload]
        self.upload_patterns_thread.start()

    def upload_patterns_other_dmds(self, success):
        """Handle one firmware-upload result and continue with the next DMD.

        Parameters
        ----------
        success : bool
            Whether the upload to the current DMD completed successfully.
        """
        self.upload_patterns_thread.quit()
        self.upload_patterns_thread.wait()

        if success:
            if self.dmd_connected[self.index_to_upload] == 1:
                ss.update_toolbutton_style(self.dmd1_icon_upload, 'on')

            elif self.dmd_connected[self.index_to_upload] == 2:
                ss.update_toolbutton_style(self.dmd2_icon_upload, 'on')

            elif self.dmd_connected[self.index_to_upload] == 3:
                ss.update_toolbutton_style(self.dmd3_icon_upload, 'on')

            elif self.dmd_connected[self.index_to_upload] == 4:
                ss.update_toolbutton_style(self.dmd4_icon_upload, 'on')

            self.index_to_upload += 1
            if self.index_to_upload < len(self.dmd_connected):
                sf.select_channel(self.dmd_connected[self.index_to_upload])
                self.dmd_selected = self.dmd_connected[self.index_to_upload]
                self.upload_patterns_thread.start()

            else:
                self.update_image_index()

        else:
            ss.update_toolbutton_style(self.dmd1_icon_upload, 'off')

    def update_progress_bar_lut(self, progress):
        """Update the shared LUT-validation progress bar.

        Parameters
        ----------
        progress : int
            Progress percentage emitted by a LUT-validation worker.
        """
        self.progress_bar_lut.setValue(progress)

    def update_progress_bar_upload(self, progress):
        """Update the firmware-upload progress bar for the active DMD.

        Parameters
        ----------
        progress : int
            Progress percentage emitted by the upload worker.
        """
        if self.dmd_selected == 1:
            self.progress_bar_dmd1.setValue(progress)
        elif self.dmd_selected == 2:
            self.progress_bar_dmd2.setValue(progress)
        elif self.dmd_selected == 3:
            self.progress_bar_dmd3.setValue(progress)
        elif self.dmd_selected == 4:
            self.progress_bar_dmd4.setValue(progress)

    def update_scroll_area(self, ret=0):
        """Refresh the firmware-pattern preview and report parsing errors.

        Parameters
        ----------
        ret : int, default=0
            Firmware parsing result. Zero indicates success; negative values identify
            memory, signature, version, header, or output-file errors.
        """
        if ret == -1:
            QMessageBox.critical(self, "Error", "Fatal Error! System Run out of memory!")
            return
        elif ret == -2:
            QMessageBox.critical(self, "Error", "Firmware Image Signature doesn't match! Bad Firmware Image!")
            return
        elif ret == -3:
            QMessageBox.warning(self, "Warning", "Old version of Firmware detected.\n\nDownload the latest release from http://www.ti.com/tool/dlpr350.")
        elif ret == -4:
            QMessageBox.warning(self, "Warning", "Firmware Image Header format not recognized!")
        elif ret == -5:
            QMessageBox.warning(self, "Warning", "Cannot save pattern image as .bmp to display. Try relocating GUI to a folder that has write permission.")

        self.upload_button.setEnabled(True)

        self.original_images_label.setText(str(self.m_splash_image_original))
        self.total_images_label.setText(str(self.m_splash_image_count))
        self.select_index_spinbox.setRange(0, self.m_splash_image_count - 1)

        for i in range(self.m_splash_image_count):
            img_file = QFile(self.m_added_splash_images[i])
            img = QImage(912, 1140, QImage.Format.Format_RGB32)
            img_size = QSize(140, 150)

            img_file.open(QIODevice.OpenModeFlag.ReadOnly)
            img.load(img_file.fileName())

            group_box = QGroupBox()
            group_box.setStyleSheet("""
                                    QGroupBox {
                                        background-color: #d3d3d3;
                                        border: 2px solid blue;
                                        border-radius: 10px;
                                        margin-top: 15px;
                                        box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.2); /* effetto ombra */
                                    }

                                    QGroupBox:title {
                                        subcontrol-origin: margin;
                                        subcontrol-position: top center;
                                        padding: 0 5px;
                                        background-color: blue;
                                        color: white;
                                        font-weight: bold;
                                        border-radius: 5px;
                                    }
                                """)
            group_box_layout = QVBoxLayout()
            number_label = QLabel(f"<b>Index:</b><br>  <br> {i}")
            number_label.setFont(QFont("Arial", 12))
            number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            image_label = QLabel()
            image_label.setFixedSize(140, 150)
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            pixmap = QPixmap.fromImage(img)
            pixmap = pixmap.scaled(img_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

            image_label.setPixmap(pixmap)

            group_box_layout.addWidget(image_label, alignment=Qt.AlignmentFlag.AlignCenter)
            group_box_layout.addWidget(number_label, alignment=Qt.AlignmentFlag.AlignCenter)

            group_box.setLayout(group_box_layout)

            self.show_pattern_layout.addWidget(group_box)
        self.show_pattern_layout.addStretch()

    def closeEvent(self, event):
        """Ask for confirmation before closing the DMD manager window.

        Parameters
        ----------
        event : QCloseEvent
            Qt close event that is accepted or ignored according to the user's choice.
        """
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Are you sure you want to close the window?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()