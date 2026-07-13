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
from bunnyland.core.ecs import replace_component
from bunnyland.core.handlers import HandlerContext
from bunnyland.foundation.social.mechanics import bond_between
from conftest import execute_handler

from bunnyland_festivalsim import GiftGivenEvent, GiveGiftHandler
from bunnyland_festivalsim.components import FestivalComponent

EPOCH = 10


def _room(world, *, title="Square"):
    return spawn_entity(world, [RoomComponent(title=title)])


def _character(world, room, name="Vin"):
    character = spawn_entity(
        world, [IdentityComponent(name=name, kind="character"), CharacterComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), character.id)
    return character


def _gift(world, holder, name="pie"):
    item = spawn_entity(world, [IdentityComponent(name=name, kind="item"), PortableComponent()])
    holder.add_relationship(Contains(mode=ContainmentMode.INVENTORY), item.id)
    return item


def _cmd(character_id, payload):
    return build_submitted_command(
        character_id=str(character_id),
        controller_id="ctrl",
        controller_generation=0,
        command_type="give-gift",
        cost=CommandCost(action=1),
        lane=Lane.WORLD,
        payload=payload,
    )


def _ctx(actor):
    return HandlerContext(world=actor.world, epoch=EPOCH)


def _open_festival(actor):
    replace_component(
        actor._clock_entity, FestivalComponent(key="spring-bloom", name="Spring Bloom")
    )


# -- give-gift --------------------------------------------------------------------------


def test_give_gift_transfers_item_and_warms_bond():
    actor = WorldActor()
    room = _room(actor.world)
    giver = _character(actor.world, room, "Vin")
    receiver = _character(actor.world, room, "Kell")
    pie = _gift(actor.world, giver)

    result = execute_handler(
        GiveGiftHandler(),
        _ctx(actor),
        _cmd(giver.id, {"item_id": str(pie.id), "recipient_id": str(receiver.id)}),
    )

    assert result.ok
    assert isinstance(result.events[0], GiftGivenEvent)
    assert pie.id in contents(receiver)
    assert pie.id not in contents(giver)
    assert bond_between(actor.world, giver.id, receiver.id).affinity > 0.0
    assert bond_between(actor.world, receiver.id, giver.id).affinity > 0.0


def test_gift_during_festival_warms_bond_more():
    actor = WorldActor()
    room = _room(actor.world)
    giver = _character(actor.world, room, "Vin")
    receiver = _character(actor.world, room, "Kell")
    _open_festival(actor)
    pie = _gift(actor.world, giver)

    result = execute_handler(
        GiveGiftHandler(),
        _ctx(actor),
        _cmd(giver.id, {"item_id": str(pie.id), "recipient_id": str(receiver.id)}),
    )

    assert result.ok
    assert result.events[0].festival_key == "spring-bloom"
    # Festival affinity (0.2) exceeds the plain gift affinity (0.1).
    assert bond_between(actor.world, giver.id, receiver.id).affinity > 0.15


def test_give_gift_rejects_invalid_giver():
    actor = WorldActor()
    result = execute_handler(
        GiveGiftHandler(),
        _ctx(actor),
        _cmd("???", {"item_id": "entity_1", "recipient_id": "entity_2"}),
    )
    assert not result.ok
    assert result.reason == "invalid character id"


def test_give_gift_rejects_missing_giver():
    actor = WorldActor()
    result = execute_handler(
        GiveGiftHandler(),
        _ctx(actor),
        _cmd("entity_9999", {"item_id": "entity_1", "recipient_id": "entity_2"}),
    )
    assert not result.ok
    assert result.reason == "character does not exist"


def test_give_gift_rejects_invalid_item():
    actor = WorldActor()
    room = _room(actor.world)
    giver = _character(actor.world, room)
    result = execute_handler(
        GiveGiftHandler(),
        _ctx(actor),
        _cmd(giver.id, {"item_id": "???", "recipient_id": "entity_2"}),
    )
    assert not result.ok
    assert result.reason == "invalid item id"


def test_give_gift_rejects_missing_item():
    actor = WorldActor()
    room = _room(actor.world)
    giver = _character(actor.world, room)
    result = execute_handler(
        GiveGiftHandler(),
        _ctx(actor),
        _cmd(giver.id, {"item_id": "entity_9999", "recipient_id": "entity_2"}),
    )
    assert not result.ok
    assert result.reason == "item does not exist"


def test_give_gift_rejects_unheld_item():
    actor = WorldActor()
    room = _room(actor.world)
    giver = _character(actor.world, room, "Vin")
    receiver = _character(actor.world, room, "Kell")
    loose = spawn_entity(
        actor.world, [IdentityComponent(name="pie", kind="item"), PortableComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), loose.id)

    result = execute_handler(
        GiveGiftHandler(),
        _ctx(actor),
        _cmd(giver.id, {"item_id": str(loose.id), "recipient_id": str(receiver.id)}),
    )

    assert not result.ok
    assert result.reason == "you are not holding that gift"


def test_give_gift_rejects_invalid_recipient():
    actor = WorldActor()
    room = _room(actor.world)
    giver = _character(actor.world, room)
    pie = _gift(actor.world, giver)
    result = execute_handler(
        GiveGiftHandler(),
        _ctx(actor),
        _cmd(giver.id, {"item_id": str(pie.id), "recipient_id": "???"}),
    )
    assert not result.ok
    assert result.reason == "invalid recipient id"


def test_give_gift_rejects_missing_recipient():
    actor = WorldActor()
    room = _room(actor.world)
    giver = _character(actor.world, room)
    pie = _gift(actor.world, giver)
    result = execute_handler(
        GiveGiftHandler(),
        _ctx(actor),
        _cmd(giver.id, {"item_id": str(pie.id), "recipient_id": "entity_9999"}),
    )
    assert not result.ok
    assert result.reason == "recipient does not exist"


def test_give_gift_rejects_non_character_recipient():
    actor = WorldActor()
    room = _room(actor.world)
    giver = _character(actor.world, room)
    pie = _gift(actor.world, giver)
    crate = spawn_entity(actor.world, [IdentityComponent(name="crate", kind="item")])
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), crate.id)

    result = execute_handler(
        GiveGiftHandler(),
        _ctx(actor),
        _cmd(giver.id, {"item_id": str(pie.id), "recipient_id": str(crate.id)}),
    )

    assert not result.ok
    assert result.reason == "you can only give gifts to a character"


def test_give_gift_rejects_self_gift():
    actor = WorldActor()
    room = _room(actor.world)
    giver = _character(actor.world, room)
    pie = _gift(actor.world, giver)

    result = execute_handler(
        GiveGiftHandler(),
        _ctx(actor),
        _cmd(giver.id, {"item_id": str(pie.id), "recipient_id": str(giver.id)}),
    )

    assert not result.ok
    assert result.reason == "you cannot gift yourself"


def test_give_gift_rejects_recipient_in_another_room():
    actor = WorldActor()
    room = _room(actor.world)
    other = _room(actor.world, title="Hall")
    giver = _character(actor.world, room, "Vin")
    receiver = _character(actor.world, other, "Kell")
    pie = _gift(actor.world, giver)

    result = execute_handler(
        GiveGiftHandler(),
        _ctx(actor),
        _cmd(giver.id, {"item_id": str(pie.id), "recipient_id": str(receiver.id)}),
    )

    assert not result.ok
    assert result.reason == "they are not here"
