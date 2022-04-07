
# speca - Converts motors and counters provided by SPEC in server mode to EPICS PV

To use bluesky(http://blueskyproject.io) instead of SPEC(https://certif.com), 
the device must be controllable with EPICS PV.

## Installation
Requires python3.7 or higher

```bash
git clone https://github.com/physwkim/speca
cd speca
pip install -e .
```

## Usage

### Run SPEC in server mode.
```bash
fourc -S 6510
```

### Enter the specification of the record to be created and connect to the SPEC sever.
```python
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

# All specificatino
pvspec = {
            'motor'   : [tth, th, chi, phi],
            'scaler' : [sec, mon, det],
            'pv'    : [preset_time, count, prestart, startall]
        }

# Run client
client = SpecClient(pvspec, addr='192.168.122.23', port=6510, prefix='spec:')

loop = asyncio.get_event_loop()
loop.run_until_complete(client.run())
```

### Connect to PV and scan from bluesky
```python
from bluesky import RunEngine
from bluesky.callbacks.best_effort import BestEffortCallback
import bluesky.plans as bp
import bluesky.plan_stubs as bps

from ophyd import Device, EpicsMotor, EpicsSignal
from ophyd.device import Component as Cpt, required_for_connection
from ophyd.ophydobj import Kind
from ophyd.status import DeviceStatus

from databroker import Broker

# RunEngine
RE = RunEngine({})

# Display Graph and table
bec = BestEffortCallback()

# Temporary database
db = Broker.named('temp')

# RunEngine subscriptions
subs = {}
subs['bec'] = RE.subscribe(bec)
subs['db'] = RE.subscribe(db.insert)

# SPEC motors
tth = EpicsMotor('spec:tth', name='tth')
th = EpicsMotor('spec:th', name='th')
chi = EpicsMotor('spec:chi', name='chi')
phi = EpicsMotor('spec:phi', name='phi')

# SPEC Counter
class SpecCounter(Device):
    count = Cpt(EpicsSignal, 'count', trigger_value=1, kind=Kind.omitted)
    preset_time = Cpt(EpicsSignal, 'preset', kind=Kind.config)

    mon = Cpt(EpicsSignal, 'mon', kind=Kind.hinted)
    sec = Cpt(EpicsSignal, 'sec', kind=Kind.hinted)
    det = Cpt(EpicsSignal, 'det', kind=Kind.hinted)

    _started_counting = False
    _counting = False

    def trigger(self):
        """Start counting"""
        signals = self.trigger_signals
        if len(signals) > 1:
            raise NotImplementedError('More than one trigger signal is not '
                                      'currently supported')

        status = DeviceStatus(self)
        if not signals:
            status.set_finished()
            return status

        acq_signal, = signals

        self.subscribe(status._finished,
                       event_type=self.SUB_ACQ_DONE, run=False)

        acq_signal.put(1, wait=False)

        return status

    @required_for_connection
    @count.sub_value
    def _count_changed(self, timestamp=None, value=None, sub_type=None,
                       **kwargs):
        """Callback from EPICS, indicating that counting status has changed"""

        was_counting = self._counting
        self._counting = (value > 0)

        started = False
        if not self._started_counting:
            started = self._started_counting = (not was_counting and self._counting)

        if was_counting and not self._counting:
            self._done_acquiring()


counter = SpecCounter('spec:', name='counter')

# set count-time to 3 sec
counter.preset_time.put(3)

# move spec motor
tth.move(1)
th.move(0.5)

# move motors simultaneously
RE(bps.mv(tth, 5, th, 2.5))


# Do scan
RE(bp.scan([counter], tth, -1, 1, th, -0.5, 0.5, 21))
```

## License
[MIT] (https://choosealicense.com/licenses/mit/)
