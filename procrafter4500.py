"""Low-level USB HID communication with the Texas Instruments DLPC350 controller.

This module builds command packets, exchanges them with a LightCrafter 4500,
parses device responses, and exposes operations for flash programming, pattern
sequences, display control, and LED configuration.
"""

from contextlib import contextmanager

import usb.core
import usb.util

import runtime_config as cfg
from message_api import HidMessageStruct

MSG_CMD_SIZE = 2
MSG_HEAD_SIZE = 4
USB_MAX_PACKET_SIZE = 64
USB_RESPONSE_SIZE = USB_MAX_PACKET_SIZE + 1
USB_OUT_ENDPOINT = 0x01
USB_IN_ENDPOINT = 0x81
USB_TIMEOUT_MS = 2000
HID_MESSAGE_MAX_SIZE = 512
STAT_BIT_FLASH_BUSY = 0x08
MAX_IMAGE_LUT_ENTRIES = 64

cmd_list = {
    'GET_MAN_ID': [0x00, 0x15, 0x01],
    'GET_DEV_ID': [0x00, 0x15, 0x01],
    'GET_CHKSUM': [0x00, 0x15, 0x01],
    'ENTER_PROG_MODE': [0x30, 0x01, 0x00],
    'EXIT_PROG_MODE': [0x00, 0x30, 0x01],
    'SET_SECTADDR': [0x00, 0x29, 0x04],
    'SECT_ERASE': [0x00, 0x28, 0x00],
    'SET_DNLDSIZE': [0x00, 0x2C, 0x04],
    'DNLD_DATA': [0x00, 0x25, 0x00],
    'FLASH_TYPE': [0x00, 0x2F, 0x01],
    'CALC_CHKSUM': [0x00, 0x26, 0x00],

    'STATUS_MAIN': [0x1A, 0x0C, 0x00],
    'POWER_CONTROL': [0x02, 0x00, 0x01],
    'SW_RESET': [0x08, 0x02, 0x00],
    'NUM_IMAGE_IN_FLASH': [0x1A, 0x42, 0x01],
    'PAT_TRIG_MODE': [0x1A, 0x23, 0x01],
    'PAT_DISP_MODE': [0x1A, 0x22, 0x01],
    'DISP_MODE': [0x1A, 0x1B, 0x01],
    'PAT_START_STOP': [0x1A, 0x24, 0x01],
    'PAT_CONFIG': [0x1A, 0x31, 0x04],
    'PAT_EXPO_PRD': [0x1A, 0x29, 0x08],
    'MBOX_CONTROL': [0x1A, 0x33, 0x01],
    'MBOX_ADDRESS': [0x1A, 0x32, 0x01],
    'MBOX_DATA': [0x1A, 0x34, 0x00],
    'LUT_VALID': [0x1A, 0x1A, 0x01],
    'LED_CURRENT': [0x0B, 0x01, 0x03],
    'LED_ENABLE': [0x1A, 0x07, 0x01],
    'PWM_INVERT': [0x1A, 0x05, 0x01],
}


def create_hid_message_struct(msg):
    """Parse a raw HID response into a :class:`HidMessageStruct`.

    Parameters
    ----------
    msg
        Byte sequence returned by the USB device. The first four bytes contain
        the HID header and the remaining bytes contain the response payload.

    Returns
    -------
    HidMessageStruct
        Parsed message containing the response flags, sequence number, payload
        length, and payload data.
    """
    pmsg = HidMessageStruct()
    pmsg.head.flags = msg[0]
    pmsg.head.sequence = msg[1]
    values = list(msg)
    pmsg.head.length = values[2:4]
    pmsg.text.data = values[4:4 + pmsg.head.return_length()]

    return pmsg


