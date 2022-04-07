import asyncio
from speca.client import SpecClient

# SPEC motor spec
tth = {'name' : 'tth',
       'value' : 0,
       'dtype' : float,
       'record' : 'motor'}

th = {'name' : 'th',
      'value' : 0,
      'dtype' : float,
      'record' : 'motor'}

chi = {'name' : 'chi',
       'value' : 0,
       'dtype' : float,
       'record' : 'motor'}

phi = {'name' : 'phi',
       'value' : 0,
       'dtype' : float,
       'record' : 'motor'}

prestart = {'name' : 'prestart',
            'value' : 0,
            'dtype' : int,
            'record' : 'ai'}

startall = {'name' : 'startall',
            'value' : 0,
            'dtype' : int,
            'record' : 'ai'}

# SPEC counter
preset_time = {'name' : 'preset',
               'value' : 1.0,
               'dtype' : float,
               'record' : 'ai'}

count = {'name' : 'count',
            'value' : 0,
            'dtype' : int,
            'record' : 'ai'}

sec = {'name' : 'sec',
       'value' : 0,
       'dtype' : float,
       'record' : 'ai'}

mon = {'name' : 'mon',
       'value' : 0,
       'dtype' : float,
       'record' : 'ai'}

det = {'name' : 'det',
       'value' : 0,
       'dtype' : float,
       'record' : 'ai'}

pvspec = {
            'motor'   : [tth, th, chi, phi],
            'scaler' : [sec, mon, det],
            'pv'    : [preset_time, count, prestart, startall]
        }

client = SpecClient(pvspec, addr='192.168.122.23', port=6510, prefix='spec:')

loop = asyncio.get_event_loop()
loop.run_until_complete(client.run())
