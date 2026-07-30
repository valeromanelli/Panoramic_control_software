"""Minimal BMP serialization helpers used by the DLPC350 firmware tools."""

ERR_INVALID_PARAM = -1
BMP_DIB_HEADER_SIZE = 40
BMP_DIB_HEADER_SIZE1 = 108
BMP_FILE_HEADER_SIZE = 14


class bmp_image_t:
    """Metadata required to serialize one BMP image."""
    def __init__(self):
        self.width = 0
        self.heigth = 0
        self.num_colors = 0
        self.bit_depth = 0


def get_line_bytes(image):
    """Return the padded number of bytes in one BMP scan line."""
    return align_bytes_next(image.width * image.bit_depth, 32) // 8


def align_bytes_next(value, align):
    """Round a value up to the requested alignment."""
    return (value + align - 1) & ~ (align - 1)


def make_word_16(b1, b0):
    """Combine two one-character values into a 16-bit integer."""
    return (ord(b1) << 8) | ord(b0)


def make_word_32(b3, b2, b1, b0):
    """Combine four bytes into a 32-bit integer."""
    return (b3 << 24) | (b2 << 16) | (b1 << 8) | b0


def gen_bit_mask(s, n):
    """Return a mask containing the requested number of low-order bits."""
    return (1 << n) - 1


def bmp_init_image(image, width, height, bit_depth):
    """Initialize BMP metadata and normalize the requested bit depth."""
    if image is None:
        return -1

    image.num_colors = 256

    if bit_depth <= 1:
        bit_depth = 1
    elif bit_depth <= 4:
        bit_depth = 4
    elif bit_depth <= 8:
        bit_depth = 8
    elif bit_depth == 16:
        bit_depth = 16
    elif bit_depth == 24:
        bit_depth = 24
    else:
        return -1

    image.width = width
    image.heigth = height
    image.bit_depth = bit_depth

    return 0, image


def bmp_put_data(put_data, data_param, value, size):
    """Serialize an integer and pass it to the supplied writer callback."""
    data = value.to_bytes(4, byteorder='little')

    return put_data(data_param, data, size)


def bmp_store_image(image, put_data, data_param, get_pixels, image_buffer, pixel_param=None):
    """Serialize image metadata and pixels as a BMP stream."""
    BMP_SIGNATURE = make_word_16('M', 'B')
    header_size = BMP_DIB_HEADER_SIZE1 if image.bit_depth == 16 else BMP_DIB_HEADER_SIZE
    pix_offset = image.num_colors * 4 + BMP_FILE_HEADER_SIZE + header_size
    data_size = get_line_bytes(image) * image.heigth
    file_size = data_size + pix_offset

    bmp_put_data(put_data, data_param, BMP_SIGNATURE, 2)
    bmp_put_data(put_data, data_param, file_size, 4)
    bmp_put_data(put_data, data_param, 0, 4)
    bmp_put_data(put_data, data_param, pix_offset, 4)
    bmp_put_data(put_data, data_param, header_size, 4)
    bmp_put_data(put_data, data_param, image.width, 4)
    bmp_put_data(put_data, data_param, image.heigth, 4)
    bmp_put_data(put_data, data_param, 1, 2)
    bmp_put_data(put_data, data_param, image.bit_depth, 2)
    value = 3 if image.bit_depth == 16 else 0
    bmp_put_data(put_data, data_param, value, 4)
    bmp_put_data(put_data, data_param, data_size, 4)
    bmp_put_data(put_data, data_param, 2835, 4)
    bmp_put_data(put_data, data_param, 2835, 4)
    bmp_put_data(put_data, data_param, image.num_colors, 4)
    bmp_put_data(put_data, data_param, 0, 4)

    for i in range(image.num_colors):
        val = int((255 * i) / (image.num_colors - 1))
        color = make_word_32(255, val, val, val)

        bmp_put_data(put_data, data_param, color, 4)

    if image.bit_depth == 16:
        bmp_put_data(put_data, data_param, 0xF800, 4)
        bmp_put_data(put_data, data_param, 0x07E0, 4)
        bmp_put_data(put_data, data_param, 0x001F, 4)
        bmp_put_data(put_data, data_param, 0x0000, 4)
        bmp_put_data(put_data, data_param, 0x57696E20, 4)

        for i in range(12):
            bmp_put_data(put_data, data_param, 0, 4)

    if image.bit_depth <= 8:
        buffer = bytearray(image.width)

    mask = gen_bit_mask(0, image.bit_depth)
    line_width = get_line_bytes(image)
    line_out = bytearray(line_width)

    pixels_per_byte = int(8 / image.bit_depth)

    for y in range(image.heigth - 1, -1, -1):
        if image.bit_depth <= 8:
            _, buffer = get_pixels(pixel_param, 0, y, buffer, image.width, image_buffer)
            i = 0
            for x in range(line_width):
                byte = 0
                for j in range(pixels_per_byte):
                    byte <<= image.bit_depth
                    if i < image.width:
                        byte |= buffer[i] & mask
                        i += 1
                line_out[x] = byte
            put_data(data_param, line_out, line_width)

        else:
            _, line_out = get_pixels(pixel_param, 0, y, line_out, image.width, image_buffer)
            put_data(data_param, line_out, line_width)

    return 0, image, data_param


