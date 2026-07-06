from contextlib import contextmanager
import usb.core
import usb.util
from message_api import HidMessageStruct

MSG_CMD_SIZE = 2
MSG_HEAD_SIZE = 4
USB_MAX_PACKET_SIZE = 64
ACK_REQUIRED = True
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
    'PAT_DISP_MODE':[0x1A, 0x22, 0x01],
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
    'PWM_INVERT': [0x1A, 0x05, 0x01]
}



def create_hid_message_struct(msg):
    """
    This function creates a HidMessageStruct object from a list of bytes.

    :param msg: List of bytes.
    :return: HidMessageStruct object.
    """
    pmsg = HidMessageStruct()
    pmsg.head.flags = msg[0]
    pmsg.head.sequence = msg[1]
    pmsg.head.length = msg[2:4].tolist()
    pmsg.text.data = msg[4:4 + pmsg.head.return_length()].tolist() # deve prendere da 4 a 4 + length

    return pmsg


@contextmanager
def connect_usb():
    """
    Context manager for connecting to and releasing usb device.

    :yields: USB device.
    """
    device = usb.core.find(idVendor=0x0451, idProduct=0x6401)
    device.set_configuration()

    lcr = Dlpc350(device)

    yield lcr

    device.reset()
    del lcr
    del device


