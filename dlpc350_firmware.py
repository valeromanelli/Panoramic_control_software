"""DLPC350 firmware parsing, splash-image handling, and image rebuilding."""

import ctypes
import struct
from dataclasses import dataclass
import numpy as np
import firmware_commands


FLASH_NUM_APP_ADDRS = 4
FLASH_NUM_ASIC_CFG_ADDRS = 4
FLASH_NUM_SEQ_ADDRS = 4
FLASH_NUM_APPL_CFG_ADDRS = 4
FLASH_NUM_OSD_ADDRS = 4
FLASH_NUM_SPLASH_ADDRS = 4
FLASH_NUM_OTHER_ADDRS = 4
FLASH_NUM_SPLASH2_ADDRS = 12
FLASH_NUM_BATCHFILES = 16
FLASH_MAX_APPS = 4
FLASH_THREE_ADDRESS = 0xFB000000
FLASH_TWO_ADDRESS = 0xFA000000
FLASH_BASE_ADDRESS = 0xF9000000


@dataclass()
class IniParamInfo:
    """Description of one editable firmware configuration token."""
    token: str
    default_param: list[int]
    gui_defined_param: list[int]
    nr_default_params: int
    nr_user_defined_params: int
    is_gui_editable: bool
    frmw_offset: int
    frmw_size: int


g_iniParam_Info = [
    IniParamInfo("DEFAULT.FIRMWARE_TAG", [0x44, 0x4C, 0x50], [0x00], 3, 1, True, 0, 32),
    IniParamInfo("DEFAULT.LED_ENABLE_MAN_MODE", [0x00], [0x00], 1, 1, True, 29616, 1),
    IniParamInfo("MACHINE_DATA.COLORPROFILE_0_BRILLIANTCOLORLOOK", [0x00], [0x00], 1, 1, True, 29752, 1),
]


BMP_FILE_HEADER_SIZE = 14
class BITMAPINFOHEADER(ctypes.Structure):
    """ctypes representation of the Windows BITMAPINFOHEADER structure."""
    _fields_ = [
        ("biSize", ctypes.c_ulong),          # DWORD
        ("biWidth", ctypes.c_long),          # LONG
        ("biHeight", ctypes.c_long),         # LONG
        ("biPlanes", ctypes.c_ushort),       # WORD
        ("biBitCount", ctypes.c_ushort),     # WORD
        ("biCompression", ctypes.c_ulong),   # DWORD
        ("biSizeImage", ctypes.c_ulong),     # DWORD
        ("biXPelsPerMeter", ctypes.c_long),  # LONG
        ("biYPelsPerMeter", ctypes.c_long),  # LONG
        ("biClrUsed", ctypes.c_ulong),       # DWORD
        ("biClrImportant", ctypes.c_ulong)   # DWORD
    ]


class SPLASH_BLOB_INFO:
    """Offset and size of one splash-image blob."""
    def __init__(self):
        self.blob_offset = 0
        self.blob_size = 0

    def to_bytes(self):
        return struct.pack('<II', self.blob_offset, self.blob_size)


class SPLASH_HEADER:
    """Serializable header for one DLPC350 splash image."""
    def __init__(self):
        self.signature = 0
        self.image_width = 0
        self.image_height = 0
        self.byte_count = 0
        self.subimg_offset = 0
        self.subimg_end = 0
        self.bg_color = 0
        self.pixel_format = 0
        self.compression = 0
        self.byte_order = 0
        self.chroma_order = 0
        self.pad1 = 0
        self.pad2 = 0
        self.pad3 = 0
        self.pad4 = 0

    def serialize_splash_header(self) -> bytes:
        # Costruisce la sequenza di byte in ordine
        return (
                self.signature.to_bytes(4, 'little') +
                self.image_width.to_bytes(2, 'little') +
                self.image_height.to_bytes(2, 'little') +
                self.byte_count.to_bytes(4, 'little') +
                self.subimg_offset.to_bytes(4, 'little', signed=True) +
                self.subimg_end.to_bytes(4, 'little', signed=True) +
                self.bg_color.to_bytes(4, 'little') +
                self.pixel_format.to_bytes(1, 'little') +
                self.compression.to_bytes(1, 'little') +
                self.byte_order.to_bytes(1, 'little') +
                self.chroma_order.to_bytes(1, 'little') +
                self.pad1.to_bytes(1, 'little') +
                self.pad2.to_bytes(1, 'little') +
                self.pad3.to_bytes(1, 'little') +
                self.pad4.to_bytes(1, 'little')
        )


