"""Firmware image extraction and splash-image compression helpers."""

import numpy as np
from PyQt6.QtCore import QFile, QIODevice
import dlpc350_firmware as fw
import dlpc350_bmpparser as bmp


RELEASE_FW_VERSION = 0x030000
PTN_WIDTH = 912
PTN_HEIGHT = 1140
BYTES_PER_PIXEL = 3
MAX_SPLASH_IMAGES = 256

m_added_splash_images = [None for _ in range(MAX_SPLASH_IMAGES)]
m_splash_image_add_index = 0
m_splash_image_count = 0
m_splash_image_added = 0
m_splash_image_removed = 0


def my_file_write(param, data, size):
    """Write bytes, or seek when ``data`` is ``None``.

    Returns 0 on success and -1 when the callback cannot complete the request.
    """
    try:
        # A null data pointer represents a seek request in the original API.
        if data is None:
            param.seek(size)
        else:
            # Write exactly the requested number of bytes.
            if size > 0:
                written_bytes = param.write(data[:size])
                if written_bytes < size:
                    # Treat partial writes as an error.
                    return -1
        return 0
    except Exception as e:
        print(f"Firmware write/seek error: {e}")
        return -1


def my_image_get(param, X, Y, pix, count, buffer):
    """Copy one horizontal pixel span from an RGB image buffer."""
    if param is None:
        param = None

    if X >= PTN_WIDTH or Y >= PTN_HEIGHT:
        return 0, None
    if X + count > PTN_WIDTH:
        count = PTN_WIDTH - X
    pix[:] = buffer[(X + Y * PTN_WIDTH) * BYTES_PER_PIXEL: (X + Y * PTN_WIDTH + count) * BYTES_PER_PIXEL]

    return 0, pix


def obtain_images_loaded(file):
    """Parse firmware and export its splash images as temporary BMP files."""
    ret = 0
    with open(file, 'rb') as f:
        for i in range(MAX_SPLASH_IMAGES):
            m_added_splash_images[i] = None
        p_byte_array = f.read()
        len_data = len(p_byte_array)

        firmware = fw.Dlpc350_firmware()

        ret = firmware.frmw_copy_and_verify_image(p_byte_array, len_data)
        if ret == -2:
            return ret, None, None, None, None
        elif ret == -1:
            return ret, None, None, None, None

        p_byte_array = None
        if firmware.frmw_get_version_number() & 0xFFFFFF < RELEASE_FW_VERSION:
            ret = -3

        splash_count = firmware.frmw_get_splash_count()
        actual_splash_count = splash_count

        if splash_count < 0:
            ret = -4
        else:
            for i in range(splash_count):
                file_name = f"pattern_to_show/temp_{i}.bmp"
                out_file = QFile(file_name)
                if out_file.open(QIODevice.OpenModeFlag.ReadWrite):
                    splash_image = bmp.bmp_image_t()

                    ret = firmware.frmw_get_splash_image(i)
                    g_pimage_buffer = firmware.p_image_buffer

                    if ret != 0:
                        out_file.close()
                        if ret == -3:
                            actual_splash_count -= 1
                            continue
                        else:
                            continue

                    _, splash_image = bmp.bmp_init_image(splash_image, PTN_WIDTH, PTN_HEIGHT, 8 * BYTES_PER_PIXEL)
                    _, splash_image, out_file = bmp.bmp_store_image(splash_image, my_file_write, out_file, my_image_get, g_pimage_buffer)
                    out_file.close()
                    m_added_splash_images[i] = out_file.fileName()

                else:
                    ret = -5

            m_splash_image_add_index = actual_splash_count
            m_splash_image_count = actual_splash_count

    return ret, firmware, m_added_splash_images, m_splash_image_add_index, m_splash_image_count


