from dlpc350_bmpparser import align_bytes_next, bmp_image_t, bmp_init_image, get_line_bytes


def test_alignment() -> None:
    assert align_bytes_next(1, 4) == 4
    assert align_bytes_next(8, 4) == 8


def test_24_bit_line_padding() -> None:
    image = bmp_image_t()
    status, image = bmp_init_image(image, width=3, height=2, bit_depth=24)
    assert status == 0
    assert get_line_bytes(image) == 12