class SPLASH_SUPER_BINARY_INFO:
    """Header for a collection of splash-image blobs."""
    def __init__(self):
        self.sig1 = 0
        self.sig2 = 0
        self.blob_count = 0

    def to_bytes(self):
        return struct.pack('<III', self.sig1, self.sig2, self.blob_count)


class FLASH_BLOCK:
    """Address and byte count of one flash-memory block."""
    def __init__(self):
        self.address = 0
        self.byte_count = 0


class FLASH_TABLE:
    """Parsed DLPC350 flash table."""
    def __init__(self):
        self.signature = 0
        self.boot_address = 0
        self.version = 0
        self.free_area_start = 0
        self.app_code = [FLASH_BLOCK() for _ in range(FLASH_NUM_APP_ADDRS)]
        self.asic_config_data = [FLASH_BLOCK() for _ in range(FLASH_NUM_ASIC_CFG_ADDRS)]
        self.sequence = [FLASH_BLOCK() for _ in range(FLASH_NUM_SEQ_ADDRS)]
        self.appl_config_data = [FLASH_BLOCK() for _ in range(FLASH_NUM_APPL_CFG_ADDRS)]
        self.osd_data = [FLASH_BLOCK() for _ in range(FLASH_NUM_OSD_ADDRS)]
        self.splash_data = [FLASH_BLOCK() for _ in range(FLASH_NUM_SPLASH_ADDRS)]
        self.appl_other_binary = [FLASH_BLOCK() for _ in range(FLASH_NUM_OTHER_ADDRS)]
        self.splash_data2 = [FLASH_BLOCK() for _ in range(FLASH_NUM_SPLASH2_ADDRS)]
        self.batch_files = [FLASH_BLOCK() for _ in range(FLASH_NUM_BATCHFILES)]

    @staticmethod
    def from_bytes(data):
        flash_table = FLASH_TABLE()
        flash_table.signature = int.from_bytes(data[0:4], byteorder='little')
        flash_table.boot_address = int.from_bytes(data[4:8], byteorder='little')
        flash_table.version = int.from_bytes(data[8:12], byteorder='little')
        flash_table.free_area_start = int.from_bytes(data[12:16], byteorder='little')
        for i in range(FLASH_NUM_APP_ADDRS):
            flash_table.app_code[i].address = int.from_bytes(data[16 + i * 8:20 + i * 8], byteorder='little')
            flash_table.app_code[i].byte_count = int.from_bytes(data[20 + i * 8:24 + i * 8], byteorder='little')
        for i in range(FLASH_NUM_ASIC_CFG_ADDRS):
            flash_table.asic_config_data[i].address = int.from_bytes(data[48 + i * 8:52 + i * 8], byteorder='little')
            flash_table.asic_config_data[i].byte_count = int.from_bytes(data[52 + i * 8:56 + i * 8], byteorder='little')
        for i in range(FLASH_NUM_SEQ_ADDRS):
            flash_table.sequence[i].address = int.from_bytes(data[80 + i * 8:84 + i * 8], byteorder='little')
            flash_table.sequence[i].byte_count = int.from_bytes(data[84 + i * 8:88 + i * 8], byteorder='little')
        for i in range(FLASH_NUM_APPL_CFG_ADDRS):
            flash_table.appl_config_data[i].address = int.from_bytes(data[112 + i * 8:116 + i * 8], byteorder='little')
            flash_table.appl_config_data[i].byte_count = int.from_bytes(data[116 + i * 8:120 + i * 8], byteorder='little')
        for i in range(FLASH_NUM_OSD_ADDRS):
            flash_table.osd_data[i].address = int.from_bytes(data[144 + i * 8:148 + i * 8], byteorder='little')
            flash_table.osd_data[i].byte_count = int.from_bytes(data[148 + i * 8:152 + i * 8], byteorder='little')
        for i in range(FLASH_NUM_SPLASH_ADDRS):
            flash_table.splash_data[i].address = int.from_bytes(data[176 + i * 8:180 + i * 8], byteorder='little')
            flash_table.splash_data[i].byte_count = int.from_bytes(data[180 + i * 8:184 + i * 8], byteorder='little')
        for i in range(FLASH_NUM_OTHER_ADDRS):
            flash_table.appl_other_binary[i].address = int.from_bytes(data[208 + i * 8:212 + i * 8], byteorder='little')
            flash_table.appl_other_binary[i].byte_count = int.from_bytes(data[212 + i * 8:216 + i * 8], byteorder='little')
        for i in range(FLASH_NUM_SPLASH2_ADDRS):
            flash_table.splash_data2[i].address = int.from_bytes(data[240 + i * 8:244 + i * 8], byteorder='little')
            flash_table.splash_data2[i].byte_count = int.from_bytes(data[244 + i * 8:248 + i * 8], byteorder='little')
        for i in range(FLASH_NUM_BATCHFILES):
            flash_table.batch_files[i].address = int.from_bytes(data[336 + i * 8:340 + i * 8], byteorder='little')
            flash_table.batch_files[i].byte_count = int.from_bytes(data[340 + i * 8:344 + i * 8], byteorder='little')
        return flash_table


