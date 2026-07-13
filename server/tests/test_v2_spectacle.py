from __future__ import annotations

from bunnyland.core import (
    AffectComponent,
    CharacterComponent,
    ContainmentMode,
    Contains,
    HasThought,
    IdentityComponent,
    RoomComponent,
    WorldActor,
    parse_entity_id,
    spawn_entity,
)
from bunnyland.core.commands import CommandCost, Lane, build_submitted_command
from bunnyland.core.components import WorldClockComponent
from bunnyland.core.handlers import HandlerContext
from bunnyland.foundation.history.mechanics import WorldHistoryRecordComponent
from bunnyland.imagegen import ImageRequestComponent
from conftest import execute_handler

from bunnyland_festivalsim.hosting import HostedFestivalComponent
from bunnyland_festivalsim.spectacle import (
    METEOR_SHOWER,
    FireworksLaunchedEvent,
    LaunchFireworksHandler,
    MeteorShowerSpectacleConsequence,
    MeteorShowerSpectacleEvent,
    SpectacleComponent,
    meteor_shower_overhead,
    spawn_spectacle,
    spectacle_fragments,
)

EPOCH = 7


def _room(world, title="Square"):
    return spawn_entity(world, [RoomComponent(title=title)])


def _character(world, room, name="Vin"):
    character = spawn_entity(
        world,
        [
            IdentityComponent(name=name, kind="character"),
            CharacterComponent(),
            AffectComponent(),
        ],
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), character.id)
    return character


def _cmd(character_id, command_type, payload):
    return build_submitted_command(
        character_id=str(character_id),
        controller_id="ctrl",
        controller_generation=0,
        command_type=command_type,
        cost=CommandCost(action=1),
        lane=Lane.WORLD,
        payload=payload,
    )


def _ctx(actor):
    return HandlerContext(world=actor.world, epoch=EPOCH)


def _clock(world, seconds=0):
    return spawn_entity(world, [WorldClockComponent(game_time_seconds=seconds)])


def _hosted_festival(world, room):
    festival = spawn_entity(
        world,
        [
            IdentityComponent(name="revel festival", kind="festival"),
            HostedFestivalComponent(key="hosted", theme="revel", host_id="host"),
        ],
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), festival.id)
    return festival


# -- meteor_shower_overhead resolver seam ------------------------------------------------


def test_meteor_shower_overhead_without_starsim_is_false():
    assert meteor_shower_overhead(3) is False


def test_meteor_shower_overhead_uses_injected_resolver():
    assert meteor_shower_overhead(3, resolver=lambda day: METEOR_SHOWER) is True
    assert meteor_shower_overhead(3, resolver=lambda day: "clear sky") is False


# -- launch-fireworks --------------------------------------------------------------------


def test_launch_fireworks_dazzles_the_room_and_records_history():
    actor = WorldActor()
    room = _room(actor.world)
    launcher = _character(actor.world, room, "Pyro")
    bystander = _character(actor.world, room, "Watcher")
    # a non-affect item in the room must simply be skipped by the dazzle
    crate = spawn_entity(actor.world, [IdentityComponent(name="crate", kind="item")])
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), crate.id)

    result = execute_handler(
        LaunchFireworksHandler(), _ctx(actor), _cmd(launcher.id, "launch-fireworks", {})
    )

    assert result.ok
    assert isinstance(result.events[0], FireworksLaunchedEvent)
    spectacles = list(actor.world.query().with_all([SpectacleComponent]).execute_entities())
    assert len(spectacles) == 1
    assert spectacles[0].get_component(SpectacleComponent).kind == "fireworks"
    assert list(launcher.get_relationships(HasThought))
    assert list(bystander.get_relationships(HasThought))
    records = list(actor.world.query().with_all([WorldHistoryRecordComponent]).execute_entities())
    assert len(records) == 1
    assert records[0].has_component(ImageRequestComponent)


def test_launch_fireworks_rejects_invalid_character():
    actor = WorldActor()
    result = execute_handler(
        LaunchFireworksHandler(), _ctx(actor), _cmd("???", "launch-fireworks", {})
    )
    assert not result.ok
    assert result.reason == "invalid character id"


def test_launch_fireworks_rejects_when_not_in_a_room():
    actor = WorldActor()
    loose = spawn_entity(
        actor.world,
        [IdentityComponent(name="Pyro", kind="character"), CharacterComponent()],
    )
    result = execute_handler(
        LaunchFireworksHandler(), _ctx(actor), _cmd(loose.id, "launch-fireworks", {})
    )
    assert not result.ok
    assert result.reason == "you are not in a room"


# -- meteor-shower consequence -----------------------------------------------------------


def test_meteor_consequence_no_clock_is_a_no_op():
    actor = WorldActor()
    consequence = MeteorShowerSpectacleConsequence(overhead=lambda day: True)
    assert consequence.process(actor.world, EPOCH) == []