class Dlpc350(object):
    def __init__(self, device):
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
        self.mode = None                # Display mode
        self.action = None              # Pattern display action
        self.trig_mode = None           # Pattern trigger mode

        self.red_led = None             # Red LED current
        self.green_led = None           # Green LED current
        self.blue_led = None            # Blue LED current

    def write(self, ACK_REQUIRED):
        if ACK_REQUIRED:
            ret_val = self.dlpc.write(1, self.output_buffer)
            if ret_val > 0:
                ans = self.dlpc.read(0x81, 65, timeout=2000)
                if len(ans) > 0:
                    if self.pmsg.head.flags & (1<<5) == 1:
                        return -2
                    else:
                        return ret_val
        else:
            ret_val = self.dlpc.write(1, self.output_buffer)
        return ret_val

    def read(self):
        """The function writes the read control command and reads back 64 bytes over USB to the input buffer.

        :return: The input buffer if the read was successful, -1 if the write was unsuccessful, -2 if the read was unsuccessful."""
        if self.dlpc.write(1, self.output_buffer) > 0:
            ans = self.dlpc.read(0x81, 65, timeout=2000)
            self.input_buffer = create_hid_message_struct(ans)
            if self.input_buffer.head.flags & (1 << 5) == 1 | self.input_buffer.head.return_length() == 0:
                return -2
            else:
                return self.input_buffer.head.return_length()
        return -1

    def prep_read_cmd(self, cmd, key=None):
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
        msg = HidMessageStruct()

        msg.head.set_read()
        msg.head.set_reply()
        msg.head.set_length(3)

        msg.text.set_cmd(cmd)
        msg.text.set_data(param)

        self.output_buffer = msg

        return 0

    def prep_mem_read_cmd(self, addr):
        msg = HidMessageStruct()

        msg.head.set_read()
        msg.head.set_reply()
        msg.head.set_length(6)

        msg.text.set_cmd([0x1A, 0x16])
        msg.text.set_data(addr)
        msg.text.set_data(addr>>8)
        msg.text.set_data(addr>>16)
        msg.text.set_data(addr>>24)

        self.output_buffer = msg

        return 0

    def mem_read(self, addr):
        self.prep_mem_read_cmd(addr)

        if self.dlpc.read(0x81, 65, timeout=2000) > 0:
            msg = self.input_buffer
            self.read_word = msg.text.data[3] | (msg.text.data[2] << 8) | (msg.text.data[1] << 16) | (msg.text.data[0] << 24)
            return 0

        return -1

    def prep_write_cmd(self, cmd):
        self.pmsg.head.set_read(mode='w')
        self.pmsg.head.set_reply()
        self.pmsg.head.increase_seq_num()

        self.pmsg.text.set_cmd(cmd[0:2])
        self.pmsg.head.set_length(cmd[2] + 2)

        return 0

    def send_msg(self, ACK_REQUIRED):
        """This function sends a message over USB in chunks of 64 bytes."""
        max_data_size = USB_MAX_PACKET_SIZE - MSG_HEAD_SIZE - MSG_CMD_SIZE
        data_bytes_sent = min(self.pmsg.head.return_length(), max_data_size)

        if not ACK_REQUIRED:
            self.pmsg.head.set_reply(reply=False)

        self.output_buffer = self.pmsg.make_list()[:USB_MAX_PACKET_SIZE]

        if data_bytes_sent >= self.pmsg.head.return_length(): # if the message is less than 64 bytes
            while len(self.output_buffer) < USB_MAX_PACKET_SIZE:
                self.output_buffer.append(0)
            if self.write(ACK_REQUIRED) < 0:
                return -1

        else:
            if self.write(0) < 0: # First packet
                return -1

            while data_bytes_sent < self.pmsg.head.return_length():

                if data_bytes_sent + USB_MAX_PACKET_SIZE >= self.pmsg.head.return_length(): # Last packet
                    self.output_buffer = self.pmsg.text.data[data_bytes_sent:]
                    while len(self.output_buffer) < USB_MAX_PACKET_SIZE:
                        self.output_buffer.append(0)
                    if self.write(ACK_REQUIRED) < 0:
                        return -1

                else:
                    self.output_buffer = self.pmsg.text.data[data_bytes_sent:data_bytes_sent + USB_MAX_PACKET_SIZE]
                    if self.write(0) < 0:
                        return -1

                data_bytes_sent += USB_MAX_PACKET_SIZE

        return data_bytes_sent + MSG_HEAD_SIZE + MSG_CMD_SIZE

    def enter_programming_mode(self):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['ENTER_PROG_MODE'])
        self.pmsg.text.set_data([0x01])

        return self.send_msg(ACK_REQUIRED=False)

    def exit_programming_mode(self):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['EXIT_PROG_MODE'])
        self.pmsg.text.set_data([0x02])

        return self.send_msg(ACK_REQUIRED=False)

    def get_flash_man_id(self):
        self.prep_read_cmd(cmd_list['GET_MAN_ID'], key='GET_MAN_ID')

        if self.read() > 0:
            msg = self.input_buffer
            self.p_man_id = msg.text.data[6]
            self.p_man_id |= msg.text.data[7] << 8
            return 0

        return -1

    def get_flash_dev_id(self):
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
        # La lettura del BL_STATUS non funziona bene ma la risposta restituisce correttamente lo stato del bootloader
        # nel byte 0 della risposta
        self.prep_read_cmd(cmd_list['GET_CHKSUM'], key='GET_CHKSUM')

        if self.read() > 0:
            msg = self.input_buffer
            byte_status = msg.text.data[0]
            self.bl_status = (byte_status & 0b00001000) >> 3
            return 0

        return -1

    def set_flash_addr(self, addr):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['SET_SECTADDR'])
        self.pmsg.text.set_data([int(addr & 0xFF),
                                 int((addr >> 8) & 0xFF),
                                 int((addr >> 16) & 0xFF),
                                 int((addr >> 24) & 0xFF)])

        return self.send_msg(ACK_REQUIRED=True)

    def flash_sector_erase(self):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['SECT_ERASE'])

        return self.send_msg(ACK_REQUIRED=True)

    def set_upload_size(self, data_len):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['SET_DNLDSIZE'])
        self.pmsg.text.set_data([data_len & 0xFF,
                                 (data_len >> 8) & 0xFF,
                                 (data_len >> 16) & 0xFF,
                                 (data_len >> 24) & 0xFF])

        return self.send_msg(ACK_REQUIRED=True)

    def upload_data(self, p_byte_array, data_len):
        self.pmsg = HidMessageStruct()

        send_size = HID_MESSAGE_MAX_SIZE - MSG_HEAD_SIZE - MSG_CMD_SIZE - 2
        # The last -2 is to workaround a bug in bootloader

        if data_len > send_size:
            data_len = send_size

        cmd_list['DNLD_DATA'][2] = data_len
        self.prep_write_cmd(cmd_list['DNLD_DATA'])
        self.pmsg.text.set_data(p_byte_array[:data_len])

        ret_val = self.send_msg(ACK_REQUIRED=False)
        if ret_val > 0:
            return data_len

        return -1

    def wait_for_flash_ready(self):
        self.bl_status = STAT_BIT_FLASH_BUSY
        while (self.bl_status & STAT_BIT_FLASH_BUSY) == STAT_BIT_FLASH_BUSY:
            self.get_bl_status()

    def set_flash_type(self, type):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['FLASH_TYPE'])
        self.pmsg.text.set_data([type])

        return self.send_msg(ACK_REQUIRED=True)

    def calculate_flash_checksum(self):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['CALC_CHKSUM'])

        if self.send_msg(ACK_REQUIRED=False) <= 0:
            return -1

        return 0

    def get_flash_checksum(self):
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
        self.pmsg = HidMessageStruct()

        self.standby = standby
        self.prep_write_cmd(cmd_list['POWER_CONTROL'])
        self.pmsg.text.set_data([int(standby)])

        return self.send_msg(ACK_REQUIRED=True)

    def get_power_mode(self):
        self.prep_read_cmd(cmd_list['POWER_CONTROL'], key='POWER_CONTROL')

        if self.read() > 0:
            msg = self.input_buffer

            if msg.text.data[0] and 0x03:
                self.standby = True
            else:
                self.standby = False
        else:
            return -1

        return 0

    def software_reset(self):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['SW_RESET'])

        return self.send_msg(ACK_REQUIRED=False)

    def get_num_images_in_flash(self):
        self.prep_read_cmd(cmd_list['NUM_IMAGE_IN_FLASH'], key='NUM_IMAGE_IN_FLASH')

        if self.read() > 0:
            msg = self.input_buffer
            num_images_in_flash = msg.text.data[0] & 0xFF

            return num_images_in_flash

        return -1

    def get_pattern_trigger_mode(self):
        self.prep_read_cmd(cmd_list['PAT_TRIG_MODE'], key='PAT_TRIG_MODE')

        if self.read() > 0:
            msg = self.input_buffer
            self.trig_mode = msg.text.data[0] & 0xFF
            return 0, self.trig_mode

        return -1, None

    def set_pattern_trigger_mode(self, mode):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['PAT_TRIG_MODE'])
        self.pmsg.text.set_data([int(mode)])

        return self.send_msg(ACK_REQUIRED=True)

    def set_pattern_display_mode(self, external):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['PAT_DISP_MODE'])
        if external:
            self.pmsg.text.set_data([0])
        else:
            self.pmsg.text.set_data([3])

        return self.send_msg(ACK_REQUIRED=True)

    def get_mode(self):
        self.prep_read_cmd(cmd_list['DISP_MODE'], key='DISP_MODE')

        if self.read() > 0:
            msg = self.input_buffer
            self.mode = msg.text.data[0] != 0
            return 0, self.mode

        return -1, None

    def set_mode(self, mode):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['DISP_MODE'])
        self.pmsg.text.set_data([int(mode)])

        return self.send_msg(ACK_REQUIRED=True)

    def get_pattern_display(self):
        self.prep_read_cmd(cmd_list['PAT_START_STOP'], key='PAT_START_STOP')

        if self.read() > 0:
            msg = self.input_buffer
            self.action = msg.text.data[0] & 0xFF
            return 0, self.action

        return -1, None

    def set_pattern_config(self, num_lut_entries, repeat, num_pat_for_trig_out2, num_splash_lut_entries):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['PAT_CONFIG'])
        self.pmsg.text.set_data([num_lut_entries - 1, repeat, num_pat_for_trig_out2 - 1, num_splash_lut_entries - 1])

        return self.send_msg(ACK_REQUIRED=True)

    def set_exposure_frame_period(self, exposure_period, frame_period):
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

        return self.send_msg(ACK_REQUIRED=True)

    def open_mailbox(self, m_box_num):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['MBOX_CONTROL'])
        self.pmsg.text.set_data([m_box_num])

        return self.send_msg(ACK_REQUIRED=True)

    def mailbox_set_addr(self, addr):
        self.pmsg = HidMessageStruct()

        if addr > 127:
            return -1

        self.prep_write_cmd(cmd_list['MBOX_ADDRESS'])
        self.pmsg.text.set_data([addr])

        return self.send_msg(ACK_REQUIRED=True)

    def close_mailbox(self):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['MBOX_CONTROL'])
        self.pmsg.text.set_data([0])

        return self.send_msg(ACK_REQUIRED=True)

    def send_pat_lut(self, g_pat_lut_index, g_pat_lut):
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
        self.send_msg(ACK_REQUIRED=True)

        self.close_mailbox()
        return 0

    def send_image_lut(self, lut_entries, num_entries):
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

        bytes_sent = self.send_msg(ACK_REQUIRED=True)

        self.close_mailbox()

        return bytes_sent

    def start_pat_lut_validate(self):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['LUT_VALID'])
        if self.send_msg(ACK_REQUIRED=True) < 0:
            return 1

        return 0

    def check_pat_lut_validate(self):
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
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['PAT_START_STOP'])
        self.pmsg.text.set_data([action & 0x03])

        return self.send_msg(ACK_REQUIRED=True)

    def get_led_currents(self):
        self.prep_read_cmd(cmd_list['LED_CURRENT'], key='LED_CURRENT')

        if self.read() > 0:
            msg = self.input_buffer
            self.red_led = msg.text.data[0]
            self.green_led = msg.text.data[1]
            self.blue_led = msg.text.data[2]

            return 0

        return -1

    def set_led_currents(self, red_current, green_current, blue_current):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['LED_CURRENT'])
        self.pmsg.text.set_data([red_current, green_current, blue_current])

        return self.send_msg(ACK_REQUIRED=True)

    def set_led_enables(self, seq_ctrl, red, green, blue):
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

        return self.send_msg(ACK_REQUIRED=True)

    def set_led_pwm_invert(self, invert):
        self.pmsg = HidMessageStruct()

        self.prep_write_cmd(cmd_list['PWM_INVERT'])
        self.pmsg.text.set_data([invert])

        return self.send_msg(ACK_REQUIRED=True)




