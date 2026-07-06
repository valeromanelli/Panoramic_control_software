import os.path
import time
import nidaqmx
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, QEventLoop, QTimer, Qt
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtWidgets import QMessageBox
from nidaqmx.constants import LineGrouping, AcquisitionType
import math
import firmware_commands
import support_functions as sf
import dlpc350_commands as comm
from camere_controls import camera
import camere_basic_controls as cbc
from procrafter4500 import connect_usb
import support_classes as sc
from firmware_commands import obtain_images_loaded
import style_sheet as ss
from sequenciator import Sequenciator, SequenciatorJunior
import cv2


# CONTROL PLATFORM GUI
class CheckCameraConnectionThread(QThread):
    camera_found = pyqtSignal(int, object)
    process_finished = pyqtSignal()
    def __init__(self):
        super().__init__()

    def run(self):
        for i in range(4):
            try:
                cam_par = camera(i)
            except cbc.DCAMException:
                continue

            if cam_par.getSerialNumber() == b'S/N: 306342':
                cam1 = cam_par
                cam1.initializeCamera()
                cam1.setAcquisitionMode(sf.MODE_CONTINUOUS)
                cam1.setExposure(0.01)
                self.camera_found.emit(1, cam1)

            elif cam_par.getSerialNumber() == b'S/N: 306343':
                cam2 = cam_par
                cam2.initializeCamera()
                cam2.setAcquisitionMode(sf.MODE_CONTINUOUS)
                cam2.setExposure(0.01)
                self.camera_found.emit(2, cam2)

            elif cam_par.getSerialNumber() == b'S/N: 306340':
                cam3 = cam_par
                cam3.initializeCamera()
                cam3.setAcquisitionMode(sf.MODE_CONTINUOUS)
                cam3.setExposure(0.01)
                self.camera_found.emit(3, cam3)

            elif cam_par.getSerialNumber() == b'S/N: 301529':
                cam4 = cam_par
                cam4.initializeCamera()
                cam4.setAcquisitionMode(sf.MODE_CONTINUOUS)
                cam4.setExposure(0.01)
                self.camera_found.emit(4, cam4)

        self.process_finished.emit()
        self.quit()
        self.wait()


class CheckDMDConnectionThread(QThread):
    process_finished = pyqtSignal(bool, int)
    start_control_dmd_gui = pyqtSignal()
    def __init__(self):
        super().__init__()

    def run(self):
        sf.select_channel(1)
        try:
            comm.set_power_mode(False)
            self.process_finished.emit(True, 1)
        except AttributeError:
            self.process_finished.emit(False, 1)

        sf.select_channel(2)
        try:
            comm.set_power_mode(False)
            self.process_finished.emit(True, 2)
        except AttributeError:
            self.process_finished.emit(False, 2)

        sf.select_channel(3)
        try:
            comm.set_power_mode(False)
            self.process_finished.emit(True, 3)
        except AttributeError:
            self.process_finished.emit(False, 3)

        sf.select_channel(4)
        try:
            comm.set_power_mode(False)
            self.process_finished.emit(True, 4)
        except AttributeError:
            self.process_finished.emit(False, 4)

        sf.select_channel(0)

        self.start_control_dmd_gui.emit()

        self.quit()
        self.wait()


class EnableDMDThread(QThread):
    array_defined_signal = pyqtSignal(object)
    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

    def run(self):
        self.parent.enable_dmd_button.setEnabled(False)
        sequenciator_junior = SequenciatorJunior(self.parent.red_dc_dmd1.value(), self.parent.blue_dc_dmd1.value(),
                                                 self.parent.red_dc_dmd2.value(), self.parent.blue_dc_dmd2.value(),
                                                 self.parent.red_dc_dmd3.value(), self.parent.blue_dc_dmd3.value(),
                                                 self.parent.red_dc_dmd4.value(), self.parent.blue_dc_dmd4.value())
        sequenciator_junior.enable_dmd1(self.parent.red_led_dmd1.isChecked(), self.parent.blue_led_dmd1.isChecked())
        sequenciator_junior.enable_dmd2(self.parent.red_led_dmd2.isChecked(), self.parent.blue_led_dmd2.isChecked())
        sequenciator_junior.enable_dmd3(self.parent.red_led_dmd3.isChecked(), self.parent.blue_led_dmd3.isChecked())
        sequenciator_junior.enable_dmd4(self.parent.red_led_dmd4.isChecked(), self.parent.blue_led_dmd4.isChecked())

        array_to_send = sequenciator_junior.define_array_to_send()

        self.array_defined_signal.emit(array_to_send)

        self.quit()
        self.wait()