@contextmanager
def connect_usb():
    """Open a USB connection to the configured DLPC350 device.

    The device identifiers are read from :mod:`runtime_config`. The USB resources
    are reset and released when the context exits, including when an exception is
    raised inside the context.

    Yields
    ------
    Dlpc350
        Command interface bound to the detected USB device.

    Raises
    ------
    RuntimeError
        If no device matching the configured vendor and product identifiers is
        detected.
    """
    device = usb.core.find(
        idVendor=cfg.DMD_USB_VENDOR_ID,
        idProduct=cfg.DMD_USB_PRODUCT_ID,
    )
    if device is None:
        raise RuntimeError(
            "DLPC350 USB device not found. Check the USB connection and driver."
        )

    try:
        device.set_configuration()
        yield Dlpc350(device)
    finally:
        try:
            device.reset()
        finally:
            usb.util.dispose_resources(device)


class Dlpc350:
    """USB command interface for a configured DLPC350 controller.

    The class stores the current command and response buffers together with the
    latest device state returned by flash, display, trigger, and LED commands.
    """

    def __init__(self, device):
        """Initialize the command interface for an open PyUSB device.

        Parameters
        ----------
        device
            Configured PyUSB device handle associated with the DLPC350 controller.
        """
        self.dlpc = device

        # INPUT/OUTPUT
        self.input_buffer = HidMessageStruct()
        self.pmsg = HidMessageStruct()
        self.ans = []
        self.output_buffer = []

        # PARAMETERS
        self.standby = False            # Power mode

        self.p_man_id = None            # Flash manufacturer ID
        self.p_dev_id = None            # Flash device ID
        self.bl_status = None           # Busy bit
        self.checksum = None            # Checksum
        self.read_word = None           # Last value returned by mem_read
        self.mode = None                # Display mode
        self.action = None              # Pattern display action
        self.trig_mode = None           # Pattern trigger mode

        self.red_led = None             # Red LED current
        self.green_led = None           # Green LED current
        self.blue_led = None            # Blue LED current

    def write(self, ack_required):
        """Transmit the current output buffer to the controller.

        Parameters
        ----------
        ack_required : bool
            Whether an acknowledgement response must be read after transmission.

        Returns
        -------
        int
            Number of bytes written on success, ``-2`` when the acknowledgement
            reports a controller error, or the PyUSB write result otherwise.
        """
        if ack_required:
            ret_val = self.dlpc.write(USB_OUT_ENDPOINT, self.output_buffer)
            if ret_val > 0:
                ans = self.dlpc.read(USB_IN_ENDPOINT, USB_RESPONSE_SIZE, timeout=USB_TIMEOUT_MS)
                if len(ans) > 0:
                    response = create_hid_message_struct(ans)
                    if response.head.flags & (1 << 5):
                        return -2
                    else:
                        return ret_val
        else:
            ret_val = self.dlpc.write(USB_OUT_ENDPOINT, self.output_buffer)
        return ret_val

    def read(self):
        """Send the prepared read command and parse the controller response.

        Returns
        -------
        int
            Response payload length on success, ``-1`` if the USB write fails, or
            ``-2`` if the response is empty or contains the controller error flag.
        """
        if self.dlpc.write(USB_OUT_ENDPOINT, self.output_buffer) > 0:
            ans = self.dlpc.read(USB_IN_ENDPOINT, USB_RESPONSE_SIZE, timeout=USB_TIMEOUT_MS)
            self.input_buffer = create_hid_message_struct(ans)
            has_error = bool(self.input_buffer.head.flags & (1 << 5))
            has_empty_payload = self.input_buffer.head.return_length() == 0
            if has_error or has_empty_payload:
                return -2
            else:
                return self.input_buffer.head.return_length()
        return -1

    def prep_read_cmd(self, cmd, key=None):
        """Build a fixed-size HID read command.

        Parameters
        ----------
        cmd : sequence of int
            Command descriptor whose first two elements identify the DLPC350 command.
        key : str, optional
            Optional selector for read commands that require an additional parameter.
            The currently supported selectors are ``GET_MAN_ID``, ``GET_DEV_ID``, and
            ``GET_CHKSUM``.

        Returns
        -------
        int
            Always returns ``0`` after preparing and padding ``self.output_buffer``.
        """
        msg = HidMessageStruct()

        msg.head.set_read()
        msg.head.set_reply()
        msg.head.set_length(2)

        msg.text.set_cmd(cmd[0:2])

        if key == 'GET_MAN_ID':
            msg.text.set_data([0x0C])
            msg.head.set_length(3)

        if key == 'GET_DEV_ID':
            msg.text.set_data([0x0D])
            msg.head.set_length(3)

        if key == 'GET_CHKSUM':
            msg.text.set_data([0x00])
            msg.head.set_length(3)

        self.output_buffer = msg.make_list()
        while len(self.output_buffer) < USB_MAX_PACKET_SIZE:
            self.output_buffer.append(0)

        return 0

    def prep_read_cmd_param(self, cmd, param):
        """Build a HID read command with an additional parameter payload.

        Parameters
        ----------
        cmd : sequence of int
            Two-byte DLPC350 command identifier.
        param : sequence of int
            Parameter bytes appended to the command.

        Returns
        -------
        int
            Always returns ``0`` after preparing and padding ``self.output_buffer``.
        """
        msg = HidMessageStruct()

        msg.head.set_read()
        msg.head.set_reply()
        msg.head.set_length(3)

        msg.text.set_cmd(cmd)
        msg.text.set_data(param)

        self.output_buffer = msg.make_list()
        self.output_buffer.extend([0] * (USB_MAX_PACKET_SIZE - len(self.output_buffer)))

        return 0

    def prep_mem_read_cmd(self, addr):
        """Build a command that reads a 32-bit memory address.

        The address is serialized in little-endian byte order and the command is
        padded to one USB packet.

        Parameters
        ----------
        addr : int
            Memory address to read.

        Returns
        -------
        int
            Always returns ``0`` after preparing ``self.output_buffer``.
        """
        msg = HidMessageStruct()

        msg.head.set_read()
        msg.head.set_reply()
        msg.head.set_length(6)

        msg.text.set_cmd([0x1A, 0x16])
        msg.text.set_data([
            addr & 0xFF,
            (addr >> 8) & 0xFF,
            (addr >> 16) & 0xFF,
            (addr >> 24) & 0xFF,
        ])

        self.output_buffer = msg.make_list()
        self.output_buffer.extend([0] * (USB_MAX_PACKET_SIZE - len(self.output_buffer)))

        return 0

    def mem_read(self, addr):
        """Read one 32-bit word from the specified memory address.

        Parameters
        ----------
        addr : int
            Memory address to read.

        Returns
        -------
        int
            ``0`` on success or ``-1`` if a valid four-byte response is not received.

        Notes
        -----
        The decoded little-endian value is stored in ``self.read_word``.
        """
        self.prep_mem_read_cmd(addr)

        if self.read() > 0 and len(self.input_buffer.text.data) >= 4:
            data = self.input_buffer.text.data
            self.read_word = (
                data[0]
                | (data[1] << 8)
                | (data[2] << 16)
                | (data[3] << 24)
            )
            return 0

        return -1

    def prep_write_cmd(self, cmd):
        """Initialize the current HID message for a write command.

        Parameters
        ----------
        cmd : sequence of int
            Command descriptor containing two command bytes and the payload length.

        Returns
        -------
        int
            Always returns ``0`` after updating ``self.pmsg``.
        """
        self.pmsg.head.set_read(mode='w')
        self.pmsg.head.set_reply()
        self.pmsg.head.increase_seq_num()

        self.pmsg.text.set_cmd(cmd[0:2])
        self.pmsg.head.set_length(cmd[2] + 2)

        return 0

    def send_msg(self, ack_required):
        """Send the prepared HID message in one or more USB packets.

        The first packet contains the HID header and command bytes. Messages larger
        than one packet are continued using payload-only packets. An acknowledgement
        is requested only for the final packet when ``ack_required`` is true.

        Parameters
        ----------
        ack_required : bool
            Whether the final packet requires an acknowledgement response.

        Returns
        -------
        int
            Number of message bytes handled on success or ``-1`` if transmission
            fails.
        """
        max_data_size = USB_MAX_PACKET_SIZE - MSG_HEAD_SIZE - MSG_CMD_SIZE
        data_bytes_sent = min(self.pmsg.head.return_length(), max_data_size)

        if not ack_required:
            self.pmsg.head.set_reply(reply=False)

        self.output_buffer = self.pmsg.make_list()[:USB_MAX_PACKET_SIZE]

        if data_bytes_sent >= self.pmsg.head.return_length():
            while len(self.output_buffer) < USB_MAX_PACKET_SIZE:
                self.output_buffer.append(0)
            if self.write(ack_required) < 0:
                return -1

        else:
            if self.write(0) < 0:
                return -1

            while data_bytes_sent < self.pmsg.head.return_length():

                if data_bytes_sent + USB_MAX_PACKET_SIZE >= self.pmsg.head.return_length():
                    self.output_buffer = self.pmsg.text.data[data_bytes_sent:]
                    while len(self.output_buffer) < USB_MAX_PACKET_SIZE:
                        self.output_buffer.append(0)
                    if self.write(ack_required) < 0:
                        return -1

                else:
                    self.output_buffer = self.pmsg.text.data[
                        data_bytes_sent:data_bytes_sent + USB_MAX_PACKET_SIZE
                    ]
                    if self.write(0) < 0:
                        return -1

                data_bytes_sent += USB_MAX_PACKET_SIZE

        return data_bytes_sent + MSG_HEAD_SIZE + MSG_CMD_SIZE

    def enter_programming_mode(self):
        """Request entry into flash-programming mode.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['ENTER_PROG_MODE'])
        self.pmsg.text.set_data([0x01])

        return self.send_msg(ack_required=False)

    def exit_programming_mode(self):
        """Request exit from flash-programming mode.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['EXIT_PROG_MODE'])
        self.pmsg.text.set_data([0x02])

        return self.send_msg(ack_required=False)

    def get_flash_man_id(self):
        """Read the flash manufacturer identifier.

        Returns
        -------
        int
            ``0`` on success or ``-1`` on communication failure.

        Notes
        -----
        The decoded identifier is stored in ``self.p_man_id``.
        """
        self.prep_read_cmd(cmd_list['GET_MAN_ID'], key='GET_MAN_ID')

        if self.read() > 0:
            msg = self.input_buffer
            self.p_man_id = msg.text.data[6]
            self.p_man_id |= msg.text.data[7] << 8
            return 0

        return -1

    def get_flash_dev_id(self):
        """Read the flash device identifier.

        Returns
        -------
        int
            ``0`` on success or ``-1`` on communication failure.

        Notes
        -----
        The decoded identifier is stored in ``self.p_dev_id``.
        """
        self.prep_read_cmd(cmd_list['GET_DEV_ID'], key='GET_DEV_ID')

        if self.read() > 0:
            msg = self.input_buffer
            self.p_dev_id = msg.text.data[6]
            self.p_dev_id |= msg.text.data[7] << 8
            self.p_dev_id |= msg.text.data[8] << 16
            self.p_dev_id |= msg.text.data[9] << 24
            self.p_dev_id |= msg.text.data[12] << 32
            self.p_dev_id |= msg.text.data[13] << 40
            self.p_dev_id |= msg.text.data[14] << 48
            self.p_dev_id |= msg.text.data[15] << 56
            return 0

        return -1

    def get_bl_status(self):
        # The checksum response also exposes the bootloader status in byte 0.
        """Read the bootloader status and extract its busy flag.

        The implementation uses the first response byte returned through the checksum
        read path because that response also carries the bootloader status.

        Returns
        -------
        int
            ``0`` on success or ``-1`` on communication failure.

        Notes
        -----
        The extracted flag is stored in ``self.bl_status``.
        """
        self.prep_read_cmd(cmd_list['GET_CHKSUM'], key='GET_CHKSUM')

        if self.read() > 0:
            msg = self.input_buffer
            byte_status = msg.text.data[0]
            self.bl_status = bool(byte_status & STAT_BIT_FLASH_BUSY)
            return 0

        return -1

    def set_flash_addr(self, addr):
        """Set the start address used by subsequent flash operations.

        Parameters
        ----------
        addr : int
            32-bit flash address serialized in little-endian byte order.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['SET_SECTADDR'])
        self.pmsg.text.set_data([int(addr & 0xFF),
                                 int((addr >> 8) & 0xFF),
                                 int((addr >> 16) & 0xFF),
                                 int((addr >> 24) & 0xFF)])

        return self.send_msg(ack_required=True)

    def flash_sector_erase(self):
        """Erase the flash sector selected by the current flash address.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['SECT_ERASE'])

        return self.send_msg(ack_required=True)

    def set_upload_size(self, data_len):
        """Set the number of bytes involved in the next flash transfer.

        Parameters
        ----------
        data_len : int
            Transfer length encoded as an unsigned 32-bit little-endian value.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['SET_DNLDSIZE'])
        self.pmsg.text.set_data([data_len & 0xFF,
                                 (data_len >> 8) & 0xFF,
                                 (data_len >> 16) & 0xFF,
                                 (data_len >> 24) & 0xFF])

        return self.send_msg(ack_required=True)

    def upload_data(self, p_byte_array, data_len):
        """Upload one block of firmware data to the controller bootloader.

        Parameters
        ----------
        p_byte_array : bytes or bytearray
            Source firmware bytes.
        data_len : int
            Requested number of bytes to transmit from ``p_byte_array``.

        Returns
        -------
        int
            Number of payload bytes accepted for transmission, or ``-1`` if the USB
            transfer fails.

        Notes
        -----
        The payload is capped below the HID message limit to preserve the two-byte
        margin required by the existing bootloader workaround.
        """
        self.pmsg = HidMessageStruct()

        send_size = HID_MESSAGE_MAX_SIZE - MSG_HEAD_SIZE - MSG_CMD_SIZE - 2
        # Reserve two bytes for compatibility with the existing bootloader.

        if data_len > send_size:
            data_len = send_size

        cmd_list['DNLD_DATA'][2] = data_len
        self.prep_write_cmd(cmd_list['DNLD_DATA'])
        self.pmsg.text.set_data(p_byte_array[:data_len])

        ret_val = self.send_msg(ack_required=False)
        if ret_val > 0:
            return data_len

        return -1

    def wait_for_flash_ready(self):
        """Poll the bootloader status until the flash busy flag is cleared.

        Returns
        -------
        int
            ``0`` when the flash becomes ready or ``-1`` if the status cannot
            be read.

        Notes
        -----
        This method has no timeout and therefore blocks until the status changes
        or a status-read operation fails.
        """
        self.bl_status = True
        while self.bl_status:
            if self.get_bl_status() < 0:
                return -1
        return 0

    def set_flash_type(self, type):
        """Select the flash-memory type used by programming operations.

        Parameters
        ----------
        type : int
            Raw flash-type value expected by the DLPC350 bootloader.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['FLASH_TYPE'])
        self.pmsg.text.set_data([type])

        return self.send_msg(ack_required=True)

    def calculate_flash_checksum(self):
        """Request checksum calculation for the selected flash region.

        Returns
        -------
        int
            ``0`` when the request is transmitted successfully or ``-1`` otherwise.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['CALC_CHKSUM'])

        if self.send_msg(ack_required=False) <= 0:
            return -1

        return 0

    def get_flash_checksum(self):
        """Read the checksum calculated by the controller.

        Returns
        -------
        int
            ``0`` on success or ``-1`` on communication failure.

        Notes
        -----
        The decoded 32-bit little-endian checksum is stored in ``self.checksum``.
        """
        self.prep_read_cmd(cmd_list['GET_CHKSUM'], key='GET_CHKSUM')

        if self.read() > 0:
            msg = self.input_buffer
            self.checksum = msg.text.data[6]
            self.checksum |= msg.text.data[7] << 8
            self.checksum |= msg.text.data[8] << 16
            self.checksum |= msg.text.data[9] << 24
            return 0

        return -1

    def set_power_mode(self, standby):
        """Set the controller power mode.

        Parameters
        ----------
        standby : bool
            ``True`` requests standby mode; ``False`` requests normal operation.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.standby = standby
        self.prep_write_cmd(cmd_list['POWER_CONTROL'])
        self.pmsg.text.set_data([int(standby)])

        return self.send_msg(ack_required=True)

    def get_power_mode(self):
        """Read the current controller power mode.

        Returns
        -------
        int
            ``0`` on success or ``-1`` on communication failure.

        Notes
        -----
        The decoded state is stored as a Boolean in ``self.standby``.
        """
        self.prep_read_cmd(cmd_list['POWER_CONTROL'], key='POWER_CONTROL')

        if self.read() > 0:
            msg = self.input_buffer

            if msg.text.data[0] & 0x03:
                self.standby = True
            else:
                self.standby = False
        else:
            return -1

        return 0

    def software_reset(self):
        """Request a software reset of the DLPC350 controller.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['SW_RESET'])

        return self.send_msg(ack_required=False)

    def get_num_images_in_flash(self):
        """Read the number of images currently stored in flash memory.

        Returns
        -------
        int
            Number of stored images, or ``-1`` on communication failure.
        """
        self.prep_read_cmd(cmd_list['NUM_IMAGE_IN_FLASH'], key='NUM_IMAGE_IN_FLASH')

        if self.read() > 0:
            msg = self.input_buffer
            num_images_in_flash = msg.text.data[0] & 0xFF

            return num_images_in_flash

        return -1

    def get_pattern_trigger_mode(self):
        """Read the active pattern trigger mode.

        Returns
        -------
        tuple of (int, int or None)
            ``(0, mode)`` on success or ``(-1, None)`` on communication failure.
        """
        self.prep_read_cmd(cmd_list['PAT_TRIG_MODE'], key='PAT_TRIG_MODE')

        if self.read() > 0:
            msg = self.input_buffer
            self.trig_mode = msg.text.data[0] & 0xFF
            return 0, self.trig_mode

        return -1, None

    def set_pattern_trigger_mode(self, mode):
        """Set the pattern trigger mode.

        Parameters
        ----------
        mode : int
            Raw trigger-mode value expected by the DLPC350 controller.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['PAT_TRIG_MODE'])
        self.pmsg.text.set_data([int(mode)])

        return self.send_msg(ack_required=True)

    def set_pattern_display_mode(self, external):
        """Select the source used for pattern display data.

        Parameters
        ----------
        external : bool
            When true, transmit the protocol value used for external pattern display;
            otherwise transmit the protocol value used by the current internal mode.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['PAT_DISP_MODE'])
        if external:
            self.pmsg.text.set_data([0])
        else:
            self.pmsg.text.set_data([3])

        return self.send_msg(ack_required=True)

    def get_mode(self):
        """Read the current display mode.

        Returns
        -------
        tuple of (int, bool or None)
            ``(0, mode)`` on success or ``(-1, None)`` on communication failure.
        """
        self.prep_read_cmd(cmd_list['DISP_MODE'], key='DISP_MODE')

        if self.read() > 0:
            msg = self.input_buffer
            self.mode = msg.text.data[0] != 0
            return 0, self.mode

        return -1, None

    def set_mode(self, mode):
        """Set the display mode.

        Parameters
        ----------
        mode : int or bool
            Raw display-mode value expected by the controller.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['DISP_MODE'])
        self.pmsg.text.set_data([int(mode)])

        return self.send_msg(ack_required=True)

    def get_pattern_display(self):
        """Read the current pattern-display action.

        Returns
        -------
        tuple of (int, int or None)
            ``(0, action)`` on success or ``(-1, None)`` on communication failure.
        """
        self.prep_read_cmd(cmd_list['PAT_START_STOP'], key='PAT_START_STOP')

        if self.read() > 0:
            msg = self.input_buffer
            self.action = msg.text.data[0] & 0xFF
            return 0, self.action

        return -1, None

    def set_pattern_config(
        self,
        num_lut_entries,
        repeat,
        num_pat_for_trig_out2,
        num_splash_lut_entries,
    ):
        """Configure the pattern lookup table and trigger output behavior.

        Parameters
        ----------
        num_lut_entries : int
            Number of pattern LUT entries.
        repeat : int
            Raw repeat-mode value sent to the controller.
        num_pat_for_trig_out2 : int
            Number of patterns associated with the TRIG_OUT_2 configuration.
        num_splash_lut_entries : int
            Number of image LUT entries used by the sequence.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.

        Notes
        -----
        The three count values are encoded as ``count - 1`` by the DLPC350 command.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['PAT_CONFIG'])
        self.pmsg.text.set_data(
            [
                num_lut_entries - 1,
                repeat,
                num_pat_for_trig_out2 - 1,
                num_splash_lut_entries - 1,
            ]
        )

        return self.send_msg(ack_required=True)

    def set_exposure_frame_period(self, exposure_period, frame_period):
        """Set the pattern exposure period and frame period.

        Parameters
        ----------
        exposure_period : int
            Unsigned 32-bit exposure-period value expected by the controller.
        frame_period : int
            Unsigned 32-bit frame-period value expected by the controller.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['PAT_EXPO_PRD'])
        self.pmsg.text.set_data([exposure_period & 0xFF,
                                 (exposure_period >> 8) & 0xFF,
                                 (exposure_period >> 16) & 0xFF,
                                 (exposure_period >> 24) & 0xFF,
                                 frame_period & 0xFF,
                                 (frame_period >> 8) & 0xFF,
                                 (frame_period >> 16) & 0xFF,
                                 (frame_period >> 24) & 0xFF])

        return self.send_msg(ack_required=True)

    def open_mailbox(self, m_box_num):
        """Open a DLPC350 mailbox.

        Parameters
        ----------
        m_box_num : int
            Mailbox identifier sent to the controller.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['MBOX_CONTROL'])
        self.pmsg.text.set_data([m_box_num])

        return self.send_msg(ack_required=True)

    def mailbox_set_addr(self, addr):
        """Set the current mailbox address.

        Parameters
        ----------
        addr : int
            Mailbox address in the inclusive range 0--127.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`, or ``-1`` when ``addr`` exceeds 127.
        """
        self.pmsg = HidMessageStruct()

        if addr > 127:
            return -1

        self.prep_write_cmd(cmd_list['MBOX_ADDRESS'])
        self.pmsg.text.set_data([addr])

        return self.send_msg(ack_required=True)

    def close_mailbox(self):
        """Close the currently open mailbox.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['MBOX_CONTROL'])
        self.pmsg.text.set_data([0])

        return self.send_msg(ack_required=True)

    def send_pat_lut(self, g_pat_lut_index, g_pat_lut):
        """Write pattern lookup-table entries to mailbox 2.

        Parameters
        ----------
        g_pat_lut_index : int
            Number of entries to transmit.
        g_pat_lut : sequence of int
            Pattern LUT words. Each entry is serialized using its least-significant
            three bytes in little-endian order.

        Returns
        -------
        int
            ``0`` after the mailbox transaction or ``-1`` if the mailbox cannot be
            opened.
        """
        self.pmsg = HidMessageStruct()

        bytes_to_send = g_pat_lut_index * 3

        if self.open_mailbox(2) < 0:
            return -1
        self.mailbox_set_addr(0)
        cmd_list['MBOX_DATA'][2] = bytes_to_send

        self.prep_write_cmd(cmd_list['MBOX_DATA'])

        data = []
        for i in range(g_pat_lut_index):
            data.append(g_pat_lut[i] & 0xFF)
            data.append((g_pat_lut[i] >> 8) & 0xFF)
            data.append((g_pat_lut[i] >> 16) & 0xFF)

        self.pmsg.text.set_data(data)
        self.send_msg(ack_required=True)

        self.close_mailbox()
        return 0

    def send_image_lut(self, lut_entries, num_entries):
        """Write image lookup-table entries to mailbox 1.

        Parameters
        ----------
        lut_entries : sequence of int
            Image indices to send.
        num_entries : int
            Number of entries to transmit; valid values are 1 through
            ``MAX_IMAGE_LUT_ENTRIES``.

        Returns
        -------
        int
            Number of bytes reported by :meth:`send_msg`, or ``-1`` for an invalid
            entry count.

        Notes
        -----
        The existing two-entry case transmits the entries in reverse order to preserve
        controller-specific sequence behavior.
        """
        self.pmsg = HidMessageStruct()

        if num_entries < 1 or num_entries > MAX_IMAGE_LUT_ENTRIES:
            return -1

        self.open_mailbox(1)
        self.mailbox_set_addr(0)

        data = []
        if num_entries == 2:
            data.append(lut_entries[1])
            data.append(lut_entries[0])
        else:
            for i in range(num_entries):
                data.append(lut_entries[i])
        cmd_list['MBOX_DATA'][2] = num_entries
        self.prep_write_cmd(cmd_list['MBOX_DATA'])
        self.pmsg.text.set_data(data)

        bytes_sent = self.send_msg(ack_required=True)

        self.close_mailbox()

        return bytes_sent

    def start_pat_lut_validate(self):
        """Start validation of the configured pattern lookup table.

        Returns
        -------
        int
            ``0`` when validation is requested successfully or ``1`` if transmission
            fails.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['LUT_VALID'])
        if self.send_msg(ack_required=True) < 0:
            return 1

        return 0

    def check_pat_lut_validate(self):
        """Check whether pattern lookup-table validation has completed.

        Returns
        -------
        tuple
            ``(ready, status)`` when a response is received. ``ready`` is true when
            the controller busy bit is clear. Returns ``(-1, None)`` on communication
            failure.
        """
        status = None
        self.prep_read_cmd(cmd_list['LUT_VALID'], key='LUT_VALID')

        if self.read() > 0:
            msg = self.input_buffer
            if msg.text.data[0] & 0x80 == 0:
                status = msg.text.data[0]
                ready = True
            else:
                ready = False

            return ready, status

        else:
            return -1, status

    def pattern_display(self, action):
        """Set the pattern-display action.

        Parameters
        ----------
        action : int
            Action value; only the least-significant two bits are transmitted.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['PAT_START_STOP'])
        self.pmsg.text.set_data([action & 0x03])

        return self.send_msg(ack_required=True)

    def get_led_currents(self):
        """Read the raw red, green, and blue LED current values.

        Returns
        -------
        int
            ``0`` on success or ``-1`` on communication failure.

        Notes
        -----
        The returned values are stored in ``self.red_led``, ``self.green_led``, and
        ``self.blue_led``.
        """
        self.prep_read_cmd(cmd_list['LED_CURRENT'], key='LED_CURRENT')

        if self.read() > 0:
            msg = self.input_buffer
            self.red_led = msg.text.data[0]
            self.green_led = msg.text.data[1]
            self.blue_led = msg.text.data[2]

            return 0

        return -1

    def set_led_currents(self, red_current, green_current, blue_current):
        """Set the raw red, green, and blue LED current values.

        Parameters
        ----------
        red_current : int
            Raw red-channel current-control value.
        green_current : int
            Raw green-channel current-control value.
        blue_current : int
            Raw blue-channel current-control value.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['LED_CURRENT'])
        self.pmsg.text.set_data([red_current, green_current, blue_current])

        return self.send_msg(ack_required=True)

    def set_led_enables(self, seq_ctrl, red, green, blue):
        """Configure sequencer control and individual LED enable flags.

        Parameters
        ----------
        seq_ctrl : bool
            Enable LED selection through the pattern sequencer.
        red : bool
            Enable the red LED channel.
        green : bool
            Enable the green LED channel.
        blue : bool
            Enable the blue LED channel.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        enable = 0
        if seq_ctrl:
            enable |= 0x08
        if red:
            enable |= 0x01
        if green:
            enable |= 0x02
        if blue:
            enable |= 0x04

        self.prep_write_cmd(cmd_list['LED_ENABLE'])
        self.pmsg.text.set_data([enable])

        return self.send_msg(ack_required=True)

    def set_led_pwm_invert(self, invert):
        """Configure inversion of the LED PWM signals.

        Parameters
        ----------
        invert : int
            Raw inversion bit mask expected by the controller.

        Returns
        -------
        int
            Result returned by :meth:`send_msg`.
        """
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['PWM_INVERT'])
        self.pmsg.text.set_data([invert])

        return self.send_msg(ack_required=True)




