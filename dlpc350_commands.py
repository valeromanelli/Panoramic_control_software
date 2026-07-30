"""High-level convenience commands for the DLPC350/LightCrafter controller."""

from procrafter4500 import connect_usb
import time


start_sector = 0
temp_chksum = 0
is_cache_file_exist = False
bl_size = 128 * 1024  # Used when bootloader programming is skipped.

# Firmware signature and address constants.
FLASH_BASE_ADDRESS = 0xF9000000
MAX_NUM_RETRIES = 5


class DMD:
    """In-memory representation of a DLPC350 pattern lookup table."""
    def __init__(self):
        self.g_pat_lut = []
        self.g_pat_lut_index = 0

    def clear_pat_lut(self):
        self.g_pat_lut = []
        self.g_pat_lut_index = 0
        return 0

    def add_pat_to_lut(self, trig_type, pat_num, led_select, buf_swap, bit_depth=1):
        lut_word = trig_type & 3

        if pat_num > 24:
            return -1

        lut_word |= ((pat_num & 0x3F) << 2)
        lut_word |= ((bit_depth & 0xF) << 8)
        lut_word |= ((led_select & 0x7) << 12)

        if buf_swap:
            lut_word |= 0x00040000

        self.g_pat_lut.append(lut_word)
        self.g_pat_lut_index += 1

        return 0

def process_flash_params_line(line, fd):
    """Parse one flash-parameter line into a FlashDevice object."""
    line = line.strip()
    if line.startswith('/'):
        return False
    if not line:
        return False

    try:
        mfg_id = line.split(',')[1].strip()
        dev_id = line.split(',')[3].strip()
    except (IndexError, ValueError):
        return False

    if mfg_id == fd.mfg_id and dev_id == fd.dev_id:
        fd.mfg_id = line.split(',')[1].strip()
        fd.dev_id = line.split(',')[3].strip()

        try:
            fd.size_mbit = int(line.split(',')[4].strip(), 0)
            fd.type = int(line.split(',')[5].strip(), 0)
            fd.num_sectors = int(line.split(',')[7].strip(), 0)
        except ValueError:
            return False

        for i in range(fd.num_sectors):
            try:
                sector_value = int(line.split(',')[8 + i].strip(), 0)
                fd.sector_arr.append(sector_value)
            except ValueError:
                return False

        return True

    return False


def get_sector_num(addr, fd):
    """Return the flash sector containing the requested address."""
    i = 0
    while i < fd.num_sectors:
        if fd.sector_arr[i] > addr:
            break
        i += 1

    return 0 if i == 0 else i - 1


def get_num_images_in_flash():
    """Read the number of images stored in DMD flash memory."""
    with connect_usb() as lcr:
        return lcr.get_num_images_in_flash()


def set_dlpc350_in_pattern_mode():
    """Switch the controller to pattern display mode."""
    i = 0
    with connect_usb() as lcr:
        _, mode = lcr.get_mode()
        if mode == 0:
            lcr.set_mode(1)
            time.sleep(0.1)
            while True:
                _, mode = lcr.get_mode()
                if mode == 1:
                    break
                time.sleep(0.1)
                i += 1
                if i > MAX_NUM_RETRIES:
                    break

        else:
            _, pat_mode = lcr.get_pattern_display()
            """if pat_mode != 0:
                stop_sequence_button_clicked().emit()"""

    return


def set_pattern_trigger_mode(mode):
    """Set the DLPC350 pattern trigger mode."""
    with connect_usb() as lcr:
        return lcr.set_pattern_trigger_mode(mode)


def set_power_mode(mode):
    """Set the DLPC350 standby state."""
    with connect_usb() as lcr:
        return lcr.set_power_mode(mode)


def get_pattern_trigger_mode():
    """Read the current pattern trigger mode."""
    with connect_usb() as lcr:
        return lcr.get_pattern_trigger_mode()


def set_pattern_display_mode(mode):
    """Select internal or external pattern display mode."""
    with connect_usb() as lcr:
        lcr.set_pattern_display_mode(mode)


def set_pattern_config(num_lut_entries, repeat, num_patterns, num_splash_lut_entries):
    """Configure pattern and splash-image lookup table lengths."""
    with connect_usb() as lcr:
        return lcr.set_pattern_config(num_lut_entries, repeat, num_patterns, num_splash_lut_entries)


def set_exposure_frame_period(exposure_time, frame_period):
    """Set pattern exposure and frame period in microseconds."""
    with connect_usb() as lcr:
        return lcr.set_exposure_frame_period(exposure_time, frame_period)


def send_pat_lut(g_pat_lut_index, g_pat_lut):
    """Upload the pattern lookup table."""
    with connect_usb() as lcr:
        return lcr.send_pat_lut(g_pat_lut_index, g_pat_lut)


def send_image_lut(lut_entries, num_entries):
    """Upload the splash-image lookup table."""
    with connect_usb() as lcr:
        return lcr.send_image_lut(lut_entries, num_entries)


def start_pat_lut_validate():
    """Start lookup-table validation."""
    with connect_usb() as lcr:
        return lcr.start_pat_lut_validate()


def check_pat_lut_validate():
    """Read the lookup-table validation result."""
    with connect_usb() as lcr:
        return lcr.check_pat_lut_validate()


def pattern_display(action):
    """Start, pause, or stop pattern display."""
    with connect_usb() as lcr:
        lcr.pattern_display(action)


def pause_display():
    """Pause pattern display and verify the resulting state."""
    i = 0
    with connect_usb() as lcr:
        lcr.pattern_display(1)

        time.sleep(0.1)
        while True:
            _, pat_mode = lcr.get_pattern_display()
            if pat_mode == 1:
                break
            else:
                lcr.pattern_display(1)
            time.sleep(0.1)
            if i > MAX_NUM_RETRIES:
                break
            i += 1


def stop_display():
    """Stop pattern display and verify the resulting state."""
    i = 0
    with connect_usb() as lcr:
        lcr.pattern_display(0)

        time.sleep(0.1)
        while True:
            _, pat_mode = lcr.get_pattern_display()
            if pat_mode == 0:
                break
            else:
                lcr.pattern_display(0)
            time.sleep(0.1)
            if i > MAX_NUM_RETRIES:
                break
            i += 1


def get_led_currents():
    """Read LED current values from the controller."""
    with connect_usb() as lcr:
        lcr.get_led_currents()
        return 255-lcr.red_led, lcr.green_led, 255-lcr.blue_led


def set_led_configuration(red_current, green_current, blue_current):
    """Set LED currents and controller-enable flags."""
    with connect_usb() as lcr:
        lcr.set_led_enables(True, False, False, False)

        lcr.set_led_pwm_invert(0)

        red_current = 255 - int(red_current)
        blue_current = 255 - int(blue_current)

        lcr.set_led_currents(red_current, green_current, blue_current)