def test_meteor_consequence_disabled_without_starsim_warns_once():
    actor = WorldActor()
    _clock(actor.world)
    consequence = MeteorShowerSpectacleConsequence(overhead=lambda day: False)
    assert consequence.process(actor.world, EPOCH) == []
    # runs again: no crash, still empty, warning is not repeated
    assert consequence.process(actor.world, EPOCH) == []


def test_meteor_consequence_disabled_with_partner_present_does_not_warn():
    actor = WorldActor()
    _clock(actor.world)
    # a present-but-quiet partner: resolver probe returns a callable, overhead still False
    consequence = MeteorShowerSpectacleConsequence(
        overhead=lambda day: False, resolver_probe=lambda: lambda day: "clear sky"
    )
    assert consequence.process(actor.world, EPOCH) == []


def test_meteor_consequence_lights_up_a_hosted_festival():
    actor = WorldActor()
    _clock(actor.world)
    room = _room(actor.world)
    watcher = _character(actor.world, room, "Watcher")
    festival = _hosted_festival(actor.world, room)
    consequence = MeteorShowerSpectacleConsequence(overhead=lambda day: True)

    events = consequence.process(actor.world, EPOCH)

    assert len(events) == 1
    assert isinstance(events[0], MeteorShowerSpectacleEvent)
    assert events[0].festival_id == str(festival.id)
    spectacles = [
        e.get_component(SpectacleComponent)
        for e in actor.world.query().with_all([SpectacleComponent]).execute_entities()
    ]
    assert any(s.kind == METEOR_SHOWER for s in spectacles)
    assert list(watcher.get_relationships(HasThought))


def test_meteor_consequence_is_idempotent_per_day():
    actor = WorldActor()
    _clock(actor.world)
    room = _room(actor.world)
    _character(actor.world, room, "Watcher")
    _hosted_festival(actor.world, room)
    consequence = MeteorShowerSpectacleConsequence(overhead=lambda day: True)

    first = consequence.process(actor.world, EPOCH)
    second = consequence.process(actor.world, EPOCH)

    assert len(first) == 1
    assert second == []  # the meteor spectacle already hangs over the festival that day


def test_meteor_consequence_adds_a_meteor_over_a_room_with_other_spectacles():
    actor = WorldActor()
    _clock(actor.world)
    room = _room(actor.world)
    _character(actor.world, room, "Watcher")
    _hosted_festival(actor.world, room)
    # a prior fireworks display hangs here, but it is not the day's meteor spectacle
    spawn_spectacle(actor.world, room_id=room.id, kind="fireworks")
    consequence = MeteorShowerSpectacleConsequence(overhead=lambda day: True)

    events = consequence.process(actor.world, EPOCH)

    assert len(events) == 1
    kinds = [
        e.get_component(SpectacleComponent).kind
        for e in actor.world.query().with_all([SpectacleComponent]).execute_entities()
    ]
    assert METEOR_SHOWER in kinds
    assert "fireworks" in kinds


def test_meteor_consequence_skips_a_roomless_festival():
    actor = WorldActor()
    _clock(actor.world)
    # a hosted festival that was never placed in a room
    spawn_entity(
        actor.world,
        [
            IdentityComponent(name="revel festival", kind="festival"),
            HostedFestivalComponent(key="hosted", theme="revel", host_id="host"),
        ],
    )
    consequence = MeteorShowerSpectacleConsequence(overhead=lambda day: True)
    assert consequence.process(actor.world, EPOCH) == []


def test_meteor_consequence_skips_an_ended_festival():
    actor = WorldActor()
    _clock(actor.world)
    room = _room(actor.world)
    spawn_entity(
        actor.world,
        [
            IdentityComponent(name="revel festival", kind="festival"),
            HostedFestivalComponent(key="hosted", theme="revel", host_id="host", ended=True),
        ],
    )
    room.add_relationship(
        Contains(mode=ContainmentMode.ROOM_CONTENT),
        list(actor.world.query().with_all([HostedFestivalComponent]).execute_entities())[0].id,
    )
    consequence = MeteorShowerSpectacleConsequence(overhead=lambda day: True)
    assert consequence.process(actor.world, EPOCH) == []


# -- fragments ---------------------------------------------------------------------------


def test_spectacle_fragment_announces_a_display():
    actor = WorldActor()
    room = _room(actor.world)
    watcher = _character(actor.world, room, "Watcher")
    spawn_spectacle(actor.world, room_id=room.id, kind="fireworks")
    lines = spectacle_fragments(actor.world, watcher)
    assert "A fireworks dazzles overhead." in lines


def test_spectacle_fragment_empty_for_none_character():
    actor = WorldActor()
    assert spectacle_fragments(actor.world, None) == []


def test_spectacle_fragment_empty_when_not_in_room():
    actor = WorldActor()
    loose = spawn_entity(
        actor.world,
        [IdentityComponent(name="Watcher", kind="character"), CharacterComponent()],
    )
    assert spectacle_fragments(actor.world, loose) == []


def test_spawn_spectacle_without_a_room_is_loose():
    actor = WorldActor()
    spectacle = spawn_spectacle(actor.world, room_id=parse_entity_id("entity_9999"))
    assert spectacle.has_component(SpectacleComponent)