def splash_perform_line_compression(source_addr, image_width, image_height, num_lines):
    """Check whether repeated image lines support line compression."""
    bytes_per_pixel = 3
    line_length = image_width * bytes_per_pixel

    if line_length % 4 != 0:
        line_length = (line_length // 4 + 1) * 4

    if num_lines > 8:
        return 1, source_addr, 0xFFFF

    image_height = (image_height // num_lines) * num_lines
    source_array = np.frombuffer(source_addr, dtype=np.uint8, count=image_height * line_length)

    # Reshape in (rows, bytes_per_row)
    image_2d = source_array.reshape((image_height, line_length))

    # Confronta blocchi verticali
    for i in range(0, image_height - num_lines):
        if not np.array_equal(image_2d[i], image_2d[i + num_lines]):
            return 1, source_addr, 0xFFFFFFFF

    compressed_size = num_lines * line_length
    return 0, source_addr, compressed_size


def splash_perform_rle_compression(source_addr, destination_addr, image_width, image_height):
    """Compress a 24-bit splash image using the DLPC350 RLE format."""
    first_pixel = True
    repeat = 1
    pixel = 0
    last_color = 0
    count = 0
    pixel_size = 3

    S = 0
    D = 0

    for row in range(image_height):
        for col in range(image_width):
            pixel = source_addr[S:S + pixel_size]
            S += pixel_size

            if first_pixel:
                last_color = pixel
                repeat = 1
                first_pixel = False
                count = 0
            else:
                if pixel == last_color:
                    if count:
                        if count > 1:
                            destination_addr[D] = 0
                            D += 1
                        destination_addr[D] = count
                        D += 1
                        destination_addr[D:D + count * pixel_size] = source_addr[S - ((count + 2) + pixel_size):S - (
                                    (count + 2) * pixel_size) + count * pixel_size]
                        D += (count * pixel_size)
                        count = 0

                    repeat += 1
                    if repeat == 255:
                        destination_addr[D] = repeat
                        D += 1
                        destination_addr[D:D + pixel_size] = last_color
                        D += pixel_size
                        first_pixel = True

                else:
                    if repeat == 1:
                        count += 1
                        if count == 255:
                            if count > 1:
                                destination_addr[D] = 0
                                D += 1
                            destination_addr[D] = count
                            D += 1
                            destination_addr[D:D + (count * pixel_size)] = source_addr[
                                                                           S - ((count + 1) * pixel_size):S - (
                                                                                       (count + 1) * pixel_size) + (
                                                                                                                      count * pixel_size)]
                            D += (count * pixel_size)
                            count = 0

                    else:
                        destination_addr[D] = repeat
                        D += 1
                        destination_addr[D:D + pixel_size] = last_color
                        D += pixel_size
                        repeat = 1

                    last_color = pixel

            if col == image_width - 1 and repeat != 255 and count != 255:
                if count:
                    destination_addr[D] = 0
                    D += 1
                    destination_addr[D] = count + 1
                    D += 1
                    destination_addr[D:D + (count + 1) * pixel_size] = source_addr[S - ((count + 1) * pixel_size):S - (
                                (count + 1) * pixel_size) + (count + 1) * pixel_size]
                    D += ((count + 1) * pixel_size)
                    count = 0
                else:
                    destination_addr[D] = repeat
                    D += 1
                    destination_addr[D:D + pixel_size] = last_color
                    D += pixel_size

                first_pixel = True

        destination_addr[D] = 0
        D += 1
        destination_addr[D] = 0
        D += 1

        if D % 4 != 0:
            pad = 4 - (D % 4)
            destination_addr[D:D + pad] = bytes([0] * pad)
            D += pad

    destination_addr[D] = 0
    D += 1
    destination_addr[D] = 1
    D += 1

    if D % 16 != 0:
        pad = 16 - (D % 16)
        destination_addr[D:D + pad] = bytes([0] * pad)
        D += pad

    compressed_size = D
    return 0, source_addr, destination_addr, compressed_size


def splash_perform_rle_uncompression(source_addr, destination_addr, size):
    """Decompress a DLPC350 RLE splash image."""
    source_addr = bytearray(source_addr)
    pixel_size = 3
    S = 0
    D = 0

    while S < size:
        ctrl_byte = source_addr[S]
        color_byte = source_addr[S + 1]
        if ctrl_byte == 0:
            if color_byte == 1:
                break
            elif color_byte == 0:
                S += 2
                if S % 4 != 0:
                    pad = 4 - (S % 4)
                    S += pad
            elif color_byte >= 2:
                S += 2
                destination_addr += source_addr[S:S + color_byte * pixel_size]
                D += color_byte * pixel_size
                S += color_byte * pixel_size
            else:
                return -1, None, None
        elif ctrl_byte > 0:
            S += 1
            for i in range(ctrl_byte):
                destination_addr += source_addr[S:S + pixel_size]
                D += pixel_size
            S += pixel_size
        else:
            return -1, None, None

    size = D

    return 0, size, destination_addr