class Dlpc350_firmware:
    """Parse, modify, and rebuild a DLPC350 firmware image."""
    def __init__(self):
        # Errors
        self.ERROR_NO_MEM_FOR_MALLOC = -1
        self.ERROR_FRMW_FLASH_TABLE_SIGN_MISMATCH = -2
        self.ERROR_NO_SPLASH_IMAGE = -3
        self.ERROR_NO_BMP_FILE = -4
        self.ERROR_NOT_24bit_BMP_FILE = -5
        self.ERROR_INIT_NOT_DONE_PROPERLY = -6
        self.ERROR_WRONG_PARAMS = -7
        self.ERROR_NO_SPACE_IN_FRMW = -8

        # Variables
        self.flash_table = FLASH_TABLE()
        self.FLASH_TABLE_ADDRESS = 0x00020000
        self.FLASH_TABLE_APP_SIGNATURE = 0x01234567
        self.FLASH_BASE_ADDRESS = 0xF9000000
        self.SPLASH_4LINE_COMPRESSION = 4
        self.SPLASH_RLE_COMPRESSION = 1
        self.SPLASH_UNCOMPRESSED = 0
        self.SPLASH_NOCOMP_SPECIFIED = 5
        self.p_frmw_image_array = None
        self.splash_data_start_flash_address = 0
        self.appl_config_data_flash_address = None
        self.p_image_buffer = None
        self.spl_buffer = None
        self.splash_index = 0
        self.splash_count = 0
        self.chip_select_size = [0x00000000, 0x01000000, 0x01000000]
        self.chip_select_end = [0xFC000000, 0xFA000000, 0xFB000000]
        self.chip_select_base = [0xFB000000, 0xF9000000, 0xFA000000]

    def _get_flash_table(self, address):
        start_index = address
        end_index = address + 472
        flash_table_data = self.p_frmw_image_array[start_index:end_index]
        return FLASH_TABLE.from_bytes(flash_table_data)

    def splash_init_buffer(self, num_splash):
        binary_info = SPLASH_SUPER_BINARY_INFO()
        blob_info = SPLASH_BLOB_INFO()

        if num_splash > firmware_commands.MAX_SPLASH_IMAGES:
            return -1

        if self.spl_buffer is not None:
            self.spl_buffer = None

        self.splash_index = 0
        self.splash_count = 0

        binary_info.sig1 = 0x12345678
        binary_info.sig2 = 0x87654321
        binary_info.blob_count = num_splash

        blob_info.blob_offset = 0xFFFFFFFF
        blob_info.blob_size = 0xFFFFFFFF

        binary_bytes = binary_info.to_bytes()
        blob_bytes = blob_info.to_bytes()
        total_size = len(binary_bytes) + len(blob_bytes) * firmware_commands.MAX_SPLASH_IMAGES
        self.spl_buffer = bytearray(total_size)
        self.spl_buffer[self.splash_index:self.splash_index + len(binary_bytes)] = binary_bytes

        self.splash_index += len(binary_bytes)

        for _ in range(firmware_commands.MAX_SPLASH_IMAGES):
            self.spl_buffer[self.splash_index:self.splash_index + len(blob_bytes)] = blob_bytes
            self.splash_index += len(blob_bytes)

        return 0

    def splash_add_splash(self, p_image_buffer, compression):
        if not self.spl_buffer or self.splash_data_start_flash_address is None:
            return self.ERROR_INIT_NOT_DONE_PROPERLY, None, None, None

        bf_type, bf_size = struct.unpack_from('<HI', p_image_buffer, 0)
        bf_off_bits = struct.unpack_from('<I', p_image_buffer, 10)[0]

        header_fmt = '<IIIHHIIIIII'
        header_info = struct.unpack_from(header_fmt, p_image_buffer, 14)
        bi_width = header_info[1]
        bi_height = header_info[2]
        bi_bit_count = header_info[4]

        if bf_type != 0x4D42:
            return self.ERROR_NO_BMP_FILE, None, None, None
        if bi_bit_count != 24:
            return self.ERROR_NOT_24bit_BMP_FILE, None, None, None

        bit_map_image = bytearray(p_image_buffer[bf_off_bits:bf_size])
        bytes_per_pixel = bi_bit_count // 8
        line_length = bi_width * bytes_per_pixel
        if line_length % 4 != 0:
            line_length = (line_length // 4 + 1) * 4

        image_array = np.frombuffer(bit_map_image, dtype=np.uint8)
        image_array = image_array.reshape((bi_height, bi_width, bytes_per_pixel))
        image_array = np.flipud(image_array)
        image_array = image_array[:, :, ::-1]
        bit_map_image[:] = image_array.tobytes()

        rle_buffer_size = ((bi_height * bi_width * bytes_per_pixel) +
                           ((bi_height * bi_width * 4) // 255) +
                           (bi_width * 2) + 15) - 1
        rle_buffer = bytearray(rle_buffer_size)

        if compression == 0:
            splash_size = bi_height * line_length
            splash_image = bit_map_image
        elif compression == 1:
            _, _, splash_image, splash_size = firmware_commands.splash_perform_rle_compression(bit_map_image, rle_buffer, bi_width, bi_height)
        elif compression == 4:
            splash_size = 4 * line_length
            splash_image = bit_map_image
        else:
            _, bit_map_image, line_comp_size = firmware_commands.splash_perform_line_compression(bit_map_image, bi_width, bi_height, 4)
            _, bit_map_image, splash_image_rle, rle_comp_size = firmware_commands.splash_perform_rle_compression(bit_map_image, rle_buffer, bi_width, bi_height)

            splash_size = bi_height * line_length
            splash_image = bit_map_image
            compression = 0
            if line_comp_size < splash_size:
                splash_size = 4 * line_length
                compression = 4
            elif rle_comp_size < splash_size:
                splash_size = rle_comp_size
                splash_image = splash_image_rle
                compression = 1

        splash_header = SPLASH_HEADER()
        splash_header.signature = 0x636C7053
        splash_header.image_width = bi_width & 0xFFFF
        splash_header.image_height = bi_height & 0xFFFF
        splash_header.pixel_format = 1
        splash_header.subimg_offset = -1
        splash_header.subimg_end = -1
        splash_header.bg_color = 0
        splash_header.byte_order = 1
        splash_header.chroma_order = 0
        splash_header.byte_count = splash_size
        splash_header.compression = compression
        splash_header_bytes = splash_header.serialize_splash_header()

        flash_end = None
        if self.chip_select_size[0]:
            flash_end = FLASH_THREE_ADDRESS + self.chip_select_size[0]
        elif self.chip_select_size[2]:
            flash_end = FLASH_TWO_ADDRESS + self.chip_select_size[2]
        elif self.chip_select_size[1]:
            flash_end = FLASH_BASE_ADDRESS + self.chip_select_size[1]

        self.chip_select_end[0] = FLASH_THREE_ADDRESS + self.chip_select_size[0]
        self.chip_select_end[1] = FLASH_BASE_ADDRESS + self.chip_select_size[1]
        self.chip_select_end[2] = FLASH_TWO_ADDRESS + self.chip_select_size[2]

        if self.splash_index + self.splash_data_start_flash_address + len(splash_header_bytes) + splash_size < flash_end:
            next_chip_select = -1
            if self.splash_index + self.splash_data_start_flash_address < self.chip_select_end[1] and \
                    self.splash_index + self.splash_data_start_flash_address + len(splash_header_bytes) + splash_size > self.chip_select_end[1] and \
                    self.chip_select_size[1] != 0x01000000:
                curr_chip_select = 1
                if self.chip_select_size[2] != 0:
                    next_chip_select = 2
                elif self.chip_select_size[0] != 0:
                    next_chip_select = 0

            if self.splash_index + self.splash_data_start_flash_address < self.chip_select_end[2] and \
                    self.splash_index + self.splash_data_start_flash_address + len(splash_header_bytes) + splash_size > self.chip_select_end[2]:
                curr_chip_select = 2
                next_chip_select = 0

            if next_chip_select != -1:
                self.spl_buffer.extend([0xFF] * (self.chip_select_base[next_chip_select] - self.splash_data_start_flash_address - self.splash_index))
                self.splash_index = self.chip_select_base[next_chip_select] - self.splash_data_start_flash_address

            blob_info_offset = 12 + self.splash_count * 8
            blob_offset = self.splash_index + self.splash_data_start_flash_address
            blob_info_address = self.splash_index + self.splash_data_start_flash_address
            blob_info_size = len(splash_header_bytes) + splash_size

            if blob_info_address >= FLASH_THREE_ADDRESS:
                blob_info_address -= 0x03000000

            self.spl_buffer[blob_info_offset:blob_info_offset + 4] = struct.pack('<I', blob_offset)
            self.spl_buffer[blob_info_offset + 4:blob_info_offset + 8] = struct.pack('<I', blob_info_size)

            self.spl_buffer[self.splash_index:self.splash_index + len(splash_header_bytes)] = splash_header_bytes
            self.splash_index += len(splash_header_bytes)

            self.spl_buffer[self.splash_index:self.splash_index + splash_size] = splash_image[:splash_size]
            self.splash_index += splash_size

            self.splash_count += 1
            comp_size = splash_size

            return 0, compression, comp_size

        else:
            self.splash_count += 1
            return self.ERROR_NO_SPACE_IN_FRMW, None, None, None

    def frmw_get_new_flash_image(self):
        new_frm_file_in_len = self.splash_data_start_flash_address - FLASH_BASE_ADDRESS + self.splash_index

        offset = self.splash_data_start_flash_address - FLASH_BASE_ADDRESS
        self.p_frmw_image_array[offset:offset + self.splash_index] = self.spl_buffer[:self.splash_index]

        return self.p_frmw_image_array, new_frm_file_in_len

    def write_appl_config_data(self, app_data, token, params, num_params):
        to_upper_token = token.upper()
        for index, entry in enumerate(g_iniParam_Info):
            if entry.token.upper() == token.upper():
                break
        else:
            return self.ERROR_WRONG_PARAMS, None
        offset = g_iniParam_Info[index].frmw_offset

        if to_upper_token == "DEFAULT.FIRMWARE_TAG":
            if num_params > 32:
                return self.ERROR_WRONG_PARAMS, None

            i = 0
            while i < num_params:
                app_data[offset] = params[i]
                offset += 1
                i += 1

        else:
            if num_params > 1:
                return self.ERROR_WRONG_PARAMS, None

            value = params[0]

            app_data[offset] = value

        return 0, app_data

    def frmw_copy_and_verify_image(self, byte_array, size):
        if self.p_frmw_image_array is not None:
            self.p_frmw_image_array = None
            self.splash_data_start_flash_address = 0
            self.appl_config_data_flash_address = 0

        self.p_frmw_image_array = byte_array[:size]

        flash_table = self._get_flash_table(self.FLASH_TABLE_ADDRESS)
        if flash_table.signature != self.FLASH_TABLE_APP_SIGNATURE:
            self.FLASH_TABLE_ADDRESS = 0x00008000
            flash_table = self._get_flash_table(self.FLASH_TABLE_ADDRESS)
            if flash_table.signature != self.FLASH_TABLE_APP_SIGNATURE:
                self.FLASH_TABLE_ADDRESS = 0x00020000
                flash_table = self._get_flash_table(self.FLASH_TABLE_ADDRESS)
                if flash_table.signature != self.FLASH_TABLE_APP_SIGNATURE:
                    return self.ERROR_FRMW_FLASH_TABLE_SIGN_MISMATCH

        self.splash_data_start_flash_address = flash_table.splash_data[0].address
        self.appl_config_data_flash_address = flash_table.appl_config_data[0].address

        return 0

    def frmw_get_version_number(self):
        if self.appl_config_data_flash_address is None:
            return self.ERROR_INIT_NOT_DONE_PROPERLY

        version_number_bytes = self.p_frmw_image_array[(self.appl_config_data_flash_address - self.FLASH_BASE_ADDRESS):
                                                 (self.appl_config_data_flash_address - self.FLASH_BASE_ADDRESS + 4)]
        version_number = int.from_bytes(version_number_bytes, byteorder='little')

        return version_number

    def frmw_get_splash_count(self):
        splash_data_start_address = self.splash_data_start_flash_address - self.FLASH_BASE_ADDRESS
        binary_info = SPLASH_SUPER_BINARY_INFO()

        binary_info_data = self.p_frmw_image_array[splash_data_start_address:splash_data_start_address + 12]
        binary_info.sig1, binary_info.sig2, binary_info.blob_count = struct.unpack('<III', binary_info_data)

        if binary_info.sig1 == 0x12345678 and binary_info.sig2 == 0x87654321:
            return binary_info.blob_count
        else:
            return -1

    def frmw_get_splash_image(self, index):
        blob_info = SPLASH_BLOB_INFO()
        splash_header = SPLASH_HEADER()

        splash_data_start_address = self.splash_data_start_flash_address - self.FLASH_BASE_ADDRESS
        blob_address = splash_data_start_address + 12 + index * 8
        blob_info_data = self.p_frmw_image_array[blob_address:blob_address + 8]
        blob_info.blob_offset, blob_info.blob_size = struct.unpack('<II', blob_info_data)

        if blob_info.blob_offset == 0xffffffff:
            return self.ERROR_NO_SPLASH_IMAGE
        if blob_info.blob_offset < self.FLASH_BASE_ADDRESS:
            blob_info.blob_offset += 0x03000000

        splash_image_address = blob_info.blob_offset - self.FLASH_BASE_ADDRESS
        splash_header_data = self.p_frmw_image_array[splash_image_address:splash_image_address + 32]
        (splash_header.signature, splash_header.image_width, splash_header.image_height, splash_header.byte_count,
         splash_header.subimg_offset, splash_header.subimg_end, splash_header.bg_color, splash_header.pixel_format,
         splash_header.compression, splash_header.byte_order, splash_header.chroma_order, splash_header.pad1,
         splash_header.pad2, splash_header.pad3, splash_header.pad4) = struct.unpack('<IHHIIIIBBBBBBBB', splash_header_data)

        splash_image_address += 32

        splash_image_size = blob_info.blob_size - 32

        if splash_header.compression == self.SPLASH_4LINE_COMPRESSION:
            four_line_buffer = self.p_frmw_image_array[splash_image_address:splash_image_address + splash_image_size]

            image_buffer = bytearray(splash_header.image_width * splash_header.image_height * 3)

            for i in range(0, splash_header.image_height, 4):
                image_buffer[splash_header.image_width * 3 * i: splash_header.image_width * 3 * (i + 4)] = four_line_buffer[:splash_image_size]

            splash_image_size = splash_header.image_width * splash_header.image_height * 3

        elif splash_header.compression == self.SPLASH_RLE_COMPRESSION:
            #image_buffer = bytearray(splash_header.image_width * splash_header.image_height * 3)
            image_buffer = bytearray([])

            rle_buffer = self.p_frmw_image_array[splash_image_address:splash_image_address + splash_image_size]

            _, splash_image_size, image_buffer = firmware_commands.splash_perform_rle_uncompression(rle_buffer, image_buffer, splash_image_size)

        elif splash_header.compression == self.SPLASH_UNCOMPRESSED:
            image_buffer = self.p_frmw_image_array[splash_image_address:splash_image_address + splash_image_size]

        line_length = splash_header.image_width * 3
        line_data = bytearray(line_length)
        for i in range(splash_header.image_height):
            line_data[:] = image_buffer[(line_length * i):(line_length * (i + 1))]
            for j in range(splash_header.image_width):
                temp_byte = line_data[j * 3 + 2]
                line_data[j * 3 + 2] = line_data[j * 3 + 1]
                line_data[j * 3 + 1] = temp_byte
            image_buffer[(line_length * i):(line_length * (i + 1))] = line_data

        self.p_image_buffer = image_buffer[:splash_image_size]

        return 0
