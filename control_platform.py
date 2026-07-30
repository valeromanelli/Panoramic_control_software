"""Main PyQt6 application for configuring and running platform experiments."""

import runtime_config as cfg
import ctypes
import math
import os
import sys
import time
import nidaqmx
import numpy as np
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap, QIcon, QIntValidator
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication, QCheckBox, QHBoxLayout, QGroupBox, \
    QLineEdit, QFormLayout, QPushButton, QMessageBox, QLabel, QToolButton, QGridLayout, QSpacerItem, QSizePolicy, \
    QListWidget, QDoubleSpinBox, QDialog, QSpinBox
from nidaqmx.constants import LineGrouping
from support_classes import NotesDialog, FindThresholdDialog
from threads import CheckCameraConnectionThread, CheckDMDConnectionThread, PlaySequenceThread, StartAlignmentThread, \
    StopAlignmentThread, GenerateSequenceThread, EnableDMDThread, SendEnableDMDThread, StartTaskThread
import support_functions as sf
from configure_dmd import ConfigureDMD
from configure_camera import ConfigureCamera
import style_sheet as ss
from datetime import datetime
import tifffile as tiff
from giotto import Giotto


class DefineSequenceAndControlPlatformGUI(QMainWindow):
    """Main window that coordinates experiment phases and connected devices."""
    dmd_connected_signal = pyqtSignal()
    stop_condition_signal = pyqtSignal(int)
    enable_preview_signal = pyqtSignal(object, object, object, object)
    stop_experiment_signal = pyqtSignal()
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Platform Manager")
        self.setWindowIcon(QIcon("Icons/panoramic.png"))
        self.setGeometry(100, 30, 400, 190)

        # VARIABLES
        self.experiment_info = {
            "dmd_info": {},
            "cam_info": {},
        }
        self.electrical_stimulation = {}

        self.scan_rate = 10000000                       # Hz

        self.scan_time = 1 / self.scan_rate             # s

        self.cam1 = None
        self.cam2 = None
        self.cam3 = None
        self.cam4 = None
        self.cameras_connected = []

        self.experiment_notes_gui = NotesDialog()
        self.find_threshold_gui = FindThresholdDialog()
        self.control_dmd_gui = None
        self.master_task = None
        self.alignment_task = None
        self.parent_directory = str(cfg.CAMERA_DATA_DIRECTORY)
        self.today_date = datetime.now().strftime("%Y-%m-%d")
        self.enable_timer = QTimer(self)
        self.elapsed_seconds = 60
        self.start_pushed = False
        self.avoid_overray = False
        self.ramp_pulses_array = []

        self.experiment_info["date"] = self.today_date
        self.experiment_info["alignment_done"] = False
        self.experiment_info["stopped_before"] = False

        self.check_cameras_connection_thread = CheckCameraConnectionThread()
        self.check_dmds_connection_thread = CheckDMDConnectionThread()
        self.enable_dmd_thread = EnableDMDThread(parent=self)
        self.generate_sequence_thread = GenerateSequenceThread(parent=self)
        self.play_sequence_thread = PlaySequenceThread(parent=self)
        self.send_enable_dmd_thread = SendEnableDMDThread(parent=self)
        self.start_alignment_thread = StartAlignmentThread(parent=self)
        self.start_task_thread = StartTaskThread(parent=self)
        self.stop_alignment_thread = StopAlignmentThread(parent=self)

        # Widget layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # UPPER LAYOUT
        upper_layout = QHBoxLayout()

        # Phase manager
        phase_manager_group = QGroupBox("Phase Manager")
        phase_manager_group.setFixedHeight(360)
        phase_manager_layout = QVBoxLayout()

        checkbox_font = QFont("Arial", 12)

        height = 110
        groupbox_layout = QHBoxLayout()
        self.pre_ill_group = QGroupBox()
        self.pre_ill_group.setFixedHeight(height)
        self.pre_ill_group.setStyleSheet("""
                QGroupBox {
                    background-color: #f0f0f0;
                    border: 2px solid gray;
                    border-radius: 10px;
                    margin-top: 15px;
                    box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.2); 
                }
            """)
        pre_ill_layout = QVBoxLayout()
        self.pre_ill_phase_check = QCheckBox("Pre-Illumination")
        ss.update_checkbox_style(self.pre_ill_phase_check)
        self.pre_ill_phase_check.setFont(checkbox_font)
        self.pre_ill_phase_check.setCursor(Qt.CursorShape.PointingHandCursor)
        form_layout = QFormLayout()
        self.pre_ill_time_line = QLineEdit()
        ss.update_lineedit_style(self.pre_ill_time_line)
        self.pre_ill_time_line.setValidator(QIntValidator())
        self.pre_ill_time_line.setEnabled(False)
        self.label1 = QLabel("Time (ms):")
        self.label1.setStyleSheet("""
                                QLabel {
                                    background-color: #f0f0f0;
                                }
                            """)
        form_layout.addRow(self.label1, self.pre_ill_time_line)
        pre_ill_layout.addWidget(self.pre_ill_phase_check)
        pre_ill_layout.addLayout(form_layout)
        self.pre_ill_group.setLayout(pre_ill_layout)

        self.pre_stim_group = QGroupBox()
        self.pre_stim_group.setFixedHeight(height)
        self.pre_stim_group.setStyleSheet("""
                        QGroupBox {
                            background-color: #f0f0f0;
                            border: 2px solid gray;
                            border-radius: 10px;
                            margin-top: 15px;
                            box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.2); 
                        }
                    """)
        pre_stim_layout = QVBoxLayout()
        self.pre_stim_phase_check = QCheckBox("Pre-Stimulation")
        ss.update_checkbox_style(self.pre_stim_phase_check)
        self.pre_stim_phase_check.setFont(checkbox_font)
        self.pre_stim_phase_check.setCursor(Qt.CursorShape.PointingHandCursor)
        form_layout = QFormLayout()
        self.pre_stim_time_line = QLineEdit()
        ss.update_lineedit_style(self.pre_stim_time_line)
        self.pre_stim_time_line.setValidator(QIntValidator())
        self.pre_stim_time_line.setEnabled(False)
        self.label2 = QLabel("Time (ms):")
        self.label2.setStyleSheet("""
                            QLabel {
                                background-color: #f0f0f0;
                            }
                        """)
        form_layout.addRow(self.label2, self.pre_stim_time_line)
        pre_stim_layout.addWidget(self.pre_stim_phase_check)
        pre_stim_layout.addLayout(form_layout)
        self.pre_stim_group.setLayout(pre_stim_layout)

        self.stim_group = QGroupBox()
        self.stim_group.setStyleSheet("""
                        QGroupBox {
                            background-color: #f0f0f0;
                            border: 2px solid gray;
                            border-radius: 10px;
                            margin-top: 15px;
                            box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.2); 
                        }
                    """)
        stim_layout = QVBoxLayout()
        self.stim_phase_check = QCheckBox("Stimulation")
        ss.update_checkbox_style(self.stim_phase_check)
        self.stim_phase_check.setFont(checkbox_font)
        self.stim_phase_check.setCursor(Qt.CursorShape.PointingHandCursor)
        form_layout = QFormLayout()
        self.stim_time_line = QLineEdit()
        ss.update_lineedit_style(self.stim_time_line)
        self.stim_time_line.setValidator(QIntValidator())
        self.stim_time_line.setEnabled(False)
        self.label3 = QLabel("Time (ms):")
        self.label3.setStyleSheet("""
                                QLabel {
                                    background-color: #f0f0f0;
                                }
                            """)
        form_layout.addRow(self.label3, self.stim_time_line)
        stim_layout.addWidget(self.stim_phase_check)
        stim_layout.addLayout(form_layout)
        self.stim_group.setLayout(stim_layout)

        self.post_stim_group = QGroupBox()
        self.post_stim_group.setStyleSheet("""
                                QGroupBox {
                                    background-color: #f0f0f0;
                                    border: 2px solid gray;
                                    border-radius: 10px;
                                    margin-top: 15px;
                                    box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.2); 
                                }
                            """)
        post_stim_layout = QVBoxLayout()
        self.post_stim_phase_check = QCheckBox("Post-Stimulation")
        ss.update_checkbox_style(self.post_stim_phase_check)
        self.post_stim_phase_check.setFont(checkbox_font)
        self.post_stim_phase_check.setCursor(Qt.CursorShape.PointingHandCursor)
        form_layout = QFormLayout()
        self.post_stim_time_line = QLineEdit()
        ss.update_lineedit_style(self.post_stim_time_line)
        self.post_stim_time_line.setValidator(QIntValidator())
        self.post_stim_time_line.setEnabled(False)
        self.label4 = QLabel("Time (ms):")
        self.label4.setStyleSheet("""
                                    QLabel {
                                        background-color: #f0f0f0;
                                    }
                                """)
        form_layout.addRow(self.label4, self.post_stim_time_line)
        post_stim_layout.addWidget(self.post_stim_phase_check)
        post_stim_layout.addLayout(form_layout)
        self.post_stim_group.setLayout(post_stim_layout)

        self.cycle_group = QGroupBox()
        self.cycle_group.setStyleSheet("""
            QGroupBox {
                background-color: #f8f8f8;
                border: 2px dashed #888;
                border-radius: 10px;
                margin-top: 10px;
            }
        """)

        cycle_layout = QVBoxLayout()
        inner = QHBoxLayout()

        # Keep the internal phase boxes compact enough to fit the group.
        self.stim_group.setFixedWidth(190)
        self.post_stim_group.setFixedWidth(190)

        inner.addWidget(self.stim_group)
        inner.addWidget(self.post_stim_group)

        cycles_row = QHBoxLayout()
        cycles_label = QLabel("Cycles (Stim + Post):")
        cycles_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))

        self.cycle_spin = QSpinBox()
        self.cycle_spin.setRange(1, 999)
        self.cycle_spin.setValue(1)
        self.cycle_spin.setFixedWidth(70)

        cycles_row.addWidget(cycles_label)
        cycles_row.addStretch(1)
        cycles_row.addWidget(self.cycle_spin)

        cycle_layout.addLayout(inner)
        cycle_layout.addLayout(cycles_row)
        self.cycle_group.setLayout(cycle_layout)

        width = 200
        self.pre_ill_group.setFixedWidth(width)
        self.pre_stim_group.setFixedWidth(width)
        self.stim_group.setFixedWidth(width)
        self.post_stim_group.setFixedWidth(width)

        groupbox_layout.addWidget(self.pre_ill_group)
        groupbox_layout.addWidget(self.pre_stim_group)
        groupbox_layout.addWidget(self.cycle_group)

        duty_cycle_layout = QHBoxLayout()
        red_duty_cycle_layout = QFormLayout()
        self.red_power_value = QDoubleSpinBox()
        self.red_power_value.setFixedWidth(80)
        self.red_power_value.setRange(0.0, 2.1)
        self.red_power_value.setSingleStep(0.01)
        self.red_power_value.setDecimals(2)
        self.red_power_value.setValue(2.1)

        label_font = QFont("Arial", 10, QFont.Weight.Bold)

        red_power_label = QLabel("Red LED Intensity (mW/mm<sup>2</sup>):")
        red_power_label.setFont(label_font)
        red_power_label.setStyleSheet("""                   
                                    QLabel {
                                        color: #333;
                                        font-size: 11pt;
                                    }
                                """)
        red_dutycycle_label = QLabel("Duty Cycle Value:")
        red_dutycycle_label.setFont(QFont("Arial", 10))
        red_dutycycle_label.setStyleSheet("""                   
                                            QLabel {
                                                color: #333;
                                                font-size: 11pt;
                                            }
                                        """)
        self.red_dutycycle_value = QLabel("50.0 %")

        red_duty_cycle_layout.addRow(red_power_label, self.red_power_value)
        red_duty_cycle_layout.addRow(red_dutycycle_label, self.red_dutycycle_value)

        blue_duty_cycle_layout = QFormLayout()
        self.blue_power_value = QDoubleSpinBox()
        self.blue_power_value.setFixedWidth(80)
        self.blue_power_value.setRange(0.0, 0.7)
        self.blue_power_value.setSingleStep(0.01)
        self.blue_power_value.setDecimals(2)
        self.blue_power_value.setValue(0.7)

        blue_power_label = QLabel("Blue LED Intensity (mW/mm<sup>2</sup>):")
        blue_power_label.setFont(label_font)
        blue_power_label.setStyleSheet("""                   
                            QLabel {
                                color: #333;
                                font-size: 11pt;
                            }
                        """)
        blue_dutycycle_label = QLabel("Duty Cycle Value:")
        blue_dutycycle_label.setFont(QFont("Arial", 10))
        blue_dutycycle_label.setStyleSheet("""                   
                                            QLabel {
                                                color: #333;
                                                font-size: 11pt;
                                            }
                                        """)
        self.blue_dutycycle_value = QLabel("50.0 %")

        blue_duty_cycle_layout.addRow(blue_power_label, self.blue_power_value)
        blue_duty_cycle_layout.addRow(blue_dutycycle_label, self.blue_dutycycle_value)

        duty_cycle_layout.addLayout(red_duty_cycle_layout)
        duty_cycle_layout.addLayout(blue_duty_cycle_layout)

        buttons_layout = QHBoxLayout()
        self.generate_sequence_button = QPushButton("SEND SEQUENCE")
        self.generate_sequence_button.setFont(QFont("Arial", 14))
        self.generate_sequence_button.setFixedSize(250, 50)

        self.clear_sequence_button = QPushButton("CLEAR SEQUENCE")
        self.clear_sequence_button.setFont(QFont("Arial", 14))
        self.clear_sequence_button.setFixedSize(250, 50)

        self.find_threshold = QPushButton("Enable Threshold Potential Detection")

        buttons_layout.addWidget(self.generate_sequence_button, alignment=Qt.AlignmentFlag.AlignCenter)
        buttons_layout.addWidget(self.clear_sequence_button, alignment=Qt.AlignmentFlag.AlignCenter)

        phase_manager_layout.addLayout(groupbox_layout)
        phase_manager_layout.addLayout(duty_cycle_layout)
        phase_manager_layout.addWidget(self.find_threshold)
        phase_manager_layout.addLayout(buttons_layout)
        phase_manager_group.setLayout(phase_manager_layout)

        # Stimolazione elettrica
        stim_group = QGroupBox("Electrical Stimulation")
        stim_group.setFixedWidth(800)
        stim_layout = QGridLayout()

        self.constant_group = QGroupBox()
        self.constant_group.setFixedSize(300, 150)
        self.constant_group.setStyleSheet("""
                                        QGroupBox {
                                            background-color: #f0f0f0;
                                            border: 2px solid gray;
                                            border-radius: 10px;
                                            margin-top: 15px;
                                            box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.2); 
                                        }
                                    """)
        constant_layout = QVBoxLayout()
        self.constant_check = QCheckBox("Constant")
        ss.update_checkbox_style(self.constant_check)
        self.constant_check.setFont(checkbox_font)
        self.constant_check.setCursor(Qt.CursorShape.PointingHandCursor)
        del_dur_layout = QHBoxLayout()
        delay_layout = QFormLayout()
        self.delay_line = QLineEdit()
        ss.update_lineedit_style(self.delay_line)
        self.delay_line.setValidator(QIntValidator())
        self.delay_line.setEnabled(False)
        self.label5 = QLabel("Delay (ms):")
        self.label5.setStyleSheet("""
                            QLabel {
                                background-color: #f0f0f0;
                            }
                        """)
        delay_layout.addRow(self.label5, self.delay_line)
        duration_layout = QFormLayout()
        self.duration_line = QLineEdit()
        ss.update_lineedit_style(self.duration_line)
        self.duration_line.setValidator(QIntValidator())
        self.duration_line.setEnabled(False)
        self.label6 = QLabel("Duration (ms):")
        self.label6.setStyleSheet("""
                                    QLabel {
                                        background-color: #f0f0f0;
                                    }
                                """)
        duration_layout.addRow(self.label6, self.duration_line)
        del_dur_layout.addLayout(delay_layout)
        del_dur_layout.addLayout(duration_layout)
        frequency_layout = QFormLayout()
        self.frequency_line = QLineEdit()
        ss.update_lineedit_style(self.frequency_line)
        self.frequency_line.setValidator(QIntValidator())
        self.frequency_line.setEnabled(False)
        self.label7 = QLabel("Frequency (Hz):")
        self.label7.setStyleSheet("""
                                QLabel {
                                    background-color: #f0f0f0;
                                }
                            """)
        frequency_layout.addRow(self.label7, self.frequency_line)
        constant_layout.addWidget(self.constant_check)
        constant_layout.addLayout(del_dur_layout)
        constant_layout.addLayout(frequency_layout)
        self.constant_group.setLayout(constant_layout)

        self.s1s2_group = QGroupBox()
        self.s1s2_group.setFixedSize(300, 150)
        self.s1s2_group.setStyleSheet("""
                                                QGroupBox {
                                                    background-color: #f0f0f0;
                                                    border: 2px solid gray;
                                                    border-radius: 10px;
                                                    margin-top: 15px;
                                                    box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.2); 
                                                }
                                            """)
        s1s2_layout = QVBoxLayout()
        self.s1s2_check = QCheckBox("S1-Sn")
        ss.update_checkbox_style(self.s1s2_check)
        self.s1s2_check.setFont(checkbox_font)
        self.s1s2_check.setCursor(Qt.CursorShape.PointingHandCursor)
        s0_layout = QHBoxLayout()
        s0_cl_layout = QFormLayout()
        self.s0_cl_line = QLineEdit()
        ss.update_lineedit_style(self.s0_cl_line)
        self.s0_cl_line.setValidator(QIntValidator())
        self.s0_cl_line.setEnabled(False)
        self.label8 = QLabel("Starting (ms):")
        self.label8.setStyleSheet("""
                                    QLabel {
                                        background-color: #f0f0f0;
                                    }
                                """)
        s0_cl_layout.addRow(self.label8, self.s0_cl_line)
        s0_precond_layout = QFormLayout()
        self.s0_precond_line = QLineEdit()
        ss.update_lineedit_style(self.s0_precond_line)
        self.s0_precond_line.setValidator(QIntValidator())
        self.s0_precond_line.setEnabled(False)
        self.label9 = QLabel("Pre-Condition:")
        self.label9.setStyleSheet("""
                                    QLabel {
                                        background-color: #f0f0f0;
                                    }
                                """)
        s0_precond_layout.addRow(self.label9, self.s0_precond_line)
        s0_layout.addLayout(s0_cl_layout)
        s0_layout.addLayout(s0_precond_layout)

        sfstep_hor_layout = QHBoxLayout()
        sf_layout = QFormLayout()
        self.sf_cl_line = QLineEdit()
        ss.update_lineedit_style(self.sf_cl_line)
        self.sf_cl_line.setValidator(QIntValidator())
        self.sf_cl_line.setEnabled(False)
        self.label10 = QLabel("Final CL (ms):")
        self.label10.setStyleSheet("""
                                    QLabel {
                                        background-color: #f0f0f0;
                                    }
                                """)
        step_layout = QFormLayout()
        self.step_line = QLineEdit()
        ss.update_lineedit_style(self.step_line)
        self.step_line.setValidator(QIntValidator())
        self.step_line.setEnabled(False)
        self.label11 = QLabel("Step (ms):")
        self.label11.setStyleSheet("""
                                    QLabel {
                                        background-color: #f0f0f0;
                                    }
                                """)
        sf_layout.addRow(self.label10, self.sf_cl_line)
        step_layout.addRow(self.label11, self.step_line)
        sfstep_hor_layout.addLayout(sf_layout)
        sfstep_hor_layout.addLayout(step_layout)
        s1s2_layout.addWidget(self.s1s2_check)
        s1s2_layout.addLayout(s0_layout)
        s1s2_layout.addLayout(sfstep_hor_layout)
        self.s1s2_group.setLayout(s1s2_layout)

        self.ramp_group = QGroupBox()
        self.ramp_group.setFixedSize(600, 150)
        self.ramp_group.setStyleSheet("""
                                        QGroupBox {
                                            background-color: #f0f0f0;
                                            border: 2px solid gray;
                                            border-radius: 10px;
                                            margin-top: 15px;
                                            box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.2); 
                                        }
                                    """)
        ramp_layout = QVBoxLayout()
        self.ramp_check = QCheckBox("Ramp")
        ss.update_checkbox_style(self.ramp_check)
        self.ramp_check.setFont(checkbox_font)
        self.ramp_check.setCursor(Qt.CursorShape.PointingHandCursor)
        values_layout = QHBoxLayout()
        frequency_layout = QFormLayout()
        self.ramp_frequency = QLineEdit()
        ss.update_lineedit_style(self.ramp_frequency)
        self.ramp_frequency.setValidator(QIntValidator())
        self.ramp_frequency.setEnabled(False)
        self.label12 = QLabel("Frequency (Hz):")
        self.label12.setStyleSheet("""
                                    QLabel {
                                        background-color: #f0f0f0;
                                    }
                                """)
        frequency_layout.addRow(self.label12, self.ramp_frequency)
        self.add_value = QPushButton("Add")
        self.remove_value = QPushButton("Remove")
        self.clear_array = QPushButton("Clear Array")
        for button in [self.add_value, self.remove_value, self.clear_array]:
            button.setEnabled(False)
        numb_pulses_layout = QFormLayout()
        self.label13 = QLabel("Number of pulses:")
        self.label13.setStyleSheet("""
                                            QLabel {
                                                background-color: #f0f0f0;
                                            }
                                        """)
        self.numb_pulses_ramp = QLineEdit()
        ss.update_lineedit_style(self.numb_pulses_ramp)
        self.numb_pulses_ramp.setValidator(QIntValidator())
        self.numb_pulses_ramp.setEnabled(False)
        numb_pulses_layout.addRow(self.label13, self.numb_pulses_ramp)
        values_layout.addLayout(frequency_layout)
        values_layout.addWidget(self.add_value)
        values_layout.addWidget(self.remove_value)
        values_layout.addWidget(self.clear_array)
        values_layout.addLayout(numb_pulses_layout)
        self.ramp_values_list = QLabel("Ramp Values: NA")
        self.ramp_values_list.setStyleSheet("""
                                            QLabel {
                                                background-color: #f0f0f0;
                                            }
                                        """)
        ramp_layout.addWidget(self.ramp_check)
        ramp_layout.addLayout(values_layout)
        ramp_layout.addWidget(self.ramp_values_list)
        self.ramp_group.setLayout(ramp_layout)

        self.constant_check.stateChanged.connect(lambda: sf.sync_checkboxes(self.constant_check, [self.constant_check, self.s1s2_check, self.ramp_check]))
        self.s1s2_check.stateChanged.connect(lambda: sf.sync_checkboxes(self.s1s2_check, [self.constant_check, self.s1s2_check, self.ramp_check]))
        self.ramp_check.stateChanged.connect(lambda: sf.sync_checkboxes(self.ramp_check, [self.constant_check, self.s1s2_check, self.ramp_check]))

        stim_layout.addWidget(self.constant_group, 0, 0)
        stim_layout.addWidget(self.s1s2_group, 0, 1)
        stim_layout.addWidget(self.ramp_group, 1, 0, 1, 2)
        stim_group.setLayout(stim_layout)

        upper_layout.addWidget(phase_manager_group)
        upper_layout.addWidget(stim_group)

        # LOWER LAYOUT
        lower_layout = QHBoxLayout()

        # Platform Status
        platform_status_group = QGroupBox("Platform Status")
        platform_status_layout = QHBoxLayout()

        # Device Infos
        device_infos_group = QGroupBox("Device Infos")
        ss.update_groupbox_style(device_infos_group, mode="subgroup")
        device_infos_group.setFixedWidth(240)
        device_infos_layout = QVBoxLayout()

        self.pcie_connection_label = QLabel()
        self.pcie_connection_label.setFixedSize(110, 120)
        pixmap = QPixmap("Icons/pcie.png").scaled(self.pcie_connection_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        self.pcie_connection_label.setPixmap(pixmap)

        self.connection_status_button = QPushButton("Not Connected")
        self.connection_status_button.setFont(QFont("Arial", 11))
        self.connection_status_button.setStyleSheet("""
                                                    QPushButton {
                                                        border: 2px solid red;
                                                        border-radius: 10px;
                                                        background-color: #ffcccc;
                                                        padding: 10px;
                                                    }
                                                    QPushButton:hover {
                                                        background-color: #ffcccc;
                                                    }
                                                    QPushButton:pressed {
                                                        background-color: #ffcccc;
                                                    }
                                                """)
        self.connection_status_button.setFixedWidth(150)
        self.connection_status_button.setIcon(QIcon("Icons/led_red.png"))

        all_to_zero_layout = QHBoxLayout()
        self.all_set_zero_status = QPushButton()
        self.all_set_zero_status.setStyleSheet("""
                                                    QPushButton {
                                                        border: 2px solid black;
                                                        border-radius: 5px;
                                                        background-color: #f0f0f0;
                                                        padding: 2px;
                                                    }
                                                    QPushButton:hover {
                                                        background-color: #f0f0f0;
                                                    }
                                                    QPushButton:pressed {
                                                        background-color: #f0f0f0;
                                                    }
                                                """)
        self.all_set_zero_status.setIcon(QIcon("Icons/led_gray.png"))
        self.all_set_zero_label = QLabel("Setting Lines to 0...")
        spacer = QSpacerItem(40, 30, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        all_to_zero_layout.addItem(spacer)
        all_to_zero_layout.addWidget(self.all_set_zero_status)
        all_to_zero_layout.addWidget(self.all_set_zero_label)
        all_to_zero_layout.addStretch()

        self.update_connection_status()

        dmd_connection_layout = QGridLayout()
        icon = QIcon("Icons/dmd_icon.ico")
        self.dmd1_connection = QToolButton()
        self.dmd1_connection.setFixedSize(80, 80)
        self.dmd1_connection.setText("DMD 1")
        self.dmd1_connection.setFont(QFont("Arial", 10))
        self.dmd1_connection.setIcon(icon)
        self.dmd1_connection.setIconSize(QSize(50, 50))
        self.dmd1_connection.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.dmd2_connection = QToolButton()
        self.dmd2_connection.setFixedSize(80, 80)
        self.dmd2_connection.setText("DMD 2")
        self.dmd2_connection.setFont(QFont("Arial", 10))
        self.dmd2_connection.setIcon(icon)
        self.dmd2_connection.setIconSize(QSize(50, 50))
        self.dmd2_connection.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.dmd3_connection = QToolButton()
        self.dmd3_connection.setFixedSize(80, 80)
        self.dmd3_connection.setText("DMD 3")
        self.dmd3_connection.setFont(QFont("Arial", 10))
        self.dmd3_connection.setIcon(icon)
        self.dmd3_connection.setIconSize(QSize(50, 50))
        self.dmd3_connection.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.dmd4_connection = QToolButton()
        self.dmd4_connection.setFixedSize(80, 80)
        self.dmd4_connection.setText("DMD 4")
        self.dmd4_connection.setFont(QFont("Arial", 10))
        self.dmd4_connection.setIcon(icon)
        self.dmd4_connection.setIconSize(QSize(50, 50))
        self.dmd4_connection.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        dmd_connection_layout.addWidget(self.dmd1_connection, 0, 0)
        dmd_connection_layout.addWidget(self.dmd2_connection, 0, 1)
        dmd_connection_layout.addWidget(self.dmd3_connection, 1, 0)
        dmd_connection_layout.addWidget(self.dmd4_connection, 1, 1)

        camera_connection_layout = QGridLayout()
        icon = QIcon("Icons/camera.png")
        self.camera1_connection = QToolButton()
        self.camera1_connection.setFixedSize(80, 80)
        self.camera1_connection.setText("CAM 1")
        self.camera1_connection.setFont(QFont("Arial", 10))
        self.camera1_connection.setIcon(icon)
        self.camera1_connection.setIconSize(QSize(60, 60))
        self.camera1_connection.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.camera2_connection = QToolButton()
        self.camera2_connection.setFixedSize(80, 80)
        self.camera2_connection.setText("CAM 2")
        self.camera2_connection.setFont(QFont("Arial", 10))
        self.camera2_connection.setIcon(icon)
        self.camera2_connection.setIconSize(QSize(60, 60))
        self.camera2_connection.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.camera3_connection = QToolButton()
        self.camera3_connection.setFixedSize(80, 80)
        self.camera3_connection.setText("CAM 3")
        self.camera3_connection.setFont(QFont("Arial", 10))
        self.camera3_connection.setIcon(icon)
        self.camera3_connection.setIconSize(QSize(60, 60))
        self.camera3_connection.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.camera4_connection = QToolButton()
        self.camera4_connection.setFixedSize(80, 80)
        self.camera4_connection.setText("CAM 4")
        self.camera4_connection.setFont(QFont("Arial", 10))
        self.camera4_connection.setIcon(icon)
        self.camera4_connection.setIconSize(QSize(60, 60))
        self.camera4_connection.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        camera_connection_layout.addWidget(self.camera1_connection, 0, 0)
        camera_connection_layout.addWidget(self.camera2_connection, 0, 1)
        camera_connection_layout.addWidget(self.camera3_connection, 1, 0)
        camera_connection_layout.addWidget(self.camera4_connection, 1, 1)

        spacer = QSpacerItem(25, 30, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        device_infos_layout.addWidget(self.pcie_connection_label, alignment=Qt.AlignmentFlag.AlignCenter)
        device_infos_layout.addWidget(self.connection_status_button, alignment=Qt.AlignmentFlag.AlignCenter)
        device_infos_layout.addLayout(all_to_zero_layout)
        device_infos_layout.addItem(spacer)
        device_infos_layout.addLayout(dmd_connection_layout)
        device_infos_layout.addItem(spacer)
        device_infos_layout.addLayout(camera_connection_layout)
        device_infos_group.setLayout(device_infos_layout)

        self.check_dmds_connection()

        info_layout = QVBoxLayout()

        plat_seq_layout = QHBoxLayout()
        label_size = QSize(550, 400)
        self.platform_status_label = QLabel()
        self.platform_status_label.setFixedSize(label_size)

        self.platform_off_pixmap = QPixmap("Icons/platform_not_configured.png").scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.platform_on_pixmap = QPixmap("Icons/platform_configured.png").scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.gi8 = Giotto(self.platform_on_pixmap, self.platform_off_pixmap)

        self.current_image = self.platform_off_pixmap.copy()
        self.platform_status_label.setPixmap(self.current_image)

        self.sequence_defined_status = QPushButton()
        self.sequence_sent_status = QPushButton()
        self.electrical_stimulation_defined = QPushButton()
        for button in [self.sequence_defined_status, self.sequence_sent_status, self.electrical_stimulation_defined]:
            button.setStyleSheet("""
                                   QPushButton {
                                       border: 2px solid black;
                                       border-radius: 5px;
                                       background-color: #f0f0f0;
                                       padding: 2px;
                                   }
                                   QPushButton:hover {
                                       background-color: #f0f0f0;
                                   }
                                   QPushButton:pressed {
                                       background-color: #f0f0f0;
                                   }
                                """)
            button.setIcon(QIcon("Icons/led_gray.png"))
            button.setIconSize(QSize(30, 30))
            button.setFixedSize(40, 40)

        self.sequence_defined_label = QLabel("NO SEQUENCE DEFINED")
        self.sequence_sent_label = QLabel("NO SEQUENCE SENT")
        self.electrical_stimulation_label = QLabel("NO ELECTRICAL STIMULATION DEFINED")
        for label in [self.sequence_defined_label, self.sequence_sent_label, self.electrical_stimulation_label]:
            label.setFont(QFont("Arial", 10))
            label.setStyleSheet("""
                                QLabel {
                                    color: black;
                                    font-size: 11pt;
                                    font-weight: bold;
                                }
                                """)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedSize(100, 50)

        seq_stim_layout = QVBoxLayout()
        sequence_defined_layout = QHBoxLayout()
        spacer = QSpacerItem(40, 30, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        sequence_defined_layout.addItem(spacer)
        sequence_defined_layout.addWidget(self.sequence_defined_status)
        sequence_defined_layout.addWidget(self.sequence_defined_label)
        sequence_defined_layout.addStretch()

        sequence_sent_layout = QHBoxLayout()
        sequence_sent_layout.addItem(spacer)
        sequence_sent_layout.addWidget(self.sequence_sent_status)
        sequence_sent_layout.addWidget(self.sequence_sent_label)
        sequence_sent_layout.addStretch()

        electrical_stimulation_layout = QHBoxLayout()
        electrical_stimulation_layout.addItem(spacer)
        electrical_stimulation_layout.addWidget(self.electrical_stimulation_defined)
        electrical_stimulation_layout.addWidget(self.electrical_stimulation_label)
        electrical_stimulation_layout.addStretch()

        spacer = QSpacerItem(25, 15, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        seq_stim_layout.addItem(spacer)
        seq_stim_layout.addLayout(sequence_defined_layout)
        seq_stim_layout.addLayout(sequence_sent_layout)
        seq_stim_layout.addLayout(electrical_stimulation_layout)
        seq_stim_layout.addStretch()

        plat_seq_layout.addWidget(self.platform_status_label)
        plat_seq_layout.addLayout(seq_stim_layout)

        all_info_layout = QHBoxLayout()
        dmd_info_layout = QGridLayout()
        self.dmd1_info = QLabel("""
            <b>DMD 1:</b>
            <ul>
                <li>Red LED Current: N/A</li>
                <li>Blue LED Current: N/A</li>
                </ul>
            """)
        self.dmd2_info = QLabel("""
                    <b>DMD 2:</b>
                    <ul>
                        <li>Red LED Current: N/A</li>
                        <li>Blue LED Current: N/A</li>
                        </ul>
                """)
        self.dmd3_info = QLabel("""
                    <b>DMD 3:</b>
                    <ul>
                        <li>Red LED Current: N/A</li>
                        <li>Blue LED Current: N/A</li>
                        </ul>
                """)
        self.dmd4_info = QLabel("""
                    <b>DMD 4:</b>
                    <ul>
                        <li>Red LED Current: N/A</li>
                        <li>Blue LED Current: N/A</li>
                        </ul>
                """)
        dmd_info_layout.addWidget(self.dmd1_info, 0, 0)
        dmd_info_layout.addWidget(self.dmd2_info, 0, 1)
        dmd_info_layout.addWidget(self.dmd3_info, 1, 0)
        dmd_info_layout.addWidget(self.dmd4_info, 1, 1)

        self.cam_info = QLabel("""
            <b>CAMs:</b>
            <ul>
                <li>ROI: 2048 x 2048</li>
                <li>Trigger Source: Internal</li>
                <li>Trigger Mode: Normal</li>
                <li>Trigger Active: Edge</li>
                <li>Trigger Polarity: Positive</li>
                <li>Frame Bundle: OFF</li>
                </ul>
            """)
        self.phases_info = QLabel("""
            <b>Experiment:</b>
            <ul>
                <li>Red LED Intensity: N/A</li>
                <li>Blue LED Intensity: N/A</li>
                <li>Real Pre-Illumination Time: N/A</li>
                <li>Real Pre-Stimulation Time: N/A</li>
                <li>Real Stimulation Time: N/A</li>
                <li>Real Post-Stimulation Time: N/A</li>
                <li>Electrical Stimulation Protocol: N/A</li>
                </ul>
            """)

        all_info_layout.addLayout(dmd_info_layout)
        all_info_layout.addWidget(self.cam_info)
        all_info_layout.addWidget(self.phases_info)
        all_info_layout.addStretch()

        info_layout.addLayout(plat_seq_layout)
        info_layout.addLayout(all_info_layout)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        spacer = QSpacerItem(25, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        platform_status_layout.addWidget(device_infos_group)
        platform_status_layout.addItem(spacer)
        platform_status_layout.addLayout(info_layout)
        platform_status_group.setLayout(platform_status_layout)

        buttons_layout = QVBoxLayout()
        buttons_size = QSize(250, 40)

        # ALIGNMENT
        alignment_group = QGroupBox("Alignment")
        alignment_group.setFixedWidth(525)
        alignment_layout = QVBoxLayout()

        alignment_buttons_layout = QHBoxLayout()
        self.start_alignment_button = QPushButton("START LIVE")
        self.stop_alignment_button = QPushButton("STOP LIVE")
        self.start_alignment_button.setFont(QFont("Arial", 14))
        self.stop_alignment_button.setFont(QFont("Arial", 14))
        self.start_alignment_button.setFixedSize(buttons_size)
        self.stop_alignment_button.setFixedSize(buttons_size)
        alignment_buttons_layout.addWidget(self.start_alignment_button)
        alignment_buttons_layout.addWidget(self.stop_alignment_button)

        dmd_selection_alignment_layout = QVBoxLayout()
        dmd_selection_alignment_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.red_led_dmd1 = QCheckBox("Red LED")
        self.blue_led_dmd1 = QCheckBox("Blue LED")
        self.red_led_dmd2 = QCheckBox("Red LED")
        self.blue_led_dmd2 = QCheckBox("Blue LED")
        self.red_led_dmd3 = QCheckBox("Red LED")
        self.blue_led_dmd3 = QCheckBox("Blue LED")
        self.red_led_dmd4 = QCheckBox("Red LED")
        self.blue_led_dmd4 = QCheckBox("Blue LED")

        for checkbox in [self.red_led_dmd1, self.blue_led_dmd1, self.red_led_dmd2, self.blue_led_dmd2, self.red_led_dmd3, self.blue_led_dmd3, self.red_led_dmd4, self.blue_led_dmd4]:
            ss.update_checkbox_style(checkbox, dmd_selection=True)

        self.red_led_dmd1.stateChanged.connect(lambda: sf.sync_checkboxes(self.red_led_dmd1, self.blue_led_dmd1))
        self.blue_led_dmd1.stateChanged.connect(lambda: sf.sync_checkboxes(self.blue_led_dmd1, self.red_led_dmd1))
        self.red_led_dmd2.stateChanged.connect(lambda: sf.sync_checkboxes(self.red_led_dmd2, self.blue_led_dmd2))
        self.blue_led_dmd2.stateChanged.connect(lambda: sf.sync_checkboxes(self.blue_led_dmd2, self.red_led_dmd2))
        self.red_led_dmd3.stateChanged.connect(lambda: sf.sync_checkboxes(self.red_led_dmd3, self.blue_led_dmd3))
        self.blue_led_dmd3.stateChanged.connect(lambda: sf.sync_checkboxes(self.blue_led_dmd3, self.red_led_dmd3))
        self.red_led_dmd4.stateChanged.connect(lambda: sf.sync_checkboxes(self.red_led_dmd4, self.blue_led_dmd4))
        self.blue_led_dmd4.stateChanged.connect(lambda: sf.sync_checkboxes(self.blue_led_dmd4, self.red_led_dmd4))

        hbox_dmd1 = QHBoxLayout()
        hbox_dmd1.addWidget(self.red_led_dmd1)
        hbox_dmd1.addWidget(self.blue_led_dmd1)
        hbox_dmd2 = QHBoxLayout()
        hbox_dmd2.addWidget(self.red_led_dmd2)
        hbox_dmd2.addWidget(self.blue_led_dmd2)
        hbox_dmd3 = QHBoxLayout()
        hbox_dmd3.addWidget(self.red_led_dmd3)
        hbox_dmd3.addWidget(self.blue_led_dmd3)
        hbox_dmd4 = QHBoxLayout()
        hbox_dmd4.addWidget(self.red_led_dmd4)
        hbox_dmd4.addWidget(self.blue_led_dmd4)
        label_dmd1 = QLabel("<b>DMD 1:</b>")
        label_dmd2 = QLabel("<b>DMD 2:</b>")
        label_dmd3 = QLabel("<b>DMD 3:</b>")
        label_dmd4 = QLabel("<b>DMD 4:</b>")
        label_dmd1.setFont(QFont("Arial", 12))
        label_dmd2.setFont(QFont("Arial", 12))
        label_dmd3.setFont(QFont("Arial", 12))
        label_dmd4.setFont(QFont("Arial", 12))

        self.red_dc_dmd1 = QDoubleSpinBox()
        self.blue_dc_dmd1 = QDoubleSpinBox()
        self.red_dc_dmd2 = QDoubleSpinBox()
        self.blue_dc_dmd2 = QDoubleSpinBox()
        self.red_dc_dmd3 = QDoubleSpinBox()
        self.blue_dc_dmd3 = QDoubleSpinBox()
        self.red_dc_dmd4 = QDoubleSpinBox()
        self.blue_dc_dmd4 = QDoubleSpinBox()
        for spinbox in [self.red_dc_dmd1, self.blue_dc_dmd1, self.red_dc_dmd2, self.blue_dc_dmd2, self.red_dc_dmd3, self.blue_dc_dmd3, self.red_dc_dmd4, self.blue_dc_dmd4]:
            spinbox.setRange(0.20, 50.00)
            spinbox.setSingleStep(0.01)
            spinbox.setDecimals(2)
            spinbox.setValue(10.00)
        hbox_dc1 = QHBoxLayout()
        hbox_dc1.addWidget(self.red_dc_dmd1)
        hbox_dc1.addWidget(self.blue_dc_dmd1)
        hbox_dc2 = QHBoxLayout()
        hbox_dc2.addWidget(self.red_dc_dmd2)
        hbox_dc2.addWidget(self.blue_dc_dmd2)
        hbox_dc3 = QHBoxLayout()
        hbox_dc3.addWidget(self.red_dc_dmd3)
        hbox_dc3.addWidget(self.blue_dc_dmd3)
        hbox_dc4 = QHBoxLayout()
        hbox_dc4.addWidget(self.red_dc_dmd4)
        hbox_dc4.addWidget(self.blue_dc_dmd4)

        button_layout = QHBoxLayout()
        self.enable_dmd_button = QPushButton("Enable DMDs")
        self.enable_dmd_button.setFixedSize(150, 45)
        self.enable_dmd_button.setFont(QFont("Arial", 14))
        self.timer_label = QLabel("00:00")
        self.timer_label.setStyleSheet("""
                                QLabel {
                                    font-size: 20px;
                                    font-family: 'Arial', sans-serif;
                                    font-weight: bold;
                                    color: #FFFFFF;
                                    background-color: #4682B4;
                                    padding: 6px;
                                    border-radius: 12px;
                                    border: 1px solid #4682B4;
                                    text-align: center;
                                }
                            """)
        button_layout.addWidget(self.enable_dmd_button, alignment=Qt.AlignmentFlag.AlignCenter)
        button_layout.addWidget(self.timer_label, alignment=Qt.AlignmentFlag.AlignCenter)

        layout_par = QHBoxLayout()
        dmd_sel_left_layout = QFormLayout()
        dmd_sel_right_layout = QFormLayout()
        spacer = QSpacerItem(25, 18, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        dmd_sel_left_layout.addRow(label_dmd1, hbox_dmd1)
        dmd_sel_left_layout.addRow(QLabel("DC (%):"), hbox_dc1)
        dmd_sel_left_layout.addItem(spacer)
        dmd_sel_left_layout.addRow(label_dmd3, hbox_dmd3)
        dmd_sel_left_layout.addRow(QLabel("DC (%):"), hbox_dc3)
        dmd_sel_right_layout.addRow(label_dmd2, hbox_dmd2)
        dmd_sel_right_layout.addRow(QLabel("DC (%):"), hbox_dc2)
        dmd_sel_right_layout.addItem(spacer)
        dmd_sel_right_layout.addRow(label_dmd4, hbox_dmd4)
        dmd_sel_right_layout.addRow(QLabel("DC (%):"), hbox_dc4)

        spacer1 = QSpacerItem(15, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        layout_par.addItem(spacer1)
        layout_par.addLayout(dmd_sel_left_layout)
        layout_par.addItem(spacer)
        layout_par.addLayout(dmd_sel_right_layout)
        layout_par.setAlignment(Qt.AlignmentFlag.AlignCenter)

        dmd_selection_alignment_layout.addLayout(layout_par)
        dmd_selection_alignment_layout.addLayout(button_layout)

        spacer = QSpacerItem(25, 30, QSizePolicy.Policy.Minimum)
        alignment_layout.addLayout(alignment_buttons_layout)
        alignment_layout.addItem(spacer)
        alignment_layout.addLayout(dmd_selection_alignment_layout)
        alignment_group.setLayout(alignment_layout)

        # EXPERIMENT
        experiment_group = QGroupBox("Experiment")
        experiment_group.setFixedWidth(525)
        experiment_layout = QVBoxLayout()

        experiment_buttons_layout = QHBoxLayout()
        self.start_experiment = QPushButton("START")
        self.stop_experiment = QPushButton("STOP")
        for button in [self.start_experiment, self.stop_experiment]:
            button.setFont(QFont("Arial", 14))
            button.setFixedSize(buttons_size)
        experiment_buttons_layout.addWidget(self.start_experiment)
        experiment_buttons_layout.addWidget(self.stop_experiment)

        saves_info_layout = QHBoxLayout()
        saves_layout = QVBoxLayout()
        self.files_list = QListWidget()
        self.files_list.setFixedSize(225, 160)
        self.save_all_files = QPushButton("SAVE ALL")
        self.save_all_files.setFixedSize(225, 35)
        saves_layout.addWidget(self.files_list)
        saves_layout.addWidget(self.save_all_files)

        experiment_info_layout = QVBoxLayout()
        self.stop_condition_label = QLabel("<b>Stop Condition:</b> N/A")
        self.frames_acquired_label = QLabel("<b>Frames Acquired:</b> N/A")
        self.frames_shape_label = QLabel("<b>Frames Shape:</b> N/A")
        for label in [self.stop_condition_label, self.frames_acquired_label, self.frames_shape_label]:
            label.setFont(QFont("Arial", 12))
        experiment_info_layout.addWidget(self.stop_condition_label)
        experiment_info_layout.addWidget(self.frames_acquired_label)
        experiment_info_layout.addWidget(self.frames_shape_label)

        spacer = QSpacerItem(25, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        saves_info_layout.addLayout(saves_layout)
        saves_info_layout.addItem(spacer)
        saves_info_layout.addLayout(experiment_info_layout)

        experiment_layout.addLayout(experiment_buttons_layout)
        experiment_layout.addLayout(saves_info_layout)
        experiment_group.setLayout(experiment_layout)

        for button in [self.start_alignment_button, self.stop_alignment_button, self.save_all_files]:
            button.setEnabled(False)

        buttons_layout.addWidget(alignment_group)
        buttons_layout.addWidget(experiment_group)

        lower_layout.addWidget(platform_status_group)
        lower_layout.addLayout(buttons_layout)

        ss.style(widget=self)

        self.layout.addLayout(upper_layout)
        self.layout.addLayout(lower_layout)

        self.central_widget.setLayout(self.layout)

        # CONNECTIONS
        self.add_value.clicked.connect(self.ramp_array_add_value)
        self.ramp_frequency.returnPressed.connect(self.ramp_array_add_value)
        self.remove_value.clicked.connect(self.ramp_array_remove_value)
        self.clear_array.clicked.connect(self.ramp_array_clear)
        self.check_cameras_connection_thread.camera_found.connect(self.update_green_cameras_grid)
        self.check_cameras_connection_thread.process_finished.connect(self.update_red_cameras_grid)
        self.check_dmds_connection_thread.process_finished.connect(self.update_dmds_grid)
        self.check_dmds_connection_thread.start_control_dmd_gui.connect(self.start_control_dmd_gui)
        self.clear_sequence_button.clicked.connect(self.clear_sequence)
        self.constant_check.stateChanged.connect(self.toggle_constant)
        self.enable_dmd_button.clicked.connect(self.enable_dmds)
        self.enable_dmd_thread.array_defined_signal.connect(self.send_sequence)
        self.enable_timer.timeout.connect(self.update_time)
        self.find_threshold.clicked.connect(self.find_threshold_value)
        self.generate_sequence_button.clicked.connect(self.generate_sequence)
        self.generate_sequence_thread.update_generation_signal.connect(self.update_generation_status)
        self.generate_sequence_thread.update_sending_signal.connect(self.update_sending_status)
        self.post_stim_phase_check.stateChanged.connect(self.toggle_post_stim_time)
        self.pre_ill_phase_check.stateChanged.connect(self.toggle_pre_ill_time)
        self.pre_stim_phase_check.stateChanged.connect(self.toggle_pre_stim_time)
        self.ramp_check.stateChanged.connect(self.toggle_ramp)
        self.s1s2_check.stateChanged.connect(self.toggle_s1s2)
        self.save_all_files.clicked.connect(self.save_files)
        self.send_enable_dmd_thread.ready_to_start_signal.connect(self.start_task)
        self.start_alignment_button.clicked.connect(self.start_alignment)
        self.start_experiment.clicked.connect(self.play_sequence)
        self.start_task_thread.change_color_signal.connect(self.change_color_button)
        self.start_task_thread.start_timer_signal.connect(self.start_timer)
        self.stim_phase_check.stateChanged.connect(self.toggle_stim_time)
        self.stop_alignment_button.clicked.connect(self.stop_alignment)
        self.stop_experiment.clicked.connect(self.stop_sequence)

    # METHODS
    def add_info_to_experiment(self, key, value, priv_key):
        if key == "dmd_info":
            if value[0] in self.experiment_info[key].keys():
                if priv_key in self.experiment_info[key][value[0]].keys():
                    self.experiment_info[key][value[0]][priv_key] = [value[1], value[2]]
                else:
                    self.experiment_info[key][value[0]].update({priv_key: [value[1], value[2]]})

            else:
                self.experiment_info[key].update({value[0]: {priv_key: [value[1], value[2]]}})

        elif key == "cam_info":
            if priv_key in self.experiment_info[key].keys():
                if priv_key == "roi":
                    self.experiment_info[key][priv_key] = [value[0], value[1]]
                elif priv_key == "trigger":
                    self.experiment_info[key][priv_key] = [value[0], value[1], value[2], value[3], value[4]]

            else:
                if priv_key == "roi":
                    self.experiment_info[key].update({priv_key: [value[0], value[1]]})
                elif priv_key == "trigger":
                    self.experiment_info[key].update({priv_key: [value[0], value[1], value[2], value[3], value[4]]})

    def change_color_button(self, state):
        if state:
            self.enable_dmd_button.setStyleSheet("""
                    QPushButton {
                        background-color: #0078D4;
                        border: 2px solid green;
                        border-radius: 10px;
                        background-color: #ccffcc;
                        padding: 5px;
                    }
                    QPushButton:hover {
                        background-color: #e0e0e0;
                    }
                    QPushButton:pressed {
                        background-color: #d0d0d0;
                    }
                    """)
        else:
            self.enable_dmd_button.setStyleSheet("""
                    QPushButton {
                        background-color: #0078D4;
                        border: 2px solid blue;
                        border-radius: 10px;
                        background-color: #f0f0f0;
                        padding: 5px;
                    }
                    QPushButton:hover {
                        background-color: #e0e0e0;
                    }
                    QPushButton:pressed {
                        background-color: #d0d0d0;
                    }
                    """)

    def check_cameras_connection(self):
        self.check_cameras_connection_thread.start()

    def check_dmds_connection(self):
        ss.style(self.dmd1_connection)
        ss.style(self.dmd2_connection)
        ss.style(self.dmd3_connection)
        ss.style(self.dmd4_connection)

        self.dmd_connected = []

        self.check_dmds_connection_thread.start()

    def clear_sequence(self):
        if self.master_task is not None:
            self.master_task.close()
            self.master_task = None

            self.sequence_defined_status.setIcon(QIcon("Icons/led_gray.png"))
            self.sequence_defined_label.setText("NO SEQUENCE DEFINED")
            self.sequence_sent_status.setIcon(QIcon("Icons/led_gray.png"))
            self.sequence_sent_label.setText("NO SEQUENCE SENT")
            self.electrical_stimulation_defined.setIcon(QIcon("Icons/led_gray.png"))
            self.electrical_stimulation_label.setText("NO ELECTRICAL STIMULATION DEFINED")
            for label in [self.sequence_defined_label, self.sequence_sent_label, self.electrical_stimulation_label]:
                label.setFont(QFont("Arial", 10))
                label.setStyleSheet("""
                                    QLabel {
                                        color: black;
                                        font-size: 11pt;
                                        font-weight: bold;
                                    }
                                    """)
                label.setWordWrap(True)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setFixedSize(100, 50)
            for button in [self.sequence_defined_status, self.sequence_sent_status,
                           self.electrical_stimulation_defined]:
                button.setStyleSheet("""
                                       QPushButton {
                                           border: 2px solid black;
                                           border-radius: 5px;
                                           background-color: #f0f0f0;
                                           padding: 2px;
                                       }
                                       QPushButton:hover {
                                           background-color: #f0f0f0;
                                       }
                                       QPushButton:pressed {
                                           background-color: #f0f0f0;
                                       }
                                    """)

            self.gi8.sequences_sent = False
            for idx in range(len(self.gi8.platform_regions[:-1])):
                self.gi8.platform_states[idx] = not self.gi8.platform_states[idx]
                self.current_image = self.gi8.draw(idx, self.current_image)
            self.platform_status_label.setPixmap(self.current_image)

            self.stop_condition_label.setText("<b>Stop Condition:</b> N/A")

        self.pre_ill_phase_check.setChecked(False)
        self.pre_stim_phase_check.setChecked(False)
        self.stim_phase_check.setChecked(False)
        self.post_stim_phase_check.setChecked(False)
        self.constant_check.setChecked(False)
        self.s1s2_check.setChecked(False)
        self.ramp_check.setChecked(False)

        self.pre_ill_time_line.clear()
        self.pre_stim_time_line.clear()
        self.stim_time_line.clear()
        self.post_stim_time_line.clear()
        self.delay_line.clear()
        self.duration_line.clear()
        self.frequency_line.clear()

        self.sequence_defined_status.setIcon(QIcon("Icons/led_gray.png"))
        self.sequence_defined_label.setText("NO SEQUENCE DEFINED")
        self.sequence_sent_status.setIcon(QIcon("Icons/led_gray.png"))
        self.sequence_sent_label.setText("NO SEQUENCE SENT")
        self.electrical_stimulation_defined.setIcon(QIcon("Icons/led_gray.png"))
        self.electrical_stimulation_label.setText("NO ELECTRICAL STIMULATION DEFINED")
        for label in [self.sequence_defined_label, self.sequence_sent_label, self.electrical_stimulation_label]:
            label.setFont(QFont("Arial", 10))
            label.setStyleSheet("""
                                    QLabel {
                                        color: black;
                                        font-size: 11pt;
                                        font-weight: bold;
                                    }
                                    """)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedSize(100, 50)
        for button in [self.sequence_defined_status, self.sequence_sent_status, self.electrical_stimulation_defined]:
            button.setStyleSheet("""
                                   QPushButton {
                                       border: 2px solid black;
                                       border-radius: 5px;
                                       background-color: #f0f0f0;
                                       padding: 2px;
                                   }
                                   QPushButton:hover {
                                       background-color: #f0f0f0;
                                   }
                                   QPushButton:pressed {
                                       background-color: #f0f0f0;
                                   }
                                """)

        self.phases_info.setText("""
            <b>Experiment:</b>
            <ul>
                <li>Red LED Intensity: N/A</li>
                <li>Blue LED Intensity: N/A</li>
                <li>Real Pre-Illumination Time: N/A</li>
                <li>Real Pre-Stimulation Time: N/A</li>
                <li>Real Stimulation Time: N/A</li>
                <li>Real Post-Stimulation Time: N/A</li>
                <li>Electrical Stimulation Protocol: N/A</li>
                </ul>
            """)

        self.stop_condition_signal.emit(0)

    def enable_dmds(self):
        if len(self.dmd_connected) == 0:
            QMessageBox.warning(self, "Warning", "No DMDs connected.")
            return

        warning_dmd = []
        if any([self.red_led_dmd1, self.blue_led_dmd1]) and 1 not in self.dmd_connected:
            warning_dmd.append("DMD 1")
        if any([self.red_led_dmd2, self.blue_led_dmd2]) and 2 not in self.dmd_connected:
            warning_dmd.append("DMD 2")
        if any([self.red_led_dmd3, self.blue_led_dmd3]) and 3 not in self.dmd_connected:
            warning_dmd.append("DMD 3")
        if any([self.red_led_dmd4, self.blue_led_dmd4]) and 4 not in self.dmd_connected:
            warning_dmd.append("DMD 4")

        if len(warning_dmd) > 0:
            dmd_list = "\n".join(f"- {dmd}" for dmd in warning_dmd)
            message = f"Unable to start the following DMDs because they are not connected:\n{dmd_list}\n"
            QMessageBox.warning(self, "Warning", message)
            return

        if self.master_task is not None:
            self.master_task.close()
            self.master_task = None

            self.sequence_defined_status.setIcon(QIcon("Icons/led_gray.png"))
            self.sequence_defined_label.setText("NO SEQUENCE DEFINED")
            self.sequence_sent_status.setIcon(QIcon("Icons/led_gray.png"))
            self.sequence_sent_label.setText("NO SEQUENCE SENT")
            self.electrical_stimulation_defined.setIcon(QIcon("Icons/led_gray.png"))
            self.electrical_stimulation_label.setText("NO ELECTRICAL STIMULATION DEFINED")
            for label in [self.sequence_defined_label, self.sequence_sent_label, self.electrical_stimulation_label]:
                label.setFont(QFont("Arial", 10))
                label.setStyleSheet("""
                                        QLabel {
                                            color: black;
                                            font-size: 11pt;
                                            font-weight: bold;
                                        }
                                        """)
                label.setWordWrap(True)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setFixedSize(100, 50)
            for button in [self.sequence_defined_status, self.sequence_sent_status,
                           self.electrical_stimulation_defined]:
                button.setStyleSheet("""
                                       QPushButton {
                                           border: 2px solid black;
                                           border-radius: 5px;
                                           background-color: #f0f0f0;
                                           padding: 2px;
                                       }
                                       QPushButton:hover {
                                           background-color: #f0f0f0;
                                       }
                                       QPushButton:pressed {
                                           background-color: #f0f0f0;
                                       }
                                    """)

            self.gi8.sequences_sent = False
            for idx in range(len(self.gi8.platform_regions[:-1])):
                self.gi8.platform_states[idx] = not self.gi8.platform_states[idx]
                self.current_image = self.gi8.draw(idx, self.current_image)
            self.platform_status_label.setPixmap(self.current_image)

        if self.alignment_task is None:
            if not any([self.red_led_dmd1.isChecked(), self.blue_led_dmd1.isChecked(), self.red_led_dmd2.isChecked(),
                    self.blue_led_dmd2.isChecked(), self.red_led_dmd3.isChecked(), self.blue_led_dmd3.isChecked(),
                    self.red_led_dmd4.isChecked(), self.blue_led_dmd4.isChecked()]):
                with nidaqmx.Task() as task:
                    task.do_channels.add_do_chan(cfg.NI_PORT0, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
                    task.start()
                    task.write(0)
                    task.stop()

            else:
                self.enable_dmd_thread.start()

        else:
            if self.enable_timer.isActive():
                self.enable_timer.stop()
                self.avoid_overray = False

            self.start_task_thread.requestInterruption()

            time.sleep(1)

            if any([self.red_led_dmd1.isChecked(), self.blue_led_dmd1.isChecked(), self.red_led_dmd2.isChecked(),
                    self.blue_led_dmd2.isChecked(), self.red_led_dmd3.isChecked(), self.blue_led_dmd3.isChecked(),
                    self.red_led_dmd4.isChecked(), self.blue_led_dmd4.isChecked()]):
                with nidaqmx.Task() as task:
                    task.do_channels.add_do_chan(cfg.NI_PORT0, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
                    task.start()
                    task.write(0)
                    task.stop()
                self.enable_dmd_thread.start()

            else:
                self.timer_label.setText("00:00")

                with nidaqmx.Task() as task:
                    task.do_channels.add_do_chan(cfg.NI_PORT0, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
                    task.start()
                    task.write(0)
                    task.stop()

    def find_threshold_value(self):
        if len(self.dmd_connected) == 0:
            QMessageBox.warning(self, "Warning", "No DMDs connected.")
            return

        if self.master_task is not None:
            self.master_task.close()
            self.master_task = None

        self.sequence_defined_status.setIcon(QIcon("Icons/led_gray.png"))
        self.sequence_defined_label.setText("NO SEQUENCE DEFINED")
        self.sequence_sent_status.setIcon(QIcon("Icons/led_gray.png"))
        self.sequence_sent_label.setText("NO SEQUENCE SENT")
        self.electrical_stimulation_defined.setIcon(QIcon("Icons/led_gray.png"))
        self.electrical_stimulation_label.setText("NO ELECTRICAL STIMULATION DEFINED")
        for label in [self.sequence_defined_label, self.sequence_sent_label, self.electrical_stimulation_label]:
            label.setFont(QFont("Arial", 10))
            label.setStyleSheet("""
                                                QLabel {
                                                    color: black;
                                                    font-size: 11pt;
                                                    font-weight: bold;
                                                }
                                                """)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedSize(100, 50)
        for button in [self.sequence_defined_status, self.sequence_sent_status,
                       self.electrical_stimulation_defined]:
            button.setStyleSheet("""
                                               QPushButton {
                                                   border: 2px solid black;
                                                   border-radius: 5px;
                                                   background-color: #f0f0f0;
                                                   padding: 2px;
                                               }
                                               QPushButton:hover {
                                                   background-color: #f0f0f0;
                                               }
                                               QPushButton:pressed {
                                                   background-color: #f0f0f0;
                                               }
                                            """)

        self.gi8.sequences_sent = False
        for idx in range(len(self.gi8.platform_regions[:-1])):
            self.gi8.platform_states[idx] = not self.gi8.platform_states[idx]
            self.current_image = self.gi8.draw(idx, self.current_image)
        self.platform_status_label.setPixmap(self.current_image)

        QApplication.processEvents()

        self.find_threshold_gui.show()

    def generate_sequence(self):
        self.electrical_stimulation = {}
        self.experiment_info.pop("stimulation_protocol", None)

        if self.master_task is not None:
            self.master_task.close()
            self.master_task = None

            self.sequence_defined_status.setIcon(QIcon("Icons/led_gray.png"))
            self.sequence_defined_label.setText("NO SEQUENCE DEFINED")
            self.sequence_sent_status.setIcon(QIcon("Icons/led_gray.png"))
            self.sequence_sent_label.setText("NO SEQUENCE SENT")
            self.electrical_stimulation_defined.setIcon(QIcon("Icons/led_gray.png"))
            self.electrical_stimulation_label.setText("NO ELECTRICAL STIMULATION DEFINED")
            for label in [self.sequence_defined_label, self.sequence_sent_label, self.electrical_stimulation_label]:
                label.setFont(QFont("Arial", 10))
                label.setStyleSheet("""
                                        QLabel {
                                            color: black;
                                            font-size: 11pt;
                                            font-weight: bold;
                                        }
                                        """)
                label.setWordWrap(True)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setFixedSize(100, 50)
            for button in [self.sequence_defined_status, self.sequence_sent_status,
                           self.electrical_stimulation_defined]:
                button.setStyleSheet("""
                                       QPushButton {
                                           border: 2px solid black;
                                           border-radius: 5px;
                                           background-color: #f0f0f0;
                                           padding: 2px;
                                       }
                                       QPushButton:hover {
                                           background-color: #f0f0f0;
                                       }
                                       QPushButton:pressed {
                                           background-color: #f0f0f0;
                                       }
                                    """)

            self.gi8.sequences_sent = False
            for idx in range(len(self.gi8.platform_regions[:-1])):
                self.gi8.platform_states[idx] = not self.gi8.platform_states[idx]
                self.current_image = self.gi8.draw(idx, self.current_image)
            self.platform_status_label.setPixmap(self.current_image)

            QApplication.processEvents()

        if not self.pre_ill_phase_check.isChecked() and not self.pre_stim_phase_check.isChecked() and \
            not self.stim_phase_check.isChecked() and not self.post_stim_phase_check.isChecked():
            QMessageBox.warning(self, "Warning", "Please select at least one phase.")
            return

        if self.constant_check.isChecked():
            if self.delay_line.text() == "" or self.duration_line.text() == "" or self.frequency_line.text() == "":
                QMessageBox.warning(self, "Warning", "Please insert all the necessary values for the electrical stimulation.")
                return
            if int(self.frequency_line.text()) < 0 or int(self.frequency_line.text()) > 30:
                QMessageBox.warning(self, "Warning", "The frequency must be between 0 and 30 Hz.")
                return
            pre_ill_time = int(self.pre_ill_time_line.text()) if self.pre_ill_phase_check.isChecked() else 0
            pre_stim_time = int(self.pre_stim_time_line.text()) if self.pre_stim_phase_check.isChecked() else 0
            stim_time = int(self.stim_time_line.text()) if self.stim_phase_check.isChecked() else 0
            post_stim_time = int(self.post_stim_time_line.text()) if self.post_stim_phase_check.isChecked() else 0
            delay = int(self.delay_line.text())
            duration = int(self.duration_line.text())
            frequency = int(self.frequency_line.text())
            if pre_ill_time + pre_stim_time + stim_time + post_stim_time >= delay + duration:
                self.electrical_stimulation['Constant'] = [delay, duration, frequency]
                stimulation_starting_frame = math.floor(delay * 0.99631)
                stimulation_ending_frame = math.floor((delay + duration - pre_ill_time) * 0.99631)
                self.experiment_info["stimulation_protocol"] = ["Constant", frequency, stimulation_starting_frame, stimulation_ending_frame]
            else:
                QMessageBox.warning(self, "Warning", "The sum of the phases must be more than the delay + duration.")
                return

        elif self.s1s2_check.isChecked():
            if self.s0_cl_line.text() == "" or self.s0_precond_line.text() == "" or self.sf_cl_line.text() == "" or \
                    self.step_line.text() == "":
                QMessageBox.warning(self, "Warning", "Please insert all the necessary values for the electrical stimulation.")
                return
            if self.stim_phase_check.isChecked():
                stim_time = int(self.stim_time_line.text())
            else:
                QMessageBox.warning(self, "Warning", "For this electrical stimulation protocol, it is necessary to select the stimulation phase.")
                return
            start_cl = int(self.s0_cl_line.text())
            pre_cond = int(self.s0_precond_line.text())
            final_cl = int(self.sf_cl_line.text())
            step = int(self.step_line.text())
            if final_cl > start_cl:
                sn_values = np.arange(start_cl, final_cl + 1, step)
            else:
                sn_values = np.arange(start_cl, final_cl - 1, -step)
            time_el_stim = sn_values[0] * pre_cond
            for value in sn_values[1:]:
                time_el_stim += value
            if time_el_stim > stim_time:
                QMessageBox.warning(self, "Warning", f"The parameters set for electrical stimulation exceed the "
                                                     f"optogenetic stimulation duration by {int(time_el_stim * 1000) - stim_time} ms.")
                return
            self.electrical_stimulation['S1S2'] = [sn_values, pre_cond]

            starting_frame_values = []
            for i in range(1, pre_cond + 1):
                starting_frame_values.append(math.floor(i / sn_values[0] * 996.31))
            other_frame_values = []
            time = pre_cond / sn_values[0]
            for value in sn_values[1:]:
                time += 1 / value
                other_frame_values.append(math.floor(time * 996.31))
            self.experiment_info["stimulation_protocol"] = ["S1-S2", sn_values, pre_cond, starting_frame_values, other_frame_values]

        elif self.ramp_check.isChecked():
            if not self.ramp_pulses_array or self.numb_pulses_ramp.text() == "":
                QMessageBox.warning(self, "Error", "Please insert all the necessary values for the electrical stimulation.")
                return
            pre_ill_time = int(self.pre_ill_time_line.text()) if self.pre_ill_phase_check.isChecked() else 0
            pre_stim_time = int(self.pre_stim_time_line.text()) if self.pre_stim_phase_check.isChecked() else 0
            stim_time = int(self.stim_time_line.text()) if self.stim_phase_check.isChecked() else 0
            post_stim_time = int(self.post_stim_time_line.text()) if self.post_stim_phase_check.isChecked() else 0

            cl_values = [(1 / x) * 1000 for x in self.ramp_pulses_array if x != 0]
            numb_pulses = int(self.numb_pulses_ramp.text())
            total_stimulation_time = sum(x * numb_pulses for x in cl_values)
            if pre_ill_time + pre_stim_time + stim_time + post_stim_time >= total_stimulation_time:
                self.electrical_stimulation['Ramp'] = [cl_values, numb_pulses]
                self.experiment_info["stimulation_protocol"] = ["Ramp", cl_values, numb_pulses]
            else:
                QMessageBox.warning(self, "Warning", "The sum of the phases must be more than the total stimulation time.")
                return

        self.stim_poststim_repetitions = self.cycle_spin.value()
        if self.stim_poststim_repetitions > 1 and (not self.stim_phase_check.isChecked() and not self.post_stim_phase_check.isChecked()):
            QMessageBox.warning(self, "Warning", "Both stimulation and post-stimulation phase need to be selected to repeat them")
            return

        self.experiment_info["red_led_intensity"] = round(self.red_power_value.value(), 2)
        self.experiment_info["blue_led_intensity"] = round(self.blue_power_value.value(), 2)

        self.sequence_defined_label.setText("GENERATING SEQUENCE...")
        self.sequence_defined_label.setFont(QFont("Arial", 10))
        self.sequence_defined_label.setStyleSheet("""
                                                QLabel {
                                                    color: black;
                                                    font-size: 11pt;
                                                    font-weight: bold;
                                                }
                                                """)
        self.sequence_defined_label.setWordWrap(True)
        self.sequence_defined_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sequence_defined_label.setFixedSize(100, 50)

        self.red_duty_cycle = round(self.red_power_value.value() * 100 / 4.2, 2)
        self.blue_duty_cycle = round(self.blue_power_value.value() * 100 / 1.4, 2)
        self.experiment_info["red_duty_cycle"] = self.red_duty_cycle
        self.experiment_info["blue_duty_cycle"] = self.blue_duty_cycle
        self.experiment_info["num_cycles"] = self.cycle_spin.value()
        self.red_dutycycle_value.setText(f"{self.red_duty_cycle} %")
        self.blue_dutycycle_value.setText(f"{self.blue_duty_cycle} %")
        self.generate_sequence_thread.start()

    def ramp_array_add_value(self):
        if self.ramp_frequency.text() == "":
            return

        self.ramp_pulses_array.append(int(self.ramp_frequency.text()))
        self.ramp_frequency.clear()
        self.ramp_values_list.setText(f"Ramp values: {self.ramp_pulses_array}")

    def ramp_array_remove_value(self):
        if self.ramp_pulses_array:
            self.ramp_pulses_array.pop()
            self.ramp_values_list.setText(f"Ramp values: {self.ramp_pulses_array}")

    def ramp_array_clear(self):
        self.ramp_pulses_array.clear()
        self.ramp_values_list.setText("Ramp values: NA")

    def update_generation_status(self, datasize):
        self.sequence_defined_status.setIcon(QIcon("Icons/led_green.png"))
        self.sequence_defined_label.setText("SEQUENCE CORRECTLY GENERATED")
        self.sequence_defined_label.setFont(QFont("Arial", 10))
        self.sequence_defined_label.setStyleSheet("""
                                        QLabel {
                                            color: green;
                                            font-size: 11pt;
                                            font-weight: bold;
                                        }
                                        """)
        self.sequence_defined_status.setStyleSheet("""
                                           QPushButton {
                                               border: 2px solid green;
                                               border-radius: 5px;
                                               background-color: #f0f0f0;
                                               padding: 2px;
                                           }
                                           QPushButton:hover {
                                               background-color: #f0f0f0;
                                           }
                                           QPushButton:pressed {
                                               background-color: #f0f0f0;
                                           }
                                        """)
        self.sequence_defined_label.setWordWrap(True)
        self.sequence_defined_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sequence_defined_label.setFixedSize(100, 50)
        self.sequence_sent_label.setText("SENDING SEQUENCE...")
        self.sequence_sent_label.setFont(QFont("Arial", 10))
        self.sequence_sent_label.setStyleSheet("""
                                                QLabel {
                                                    color: black;
                                                    font-size: 11pt;
                                                    font-weight: bold;
                                                }
                                                """)
        self.sequence_sent_label.setWordWrap(True)
        self.sequence_sent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sequence_sent_label.setFixedSize(100, 50)

        self.datasize = datasize

    def update_sending_status(self, success, stop_number):
        if success:
            self.sequence_sent_status.setIcon(QIcon("Icons/led_green.png"))
            self.sequence_sent_label.setText("SEQUENCE CORRECTLY SENT")
            self.sequence_sent_label.setFont(QFont("Arial", 10))
            self.sequence_sent_label.setStyleSheet("""
                                                    QLabel {
                                                        color: green;
                                                        font-size: 11pt;
                                                        font-weight: bold;
                                                    }
                                                    """)
            self.sequence_sent_status.setStyleSheet("""
                                                       QPushButton {
                                                           border: 2px solid green;
                                                           border-radius: 5px;
                                                           background-color: #f0f0f0;
                                                           padding: 2px;
                                                       }
                                                       QPushButton:hover {
                                                           background-color: #f0f0f0;
                                                       }
                                                       QPushButton:pressed {
                                                           background-color: #f0f0f0;
                                                       }
                                                    """)
            self.sequence_sent_label.setWordWrap(True)
            self.sequence_sent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.sequence_sent_label.setFixedSize(100, 50)
            self.stop_condition_signal.emit(stop_number)

            self.gi8.sequences_sent = True
            for idx in range(len(self.gi8.platform_regions[:-1])):
                self.gi8.platform_states[idx] = not self.gi8.platform_states[idx]
                self.current_image = self.gi8.draw(idx, self.current_image)
            self.platform_status_label.setPixmap(self.current_image)

        else:
            self.sequence_sent_status.setIcon(QIcon("Icons/led_red.png"))
            self.sequence_sent_label.setText("ERROR IN SENDING SEQUENCE")
            self.sequence_sent_label.setFont(QFont("Arial", 10))
            self.sequence_sent_label.setStyleSheet("""
                                                        QLabel {
                                                            color: black;
                                                            font-size: 11pt;
                                                            font-weight: bold;
                                                        }
                                                        """)
            self.sequence_sent_label.setWordWrap(True)
            self.sequence_sent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.sequence_sent_label.setFixedSize(100, 50)

            self.gi8.sequences_sent = False
            for idx in range(len(self.gi8.platform_regions[:-1])):
                self.gi8.platform_states[idx] = not self.gi8.platform_states[idx]
                self.current_image = self.gi8.draw(idx, self.current_image)
            self.platform_status_label.setPixmap(self.current_image)

    def play_sequence(self):
        if self.master_task is None:
            QMessageBox.critical(self, "Error", "No sequence defined.")
            return
        
        if self.files_list.count() > 0:
            reply = QMessageBox.question(self, "Warning", "Do you want to start a new experiment without saving the previous data?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        self.files_list.clear()
        self.frames_acquired_label.setText("<b>Frames Acquired:</b> N/A")
        self.frames_shape_label.setText("<b>Frames Shape:</b> N/A")

        not_started_devices = []
        try:
            if not self.control_dmd_gui.start_done:
                not_started_devices.append("DMDs")
        except AttributeError:
            pass
        try:
            if not self.control_camera_gui.start_done:
                not_started_devices.append("CAMs")
        except AttributeError:
            pass

        if not_started_devices:
            device_list = "\n".join(f"- {device}" for device in not_started_devices)
            message = f"Start command was not sent to the DMDs:\n{device_list}\n\nDo you want to proceed anyway?"
            reply = QMessageBox.question(
                self,
                "Warning",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        self.experiment_info["start_time"] = datetime.now().strftime("%H:%M:%S")

        self.start_pushed = True
        self.play_sequence_thread.start()

    def save_files(self):
        if self.files_list.count() == 0:
            QMessageBox.critical(self, "Error", "No files to save.")
            return

        self.frames_acquired_label.setText("<b>Frames Acquired:</b> N/A")
        self.frames_shape_label.setText("<b>Frames Shape:</b> N/A")

        directory_name = f"{self.today_date}"
        directory_path = os.path.join(self.parent_directory, directory_name)

        if os.path.exists(directory_path):
            i = 1
            subfolders = [f.name for f in os.scandir(directory_path) if f.is_dir()]
            find = False
            while not find:
                sub_directory_name = f"Experiment {i}"
                if sub_directory_name not in subfolders:
                    sub_directory_path = os.path.join(directory_path, sub_directory_name)
                    os.makedirs(sub_directory_path)
                    find = True
                i += 1

        else:
            os.makedirs(directory_path)

            sub_directory_name = "Experiment 1"
            sub_directory_path = os.path.join(directory_path, sub_directory_name)
            os.makedirs(sub_directory_path)

        tiff.imwrite(os.path.join(sub_directory_path, "CAM1.tif"), self.cam1_acquisition, photometric="minisblack")
        tiff.imwrite(os.path.join(sub_directory_path, "CAM2.tif"), self.cam2_acquisition, photometric="minisblack")
        tiff.imwrite(os.path.join(sub_directory_path, "CAM3.tif"), self.cam3_acquisition, photometric="minisblack")
        tiff.imwrite(os.path.join(sub_directory_path, "CAM4.tif"), self.cam4_acquisition, photometric="minisblack")

        reply = QMessageBox.question(self, "LOG File Generator", "Do you want to generate a LOG file?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.experiment_notes_gui.exec() == QDialog.DialogCode.Accepted:
                self.experiment_info["notes"] = self.experiment_notes_gui.notes

            self.experiment_info["saving_time"] = datetime.now().strftime("%H:%M:%S")
            if "numb_dmd_connected" in self.experiment_info.keys():
                self.experiment_info["file_directory"] = os.listdir('flash_firmware')[0]

            file_log_path = os.path.join(sub_directory_path, "Experiment Info.txt")
            sf.generate_experiment_log(file_log_path, self.experiment_info)

        self.files_list.clear()

    def show_frames(self, cam1_acquisition, cam2_acquisition, cam3_acquisition, cam4_acquisition):
        self.control_camera_gui.start_done = False
        self.start_pushed = False

        self.cam1_acquisition = np.array(cam1_acquisition, dtype=np.uint16)
        self.cam2_acquisition = np.array(cam2_acquisition, dtype=np.uint16)
        self.cam3_acquisition = np.array(cam3_acquisition, dtype=np.uint16)
        self.cam4_acquisition = np.array(cam4_acquisition, dtype=np.uint16)

        min_len = min(self.cam1_acquisition.shape[0], self.cam2_acquisition.shape[0], self.cam3_acquisition.shape[0], self.cam4_acquisition.shape[0])
        self.cam1_acquisition = self.cam1_acquisition[:min_len]
        self.cam2_acquisition = self.cam2_acquisition[:min_len]
        self.cam3_acquisition = self.cam3_acquisition[:min_len]
        self.cam4_acquisition = self.cam4_acquisition[:min_len]

        if self.constant_check.isChecked() and self.experiment_info["stimulation_protocol"][3] > min_len:
            self.experiment_info["stimulation_protocol"][3] = min_len

        self.frames_acquired_label.setText(f"<b>Frames Acquired:</b> {self.cam1_acquisition.shape[0]}")
        self.frames_shape_label.setText(f"<b>Frames Shape:</b> {self.cam1_acquisition.shape[1]} x {self.cam1_acquisition.shape[2]}")

        self.experiment_info["numb_frames_acquired"] = self.cam1_acquisition.shape[0]

        self.files_list.addItem("Acquisition CAM 1")
        self.files_list.addItem("Acquisition CAM 2")
        self.files_list.addItem("Acquisition CAM 3")
        self.files_list.addItem("Acquisition CAM 4")

        self.save_all_files.setEnabled(True)

    def start_alignment(self):
        self.experiment_info["alignment_done"] = True

        self.control_camera_gui.switch_subarray_mode.changeStatusManually()
        self.control_camera_gui.switch_roi_label.setText("OFF")
        self.control_camera_gui.switch_trigger_mode.changeStatusManually()
        self.control_camera_gui.switch_trigger_label.setText("OFF")

        self.start_alignment_thread.start()

    def start_control_dmd_gui(self):
        if self.control_dmd_gui is not None:
            self.dmd_connected_signal.emit()

        elif len(self.dmd_connected) == 0:
            QMessageBox.warning(self, "Warning", "No DMDs connected")
            return

    def start_timer(self):
        self.elapsed_seconds = 60
        self.avoid_overray = True
        self.timer_label.setText("01:00")
        self.enable_timer.start(1000)

    def stop_alignment(self):
        if not self.control_camera_gui.live:
            QMessageBox.warning(self, "Warning", "No live camera detected")
            return

        self.stop_alignment_thread.start()

    def stop_sequence(self):
        if not self.start_pushed:
            QMessageBox.warning(self, "Warning", "No Sequence Playing!")
            return

        self.start_pushed = False
        self.control_camera_gui.start_done = False
        self.control_camera_gui.acquire_thread.request_stop()
        n_frames_acquired = self.control_camera_gui.acquire_thread.n_frames_acquired1

        self.experiment_info["stopped_before"] = True
        self.control_camera_gui.stop_recording(n_frames_acquired)

        self.control_camera_gui.cam1_acquisition = sf.elaborate_frame(self.control_camera_gui.cam1_acquisition)
        self.control_camera_gui.cam2_acquisition = sf.elaborate_frame(self.control_camera_gui.cam2_acquisition)
        self.control_camera_gui.cam3_acquisition = sf.elaborate_frame(self.control_camera_gui.cam3_acquisition)
        self.control_camera_gui.cam4_acquisition = sf.elaborate_frame(self.control_camera_gui.cam4_acquisition)
        self.show_frames(self.control_camera_gui.cam1_acquisition, self.control_camera_gui.cam2_acquisition, self.control_camera_gui.cam3_acquisition, self.control_camera_gui.cam4_acquisition)

    def send_sequence(self, array_defined):
        self.array_defined = array_defined
        self.send_enable_dmd_thread.start()

    def start_task(self):
        self.start_task_thread.start()

    def toggle_constant(self):
        if self.constant_check.isChecked():
            ss.update_groupbox_style(self.constant_group,'checked', self.label5, self.label6, self.label7)
            self.delay_line.setEnabled(True)
            self.duration_line.setEnabled(True)
            self.frequency_line.setEnabled(True)
        else:
            ss.update_groupbox_style(self.constant_group,'unchecked', self.label5, self.label6, self.label7)
            self.delay_line.setEnabled(False)
            self.duration_line.setEnabled(False)
            self.frequency_line.setEnabled(False)

    def toggle_pre_ill_time(self):
        if self.pre_ill_phase_check.isChecked():
            ss.update_groupbox_style(self.pre_ill_group,'checked', self.label1)
            self.pre_ill_time_line.setEnabled(True)
        else:
            ss.update_groupbox_style(self.pre_ill_group,'unchecked', self.label1)
            self.pre_ill_time_line.setEnabled(False)

    def toggle_pre_stim_time(self):
        if self.pre_stim_phase_check.isChecked():
            ss.update_groupbox_style(self.pre_stim_group,'checked', self.label2)
            self.pre_stim_time_line.setEnabled(True)
        else:
            ss.update_groupbox_style(self.pre_stim_group,'unchecked', self.label2)
            self.pre_stim_time_line.setEnabled(False)

    def toggle_stim_time(self):
        if self.stim_phase_check.isChecked():
            ss.update_groupbox_style(self.stim_group,'checked', self.label3)
            self.stim_time_line.setEnabled(True)
        else:
            ss.update_groupbox_style(self.stim_group,'unchecked', self.label3)
            self.stim_time_line.setEnabled(False)

    def toggle_post_stim_time(self):
        if self.post_stim_phase_check.isChecked():
            ss.update_groupbox_style(self.post_stim_group,'checked', self.label4)
            self.post_stim_time_line.setEnabled(True)
        else:
            ss.update_groupbox_style(self.post_stim_group,'unchecked', self.label4)
            self.post_stim_time_line.setEnabled(False)

    def toggle_ramp(self):
        if self.ramp_check.isChecked():
            ss.update_groupbox_style(self.ramp_group,'checked', self.label12, self.label12)
            self.ramp_frequency.setEnabled(True)
            self.numb_pulses_ramp.setEnabled(True)
            self.ramp_values_list.setStyleSheet("background-color: rgb(255, 255, 255);")
            for button in [self.add_value, self.remove_value, self.clear_array]:
                button.setEnabled(True)
        else:
            ss.update_groupbox_style(self.ramp_group,'unchecked', self.label12, self.label12)
            self.ramp_frequency.setEnabled(False)
            self.numb_pulses_ramp.setEnabled(False)
            self.ramp_values_list.setStyleSheet("background-color: #f0f0f0;")
            for button in [self.add_value, self.remove_value, self.clear_array]:
                button.setEnabled(False)

    def toggle_s1s2(self):
        if self.s1s2_check.isChecked():
            ss.update_groupbox_style(self.s1s2_group,'checked', self.label8, self.label9, self.label10, self.label11)
            self.s0_cl_line.setEnabled(True)
            self.s0_precond_line.setEnabled(True)
            self.sf_cl_line.setEnabled(True)
            self.step_line.setEnabled(True)
        else:
            ss.update_groupbox_style(self.s1s2_group,'unchecked', self.label8, self.label9, self.label10, self.label11)
            self.s0_cl_line.setEnabled(False)
            self.s0_precond_line.setEnabled(False)
            self.sf_cl_line.setEnabled(False)
            self.step_line.setEnabled(False)

    def update_connection_status(self):
        if sf.check_pcie_connectivity():
            icon = QIcon("Icons/led_green.png")
            self.connection_status_button.setText("Connected")
            self.connection_status_button.setStyleSheet("""
                                            QPushButton {
                                                border: 2px solid green;
                                                border-radius: 10px;
                                                background-color: #ccffcc;
                                                padding: 10px;
                                            }
                                        """)
            self.connection_status_button.setIcon(icon)

            self.all_set_zero_label.setText("All Lines Set to 0")
            self.all_set_zero_status.setIcon(icon)

    def update_dmds_grid(self, success, dmd):
        if success:
            self.dmd_connected.append(dmd)
            if dmd == 1:
                ss.update_toolbutton_style(self.dmd1_connection, 'on')
            elif dmd == 2:
                ss.update_toolbutton_style(self.dmd2_connection, 'on')
            elif dmd == 3:
                ss.update_toolbutton_style(self.dmd3_connection, 'on')
            elif dmd == 4:
                self.check_cameras_connection()
                ss.update_toolbutton_style(self.dmd4_connection, 'on')
                self.experiment_info["numb_dmd_connected"] = len(self.dmd_connected)

                if len(self.dmd_connected) > 0:
                    self.control_dmd_gui = ConfigureDMD(parent=self)
                    self.control_dmd_gui.new_info_signal.connect(self.add_info_to_experiment)
                    self.control_dmd_gui.show()

        else:
            if dmd == 1:
                ss.update_toolbutton_style(self.dmd1_connection, 'off')
            elif dmd == 2:
                ss.update_toolbutton_style(self.dmd2_connection, 'off')
            elif dmd == 3:
                ss.update_toolbutton_style(self.dmd3_connection, 'off')
            elif dmd == 4:
                self.check_cameras_connection()
                ss.update_toolbutton_style(self.dmd4_connection, 'off')

                if len(self.dmd_connected) > 0:
                    self.control_dmd_gui = ConfigureDMD(parent=self)
                    self.control_dmd_gui.new_info_signal.connect(self.add_info_to_experiment)
                    self.control_dmd_gui.show()

    def update_green_cameras_grid(self, n_cam, cam):
        if n_cam == 1:
            self.cam1 = cam
            self.cameras_connected.append(n_cam)
            ss.update_toolbutton_style(self.camera1_connection, 'on')
        elif n_cam == 2:
            self.cam2 = cam
            self.cameras_connected.append(n_cam)
            ss.update_toolbutton_style(self.camera2_connection, 'on')
        elif n_cam == 3:
            self.cam3 = cam
            self.cameras_connected.append(n_cam)
            ss.update_toolbutton_style(self.camera3_connection, 'on')
        elif n_cam == 4:
            self.cam4 = cam
            self.cameras_connected.append(n_cam)
            ss.update_toolbutton_style(self.camera4_connection, 'on')

    def update_red_cameras_grid(self):
        if 1 not in self.cameras_connected:
            ss.update_toolbutton_style(self.camera1_connection, 'off')
        if 2 not in self.cameras_connected:
            ss.update_toolbutton_style(self.camera2_connection, 'off')
        if 3 not in self.cameras_connected:
            ss.update_toolbutton_style(self.camera3_connection, 'off')
        if 4 not in self.cameras_connected:
            ss.update_toolbutton_style(self.camera4_connection, 'off')

        if len(self.cameras_connected) == 4:
            self.start_alignment_button.setEnabled(True)
            self.stop_alignment_button.setEnabled(True)
            self.control_camera_gui = ConfigureCamera(parent=self)
            self.control_camera_gui.acquire_thread.send_frames.connect(self.show_frames)
            self.control_camera_gui.show()
            self.control_camera_gui.new_info_signal.connect(self.add_info_to_experiment)
            self.control_camera_gui.update_stop_number_signal.connect(self.update_stop_number_label)
            self.enable_preview_signal.emit(self.cam1, self.cam2, self.cam3, self.cam4)
            self.experiment_info["numb_cam_connected"] = len(self.cameras_connected)

        else:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setText("All cameras must be connected.<br>Please check the connections and then click <b>Retry</b>.")
            msg_box.setWindowTitle("Warning")
            msg_box.exec()

    def update_stop_number_label(self, stop_number):
        self.stop_condition_label.setText(f"<b>Stop Condition:</b> {stop_number}")

    def update_time(self):
        if self.elapsed_seconds > 0:
            self.elapsed_seconds -= 1
            minutes = self.elapsed_seconds // 60
            seconds = self.elapsed_seconds % 60
            self.timer_label.setText(f"{minutes:02d}:{seconds:02d}")
        else:
            self.enable_timer.stop()
            self.timer_label.setText("00:00")
            self.avoid_overray = False

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Are you sure you want to close the window?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.cam1 is not None:
                self.cam1.stopCamera()
            if self.cam2 is not None:
                self.cam2.stopCamera()
            if self.cam3 is not None:
                self.cam3.stopCamera()
            if self.cam4 is not None:
                self.cam4.stopCamera()

            self.control_dmd_gui.close()
            self.control_camera_gui.close()

            event.accept()

        else:
            event.ignore()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("/Icons/panoramic.ico"))

    my_app_id = 'optocardlab.device.panoramic'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(my_app_id)

    main_window = DefineSequenceAndControlPlatformGUI()
    main_window.show()
    sys.exit(app.exec())


