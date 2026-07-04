from __future__ import annotations

import asyncio

from bunnyland.core import RoomComponent, WorldActor, contents, spawn_entity
from bunnyland.core.components import GenerationIntentComponent
from bunnyland.core.events import RoomGeneratedEvent, event_base
from bunnyland.plugins import apply_plugins, load_modules

from bunnyland_festivalsim import ContestComponent, DecorationComponent


def _actor():
    actor = WorldActor()
    apply_plugins(load_modules(["bunnyland_festivalsim"]), actor)
    return actor


def _publish(actor, event):
    asyncio.run(actor.bus.publish(event))


def _generate_room(actor, *, title="A place", room_key="room", tags=()):
    room = spawn_entity(actor.world, [RoomComponent(title=title)])
    event = RoomGeneratedEvent(
        **event_base(0),
        seed="seed",
        entity_id=str(room.id),
        entity_key=room_key,
        entity_kind="room",
        generation=GenerationIntentComponent(tags=tuple(tags)),
        room_key=room_key,
    )
    _publish(actor, event)
    return room


def _kinds_in(actor, room, component_type):
    return [
        entity_id
        for entity_id in contents(room)
        if actor.world.get_entity(entity_id).has_component(component_type)
    ]


def test_town_square_is_dressed_with_decorations_and_a_contest():
    actor = _actor()
    room = _generate_room(actor, room_key="town-square", tags=("square", "gathering"))

    assert len(_kinds_in(actor, room, DecorationComponent)) == 2
    assert len(_kinds_in(actor, room, ContestComponent)) == 1


def test_plain_room_is_left_undressed():
    actor = _actor()
    room = _generate_room(actor, room_key="cellar", tags=("dark", "storage"))

    assert _kinds_in(actor, room, DecorationComponent) == []
    assert _kinds_in(actor, room, ContestComponent) == []


def test_dressing_a_square_is_idempotent():
    actor = _actor()
    room = spawn_entity(actor.world, [RoomComponent(title="Plaza")])
    event = RoomGeneratedEvent(
        **event_base(0),
        seed="seed",
        entity_id=str(room.id),
        entity_key="plaza",
        entity_kind="room",
        generation=GenerationIntentComponent(tags=("plaza",)),
        room_key="plaza",
    )
    _publish(actor, event)
    _publish(actor, event)  # second pass must not double-dress

    assert len(_kinds_in(actor, room, DecorationComponent)) == 2
    assert len(_kinds_in(actor, room, ContestComponent)) == 1
