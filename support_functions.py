"""Shared camera, DMD, NI-DAQ, logging, and image-display utilities."""

import runtime_config as cfg
import time
import nidaqmx
from PyQt6.QtWidgets import QMessageBox
from nidaqmx.constants import LineGrouping
import numpy as np
import cv2
import subprocess
import socket
import json


# CAMERA
# Acquisition Mode
MODE_CONTINUOUS = 1
MODE_SINGLE_SHOT = 0
MODE_PANORAMIC = 2

# Trigger Source
INTERNAL_TRIGGER = 1
EXTERNAL_TRIGGER = 2
SOFTWARE_TRIGGER = 3
MASTER_PULSE_TRIGGER = 4

# Trigger Mode
NORMAL_TRIGGER = 1
START_TRIGGER = 6

# Trigger Active
EDGE_TRIGGER = 1
LEVEL_TRIGGER = 2
SYNCREADOUT_TRIGGER = 3

# Trigger Polarity
NEGATIVE_TRIGGER = 1
POSITIVE_TRIGGER = 2

# Framebundle Mode
FRAMEBUNDLE_OFF = 1
FRAMEBUNDLE_ON = 2
FRAMEBUNDLE_NUMBER = 2


# DMD
DMD1_CHANNEL = 0x10
DMD2_CHANNEL = 0x07
DMD3_CHANNEL = 0x06
DMD4_CHANNEL = 0x00


def able_trig_mode_camera(cam):
    """Configure a camera for synchronized external triggering."""
    cam.setTrigMode(NORMAL_TRIGGER)
    cam.setTrigSource(EXTERNAL_TRIGGER)
    cam.setTrigActive(SYNCREADOUT_TRIGGER)
    cam.setTrigPolarity(POSITIVE_TRIGGER)

    cam.setFrameBundleMode(FRAMEBUNDLE_ON)
    cam.setFrameBundleNumber(FRAMEBUNDLE_NUMBER)


