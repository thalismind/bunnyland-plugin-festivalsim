import asyncio

from bunnyland.core import Contains, WorldActor
from bunnyland.plugins import apply_plugins
from bunnyland.worldgen import RoomSpec, WorldProposal, instantiate

from bunnyland_festivalsim import ContestComponent, DecorationComponent
from bunnyland_festivalsim.plugin import bunnyland_plugins as _plugins


def _room(spec):
    actor = WorldActor()
    apply_plugins(_plugins(), actor)
    result = asyncio.run(instantiate(actor, WorldProposal(seed="seed", rooms=[spec])))
    return actor, actor.world.get_entity(result.rooms[spec.key])


def _children(actor, room, component):
    return [
        actor.world.get_entity(target)
        for _edge, target in room.get_relationships(Contains)
        if actor.world.get_entity(target).has_component(component)
    ]


def test_town_square_is_dressed_with_decorations_and_a_contest():
    actor, room = _room(RoomSpec(key="town-square", title="Town Square"))
    decorations = _children(actor, room, DecorationComponent)
    contests = _children(actor, room, ContestComponent)
    assert sorted(item.get_component(DecorationComponent).kind for item in decorations) == [
        "banner",
        "lantern",
    ]
    assert len(contests) == 1
    assert contests[0].get_component(ContestComponent).title == "Village Bake-Off"


def test_plain_room_is_not_dressed():
    actor, room = _room(RoomSpec(key="cave", title="Quiet Cave"))
    assert _children(actor, room, DecorationComponent) == []
    assert _children(actor, room, ContestComponent) == []
