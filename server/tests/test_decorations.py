from __future__ import annotations

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    IdentityComponent,
    PortableComponent,
    RoomComponent,
    WorldActor,
    contents,
    spawn_entity,
)
from bunnyland.core.commands import CommandCost, Lane, build_submitted_command
from bunnyland.core.handlers import HandlerContext
from conftest import execute_handler

from bunnyland_festivalsim import (
    DecorateHandler,
    DecorationComponent,
    RoomDecoratedEvent,
    decoration_fragments,
    room_festivity,
    spawn_decoration,
)

EPOCH = 10


def _room(world, *, title="Square"):
    return spawn_entity(world, [RoomComponent(title=title)])


def _character(world, room, name="Vin"):
    character = spawn_entity(
        world, [IdentityComponent(name=name, kind="character"), CharacterComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), character.id)
    return character


def _hold(holder, item):
    holder.add_relationship(Contains(mode=ContainmentMode.INVENTORY), item.id)


def _cmd(character_id, payload):
    return build_submitted_command(
        character_id=str(character_id),
        controller_id="ctrl",
        controller_generation=0,
        command_type="decorate",
        cost=CommandCost(action=1),
        lane=Lane.WORLD,
        payload=payload,
    )


def _ctx(actor):
    return HandlerContext(world=actor.world, epoch=EPOCH)


def _decorations_in(world, room):
    return [
        world.get_entity(entity_id)
        for entity_id in contents(room)
        if world.has_entity(entity_id)
        and world.get_entity(entity_id).has_component(DecorationComponent)
    ]


# -- decorate ---------------------------------------------------------------------------


def test_decorate_spawns_a_decoration_in_the_room():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)

    result = execute_handler(DecorateHandler(), _ctx(actor), _cmd(character.id, {"kind": "banner"}))

    assert result.ok
    assert isinstance(result.events[0], RoomDecoratedEvent)
    assert result.events[0].kind == "banner"
    decorations = _decorations_in(actor.world, room)
    assert len(decorations) == 1
    assert decorations[0].get_component(DecorationComponent).kind == "banner"


def test_decorate_defaults_to_a_lantern():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)

    result = execute_handler(DecorateHandler(), _ctx(actor), _cmd(character.id, {}))

    assert result.ok
    decoration = _decorations_in(actor.world, room)[0]
    assert decoration.get_component(DecorationComponent).kind == "lantern"


def test_decorate_hangs_a_held_item():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    item = spawn_entity(
        actor.world, [IdentityComponent(name="cloth", kind="item"), PortableComponent()]
    )
    _hold(character, item)

    result = execute_handler(
        DecorateHandler(),
        _ctx(actor),
        _cmd(character.id, {"kind": "garland", "item_id": str(item.id)}),
    )

    assert result.ok
    assert item.has_component(DecorationComponent)
    # It moved out of the inventory and into the room.
    assert item.id not in contents(character)
    assert item.id in contents(room)


def test_decorate_rejects_invalid_character():
    actor = WorldActor()
    result = execute_handler(DecorateHandler(), _ctx(actor), _cmd("???", {}))
    assert not result.ok
    assert result.reason == "invalid character id"


def test_decorate_rejects_missing_character():
    actor = WorldActor()
    result = execute_handler(DecorateHandler(), _ctx(actor), _cmd("entity_9999", {}))
    assert not result.ok
    assert result.reason == "character does not exist"


def test_decorate_rejects_character_without_a_room():
    actor = WorldActor()
    character = spawn_entity(
        actor.world, [IdentityComponent(name="drifter", kind="character"), CharacterComponent()]
    )
    result = execute_handler(DecorateHandler(), _ctx(actor), _cmd(character.id, {}))
    assert not result.ok
    assert result.reason == "you are not in a room"


def test_decorate_rejects_invalid_item():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    result = execute_handler(DecorateHandler(), _ctx(actor), _cmd(character.id, {"item_id": "???"}))
    assert not result.ok
    assert result.reason == "invalid item id"


def test_decorate_rejects_missing_item():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    result = execute_handler(
        DecorateHandler(), _ctx(actor), _cmd(character.id, {"item_id": "entity_9999"})
    )
    assert not result.ok
    assert result.reason == "item does not exist"


def test_decorate_rejects_unheld_item():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    item = spawn_entity(
        actor.world, [IdentityComponent(name="cloth", kind="item"), PortableComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), item.id)  # on the floor

    result = execute_handler(
        DecorateHandler(), _ctx(actor), _cmd(character.id, {"item_id": str(item.id)})
    )

    assert not result.ok
    assert result.reason == "you are not holding that item"


# -- festivity + fragments --------------------------------------------------------------


def test_room_festivity_sums_decoration_values():
    actor = WorldActor()
    room = _room(actor.world)
    spawn_decoration(actor.world, room_id=room.id, kind="lantern", festive=1.0)
    spawn_decoration(actor.world, room_id=room.id, kind="banner", festive=2.5)

    assert room_festivity(actor.world, room) == 3.5


def test_decoration_fragment_lists_room_decorations():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    spawn_decoration(actor.world, room_id=room.id, kind="lantern")

    lines = decoration_fragments(actor.world, character)

    assert lines == ["A festive lantern decorates the room."]


def test_decoration_fragment_empty_in_a_bare_room():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)

    assert decoration_fragments(actor.world, character) == []


def test_decoration_fragment_empty_for_none_character():
    actor = WorldActor()
    assert decoration_fragments(actor.world, None) == []


def test_decoration_fragment_empty_for_roomless_character():
    actor = WorldActor()
    character = spawn_entity(
        actor.world, [IdentityComponent(name="drifter", kind="character"), CharacterComponent()]
    )
    assert decoration_fragments(actor.world, character) == []
