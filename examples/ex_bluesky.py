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

"""
# Move spec motor
tth.move(1)
th.move(0.5)

# Simultaneously
RE(bps.mv(tth, 5, th, 2.5))
"""