def check_pcie_connectivity():
    """Return whether the expected NI PCIe-6612 board is available."""
    local_system = nidaqmx.system.System.local()

    for device in local_system.devices:
        if device.product_type == 'PCIe-6612':
            with nidaqmx.Task() as task:
                task.do_channels.add_do_chan(cfg.NI_PORT0, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
                task.write(0)
                task.stop()

            with nidaqmx.Task() as task:
                task.do_channels.add_do_chan(cfg.NI_PORT1, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
                task.write(0)
                task.stop()

            return True

    return False


def clear_layout(layout):
    """Delete all widgets currently owned by a Qt layout."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def disable_trig_mode_camera(cam):
    """Restore internal camera triggering and disable frame bundling."""
    cam.setTrigMode(NORMAL_TRIGGER)
    cam.setTrigSource(INTERNAL_TRIGGER)
    cam.setTrigActive(EDGE_TRIGGER)
    cam.setTrigPolarity(NEGATIVE_TRIGGER)

    cam.setFrameBundleMode(FRAMEBUNDLE_OFF)


def elaborate_frame(array):
    """Split frame-bundle data into rotated 192 x 192 images."""
    dims = [192, 192]
    new_array = []

    for frame in array:
        i = 0
        for f in frame:
            i += 1
            d = f.getData()

            if d.size > 73728:
                print("wait > 73728!")
            #192x192: 36864 - 73728
            #128x128: 16384 - 32768
            d1 = d[0:36864]
            d1 = np.reshape(d1, (dims[1], dims[0]))
            d1 = d1.T
            d1 = np.rot90(d1)

            d2 = d[36864:73728]
            d2 = np.reshape(d2, (dims[1], dims[0]))
            d2 = d2.T
            d2 = np.rot90(d2)

            new_array.append(d1)
            new_array.append(d2)
        if i != 1:
            print(i)

    return new_array

def elaborate_frame2(array, frame):
    """Append one frame bundle to an existing image list."""
    dims = [192, 192]

    i = 0
    for f in frame:
        i += 2
        d = f.getData()
        if d.size > 73728:
            print(d.size)
        #192x192: 36864 - 73728
        #128x128: 16384 - 32768
        d1 = d[0:36864]
        d1 = np.reshape(d1, (dims[1], dims[0]))
        d1 = d1.T
        d1 = cv2.flip(d1, 0)
        d1 = np.rot90(d1, k=-1)

        d2 = d[36864:73728]
        d2 = np.reshape(d2, (dims[1], dims[0]))
        d2 = d2.T
        d2 = cv2.flip(d2, 0)
        d2 = np.rot90(d2, k=-1)

        array.append(d1)
        array.append(d2)

    return array, i


def generate_experiment_log(filename, info):
    """Write a human-readable experiment metadata log."""
    with open(filename, 'w') as file:
        # Header with date and time
        file.write(f"{info["date"]} - {info["saving_time"]}\n")
        file.write("\n")
        file.write("=" * 60 + "\n")

        # Section 1: Devices
        if "numb_dmd_connected" in info.keys():
            file.write("Device: LightCrafter 4500\n")
            file.write(f"\t- Number of projectors connected at startup: {info["numb_dmd_connected"]}\n")
            file.write(f"\t- Directory of the file loaded into memory: {info["file_directory"]}\n")
            file.write(f"\t- Number of patterns in the file: {info["numb_pattern_file"]}\n\n")

        file.write("Device: ORCA-Flash4.0 v3\n")
        file.write(f"\t- Number of cameras connected: {info["numb_cam_connected"]}\n")
        file.write("=" * 60 + "\n")

        # Section 2: Device Settings
        try:
            file.write("DEVICE SETTINGS FOR THE EXPERIMENT\n\n")
            if "numb_dmd_connected" in info.keys():
                for dmd in info["dmd_info"].keys():
                    file.write(f"{dmd}:\n")
                    file.write(f"\t- Current set for the red LED: {info["dmd_info"][dmd]["led_currents"][0]} A\n")
                    file.write(f"\t- Current set for the blue LED: {info["dmd_info"][dmd]["led_currents"][1]} A\n")
                    file.write(f"\t- Index pattern associated with red: {info["dmd_info"][dmd]["pattern_index"][0]}\n")
                    file.write(f"\t- Index pattern associated with blue: {info["dmd_info"][dmd]["pattern_index"][1]}\n\n")
                file.write(f"Red LED intensity: {info["red_led_intensity"]} mW/mm2\n")
                file.write(f"Blue LED intensity: {info["blue_led_intensity"]} mW/mm2\n\n")
        except KeyError:
            QMessageBox.warning(None, "Warning", "File generated without DMD information. Check the settings!")

        try:
            for cam in range(4):
                file.write("\n")
                file.write(f"CAM {cam + 1}:\n")
                file.write(f"\t- ROI set: {info["cam_info"]["roi"][0]}x{info["cam_info"]["roi"][1]}\n")
                file.write(f"\t- Trigger Source: {info["cam_info"]["trigger"][0]}\n")
                file.write(f"\t- Trigger Mode: {info["cam_info"]["trigger"][1]}\n")
                file.write(f"\t- Trigger Active: {info["cam_info"]["trigger"][2]}\n")
                file.write(f"\t- Trigger Polarity: {info["cam_info"]["trigger"][3]}\n")
                if info["cam_info"]["trigger"][4][0] == "on":
                    file.write("\t- Frame Bundle Mode: ON\n")
                    file.write(f"\t- Frame Bundle Number: {info["cam_info"]["trigger"][4][1]}\n")
                else:
                    file.write("\t- Frame Bundle Mode: OFF\n")
        except KeyError:
            QMessageBox.warning(None, "Warning", "File generated without CAM information. Check the settings!")

        file.write("=" * 60 + "\n")

        # Section 3: Experiment Phases
        file.write("EXPERIMENT PHASES\n\n")
        file.write(f"Duty cycle for red LED (set by LED intensity): {info["red_duty_cycle"]} %\n")
        file.write(f"Duty cycle for blue LED (set by LED intensity): {info["blue_duty_cycle"]} %\n\n")
        for phase_info in info["phases"]:
            file.write(f"{phase_info[0]}:\n")
            file.write(f"\t- Set duration of the phase: {phase_info[1]} s\n")
            file.write(f"\t- Actual duration of the phase: {phase_info[2]} s\n\n")
        file.write("\n")
        file.write(f"Number of repetitions for stimulation and post-stimulation phases: {info["num_cycles"]}\n")
        file.write("\n")
        if "stimulation_protocol" in info.keys():
            if info["stimulation_protocol"][0] == "Constant":
                file.write(f"Electrical stimulation protocol: {info["stimulation_protocol"][0]}\n")
                file.write(f"Frequency: {info["stimulation_protocol"][1]} Hz\n")
                file.write(f"Starting frame: {info["stimulation_protocol"][2]}\n")
                file.write(f"Ending frame: {info["stimulation_protocol"][3]}\n")
            elif info["stimulation_protocol"][0] == "S1-S2":
                file.write(f"Electrical stimulation protocol: {info["stimulation_protocol"][0]}\n")
                file.write(f"Starting frequency: {info['stimulation_protocol'][1][0]} Hz\n")
                file.write(f"Pre-condition: {info['stimulation_protocol'][2]}\n")
                file.write(f"Starting pacing frames; {info['stimulation_protocol'][3]}\n")
                file.write(f"Frequency series: {info['stimulation_protocol'][1][1:]}\n")
                file.write(f"Pacing frames: {info['stimulation_protocol'][4]}\n")
        else:
            file.write("Stimulation protocol: None\n")
        file.write("\n")
        file.write(f"Total duration of the experiment: {info["real_total_duration"]} s\n")
        file.write("=" * 60 + "\n")

        # Section 4: Experiment
        file.write("EXPERIMENT\n\n")
        file.write(f"Start time: {info["start_time"]}\n")
        file.write(f"End time: {info["end_time"]}\n")
        file.write(f"Alignment required: {"Yes" if info["alignment_done"] else "No"}\n\n")
        file.write(f"Experiment stopped early: {"Yes" if info["stopped_before"] else "No"}\n")
        file.write(f"Stop condition for acquisition: {info["stop_condition"]}\n")
        file.write(f"Frames acquired: {info["numb_frames_acquired"]}\n")
        file.write(f"Frames lost: {info["stop_condition"] - info["numb_frames_acquired"]}\n")

        # Section 5: Notes
        if info["notes"] != "":
            file.write("=" * 60 + "\n")
            file.write("NOTES\n\n")
            file.write(info["notes"])


def run_server_32bit():
    """Start the external 32-bit helper process used by the DAC interface."""
    subprocess.Popen(
        [str(cfg.PYTHON_32BIT_EXECUTABLE), str(cfg.SERVER_32BIT_SCRIPT)],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def select_channel(channel):
    """Select one DMD channel through the NI digital output port."""
    if channel == 0 or channel == 4:
        data = DMD4_CHANNEL
    elif channel == 1:
        data = DMD1_CHANNEL
    elif channel == 2:
        data = DMD2_CHANNEL
    elif channel == 3:
        data = DMD3_CHANNEL

    with nidaqmx.Task() as task:
        task.do_channels.add_do_chan(cfg.NI_PORT1, line_grouping=LineGrouping.CHAN_FOR_ALL_LINES)
        task.start()
        task.write(data)
        task.stop()

    time.sleep(1)


def send_command_to_board(commands):
    """Send serialized DAC commands to the local helper server."""
    host = cfg.DAC_SERVER_HOST
    port = cfg.DAC_SERVER_PORT

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for _ in range(10):
        try:
            client_socket.connect((host, port))
            break
        except ConnectionRefusedError:
            time.sleep(1)
    else:
        raise ConnectionError("The local DAC server is not available.")

    serialized_commands = json.dumps(commands).encode('utf-8')
    client_socket.send(serialized_commands)

    response = client_socket.recv(1024).decode('utf-8')

    client_socket.close()

    return response


def set_levels_histogram(image_view):
    """Set image-display levels to the current image minimum and maximum."""
    min_lev = np.min(image_view.image)
    max_lev = np.max(image_view.image)

    image_view.setLevels(min_lev, max_lev)


def show_frame_x_thread(frame, image_view):
    """Resize, rotate, and display one camera frame."""
    new_size = (512, 512)

    frame = cv2.resize(frame, new_size, interpolation=cv2.INTER_LINEAR)
    frame = np.rot90(frame)

    image_view.setImage(frame, autoLevels=False, autoRange=False, autoHistogramRange=False)

def sync_checkboxes(clicked_checkbox, all_checkboxes):
    """Keep only the clicked checkbox selected within a group."""
    if clicked_checkbox.isChecked():
        for cb in all_checkboxes:
            if cb != clicked_checkbox:
                cb.setChecked(False)


def update_image(frame):
    """Resize and rotate one frame for display."""
    new_size = (512, 512)

    frame = cv2.resize(frame, new_size, interpolation=cv2.INTER_LINEAR)
    frame = np.rot90(frame)

    return frame




