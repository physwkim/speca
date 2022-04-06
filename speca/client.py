import time
import asyncio
import struct
import logging

from caproto.server import PVSpec
from caproto.asyncio.utils import _TaskHandler
from caproto.asyncio.server import Context

from .spec import SpecCommand, SpecDataType, Header, Motor

logger = logging.getLogger(__name__)

__all__ = ['SpecClient']

class SpecClient:
    """
        Converts motors and counters provided by SPEC in server mode to EPICS PV

        Attributes
        ----------
        pvspec : dict
            information of motor, scaler, pure PV defined as mnemonic in SPEC
        prefix : string
            prefix is placed before the name of the PV to be created
        addr   : string
            IP address or hostname where server mode is running
        port   : int
            port number where server mode is running
    """
    SV_SPEC_MAGIC = 4277009102
    SV_NAME_LEN = 80
    SV_VERSION = 4

    def __init__(self, pvspec, *args, **kwargs):
        self.lock = asyncio.Lock()

        self.motors = []
        self.scalers = []
        self.pvs = []
        self.pvdb = {}

        self.pvspec = pvspec
        self.prefix = kwargs.get('prefix', '')
        self.addr = kwargs.get('addr', '192.168.122.23')
        self.port = kwargs.get('port', 6510)

        # Make PV list
        for key, pvspec in self.pvspec.items():
            if key == 'motor':
                for spec in pvspec:
                    chan = PVSpec(put=self.motor_put, **spec).create(group=None,)
                    chan.field_inst.stop.putter = self.abortall
                    self.pvdb[self.prefix + spec['name']] = chan

            elif key == 'scaler':
                for spec in pvspec:
                    self.pvdb[self.prefix + spec['name']] = PVSpec(**spec).create(group=None,)

            elif key == 'pv':
                for spec in pvspec:
                    spec_name = spec['name']
                    chan = PVSpec(**spec).create(group=None,)

                    if spec_name == 'prestart':
                        chan.putter = self.prestart
                    elif spec_name == 'startall':
                        chan.putter = self.start_all
                    elif spec_name == 'count':
                        chan.putter = self.count

                    self.pvdb[self.prefix + spec_name] = chan

        # EPICS IOC tasks
        self.server_tasks = _TaskHandler()

        print("Caproto Server is running!")
        print("PVs: {}".format([self.prefix + spec.name for _, spec in self.pvdb.items()]))

    async def subscribe(self, name, dtype='motor'):
        if dtype == 'motor':
            if name not in self.motors:
                self.motors.append(name)

                for prop in Motor._fields:
                    await self.send('motor/{name}/{prop}'.format(name=name, prop=prop),
                                    '',
                                    cmd_type=SpecCommand.SV_REGISTER)

        elif dtype == 'scaler':
            if name not in self.scalers:
                self.scalers.append(name)

                await self.send('scaler/{name}/value'.format(name=name),
                                '',
                                cmd_type=SpecCommand.SV_REGISTER)

        elif dtype == 'pv':
            if name == 'count':
                self.pvs.append(name)

                await self.send('scaler/.all./count',
                                '',
                                cmd_type=SpecCommand.SV_REGISTER)

    async def subs(self):
        for dtype, pvspec in self.pvspec.items():
            for spec in pvspec:
                await self.subscribe(spec['name'], dtype=dtype)

    async def motor_put(self, instance, value):
        if value != instance.field_inst.user_readback_value.value:
            logger.info("motor : {}, moving to : {}".format(instance.name, value))
            await self.move(instance.name, value)

    async def epics_ioc_loop(self):
        """run epics IOC"""
        pvdb = {
            self.prefix + name : data for name, data in self.pvdb.items()
        }
        ctx = Context(self.pvdb, None)
        return await ctx.run(log_pv_names=True, startup_hook=None)

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
            await self.unsubscribe(name, dtype='motor')

        for name in self.scalers:
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
        # packet header structure
        # https://certif.com/spec_help/server.html
        header = struct.pack("IiIIIIiiIIIii80s",
                             self.SV_SPEC_MAGIC,                 # SV_SPEC_MAGIC
                             self.SV_VERSION,                    # Protocol version number
                             132,                                # Size of the structure
                             1234,                               # Serial number (client's choice)
                             int(time.time()),                   # Time when sent (seconds)
                             int(time.time()*(10**6)) & 2**32-1, # Time when sent (microseconds)
                             cmd_type,                           # Command code
                             2,                                  # Type of data
                             0,                                  # Number of rows if array data
                             0,                                  # Number of cols if array data
                             len(msg),                           # Bytes of data that follow
                             0,                                  # Error code
                             0,                                  # Flags
                             name.encode("ascii"))               # Name of property

        data = header  + msg.encode()
        return data

    def decode(self, header):
        raw_header = struct.unpack("IiIIIIiiIIIii80s", header)
        header = Header(*raw_header)
        header = header._replace(name=header.name.decode('utf-8').rstrip('\x00'))
        return header

    async def send(self, name, msg, cmd_type=SpecCommand.SV_CMD):
        data = self.encode(name, msg, cmd_type)

        async with self.lock:
            self.writer.write(data)
            await self.writer.drain()

    async def prestart(self, instance, value):
        if value > 0:
            await self.send('motor/../prestart_all',
                            '',
                            SpecCommand.SV_CHAN_SEND)

    async def start_all(self, instance, value):
        if value > 0:
            await self.send('motor/../start_all',
                            '',
                            SpecCommand.SV_CHAN_SEND)

    async def abortall(self, instance, value):
        if value > 0:
            await self.send('motor/../abort_all',
                            '',
                            SpecCommand.SV_CHAN_SEND)

    async def move(self, motor, value):
        await self.send('motor/{}/start_one'.format(motor),
                        str(value),
                        SpecCommand.SV_CHAN_SEND)

    async def count(self, instance, value):
        name = instance.name
        val = self.pvdb[self.prefix + 'preset'].value

        was_counting = self.pvdb[self.prefix + 'count'].value
        if was_counting == 0:
            await self.send('scaler/.all./count',
                            str(val),
                            SpecCommand.SV_CHAN_SEND)

    async def process(self, header, data):
        cmd_type, mnemonic, prop = header.name.split('/')
        mnemonic = mnemonic.strip('.')

        logger.debug("cmd_type : {}, mnemonic : {}, prop : {}, data : {}".format(cmd_type, mnemonic, prop, data))
        if cmd_type == 'motor':
            inst = self.pvdb[self.prefix + mnemonic]
            value = float(data)

            if prop == 'position':
                if value != inst.field_inst.user_readback_value.value:
                    await inst.field_inst.user_readback_value.write(value)
                    await inst.field_inst.dial_readback_value.write(value)
                    await inst.field_inst.raw_readback_value.write(value)

            elif prop == 'move_done':
                moving_done = not bool(int(value))

                if moving_done != inst.field_inst.done_moving_to_value.value:
                    await inst.field_inst.done_moving_to_value.write(moving_done)
                if (not moving_done) != inst.field_inst.motor_is_moving.value:
                    await inst.field_inst.motor_is_moving.write(not moving_done)


            elif prop == 'low_limit':
                value  = bool(int(value))
                if value != inst.field_inst.user_low_limit.value:
                    await inst.field_inst.user_low_limit.write(value)

            elif prop == 'high_limit':
                value  = bool(int(value))
                if value != inst.field_inst.user_high_limit.value:
                    await inst.field_inst.user_high_limit.write(value)

            elif prop == 'low_limit_hit':
                value  = bool(int(value))
                if value != inst.field_inst.user_low_limit_switch.value:
                    await inst.field_inst.user_low_limit_switch.write(value)

            elif prop == 'high_limit_hit':
                value  = bool(int(value))
                if value != inst.field_inst.user_high_limit_switch.value:
                    await inst.field_inst.user_high_limit_switch.write(value)

        if cmd_type == 'scaler':
            if mnemonic == 'all':
                mnemonic = prop

            inst = self.pvdb[self.prefix + mnemonic]
            value = int(data) if mnemonic == 'count' else float(data)

            if value != inst.value:
                await inst.write(value)

    async def run(self):
        # make EPICS ioc
        self.server_tasks.create(self.epics_ioc_loop())

        # make connection to SPEC server
        self.reader, self.writer = await asyncio.open_connection(self.addr, self.port)

        # subscribe devices
        await self.subs()

        while True:
            try:
                header, data = await self.recv()
                if header:
                    await self.process(header, data)
            except KeyboardInterrupt:
                break
            except:
                continue
