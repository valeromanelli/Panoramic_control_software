from PyQt6 import QtCore
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPainter, QBrush, QColor, QIcon, QFont
from PyQt6.QtWidgets import QWidget, QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QGroupBox, QFormLayout, \
    QDoubleSpinBox, QSpinBox, QHBoxLayout, QListWidget, QListWidgetItem, QApplication
import style_sheet as ss
from sequenciator import SequenciatorThreshold
import nidaqmx
from nidaqmx.constants import LineGrouping, AcquisitionType


class FlashDevice:
    def __init__(self):
        self.mfg = ''
        self.mfg_id = 0
        self.lmfg_id = 0
        self.dev = 0
        self.dev_id = 0
        self.ldev_id = 0
        self.size_mbit = 0
        self.type = ''
        self.num_sectors = 0
        self.sector_arr = []


class NotesDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Notes for the Experiment")
        self.setGeometry(300, 200, 300, 150)

        self.notes = ""

        layout = QVBoxLayout()
        self.label = QLabel("Insert here any notes or comments about the experiment <b>(optional)</b>:")
        self.text_edit = QTextEdit()
        self.text_edit.setFixedSize(300, 100)
        self.text_edit.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.save_button = QPushButton("Save")

        layout.addWidget(self.label)
        layout.addWidget(self.text_edit, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.save_button)
        self.setLayout(layout)

        ss.style(self)

        self.save_button.clicked.connect(self.save_notes)

    def save_notes(self):
        self.notes = self.text_edit.toPlainText()
        self.text_edit.clear()
        self.accept()


class FindThresholdDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Threshold Potential Detection")

        layout = QVBoxLayout(self)

        self.i = 0
        self.master_task = None
        self.scan_rate = 0
        self.numb_cycles = 0
        self.frequency_value = 0
        self.duration_value = 0
        self.intensity_value = 0
        self.history = {}

        settings_layout = QHBoxLayout()
        # GroupBox for general parameters
        general_group = QGroupBox("General Parameters")
        general_layout = QFormLayout()
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setDecimals(2)
        self.freq_spin.setRange(0, 10000)

        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setDecimals(2)
        self.duration_spin.setRange(0, 3600)

        self.cycles_spin = QSpinBox()
        self.cycles_spin.setRange(1, 100)

        self.intensity = QDoubleSpinBox()
        self.intensity.setRange(0, 0.70)
        self.intensity.setDecimals(2)
        self.intensity.setSingleStep(0.01)
        self.intensity.setValue(0.70)

        general_layout.addRow("Frequency (Hz):", self.freq_spin)
        general_layout.addRow("Pulse Duration (ms):", self.duration_spin)
        general_layout.addRow("Number of pulses:", self.cycles_spin)
        general_layout.addRow("Blue LED Intensity (mW/mm<sup>2</sup>):", self.intensity)
        general_group.setLayout(general_layout)

        info_confirm_layout = QVBoxLayout()

        # GroupBox for the info
        info_group = QGroupBox("General Infos")
        info_group.setFixedWidth(210)
        info_layout = QFormLayout()

        self.signal_duration_label = QLabel("N/A")
        self.numb_of_pulses_x_cycle_label = QLabel("N/A")
        self.duty_cycle_set_label = QLabel("N/A")

        info_layout.addRow("Signal Duration (s):", self.signal_duration_label)
        info_layout.addRow("Number of Pulses per Cycle:", self.numb_of_pulses_x_cycle_label)
        info_layout.addRow("Duty Cycle Set (%):", self.duty_cycle_set_label)
        info_group.setLayout(info_layout)

        self.try_button = QPushButton("Try")

        info_confirm_layout.addWidget(info_group)
        info_confirm_layout.addWidget(self.try_button)

        settings_layout.addWidget(general_group)
        settings_layout.addLayout(info_confirm_layout)

        # GroupBox for the status
        status_group = QGroupBox("Potential Threshold Detection")
        status_layout = QVBoxLayout()

        testing_layout = QFormLayout()
        self.testing_label = QLabel("<b>Testing value:</b>")
        self.testing_label.setFont(QFont("Arial", 12))
        self.testing_value = QLabel("N/A")
        testing_layout.addRow(self.testing_label, self.testing_value)

        play_layout = QHBoxLayout()
        self.sequence_play = QPushButton()
        self.sequence_play.setIcon(QIcon("Icons/led_gray.png"))
        self.play_label = QLabel("No Sequence Currently Playing")
        self.play_label.setFont(QFont("Arial", 12))
        play_layout.addWidget(self.sequence_play)
        play_layout.addWidget(self.play_label)
        play_layout.addStretch()

        conf_esc_layout = QHBoxLayout()
        self.confirm_button = QPushButton("✅ Confirm")
        self.exclude_button = QPushButton("❌ Exclude")
        conf_esc_layout.addWidget(self.confirm_button)
        conf_esc_layout.addWidget(self.exclude_button)

        self.history_button = QPushButton("Display Value History")

        status_layout.addLayout(testing_layout)
        status_layout.addLayout(play_layout)
        status_layout.addLayout(conf_esc_layout)
        status_layout.addWidget(self.history_button)
        status_group.setLayout(status_layout)

        layout.addLayout(settings_layout)
        layout.addWidget(status_group)

        ss.style(widget=self)

        # Connections
        self.try_button.clicked.connect(self.generate)
        self.confirm_button.clicked.connect(self.confirm)
        self.exclude_button.clicked.connect(self.exclude)
        self.history_button.clicked.connect(self.show_history)

    # Methods
    def confirm(self):
        self.history[self.intensity_value] = "ok"

    def exclude(self):
        self.history[self.intensity_value] = "fail"

    def generate(self):
        if self.i == 0:
            self.numb_cycles = self.cycles_spin.value()
            self.frequency_value = self.freq_spin.value()
            self.duration_value = self.duration_spin.value()
            self.intensity_value = self.intensity.value()
            self.sequenciator = SequenciatorThreshold(self.numb_cycles, self.frequency_value, self.duration_value)

            blue_duty_cycle = round(self.intensity_value * 100 / 1.4, 2)
            self.testing_value.setText(f"{self.intensity_value:.2f}")
            self.signal_duration_label.setText(f"{self.numb_cycles / self.frequency_value}")
            self.numb_of_pulses_x_cycle_label.setText(f"{self.sequenciator.numb_periods_x_cycle}")
            self.duty_cycle_set_label.setText(f"{blue_duty_cycle:.2f}")

            QApplication.processEvents()

            self.array_to_send, self.scan_rate = self.sequenciator.define_array_to_send(blue_duty_cycle)
            self.i += 1

        else:
            new_numb_cycles = self.cycles_spin.value()
            new_frequency_value = self.freq_spin.value()
            new_duration_value = self.duration_spin.value()
            new_intensity_value = self.intensity.value()

            if new_intensity_value == self.intensity_value and new_numb_cycles == self.numb_cycles and \
               new_frequency_value == self.frequency_value and new_duration_value == self.duration_value:
                self.testing_value.setText(f"{self.intensity_value:.2f}")
                self.sequence_play.setIcon(QIcon("Icons/led_green.png"))
                self.play_label.setText("Sequence is Playing")
                QApplication.processEvents()
                self.master_task.start()
                self.master_task.wait_until_done(timeout=1 / self.scan_rate * self.array_to_send.size + 1)
                self.master_task.stop()
                self.sequence_play.setIcon(QIcon("Icons/led_gray.png"))
                self.play_label.setText("No Sequence Currently Playing")
                QApplication.processEvents()
                return

            else:
                if self.master_task is not None:
                    self.master_task.close()
                    self.master_task = None

                if new_numb_cycles != self.numb_cycles:
                    self.sequenciator.change_numb_cycles(new_numb_cycles)
                    self.numb_cycles = new_numb_cycles

                    self.signal_duration_label.setText(f"{self.numb_cycles / self.frequency_value:.2f}")
                    QApplication.processEvents()

                if new_frequency_value != self.frequency_value:
                    self.sequenciator.change_frequency(new_frequency_value)
                    self.frequency_value = new_frequency_value

                    self.signal_duration_label.setText(f"{self.numb_cycles / self.frequency_value:.2f}")
                    QApplication.processEvents()

                if new_duration_value != self.duration_value:
                    self.sequenciator.change_cycle_duration(new_duration_value)
                    self.duration_value = new_duration_value

                    self.numb_of_pulses_x_cycle_label.setText(f"{self.sequenciator.numb_periods_x_cycle}")
                    QApplication.processEvents()

                self.intensity_value = new_intensity_value
                blue_duty_cycle = round(self.intensity_value * 100 / 1.4, 2)
                self.testing_value.setText(f"{self.intensity_value:.2f}")
                self.duty_cycle_set_label.setText(f"{blue_duty_cycle:.2f}")
                self.array_to_send, self.scan_rate = self.sequenciator.define_array_to_send(blue_duty_cycle)

        self.master_task = nidaqmx.Task()
        self.master_task.do_channels.add_do_chan("Dev2/port0/line0:31", line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
        self.master_task.timing.cfg_samp_clk_timing(rate=self.scan_rate, sample_mode=AcquisitionType.FINITE, samps_per_chan=self.array_to_send.size)
        self.master_task.write(self.array_to_send)

        self.sequence_play.setIcon(QIcon("Icons/led_green.png"))
        self.play_label.setText("Sequence is Playing")
        QApplication.processEvents()
        self.master_task.start()
        self.master_task.wait_until_done(timeout=1 / self.scan_rate * self.array_to_send.size + 1)
        self.master_task.stop()
        self.sequence_play.setIcon(QIcon("Icons/led_gray.png"))
        self.play_label.setText("No Sequence Currently Playing")
        QApplication.processEvents()

    def show_history(self):
        dialog = HistoryDialog(self.history)
        dialog.exec()

    def closeEvent(self, event):
        if self.master_task is not None:
            self.master_task.close()
            self.master_task = None


class HistoryDialog(QDialog):
    def __init__(self, storico_dict):
        super().__init__()
        self.setWindowTitle("Tested Values History")
        layout = QVBoxLayout()

        self.list_widget = QListWidget()
        for valore, stato in sorted(storico_dict.items()):
            item = QListWidgetItem(f"  {valore:.2f}")
            if stato == "ok":
                item.setText("✅  " + item.text())
            else:
                item.setText("❌  " + item.text())
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)
        self.setLayout(layout)


class QToggleSwitch(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 20)
        self.checked = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        self.checked = not self.checked
        self.update()
        self.toggled.emit(self.checked)

    def changeStatusManually(self):
        self.checked = False
        self.update()

    def paintEvent(self, event):
        # Drawing the switch
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Background
        if self.checked:
            painter.setBrush(QBrush(QColor(0, 200, 0)))
        else:
            painter.setBrush(QBrush(QColor(200, 0, 0)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), self.height() / 2, self.height() / 2)
        # Handle
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        if self.checked:
            painter.drawEllipse(self.width() - self.height(), 0, self.height(), self.height())
        else:
            painter.drawEllipse(0, 0, self.height(), self.height())

    def sizeHint(self):
        return QSize(60, 30)

    toggled = QtCore.pyqtSignal(bool)


if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = FindThresholdDialog()
    dialog.show()
    sys.exit(app.exec())