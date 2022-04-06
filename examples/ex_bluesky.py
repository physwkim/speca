from bluesky import RunEngine
from bluesky.callbacks.best_effort import BestEffortCallback
import bluesky.plans as bp
import bluesky.plan_stubs as bps

from ophyd import Device, EpicsMotor, EpicsSignal
from ophyd.device import Component as Cpt
from ophyd.ophydobj import Kind

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

counter = SpecCounter('spec:', name='counter')

