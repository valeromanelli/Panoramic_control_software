from message_api import HidMessageStruct, bits_to_bytes, conv_len


def test_conv_len_and_byte_order() -> None:
    assert conv_len(0x1234, 16) == "0001001000110100"
    assert bits_to_bytes("0001001000110100") == [0x34, 0x12]


def test_hid_message_serialization() -> None:
    message = HidMessageStruct()
    message.head.set_read(mode="w")
    message.head.set_reply()
    message.head.set_length(4)
    message.text.set_cmd([0x1A, 0x23])
    message.text.set_data([0x01, 0x02])

    assert message.make_list() == [0x40, 0x00, 0x04, 0x00, 0x23, 0x1A, 0x01, 0x02]
