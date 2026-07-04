from __future__ import annotations

from bunnyland.core import (
    AffectComponent,
    CharacterComponent,
    DeadComponent,
    IdentityComponent,
    SuspendedComponent,
    WorldActor,
    spawn_entity,
)
from bunnyland.core.components import AffectVector
from bunnyland.core.ecs import replace_component

from bunnyland_festivalsim import SeasonalMoodConsequence
from bunnyland_festivalsim.components import FestivalComponent

EPOCH = 10


def _open_festival(actor, *, mood_lift=1.0):
    replace_component(
        actor._clock_entity,
        FestivalComponent(key="midwinter", name="Midwinter", mood_lift=mood_lift),
    )


def _reveller(world, *, valence=0.0, sociability=0.0):
    return spawn_entity(
        world,
        [
            IdentityComponent(name="Vin", kind="character"),
            CharacterComponent(),
            AffectComponent(current=AffectVector(valence=valence, sociability=sociability)),
        ],
    )


def _current(entity):
    return entity.get_component(AffectComponent).current


def test_festival_lifts_mood():
    actor = WorldActor()
    _open_festival(actor, mood_lift=1.0)
    reveller = _reveller(actor.world)

    SeasonalMoodConsequence().process(actor.world, EPOCH)

    assert _current(reveller).valence == 1.0
    assert _current(reveller).sociability == 1.0


def test_no_festival_no_change():
    actor = WorldActor()
    reveller = _reveller(actor.world)

    assert SeasonalMoodConsequence().process(actor.world, EPOCH) == []
    assert _current(reveller).valence == 0.0


def test_mood_lift_caps_at_ceiling():
    actor = WorldActor()
    _open_festival(actor, mood_lift=1.0)
    reveller = _reveller(actor.world, valence=4.8, sociability=4.8)

    SeasonalMoodConsequence(valence_cap=5.0, sociability_cap=5.0).process(actor.world, EPOCH)

    assert _current(reveller).valence == 5.0
    assert _current(reveller).sociability == 5.0


def test_no_change_once_already_capped():
    actor = WorldActor()
    _open_festival(actor, mood_lift=1.0)
    reveller = _reveller(actor.world, valence=5.0, sociability=5.0)

    SeasonalMoodConsequence(valence_cap=5.0, sociability_cap=5.0).process(actor.world, EPOCH)

    assert _current(reveller).valence == 5.0


def test_suspended_reveller_is_skipped():
    actor = WorldActor()
    _open_festival(actor)
    reveller = _reveller(actor.world)
    reveller.add_component(SuspendedComponent())

    SeasonalMoodConsequence().process(actor.world, EPOCH)

    assert _current(reveller).valence == 0.0


def test_dead_reveller_is_skipped():
    actor = WorldActor()
    _open_festival(actor)
    reveller = _reveller(actor.world)
    reveller.add_component(DeadComponent(died_at_epoch=EPOCH, cause="ennui"))

    SeasonalMoodConsequence().process(actor.world, EPOCH)

    assert _current(reveller).valence == 0.0