class FindThresholdThread(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

    def run(self):
        pass


class GenerateSequenceThread(QThread):
    update_generation_signal = pyqtSignal(int)
    update_sending_signal = pyqtSignal(bool, int)
    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

    def run(self):
        real_total_time = 0

        real_pre_ill_time = 0
        real_pre_stim_time = 0
        real_stim_time = 0
        real_post_stim_time = 0

        acquiring_time = 0

        phases_list = []

        sequence_generator = Sequenciator(self.parent.scan_rate, self.parent.red_duty_cycle, self.parent.blue_duty_cycle, self.parent.electrical_stimulation)

        if self.parent.pre_ill_phase_check.isChecked():
            if self.parent.pre_ill_time_line.text() == "":
                QMessageBox.warning(self.parent, "Warning", "Please insert the time for the Pre-Illumination phase.")
                return
            else:
                pre_ill_time = int(self.parent.pre_ill_time_line.text())
                real_pre_ill_time = round(sequence_generator.define_pre_ill_array(pre_ill_time), 6)
                real_total_time += real_pre_ill_time
                phases_list.append(("Pre-Illumination", pre_ill_time * 1e-3, real_pre_ill_time))

        if self.parent.pre_stim_phase_check.isChecked():
            if self.parent.pre_stim_time_line.text() == "":
                QMessageBox.warning(self.parent, "Warning", "Please insert the time for the Pre-Stimulation phase.")
                return
            else:
                pre_stim_time = int(self.parent.pre_stim_time_line.text())
                acquiring_time += int(self.parent.pre_stim_time_line.text())
                real_pre_stim_time = round(sequence_generator.define_pre_stim_array(pre_stim_time), 6)
                real_total_time += real_pre_stim_time
                phases_list.append(("Pre-Stimulation", pre_stim_time * 1e-3, real_pre_stim_time))

        if self.parent.stim_poststim_repetitions > 1:
            if self.parent.stim_time_line.text() == "" or self.parent.post_stim_time_line.text() == "":
                QMessageBox.warning(self.parent, "Warning", "Please insert the time for the phases.")
                return

            for i in range(self.parent.stim_poststim_repetitions):
                stim_time = int(self.parent.stim_time_line.text())
                acquiring_time += int(self.parent.stim_time_line.text())
                real_stim_time = round(sequence_generator.define_stim_array(stim_time), 6)
                real_total_time += real_stim_time

                post_stim_time = int(self.parent.post_stim_time_line.text())
                acquiring_time += int(self.parent.post_stim_time_line.text())
                real_post_stim_time = round(sequence_generator.define_post_stim_array(post_stim_time), 6)
                real_total_time += real_post_stim_time

            phases_list.append(("Stimulation", stim_time * 1e-3, real_stim_time))
            phases_list.append(("Post-Stimulation", post_stim_time * 1e-3, real_post_stim_time))

        else:
            if self.parent.stim_phase_check.isChecked():
                if self.parent.stim_time_line.text() == "":
                    QMessageBox.warning(self.parent, "Warning", "Please insert the time for the Stimulation phase.")
                    return
                else:
                    stim_time = int(self.parent.stim_time_line.text())
                    acquiring_time += int(self.parent.stim_time_line.text())
                    real_stim_time = round(sequence_generator.define_stim_array(stim_time), 6)
                    real_total_time += real_stim_time
                    phases_list.append(("Stimulation", stim_time * 1e-3, real_stim_time))

            if self.parent.post_stim_phase_check.isChecked():
                if self.parent.post_stim_time_line.text() == "":
                    QMessageBox.warning(self.parent, "Warning", "Please insert the time for the Post-Stimulation phase.")
                    return
                else:
                    post_stim_time = int(self.parent.post_stim_time_line.text())
                    acquiring_time += int(self.parent.post_stim_time_line.text())
                    real_post_stim_time = round(sequence_generator.define_post_stim_array(post_stim_time), 6)
                    real_total_time += real_post_stim_time
                    phases_list.append(("Post-Stimulation", post_stim_time * 1e-3, real_post_stim_time))

        self.array_to_send, shock = sequence_generator.define_array_to_send()
        np.save("array.npy", self.array_to_send)
        if shock:
            self.parent.electrical_stimulation_defined.setIcon(QIcon("Icons/led_green.png"))
            self.parent.electrical_stimulation_label.setText("ELECTRICAL STIMULATION DEFINED")
            self.parent.electrical_stimulation_label.setFont(QFont("Arial", 10))
            self.parent.electrical_stimulation_label.setStyleSheet("""
                                                                    QLabel {
                                                                        color: green;
                                                                        font-size: 11pt;
                                                                        font-weight: bold;
                                                                    }
                                                                    """)
            self.parent.electrical_stimulation_defined.setStyleSheet("""
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
            self.parent.electrical_stimulation_label.setWordWrap(True)
            self.parent.electrical_stimulation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.parent.electrical_stimulation_label.setFixedSize(100, 50)

        self.parent.experiment_info["phases"] = phases_list
        self.parent.experiment_info["real_total_duration"] = real_total_time
        self.parent.phases_info.setText(f"""
                    <b>Experiment:</b>
                    <ul>
                        <li>Red LED Intensity: {round(self.parent.red_power_value.value(), 2)} mW/mm<sup>2</sup></li>
                        <li>Blue LED Intensity: {round(self.parent.blue_power_value.value(), 2)} mW/mm<sup>2</sup></li>
                        <li>Real Pre-Illumination Time: {real_pre_ill_time} s</li>
                        <li>Real Pre-Stimulation Time: {real_pre_stim_time} s</li>
                        <li>Real Stimulation Time: {real_stim_time} s</li>
                        <li>Real Post-Stimulation Time: {real_post_stim_time} s</li>
                        <li>Electrical Stimulation Protocol: {self.parent.experiment_info["stimulation_protocol"][0] if shock else "N/A"}</li>
                        </ul>
                    """)

        self.update_generation_signal.emit(self.array_to_send.size)

        self.parent.master_task = nidaqmx.Task()
        self.parent.master_task.do_channels.add_do_chan("Dev2/port0/line0:31", line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
        self.parent.master_task.timing.cfg_samp_clk_timing(rate=self.parent.scan_rate, sample_mode=AcquisitionType.FINITE,samps_per_chan=self.array_to_send.size)
        number_of_samples_written = self.parent.master_task.write(self.array_to_send)

        if number_of_samples_written == self.array_to_send.size:
            if acquiring_time > 270:
                stop_number = acquiring_time * sequence_generator.frame_rate * 1e-3
            else:
                stop_number = (acquiring_time * sequence_generator.frame_rate * 1e-3) - 2
            self.update_sending_signal.emit(True, math.floor(stop_number))
        else:
            self.update_sending_signal.emit(False, 0)


class PlaySequenceThread(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

    def run(self):
        self.parent.master_task.start()
        print(self.parent.datasize)
        self.parent.master_task.wait_until_done(timeout=self.parent.scan_time * self.parent.datasize + 1)
        self.parent.master_task.stop()

        self.quit()
        self.wait()


class StartAlignmentThread(QThread):
    process_finished = pyqtSignal(bool)
    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

    def run(self):
        self.parent.control_camera_gui.subarray_mode(True, True)
        self.parent.control_camera_gui.trigger_mode(False, True)

        self.parent.control_camera_gui.start_live()

        self.process_finished.emit(True)

        self.quit()
        self.wait()


class SendEnableDMDThread(QThread):
    ready_to_start_signal = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

    def run(self):
        self.parent.alignment_task = nidaqmx.Task()
        self.parent.alignment_task.do_channels.add_do_chan("Dev2/port0/line0:31", line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
        self.parent.alignment_task.timing.cfg_samp_clk_timing(rate=1000000, sample_mode=AcquisitionType.FINITE,
                                               samps_per_chan=self.parent.array_defined.size)
        self.parent.alignment_task.write(self.parent.array_defined)

        self.ready_to_start_signal.emit()
        self.quit()
        self.wait()


class StartTaskThread(QThread):
    change_color_signal = pyqtSignal(bool)
    start_timer_signal = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

    def run(self):
        if any([self.parent.red_led_dmd1.isChecked(), self.parent.blue_led_dmd1.isChecked()]):
            sf.select_channel(1)
            comm.pattern_display(2)
        if any([self.parent.red_led_dmd2.isChecked(), self.parent.blue_led_dmd2.isChecked()]):
            sf.select_channel(2)
            comm.pattern_display(2)
        if any([self.parent.red_led_dmd3.isChecked(), self.parent.blue_led_dmd3.isChecked()]):
            sf.select_channel(3)
            comm.pattern_display(2)
        if any([self.parent.red_led_dmd4.isChecked(), self.parent.blue_led_dmd4.isChecked()]):
            sf.select_channel(4)
            comm.pattern_display(2)

        self.parent.enable_dmd_button.setEnabled(True)
        self.change_color_signal.emit(True)
        self.parent.alignment_task.start()
        self.start_timer_signal.emit()
        for _ in range(61):
            if self.isInterruptionRequested():
                break
            time.sleep(1)

        try:
            self.parent.alignment_task.stop()
            self.parent.alignment_task.close()
        except nidaqmx.DaqWarning:
            self.parent.alignment_task.close()

        self.parent.alignment_task = None

        self.change_color_signal.emit(False)

        self.quit()
        self.wait()


class StopAlignmentThread(QThread):
    process_finished = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

    def run(self):
        self.parent.control_camera_gui.stop_live()
        time.sleep(0.3)
        self.parent.control_camera_gui.subarray_mode(False)

        self.quit()
        self.wait()


# DMD CONTROL GUI
class AcquireSingleThread(QThread):
    finished_signal = pyqtSignal(object, object, object, object)
    def __init__(self, cam1, cam2, cam3, cam4, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.cam1 = cam1
        self.cam2 = cam2
        self.cam3 = cam3
        self.cam4 = cam4

    def run(self):
        self.n_frames_acquired = 0

        self.cam1.triggerCamera(sf.MODE_PANORAMIC, 1)
        self.cam2.triggerCamera(sf.MODE_PANORAMIC, 1)
        self.cam3.triggerCamera(sf.MODE_PANORAMIC, 1)
        self.cam4.triggerCamera(sf.MODE_PANORAMIC, 1)


        while self.n_frames_acquired < 1:
            frame1 = self.cam1.readCamera()
            frame2 = self.cam2.readCamera()
            frame3 = self.cam3.readCamera()
            frame4 = self.cam4.readCamera()

            self.n_frames_acquired += 1

        self.cam1.stopAcq()
        self.cam2.stopAcq()
        self.cam3.stopAcq()
        self.cam4.stopAcq()

        self.finished_signal.emit(frame1, frame2, frame3, frame4)

        self.quit()
        self.wait()


class ShowUploadedImagesThread(QThread):
    finished_signal = pyqtSignal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    def run(self):
        verify, self.parent.actual_firmware, self.parent.m_added_splash_images, self.parent.m_splash_image_add_index, self.parent.m_splash_image_original = obtain_images_loaded(self.parent.file_to_show)
        self.parent.m_splash_image_count = self.parent.m_splash_image_original

        self.finished_signal.emit(verify)

        self.quit()
        self.wait()


class ModifyFirmwareThread(QThread):
    finished_signal = pyqtSignal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    def run(self):
        fw = self.parent.actual_firmware

        text = "abc"
        params = [0] * 32

        for i, ch in enumerate(text):
            if i > 31:
                break
            params[i] = ord(ch) & 0xFF

        app_data = bytearray(29748)
        ret, app_data = fw.write_appl_config_data(app_data, "DEFAULT.FIRMWARE_TAG", params, len(params))
        if ret < 0:
            QMessageBox.critical(self.parent, "Error", "Unable to add firmware tag information")
            return

        appl_config_data_start_address = fw.appl_config_data_flash_address - fw.FLASH_BASE_ADDRESS + 4
        fw.p_frmw_image_array = bytearray(fw.p_frmw_image_array)
        fw.p_frmw_image_array[appl_config_data_start_address:appl_config_data_start_address + len(app_data)] = app_data

        if len(self.parent.m_added_splash_images) < firmware_commands.MAX_SPLASH_IMAGES:
            none_to_add = firmware_commands.MAX_SPLASH_IMAGES - len(self.parent.m_added_splash_images)
            for i in range(none_to_add):
                self.parent.m_added_splash_images.append(None)
        count = self.parent.m_splash_image_count

        if fw.splash_init_buffer(count) < 0:
            QMessageBox.critical(self.parent, "Error", "Unable to allocate memory for splash images.")
            return

        with open("Frmw-build.log", "w") as log_file:
            log_file.write("Building Images from specified BMPs\n\n")
            for i in range(firmware_commands.MAX_SPLASH_IMAGES):
                if self.parent.m_added_splash_images[i] is None:
                    break

                img_file_path = self.parent.m_added_splash_images[i]
                file_len = os.path.getsize(img_file_path)
                with open(img_file_path, "rb") as img_file:
                    p_byte_array = img_file.read(file_len)

                    if p_byte_array is None:
                        QMessageBox.critical(self.parent, "Error", "Memory alloc for file read failed")
                        return

                log_file.write(f"{self.parent.m_added_splash_images[i]}\n")
                log_file.write(f"\tUncompressed Size = {file_len} Compression type : ")

                if "_nocomp.bmp" in self.parent.m_added_splash_images[i]:
                    compression = fw.SPLASH_UNCOMPRESSED
                elif "_rle.bmp" in self.parent.m_added_splash_images[i]:
                    compression = fw.SPLASH_RLE_COMPRESSION
                elif "_4line.bmp" in self.parent.m_added_splash_images[i]:
                    compression = fw.SPLASH_4LINE_COMPRESSION
                else:
                    compression = fw.SPLASH_NOCOMP_SPECIFIED

                ret, compression, comp_size = fw.splash_add_splash(p_byte_array, compression)
                if ret < 0:
                    filename = os.path.basename(img_file_path)

                    if ret == -4:
                        dbgStr = f"Error building firmware - {filename} is not in BMP format"
                    elif ret == -5:
                        dbgStr = f"Error building firmware - {filename} is not in 24-bit format"
                    elif ret == -1:
                        dbgStr = f"Error building firmware with {filename} - Insufficient memory"
                    else:
                        dbgStr = f"Error building firmware with {filename} - error code {ret}"

                    QMessageBox.critical(self.parent, "Error", dbgStr)
                    return

                if compression == fw.SPLASH_UNCOMPRESSED:
                    log_file.write("Uncompressed\n")
                elif compression == fw.SPLASH_RLE_COMPRESSION:
                    log_file.write("RLE Compression\n")
                elif compression == fw.SPLASH_4LINE_COMPRESSION:
                    log_file.write("4 Line Compression\n")

                log_file.write(f"Compressed Size = {comp_size}\n\n")

        new_frmw_image, new_frmw_size = fw.frmw_get_new_flash_image()

        self.finished_signal.emit(new_frmw_image)


class AddAndValidateSequenceThreadDMD1(QThread):
    finished_signal = pyqtSignal(bool)
    progress_signal = pyqtSignal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.pattern_exposure_time = 10000
        self.pattern_period = 10000
        self.red_icon = QIcon("Icons/led_red.png")
        self.green_icon = QIcon("Icons/led_green.png")

    def run(self):
        splash_lut = []
        total_steps = 6
        step = 0

        comm.set_dlpc350_in_pattern_mode()

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        num_lut_entries = 2
        num_splash_lut_entries = 0
        buf_swap = True
        self.parent.dmd1.clear_pat_lut()
        if self.parent.dmd1.add_pat_to_lut(trig_type=1, pat_num=7, led_select=1, buf_swap=buf_swap) < 0:
            QMessageBox.critical(self.parent, "Error", "Error adding red pattern to DMD 1 LUT")
            self.finished_signal.emit(False)
        splash_lut.append(self.parent.red_pattern_dmd1.value())
        num_splash_lut_entries += 1

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        splash_lut.append(self.parent.blue_pattern_dmd1.value())
        num_splash_lut_entries += 1

        if self.parent.dmd1.add_pat_to_lut(trig_type=2, pat_num=15, led_select=4, buf_swap=buf_swap) < 0:
            QMessageBox.critical(self.parent, "Error", "Error adding blue pattern to DMD 1 LUT")
            self.finished_signal.emit(False)

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        comm.set_pattern_display_mode(False)

        if comm.set_pattern_config(num_lut_entries, 1, 1, num_splash_lut_entries) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Pattern Config to DMD 1")
            self.finished_signal.emit(False)
        if comm.set_exposure_frame_period(self.pattern_exposure_time, self.pattern_period) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Exposure Period to DMD 1")
            self.finished_signal.emit(False)
        if comm.set_pattern_trigger_mode(1) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Trigger Mode to DMD 1")
            self.finished_signal.emit(False)

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        if comm.send_pat_lut(self.parent.dmd1.g_pat_lut_index, self.parent.dmd1.g_pat_lut) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Pattern LUT to DMD 1")
            self.finished_signal.emit(False)
        if comm.send_image_lut(splash_lut, num_splash_lut_entries) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Image LUT to DMD 1")
            self.finished_signal.emit(False)

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        # Validazione sequenza
        i = 0

        if comm.start_pat_lut_validate() < 0:
            QMessageBox.critical(self.parent, "Error", "Error Validating LUT Data to DMD 1")
            self.finished_signal.emit(False)

        loop = QEventLoop()
        while True:
            ready, status = comm.check_pat_lut_validate()
            if ready < 0:
                QMessageBox.critical(self.parent, "Error", "Error Validating LUT Data to DMD 1")
                self.finished_signal.emit(False)

            if ready:
                break
            else:
                # Usa QTimer per uscire dal loop dopo 1 secondo
                timer = QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(loop.quit)
                timer.start(1000)
                loop.exec()

            if i > 5:
                break
            i += 1

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        if (status & 0x01) == 0 and (status & 0x02) == 0:
            self.parent.state_dmd1_label.setText(f"<b>DMD 1:</b> {splash_lut[0]} - {splash_lut[1]}")
            self.parent.state_dmd1_button.setIcon(self.green_icon)
            self.finished_signal.emit(True)
        else:
            self.parent.state_dmd1_button.setIcon(self.red_icon)
            self.finished_signal.emit(False)

        self.quit()
        self.wait()


class AddAndValidateSequenceThreadDMD2(QThread):
    finished_signal = pyqtSignal(bool)
    progress_signal = pyqtSignal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.pattern_exposure_time = 10000
        self.pattern_period = 10000
        self.red_icon = QIcon("Icons/led_red.png")
        self.green_icon = QIcon("Icons/led_green.png")

    def run(self):
        splash_lut = []
        total_steps = 6
        step = 0

        comm.set_dlpc350_in_pattern_mode()

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        num_lut_entries = 2
        num_splash_lut_entries = 0
        buf_swap = True

        self.parent.dmd2.clear_pat_lut()
        if self.parent.dmd2.add_pat_to_lut(trig_type=1, pat_num=7, led_select=1, buf_swap=buf_swap) < 0:
            QMessageBox.critical(self.parent, "Error", "Error adding red pattern to DMD 1 LUT")
            self.finished_signal.emit(False)
        splash_lut.append(self.parent.red_pattern_dmd2.value())
        num_splash_lut_entries += 1

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        splash_lut.append(self.parent.blue_pattern_dmd2.value())
        num_splash_lut_entries += 1

        if self.parent.dmd2.add_pat_to_lut(trig_type=2, pat_num=15, led_select=4, buf_swap=buf_swap) < 0:
            QMessageBox.critical(self.parent, "Error", "Error adding blue pattern to DMD 1 LUT")
            self.finished_signal.emit(False)

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        comm.set_pattern_display_mode(False)

        if comm.set_pattern_config(num_lut_entries, 1, 1, num_splash_lut_entries) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Pattern Config to DMD 1")
            self.finished_signal.emit(False)
        if comm.set_exposure_frame_period(self.pattern_exposure_time, self.pattern_period) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Exposure Period to DMD 1")
            self.finished_signal.emit(False)
        if comm.set_pattern_trigger_mode(1) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Trigger Mode to DMD 1")
            self.finished_signal.emit(False)

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        if comm.send_pat_lut(self.parent.dmd2.g_pat_lut_index, self.parent.dmd2.g_pat_lut) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Pattern LUT to DMD 1")
            self.finished_signal.emit(False)
        if comm.send_image_lut(splash_lut, num_splash_lut_entries) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Image LUT to DMD 1")
            self.finished_signal.emit(False)

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        # Validazione sequenza
        i = 0

        if comm.start_pat_lut_validate() < 0:
            QMessageBox.critical(self.parent, "Error", "Error Validating LUT Data to DMD 1")
            self.finished_signal.emit(False)

        loop = QEventLoop()
        while True:
            ready, status = comm.check_pat_lut_validate()
            if ready < 0:
                QMessageBox.critical(self.parent, "Error", "Error Validating LUT Data to DMD 1")
                self.finished_signal.emit(False)

            if ready:
                break
            else:
                # Usa QTimer per uscire dal loop dopo 1 secondo
                timer = QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(loop.quit)
                timer.start(1000)
                loop.exec()

            if i > 5:
                break
            i += 1

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        if (status & 0x01) == 0 and (status & 0x02) == 0:
            self.parent.state_dmd2_label.setText(f"<b>DMD 2:</b> {splash_lut[0]} - {splash_lut[1]}")
            self.parent.state_dmd2_button.setIcon(self.green_icon)
            self.finished_signal.emit(True)
        else:
            self.parent.state_dmd2_button.setIcon(self.red_icon)
            self.finished_signal.emit(False)

        self.quit()
        self.wait()


class AddAndValidateSequenceThreadDMD3(QThread):
    finished_signal = pyqtSignal(bool)
    progress_signal = pyqtSignal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.pattern_exposure_time = 10000
        self.pattern_period = 10000
        self.red_icon = QIcon("Icons/led_red.png")
        self.green_icon = QIcon("Icons/led_green.png")

    def run(self):
        splash_lut = []
        total_steps = 6
        step = 0

        comm.set_dlpc350_in_pattern_mode()

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        num_lut_entries = 2
        num_splash_lut_entries = 0
        buf_swap = True

        self.parent.dmd3.clear_pat_lut()
        if self.parent.dmd3.add_pat_to_lut(trig_type=1, pat_num=7, led_select=1, buf_swap=buf_swap) < 0:
            QMessageBox.critical(self.parent, "Error", "Error adding red pattern to DMD 1 LUT")
            self.finished_signal.emit(False)
        splash_lut.append(self.parent.red_pattern_dmd3.value())
        num_splash_lut_entries += 1

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        splash_lut.append(self.parent.blue_pattern_dmd3.value())
        num_splash_lut_entries += 1

        if self.parent.dmd3.add_pat_to_lut(trig_type=2, pat_num=15, led_select=4, buf_swap=buf_swap) < 0:
            QMessageBox.critical(self.parent, "Error", "Error adding blue pattern to DMD 1 LUT")
            self.finished_signal.emit(False)

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        comm.set_pattern_display_mode(False)

        if comm.set_pattern_config(num_lut_entries, 1, 1, num_splash_lut_entries) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Pattern Config to DMD 1")
            self.finished_signal.emit(False)
        if comm.set_exposure_frame_period(self.pattern_exposure_time, self.pattern_period) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Exposure Period to DMD 1")
            self.finished_signal.emit(False)
        if comm.set_pattern_trigger_mode(1) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Trigger Mode to DMD 1")
            self.finished_signal.emit(False)

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        if comm.send_pat_lut(self.parent.dmd3.g_pat_lut_index, self.parent.dmd3.g_pat_lut) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Pattern LUT to DMD 1")
            self.finished_signal.emit(False)
        if comm.send_image_lut(splash_lut, num_splash_lut_entries) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Image LUT to DMD 1")
            self.finished_signal.emit(False)

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        # Validazione sequenza
        i = 0

        if comm.start_pat_lut_validate() < 0:
            QMessageBox.critical(self.parent, "Error", "Error Validating LUT Data to DMD 1")
            self.finished_signal.emit(False)

        loop = QEventLoop()
        while True:
            ready, status = comm.check_pat_lut_validate()
            if ready < 0:
                QMessageBox.critical(self.parent, "Error", "Error Validating LUT Data to DMD 1")
                self.finished_signal.emit(False)

            if ready:
                break
            else:
                # Usa QTimer per uscire dal loop dopo 1 secondo
                timer = QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(loop.quit)
                timer.start(1000)
                loop.exec()

            if i > 5:
                break
            i += 1

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        if (status & 0x01) == 0 and (status & 0x02) == 0:
            self.parent.state_dmd3_label.setText(f"<b>DMD 3:</b> {splash_lut[0]} - {splash_lut[1]}")
            self.parent.state_dmd3_button.setIcon(self.green_icon)
            self.finished_signal.emit(True)
        else:
            self.parent.state_dmd3_button.setIcon(self.red_icon)
            self.finished_signal.emit(False)

        self.quit()
        self.wait()


class AddAndValidateSequenceThreadDMD4(QThread):
    finished_signal = pyqtSignal(bool)
    progress_signal = pyqtSignal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        self.pattern_exposure_time = 10000
        self.pattern_period = 10000
        self.red_icon = QIcon("Icons/led_red.png")
        self.green_icon = QIcon("Icons/led_green.png")

    def run(self):
        splash_lut = []
        total_steps = 6
        step = 0

        comm.set_dlpc350_in_pattern_mode()

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        num_lut_entries = 2
        num_splash_lut_entries = 0
        buf_swap = True

        self.parent.dmd4.clear_pat_lut()
        if self.parent.dmd4.add_pat_to_lut(trig_type=1, pat_num=7, led_select=1, buf_swap=buf_swap) < 0:
            QMessageBox.critical(self.parent, "Error", "Error adding red pattern to DMD 1 LUT")
            self.finished_signal.emit(False)

        splash_lut.append(self.parent.red_pattern_dmd4.value())
        num_splash_lut_entries += 1

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        splash_lut.append(self.parent.blue_pattern_dmd4.value())
        num_splash_lut_entries += 1

        if self.parent.dmd4.add_pat_to_lut(trig_type=2, pat_num=15, led_select=4, buf_swap=buf_swap) < 0:
            QMessageBox.critical(self.parent, "Error", "Error adding blue pattern to DMD 1 LUT")
            self.finished_signal.emit(False)

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        comm.set_pattern_display_mode(False)

        if comm.set_pattern_config(num_lut_entries, 1, 1, num_splash_lut_entries) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Pattern Config to DMD 1")
            self.finished_signal.emit(False)
        if comm.set_exposure_frame_period(self.pattern_exposure_time, self.pattern_period) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Exposure Period to DMD 1")
            self.finished_signal.emit(False)
        if comm.set_pattern_trigger_mode(1) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Trigger Mode to DMD 1")
            self.finished_signal.emit(False)

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        if comm.send_pat_lut(self.parent.dmd4.g_pat_lut_index, self.parent.dmd4.g_pat_lut) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Pattern LUT to DMD 1")
            self.finished_signal.emit(False)
        if comm.send_image_lut(splash_lut, num_splash_lut_entries) < 0:
            QMessageBox.critical(self.parent, "Error", "Error Sending Image LUT to DMD 1")
            self.finished_signal.emit(False)

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        # Validazione sequenza
        i = 0

        if comm.start_pat_lut_validate() < 0:
            QMessageBox.critical(self.parent, "Error", "Error Validating LUT Data to DMD 1")
            self.finished_signal.emit(False)

        loop = QEventLoop()
        while True:
            ready, status = comm.check_pat_lut_validate()
            if ready < 0:
                QMessageBox.critical(self.parent, "Error", "Error Validating LUT Data to DMD 1")
                self.finished_signal.emit(False)

            if ready:
                break
            else:
                # Usa QTimer per uscire dal loop dopo 1 secondo
                timer = QTimer()
                timer.setSingleShot(True)
                timer.timeout.connect(loop.quit)
                timer.start(1000)
                loop.exec()

            if i > 5:
                break
            i += 1

        step += 1
        self.progress_signal.emit(int((step / total_steps) * 100))

        if (status & 0x01) == 0 and (status & 0x02) == 0:
            self.parent.state_dmd4_label.setText(f"<b>DMD 4:</b> {splash_lut[0]} - {splash_lut[1]}")
            self.parent.state_dmd4_button.setIcon(self.green_icon)
            self.finished_signal.emit(True)
        else:
            self.parent.state_dmd4_button.setIcon(self.red_icon)
            self.finished_signal.emit(False)

        self.quit()
        self.wait()


class UploadPatternsThread(QThread):
    finished_signal = pyqtSignal(bool, int)
    progress_signal = pyqtSignal(int)
    def __init__(self, upload_file, parent=None):
        super().__init__(parent)
        self.upload_file = upload_file
        self.parent = parent

    def run(self):
        if self.parent.dmd_selected == 1:
            info_label = self.parent.info_labels1
        elif self.parent.dmd_selected == 2:
            info_label = self.parent.info_labels2
        elif self.parent.dmd_selected == 3:
            info_label = self.parent.info_labels3
        elif self.parent.dmd_selected == 4:
            info_label = self.parent.info_labels4

        with connect_usb() as lcr:
            # Enter Programming Mode
            if lcr.enter_programming_mode() < 0:
                QMessageBox.critical(self.parent, "Error", "Unable to enter Programming Mode.")
                self.finished_signal.emit(False, -1)
            # TO DO: Per ora va fatto a parte. Poi trovare un modo per fare una verifica
            info_label.setText("Waiting to enter Programming Mode...")
            time.sleep(5)

        with connect_usb() as lcr:
            lcr.enter_programming_mode()

            # Read Flash information
            flash_device = sc.FlashDevice()
            if lcr.get_flash_man_id() < 0:
                QMessageBox.critical(self.parent, "Error", "Unable to read Flash Manufacturer ID.")
                self.finished_signal.emit(False, -1)
            man_id = lcr.p_man_id

            if lcr.get_flash_dev_id() < 0:
                QMessageBox.critical(self.parent, "Error", "Unable to read Flash Device ID.")
                self.finished_signal.emit(False, -1)
            dev_id = lcr.p_dev_id & 0xFFFF

            flash_device.mfg_id = hex(man_id)
            flash_device.dev_id = hex(dev_id)

            # Populate flash layout from FlashDeviceParameters for given g_FlashDevice Mfg_ID & Dev_ID
            with open("Flash/FlashDeviceParameters.txt", "r") as f:
                # se non si riesce ad aprire mostra un errore
                if f is None:
                    QMessageBox.critical(self.parent, "Error", "Unable to open FlashDeviceParameters.txt.")
                    self.finished_signal.emit(False, -1)

                found = False
                for line in f:
                    if comm.process_flash_params_line(line, flash_device):
                        found = True
                        break

                if not found:
                    QMessageBox.critical(self.parent, "Error", f"Unsopported Flash Device: Mfg_ID: {flash_device.mfg_id}, Dev_ID: {flash_device.dev_id}.")
                    self.finished_signal.emit(False, -1)

            # Program Flash
            with open(self.upload_file, "rb") as img_file:
                p_byte_array = img_file.read()
                data_len = len(p_byte_array)

                start_sector = comm.get_sector_num(comm.bl_size, flash_device)
                last_sector_to_erase = comm.get_sector_num(data_len, flash_device)

                if data_len == flash_device.sector_arr[last_sector_to_erase]:
                    last_sector_to_erase -= 1

                lcr.set_flash_type(flash_device.type)

                for i in range(start_sector, last_sector_to_erase + 1):
                    sector_address = comm.FLASH_BASE_ADDRESS + flash_device.sector_arr[i]
                    info_label.setText(f"Erasing sector @ 0x{sector_address:08X}")
                    lcr.set_flash_addr(flash_device.sector_arr[i])
                    lcr.flash_sector_erase()
                    progress = int((i - start_sector) / (last_sector_to_erase - start_sector) * 100)
                    self.progress_signal.emit(progress)

                # if not is_cache_file_exist:
                data_len -= comm.bl_size
                lcr.set_flash_addr(comm.bl_size)
                lcr.set_upload_size(data_len)

                data_len_full = data_len
                while data_len > 0:
                    sector_address = comm.FLASH_BASE_ADDRESS + comm.bl_size + data_len_full - data_len
                    info_label.setText(f"Programming sector @ 0x{sector_address:08X}")
                    bytes_sent = lcr.upload_data(
                        p_byte_array[comm.bl_size + data_len_full - data_len:comm.bl_size + data_len_full], data_len)

                    if bytes_sent < 0:
                        QMessageBox.critical(self.parent, "Error", "Flash data download failed.")
                        self.finished_signal.emit(False, -1)

                    data_len -= bytes_sent
                    progress = int((data_len_full - data_len) / data_len_full * 100)
                    self.progress_signal.emit(progress)

            # Compute Checksum
            expected_checksum = 0
            with open(self.upload_file, "rb") as img_file:
                img_file.seek(0, 2)
                data_len = img_file.tell()
                img_file.seek(0, 0)
                if comm.bl_size > 0:
                    p_byte_array = img_file.read(comm.bl_size)

                while True:
                    p_byte_array = img_file.read(1024)
                    temp_var = len(p_byte_array)

                    if temp_var <= 0:
                        break

                    for i in range(temp_var):
                        expected_checksum += p_byte_array[i]

                lcr.set_flash_addr(comm.bl_size)
                lcr.set_upload_size(data_len - comm.bl_size)

            checksum = 0
            i = 0
            if comm.bl_size:
                while flash_device.sector_arr[i] < comm.bl_size:
                    i += 1
                if i >= flash_device.num_sectors:
                    QMessageBox.critical(self.parent, "Error", "Sector size is not a multiple of bootloader application size of 128KB.")
                    self.finished_signal.emit(False, -1)

            while i < flash_device.num_sectors - 2 and flash_device.sector_arr[i + 1] < data_len:
                lcr.set_flash_addr(flash_device.sector_arr[i])
                lcr.set_upload_size(flash_device.sector_arr[i + 1] - flash_device.sector_arr[i])
                lcr.calculate_flash_checksum()
                lcr.wait_for_flash_ready()

                if lcr.get_flash_checksum() >= 0:
                    checksum += lcr.checksum
                    i += 1
                else:
                    QMessageBox.critical(self.parent, "Error", "Error during checksum computation of the flash with Cached firmware.")
                    self.finished_signal.emit(False, -1)

            if i == flash_device.num_sectors - 2:
                if flash_device.sector_arr[i + 1] < data_len:
                    lcr.set_flash_addr(flash_device.sector_arr[i])
                    lcr.set_upload_size((flash_device.sector_arr[i + 1] - flash_device.sector_arr[i]))
                    lcr.calculate_flash_checksum()
                    lcr.wait_for_flash_ready()

                    if lcr.get_flash_checksum() >= 0:
                        checksum += lcr.checksum
                        i += 1
                    else:
                        QMessageBox.critical(self.parent, "Error", "Error during checksum computation of the flash with Cached firmware.")
                        self.finished_signal.emit(False, -1)

                    # Last Sector
                    if flash_device.sector_arr[i] < data_len:
                        lcr.set_flash_addr(flash_device.sector_arr[i])
                        lcr.set_upload_size(data_len - flash_device.sector_arr[i])
                        lcr.calculate_flash_checksum()
                        lcr.wait_for_flash_ready()

                        if lcr.get_flash_checksum() >= 0:
                            checksum += lcr.checksum
                        else:
                            QMessageBox.critical(self.parent, "Error", "Error during checksum computation of the flash with Cached firmware.")
                            self.finished_signal.emit(False, -1)

                else:
                    # Last Sector
                    lcr.set_flash_addr(flash_device.sector_arr[i])
                    lcr.set_upload_size(data_len - flash_device.sector_arr[i])
                    lcr.calculate_flash_checksum()
                    lcr.wait_for_flash_ready()

                    if lcr.get_flash_checksum() >= 0:
                        checksum += lcr.checksum
                        i += 1
                    else:
                        QMessageBox.critical(self.parent, "Error", "Error during checksum computation of the flash with Cached firmware.")
                        self.finished_signal.emit(False, -1)

            else:
                # Last Sector
                lcr.set_flash_addr(flash_device.sector_arr[i])
                lcr.set_upload_size(data_len - flash_device.sector_arr[i])
                lcr.calculate_flash_checksum()
                lcr.wait_for_flash_ready()

                if lcr.get_flash_checksum() >= 0:
                    checksum += lcr.checksum
                else:
                    QMessageBox.critical(self.parent, "Error", "Error during checksum computation of the flash with Cached firmware.")
                    self.finished_signal.emit(False, -1)

            if checksum != expected_checksum:
                QMessageBox.critical(self.parent, "Error", "Checksum mismatch: Expected: 0x{:X}, Received: 0x{:X}".format(expected_checksum, checksum))
                self.finished_signal.emit(False, -1)

            else:
                info_label.setText("Exiting Programming Mode...")
                lcr.exit_programming_mode()
                info_label.setText("Pattern Uploaded Successfully")

        self.finished_signal.emit(True, 0)


# CAMERA CONTROL GUI
class AcquireThread(QThread):
    acquisition_finished = pyqtSignal(int)
    black_screen_signal = pyqtSignal()
    send_frames = pyqtSignal(list, list, list, list)
    update_image_view_signal = pyqtSignal(object, object, object, object)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.main = parent.parent

        self.stop_requested = False

    def run(self):
        self.n_frames_acquired1 = 0
        self.n_frames_acquired2 = 0
        self.n_frames_acquired3 = 0
        self.n_frames_acquired4 = 0

        self.parent.cam1.triggerCamera(sf.MODE_PANORAMIC, self.parent.stop_number)
        self.parent.cam2.triggerCamera(sf.MODE_PANORAMIC, self.parent.stop_number)
        self.parent.cam3.triggerCamera(sf.MODE_PANORAMIC, self.parent.stop_number)
        self.parent.cam4.triggerCamera(sf.MODE_PANORAMIC, self.parent.stop_number)

        while not self.stop_requested and not all(n >= self.parent.stop_number for n in [
                            self.n_frames_acquired1,
                            self.n_frames_acquired2,
                            self.n_frames_acquired3,
                            self.n_frames_acquired4]):

            if self.n_frames_acquired1 < self.parent.stop_number:
                packet1, dims1 = self.parent.cam1.getFrames()
                self.parent.cam1_acquisition, n_frames1 = sf.elaborate_frame2(self.parent.cam1_acquisition, packet1)
                self.n_frames_acquired1 += n_frames1

            if self.n_frames_acquired2 < self.parent.stop_number:
                packet2, dims2 = self.parent.cam2.getFrames()
                self.parent.cam2_acquisition, n_frames2 = sf.elaborate_frame2(self.parent.cam2_acquisition, packet2)
                self.n_frames_acquired2 += n_frames2

            if self.n_frames_acquired3 < self.parent.stop_number:
                packet3, dims3 = self.parent.cam3.getFrames()
                self.parent.cam3_acquisition, n_frames3 = sf.elaborate_frame2(self.parent.cam3_acquisition, packet3)
                self.n_frames_acquired3 += n_frames3

            if self.n_frames_acquired4 < self.parent.stop_number:
                packet4, dims4 = self.parent.cam4.getFrames()
                self.parent.cam4_acquisition, n_frames4 = sf.elaborate_frame2(self.parent.cam4_acquisition, packet4)
                self.n_frames_acquired4 += n_frames4

            if self.n_frames_acquired1 % 25 == 0:
                new_size = (512, 512)

                frame1 = cv2.resize(self.parent.cam1_acquisition[-1], new_size, interpolation=cv2.INTER_LINEAR)
                frame2 = cv2.resize(self.parent.cam2_acquisition[-1], new_size, interpolation=cv2.INTER_LINEAR)
                frame3 = cv2.resize(self.parent.cam3_acquisition[-1], new_size, interpolation=cv2.INTER_LINEAR)
                frame4 = cv2.resize(self.parent.cam4_acquisition[-1], new_size, interpolation=cv2.INTER_LINEAR)

                frame1 = cv2.rotate(frame1, cv2.ROTATE_90_COUNTERCLOCKWISE)
                frame2 = cv2.rotate(frame2, cv2.ROTATE_90_COUNTERCLOCKWISE)
                frame3 = cv2.rotate(frame3, cv2.ROTATE_90_COUNTERCLOCKWISE)
                frame4 = cv2.rotate(frame4, cv2.ROTATE_90_COUNTERCLOCKWISE)

                self.update_image_view_signal.emit(frame1, frame2, frame3, frame4)

        self.parent.cam1.stopAcq()
        self.parent.cam2.stopAcq()
        self.parent.cam3.stopAcq()
        self.parent.cam4.stopAcq()

        self.stop_requested = False

        self.black_screen_signal.emit()

        self.acquisition_finished.emit(self.n_frames_acquired1)

        self.send_frames.emit(self.parent.cam1_acquisition, self.parent.cam2_acquisition, self.parent.cam3_acquisition, self.parent.cam4_acquisition)
        self.quit()
        self.wait()

    def request_stop(self):
        self.stop_requested = True


class AppendThread(QThread):
    send_frames = pyqtSignal(object, object, object, object)
    #show_frames = pyqtSignal(object, object, object, object)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.main = parent.parent
        self.parent.acquisition_finished.connect(self.finish_acquisition)
        self.parent.frame_acquired.connect(self.append_frames)

    def run(self):
        """while self.parent.frame1_queue.qsize() > 0 or \
                self.parent.frame2_queue.qsize() > 0 or \
                self.parent.frame3_queue.qsize() > 0 or \
                self.parent.frame4_queue.qsize() > 0:  # Continua fino alla fine dell'acquisizione

            # Controlla ed elabora un frame per ogni coda
            if not self.parent.frame1_queue.empty():
                frame1, dims1 = self.parent.frame1_queue.get()
                #frame1 = sf.elaborate_frame(frame1, dims1)
                self.main.cam1_acquisition.append(frame1)

            if not self.parent.frame2_queue.empty():
                frame2, dims2 = self.parent.frame2_queue.get()
                #frame2 = sf.elaborate_frame(frame2, dims2)
                self.main.cam2_acquisition.append(frame2)

            if not self.parent.frame3_queue.empty():
                frame3, dims3 = self.parent.frame3_queue.get()
                #frame3 = sf.elaborate_frame(frame3, dims3)
                self.main.cam3_acquisition.append(frame3)

            if not self.parent.frame4_queue.empty():
                frame4, dims4 = self.parent.frame4_queue.get()
                #frame4 = sf.elaborate_frame(frame4, dims4)
                self.main.cam4_acquisition.append(frame4)"""
        pass

    def append_frames(self, frame1, frame2, frame3, frame4, dims1, dims2, dims3, dims4):
        #frame11, frame12 = sf.elaborate_frame(frame1, dims1)
        #frame1 = sf.elaborate_frame(frame1, dims1)
        """self.main.cam1_acquisition.append(frame11)
        self.main.cam1_acquisition.append(frame12)"""
        self.main.cam1_acquisition.append(frame1)

        #frame21, frame22 = sf.elaborate_frame(frame2, dims2)
        #frame2 = sf.elaborate_frame(frame2, dims2)
        """self.main.cam2_acquisition.append(frame21)
        self.main.cam2_acquisition.append(frame22)"""
        self.main.cam2_acquisition.append(frame2)

        #frame31, frame32 = sf.elaborate_frame(frame3, dims3)
        #frame3 = sf.elaborate_frame(frame3, dims3)
        """self.main.cam3_acquisition.append(frame31)
        self.main.cam3_acquisition.append(frame32)"""
        self.main.cam3_acquisition.append(frame3)

        #frame41, frame42 = sf.elaborate_frame(frame4, dims4)
        #frame4 = sf.elaborate_frame(frame4, dims4)
        """self.main.cam4_acquisition.append(frame41)
        self.main.cam4_acquisition.append(frame42)"""
        self.main.cam4_acquisition.append(frame4)

        #self.show_frames.emit(frame11, frame21, frame31, frame41)

    def finish_acquisition(self):
        if self.main.cam1_acquisition and self.main.cam2_acquisition and self.main.cam3_acquisition and self.main.cam4_acquisition:
            self.send_frames.emit(self.main.cam1_acquisition, self.main.cam2_acquisition, self.main.cam3_acquisition, self.main.cam4_acquisition)

        self.quit()
        self.wait()


class CheckExposureTimeValueThread(QThread):
    error_signal = pyqtSignal(list)
    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

    def run(self):
        self.parent.start_button.setEnabled(False)

        exp_value = float(self.parent.exposure_time_value.text())
        exp_range = self.parent.cam1.getPropRange("exposure_time")

        if exp_value < exp_range[0] or exp_value > exp_range[1]:
            self.parent.exposure_time_value.setText(str(round(self.parent.cam1.getExposure(), 8)))

            self.error_signal.emit(exp_range)

            self.quit()
            self.wait()

        else:
            self.parent.cam1.setExposure(exp_value)
            self.parent.cam2.setExposure(exp_value)
            self.parent.cam3.setExposure(exp_value)
            self.parent.cam4.setExposure(exp_value)
            self.parent.frame_rate_label.setText(str(round(self.parent.cam1.getFrameRate(), 8)))

        self.parent.start_button.setEnabled(True)

        self.quit()
        self.wait()


class LiveThread(QThread):
    black_screen_signal = pyqtSignal()
    update_image_view_signal = pyqtSignal(object, object, object, object)
    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

    def run(self):
        ss.update_toolbutton_style(self.parent.cam1_icon, 'on')
        ss.update_toolbutton_style(self.parent.cam2_icon, 'on')
        ss.update_toolbutton_style(self.parent.cam3_icon, 'on')
        ss.update_toolbutton_style(self.parent.cam4_icon, 'on')

        self.parent.cam1.triggerCamera()
        self.parent.cam2.triggerCamera()
        self.parent.cam3.triggerCamera()
        self.parent.cam4.triggerCamera()

        while self.parent.live:
            try:
                frame1 = self.parent.cam1.readCamera()
                frame2 = self.parent.cam2.readCamera()
                frame3 = self.parent.cam3.readCamera()
                frame4 = self.parent.cam4.readCamera()
            except Exception as e:
                print(e)

            frame1 = sf.update_image(frame1)
            frame2 = sf.update_image(frame2)
            frame3 = sf.update_image(frame3)
            frame4 = sf.update_image(frame4)

            self.update_image_view_signal.emit(frame1, frame2, frame3, frame4)

            self.parent.n_frames += 1
            self.parent.frames_acquired_label.setText(str(self.parent.n_frames))

            time.sleep(0.025)

        ss.update_toolbutton_style(self.parent.cam1_icon, 'off')
        ss.update_toolbutton_style(self.parent.cam2_icon, 'off')
        ss.update_toolbutton_style(self.parent.cam3_icon, 'off')
        ss.update_toolbutton_style(self.parent.cam4_icon, 'off')

        self.parent.cam1.stopAcq()
        self.parent.cam2.stopAcq()
        self.parent.cam3.stopAcq()
        self.parent.cam4.stopAcq()

        self.black_screen_signal.emit()

        self.quit()
        self.wait()


"""class UpdateImageViewThread(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.main = parent.parent
        self.counter = 0

        self.parent.append_thread.show_frames.connect(self.update_counter)
        self.parent.acquisition_finished.connect(self.stop_showing)

    def run(self):
        pass

    def update_counter(self, frame1, frame2, frame3, frame4):
        self.counter += 1

        if self.counter == 24:
            sf.show_frame_x_thread(frame1, self.main.image_view1)
            sf.show_frame_x_thread(frame2, self.main.image_view2)
            sf.show_frame_x_thread(frame3, self.main.image_view3)
            sf.show_frame_x_thread(frame4, self.main.image_view4)

            self.counter = 0

    def stop_showing(self):
        self.quit()
        self.wait()"""