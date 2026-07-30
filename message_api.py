"""USB HID message structures and byte-conversion helpers for DLPC350 commands."""

def conv_len(a, l):
    """
    Function that converts a number into a bit string of given length.

    :param int a: Number to convert.
    :param int l: Length of bit string.

    :return: Padded bit string.
    """
    b = bin(a)[2:]
    padding = l - len(b)
    b = '0' * padding + b
    return b


def bits_to_bytes(a, reverse=True):
    """
    Function that converts bit string into a given number of bytes.

    :param str a: Bytes to convert.
    :param bool reverse: Whether or not to reverse the byte list.

    :return: List of bytes.
    """
    bytelist = []

    if len(a) % 8 != 0:
        padding = 8 - len(a) % 8
        a = '0' * padding + a

    # convert to bytes
    for i in range(len(a) // 8):
        bytelist.append(int(a[8 * i:8 * (i + 1)], 2))

    if reverse:
        bytelist.reverse()
    return bytelist


class MessageHeader:
    """Four-byte HID message header."""
    def __init__(self):
        self.flags = 0
        self.sequence = 0
        self.following_sequence = 0
        self.length = []

    def make_list(self):
        """Return the serialized header bytes."""
        values = [self.flags, self.sequence] + self.length
        return values

    def set_reply(self, reply=True):
        """Enable or disable the reply-request flag."""
        if reply:
            self.flags |= (1 << 6)
        else:
            self.flags &= ~(1 << 6)

    def set_read(self, mode='r'):
        """Set the read/write flag."""
        if mode == 'r':
            self.flags |= (1 << 7)
        elif mode == 'w':
            self.flags &= ~(1 << 7)
        else:
            raise ValueError("mode must be 'r' or 'w'")

    def set_length(self, length):
        """Store a 16-bit payload length in little-endian byte order."""
        self.length = conv_len(length, 16)
        self.length = bits_to_bytes(self.length)

    def return_length(self):
        """Decode the stored little-endian payload length."""
        length = 0
        for i in range(len(self.length)):
            length += self.length[i] << (8 * i)
        return length

    def increase_seq_num(self):
        """Assign and increment the message sequence number."""
        self.sequence = self.following_sequence
        self.following_sequence += 1


class MessageText:
    """Command and payload portion of a HID message."""
    def __init__(self):
        self.cmd = []
        self.data = []

    def make_list(self):
        """Return command bytes followed by payload bytes."""
        return self.cmd + self.data

    def set_cmd(self, cmd):
        """Store a two-byte command in HID wire order."""
        self.cmd = []
        self.cmd.append(cmd[1])
        self.cmd.append(cmd[0])

    def set_data(self, data):
        """Replace the message payload with the supplied bytes."""
        self.data = list(data)


class HidMessageStruct:
    """Complete HID message composed of a header and payload."""
    def __init__(self):
        self.head = MessageHeader()
        self.text = MessageText()

    def make_list(self):
        """Serialize the complete HID message."""
        head = self.head.make_list()
        text = self.text.make_list()
        return head + text
