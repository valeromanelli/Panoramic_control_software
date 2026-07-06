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

    # check if needs padding
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
    def __init__(self):
        self.flags = 0
        self.sequence = 0
        self.following_sequence = 0
        self.length = []

    def make_list(self):
        list = [self.flags, self.sequence] + self.length
        return list

    def set_reply(self, reply=True):
        if reply:
            self.flags |= (1 << 6)
        else:
            self.flags &= ~(1 << 6)

    def set_read(self, mode='r'):
        if mode == 'r':
            self.flags |= (1 << 7)
        if mode == 'w':
            self.flags &= ~(1 << 7)

    def set_length(self, length):
        self.length = conv_len(length, 16)
        self.length = bits_to_bytes(self.length)

    def return_length(self):
        length = 0
        for i in range(len(self.length)):
            length += self.length[i] << (8 * i)
        return length

    def increase_seq_num(self):
        self.sequence = self.following_sequence
        self.following_sequence += 1


class MessageText:
    def __init__(self):
        self.cmd = []
        self.data = []

    def make_list(self):
        return self.cmd + self.data

    def set_cmd(self, cmd):
        self.cmd = []
        self.cmd.append(cmd[1])
        self.cmd.append(cmd[0])

    def set_data(self, data):
        self.data = []
        self.data = list(data)


class HidMessageStruct:
    def __init__(self):
        self.head = MessageHeader()
        self.text = MessageText()

    def make_list(self):
        head = self.head.make_list()
        text = self.text.make_list()
        return head + text
