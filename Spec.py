from enum import IntEnum
from collections import namedtuple

class SpecCommand(IntEnum):
    """
        SPEC command code
        See https://certif.com/spec_help/server.html
    """
    SV_CLOSE = 1  # From Client
    SV_ABORT = 2  # From Client
    SV_CMD = 3    # From Client
    SV_CMD_WITH_RETURN = 4 # From Client
    SV_RETURN = 5 # Not yet used
    SV_REGISTER = 6 # From Client
    SV_UNREGISTER = 7 # From Client
    SV_EVENT = 8 # From Server
    SV_FUNC = 9 # From Client
    SV_FUNC_WITH_RETURN = 10 # From Client
    SV_CHAN_READ = 11 # From Client
    SV_CHAN_SEND = 12 # From Client
    SV_REPLY = 13 # From Server
    SV_HELLO = 14 # From Client
    SV_REPLY_REPLY = 15 # From Server

class SpecDataType(IntEnum):
    """
        The type of data folloing the header
        See https://certif.com/spec_help/server.html
    """
    SV_DOUBLE = 1
    SV_STRING = 2
    SV_ERROR = 3
    SV_ASSOC = 4
    SV_ARR_DOUBLE = 5
    SV_ARR_FLOAT = 6
    SV_ARR_LONG = 7
    SV_ARR_ULONG = 8
    SV_ARR_SHORT = 9
    SV_ARR_USHORT = 10
    SV_ARR_CHAR = 11
    SV_ARR_UCHAR = 12
    SV_ARR_STRING = 13
    SV_ARR_LONG64 = 14
    SV_ARR_ULONG64 = 15

# Spec header structure
Header = namedtuple('Header', ['magic', 'vers', 'size', 'sn', 'sec',
                               'usec', 'cmd', 'type', 'rows', 'cols',
                               'len', 'err', 'flags', 'name'])

# Motor structure
Motor = namedtuple('Motor',
                   ['position', 'move_done', 'low_limit',
                    'high_limit', 'low_lim_hit', 'high_lim_hit'],
                   defaults=[0, 0, 0, 0, 0, 0])

