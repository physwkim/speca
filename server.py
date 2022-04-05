import time
import asyncio
import struct
from collections import namedtuple
from enum import IntEnum

from caproto.server import PVSpec
from caproto.asyncio.utils import _TaskHandler
from caproto.asyncio.server import Context


class SpecCommand(IntEnum):
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

# Spec Header Structure
Header = namedtuple('Header', ['magic', 'vers', 'size', 'sn', 'sec',
                               'usec', 'cmd', 'type', 'rows', 'cols',
                               'len', 'err', 'flags', 'name'])

# Motor structure
Motor = namedtuple('Motor',
                   ['position', 'move_done', 'low_limit',
                    'high_limit', 'low_lim_hit', 'high_lim_hit'],
                   defaults=[0, 0, 0, 0, 0, 0])

class SpecClient:
    SV_SPEC_MAGIC = 4277009102
    SV_NAME_LEN = 80
    SV_VERSION = 4

    def __init__(self, pvspec, *args, **kwargs):
        self.prefix = kwargs.get('prefix', '')

        self.addr = kwargs.get('addr', '192.168.122.23')
        self.port = kwargs.get('port', 6510)

        self.motors = []
        self.scalers = []

        # PV list
        self.pvdb = {spec['name'] : PVSpec(put=self.putter, **spec).create(group=None, )
                     for spec in pvspec}

        self.server_tasks = _TaskHandler()

        self.lock = asyncio.Lock()

        print("Caproto Server is running!")
        print("PVs: {}".format([self.prefix + spec.name for _, spec in self.pvdb.items()]))

    async def putter(self, instance, value):
        print("motor : {}, moving to : {}".format(instance.name, value))
        await self.move(instance.name, value)

    async def epics_ioc_loop(self):
        """run epics IOC"""
        ctx = Context(self.pvdb, None)
        return await ctx.run(log_pv_names=False, startup_hook=None)

    async def subscribe(self, name, dtype='motor'):
        if dtype == 'motor':
            if name not in self.motors:
                self.motors.append(name)

                for prop in Motor._fields:
                    await self.send('motor/{name}/{prop}'.format(name=name, prop=prop),
                                    '',
                                    cmd_type=SpecCommand.SV_REGISTER)

        elif dtype == 'scaler':
            if 'count' not in self.scalers:
                self.scalers.append('count')

                await self.send('scaler/.all./count',
                                '',
                                cmd_type=SpecCommand.SV_REGISTER)

            if name not in self.scalers:
                self.scalers.append(name)

                await self.send('scaler/{name}/value'.format(name=name),
                                '',
                                cmd_type=SpecCommand.SV_REGISTER)

    async def unsubscribe(self, name, dtype='motor'):
        if dtype == 'motor':
            for prop in Motor._fields:
                await self.send('motor/{name}/{prop}'.format(name=name, prop=prop),
                                '',
                                cmd_type=SpecCommand.SV_UNREGISTER)

            if name in self.motors:
                self.motors.remove(name)

        elif dtype == 'scaler':
            await self.send('scaler/{name}/value'.format(name=name),
                            '',
                            cmd_type=SpecCommand.SV_UNREGISTER)

            if name in self.scalers:
                self.scalers.remove(name)

    async def unsubscribe_all(self):
        for name in self.motors:
            # print("name : {}".format(name))
            await self.unsubscribe(name, dtype='motor')

        for name in self.scalers:
            # print("name : {}".format(name))
            await self.unsubscribe(name, dtype='scaler')

    async def recv(self):
        size = 132
        readings = await self.reader.read(size)

        if len(readings) < size:
            raise

        header = self.decode(readings)

        # No proper spec message
        if header.magic != self.SV_SPEC_MAGIC:
            raise

        if header.len > 0:
            readings = await self.reader.read(header.len)

            if header.type ==  SpecDataType.SV_STRING:
                data = readings.decode('utf-8').rstrip('\x00')
            else:
                data = readings
        else:
            data = None

        return header, data

    def encode(self, name, msg, cmd_type=SpecCommand.SV_CMD):
        header = struct.pack("IiIIIIiiIIIii80s",
                             self.SV_SPEC_MAGIC, # SV_SPEC_MAGIC
                             self.SV_VERSION, # Protocol version number
                             132,  # Size of the structure
                             1234, # Serial number (client's choice)
                             int(time.time()), # Time when sent (seconds)
                             int(time.time()*(10**6)) & 2**32-1, # time when sent (microseconds)
                             cmd_type, # Command code
                             2, # Type of data
                             0, # Number of rows if array data
                             0, # Number of columns if array data
                             len(msg), # Bytes of data that follow
                             0, # Error code
                             0, # Flags
                             name.encode("ascii")) # Name of property
        data = header  + msg.encode()
        return data

    def decode(self, header):
        raw_header = struct.unpack("IiIIIIiiIIIii80s", header)
        header = Header(*raw_header)
        header = header._replace(name=header.name.decode('utf-8').rstrip('\x00'))
        return header

    async def prestart(self):
        await self.send('motor/../prestart_all',
                        '',
                        SpecCommand.SV_CHAN_SEND)

    async def startall(self):
        await self.send('motor/../start_all',
                        '',
                        SpecCommand.SV_CHAN_SEND)

    async def abortall(self):
        await self.send('motor/../abort_all',
                        '',
                        SpecCommand.SV_CHAN_SEND)

    async def move(self, motor, value):
        await self.send('motor/{}/start_one'.format(motor),
                        str(value),
                        SpecCommand.SV_CHAN_SEND)

    async def send(self, name, msg, cmd_type=SpecCommand.SV_CMD):
        data = self.encode(name, msg, cmd_type)

        async with self.lock:
            self.writer.write(data)
            await self.writer.drain()

    async def run(self):
        # make ioc
        self.server_tasks.create(self.epics_ioc_loop())
        self.reader, self.writer = await asyncio.open_connection(self.addr, self.port)

        await self.subscribe('tth')
        await self.subscribe('th')

        while True:
            try:
                header, data = await self.recv()
                if header:
                    # print("name : {}, data : {}".format(header.name, data))
                    await self.process(header, data)
            except KeyboardInterrupt:
                break
            except:
                continue

    async def process(self, header, data):
        cmd_type, motorName, prop = header.name.split('/')

        if cmd_type == 'motor':
            inst = self.pvdb[motorName]
            # print("inst : {}, format(inst) : {}".format(inst, type(inst)))
            value = float(data)

            if prop == 'position':
                await inst.field_inst.user_readback_value.write(value)
                await inst.field_inst.user_readback_value.write(value)
                await inst.field_inst.raw_readback_value.write(value)

            elif prop == 'move_done':
                moving_done = not bool(int(value))
                await inst.field_inst.done_moving_to_value.write(moving_done)
                await inst.field_inst.motor_is_moving.write(not moving_done)

            elif prop == 'low_limit':
                value  = bool(int(value))
                await inst.field_inst.user_low_limit.write(value)

            elif prop == 'high_limit':
                value  = bool(int(value))
                await inst.field_inst.user_high_limit.write(value)

            elif prop == 'low_limit_hit':
                value  = bool(int(value))
                await inst.field_inst.user_low_lmit_switch.write(value)

            elif prop == 'high_limit_hit':
                value  = bool(int(value))
                await inst.field_inst.user_high_lmit_switch.write(value)

if __name__ == '__main__':
    tth = {'name' : 'tth',
           'value' : 0,
           'record' : 'motor'}

    th = {'name' : 'th',
           'value' : 0,
          'record' : 'motor'}

    chi = {'name' : 'chi',
           'value' : 0,
          'record' : 'motor'}

    phi = {'name' : 'phi',
           'value' : 0,
           'record' : 'motor'}

    pvspec = [tth, th, chi, phi]

    conn = SpecClient(pvspec, addr='192.168.122.23', port=6510)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(conn.run())
