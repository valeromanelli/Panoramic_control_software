# Panoramic Control Software

Python/PyQt6 software for the synchronized control of a panoramic cardiac optical mapping platform. It provides a graphical interface to configure cameras and projectors, define experimental phases, generate hardware-timed trigger sequences, and manage image acquisition and illumination during optical mapping experiments.

## Main features

- Configure and monitor four cameras, including live view, exposure, region of interest (ROI), triggering, and image acquisition.
- Configure four DMD projectors, upload and select projection patterns, manage pattern sequences, and adjust LED illumination.
- Define pre-illumination, pre-stimulation, stimulation, and post-stimulation phases, including repeated protocols and optional electrical stimulation.
- Synchronize cameras, DMDs, and stimulation signals through NI-DAQ digital waveforms; record experimental settings and acquisition information.

## Connected devices

| Device | Role |
| --- | --- |
| **4 Hamamatsu ORCA-Flash4.0 V3 cameras** | Acquire optical mapping images from four viewpoints using the Hamamatsu DCAM interface. |
| **4 Texas Instruments DLP LightCrafter 4500 projectors (DLPC350)** | Project programmable illumination patterns and deliver controlled optical stimulation via USB communication. |
| **National Instruments PCIe-6612** | Generate and coordinate digital timing, camera triggers, and projector/illumination enable signals. |
| **External LED-current DAC controller** | Set LED driving currents through a separate local 32-bit control service. |

## Repository structure

| Python file | Purpose |
| --- | --- |
| `control_platform.py` | Main application window and overall management of experiment phases and connected devices. |
| `configure_camera.py` | Camera configuration GUI, live image display, triggering, and acquisition controls. |
| `configure_dmd.py` | DMD configuration GUI, pattern/firmware management, pattern sequences, and LED-current settings. |
| `camere_basic_controls.py` | Low-level Hamamatsu camera communication through the DCAM-API. |
| `camere_controls.py` | Higher-level Hamamatsu camera driver and control methods. |
| `skeleton.py` | Common base interface defining camera-control operations. |
| `procrafter4500.py` | Low-level USB HID communication with LightCrafter 4500 controllers. |
| `dlpc350_commands.py` | Higher-level commands for the DLPC350 controller. |
| `dlpc350_firmware.py` | Parsing and modification of DMD firmware images and stored patterns. |
| `dlpc350_bmpparser.py` | BMP image format utilities for DMD firmware operations. |
| `firmware_commands.py` | Firmware image extraction, rebuilding, and pattern compression utilities. |
| `message_api.py` | USB HID message structures and byte conversion utilities. |
| `sequenciator.py` | Generation of synchronized digital waveforms for acquisition, illumination, and stimulation phases. |
| `threads.py` | Background Qt workers for hardware communication and acquisition tasks. |
| `runtime_config.py` | Workstation-dependent paths, device identifiers, and connection settings. |
| `support_functions.py` | Shared utilities for hardware control, data handling, image processing, and logging. |
| `support_classes.py` | Reusable GUI widgets, dialogs, and supporting classes. |
| `style_sheet.py` | Visual styling of the PyQt6 interface. |
| `giotto.py` | Graphical visualization of connected-device status on the platform diagram. |
| `examples/generate_sequence.py` | Offline example of experimental waveform generation, without hardware access. |
| `tests/conftest.py` | Test import-path configuration. |
| `tests/test_bmp_parser.py` | Unit tests for BMP image alignment helpers. |
| `tests/test_message_api.py` | Unit tests for USB message conversion and serialization. |
| `tests/test_sequenciator.py` | Unit tests for digital sequence generation. |

### DAC communication project (`32bitPython.zip`)

The repository also includes a **separate Python project**, distributed as the `32bitPython.zip` archive, for communication with the Analog Devices DAC evaluation board used to set LED drive currents. The main application launches its 32-bit helper using the paths in `runtime_config.py` and sends channel/voltage commands as JSON over a local TCP connection (`127.0.0.1:65432` by default). The helper translates those commands into calls to the vendor's Windows DLL and updates the DAC outputs.

| File or directory inside `32bitPython/` | Purpose |
| --- | --- |
| `server_32bit.py` | Local TCP server that receives channel-to-voltage commands and returns the indices of unsuccessful writes. |
| `ad5361_commands.py` | DAC board driver: loads the vendor DLL, connects to the board, downloads the controller firmware, writes channel voltages via SPI, and pulses LDAC. |
| `server_32bit_prova.py` | Alternative test version of the socket server for sending a single channel/voltage command. |
| `attachments/DLL Sample VIs/` | Vendor `ADI_CYUSB_USB4.dll` and LabVIEW examples for USB communication. |
| `attachments/Drivers/` | DAC USB driver installer (`ADI_PDA_Drivers.exe`) and controller firmware (`AD536xSPI.hex`). |

The archive must be **extracted before use**. The DAC helper requires a compatible **32-bit Python interpreter on Windows**; the DLL, firmware, and helper paths are workstation-specific and must be configured for the target computer. The archive also contains PyCharm project metadata, which is not required at runtime.

## Requirements and launch

The software is designed for a **Windows acquisition workstation**, using **Python 3.12+**, the packages in `requirements.txt`, the Hamamatsu DCAM drivers, NI-DAQmx, and the relevant device drivers/hardware.

```bash
python -m pip install -r requirements.txt
python control_platform.py
```

Before launching, adapt the device IDs and paths using `runtime_config.py` or its environment-variable overrides. Some workstation-specific GUI image assets are not included in this repository snapshot. The separate DAC helper is supplied in `32bitPython.zip` but requires extraction and configuration.

