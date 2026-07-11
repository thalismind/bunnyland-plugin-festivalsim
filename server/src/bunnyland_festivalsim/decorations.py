"""Decorations: hang lanterns and banners that raise a room's festive mood.

The ``decorate`` verb places a :class:`~bunnyland_festivalsim.components.DecorationComponent`
in the room the character stands in — either by spawning a fresh decoration or by hanging a
held item (which is moved from the character's inventory into the room). A room's *festivity*
is the summed ``festive`` value of the decorations resting in it, surfaced in prompts and
reused as an ambience signal by the rest of the pack.

Verb validation follows the project order: invalid id -> missing entity -> not held ->
apply.
"""

from __future__ import annotations

from bunnyland.core import (
    ContainmentMode,
    Contains,
    IdentityComponent,
    contents,
    remove_from_container,
    spawn_entity,
)
from bunnyland.core.actions import ActionArgument, ActionDefinition
from bunnyland.core.commands import CommandCost, Lane, SubmittedCommand
from bunnyland.core.ecs import replace_component
from bunnyland.core.events import DomainEvent, EventVisibility
from bunnyland.core.handlers import (
    HandlerContext,
    HandlerResult,
    ok,
    rejected,
    require_character,
    require_entity,
)
from bunnyland.prompts.context import ComponentPromptContext
from relics import Entity, World

from .components import DecorationComponent
from .spatial import holder_of, room_of


class RoomDecoratedEvent(DomainEvent):
    """A character hung a decoration in a room."""

    room_id_decorated: str
    decoration_id: str
    kind: str


def _link_into_room(world: World, item: Entity, room_id) -> None:
    if room_id is None or not world.has_entity(room_id):
        return
    world.get_entity(room_id).add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), item.id)


def spawn_decoration(
    world: World, *, room_id=None, kind: str = "lantern", festive: float = 1.0
) -> Entity:
    """Spawn a decoration entity, optionally placed in ``room_id``."""
    decoration = spawn_entity(
        world,
        [
            IdentityComponent(name=kind, kind="decoration", tags=("festivalsim",)),
            DecorationComponent(kind=kind, festive=festive),
        ],
    )
    _link_into_room(world, decoration, room_id)
    return decoration


def room_festivity(world: World, room: Entity) -> float:
    """The summed festive value of decorations resting in ``room``."""
    total = 0.0
    for entity_id in contents(room):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)
        if entity.has_component(DecorationComponent):
            total += entity.get_component(DecorationComponent).festive
    return total


class DecorateHandler:
    """Hang a decoration in the room you stand in (a fresh one, or a held item)."""

    command_type = "decorate"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        character_id, _character, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        room = room_of(ctx.world, character_id)
        if room is None:
            return rejected("you are not in a room")
        kind = str(command.payload.get("kind", "lantern"))

        raw_item = command.payload.get("item_id")
        if raw_item is not None:
            item_id, item, rejection = require_entity(
                ctx,
                raw_item,
                invalid_reason="invalid item id",
                missing_reason="item does not exist",
            )
            if rejection is not None:
                return rejection
            holder = holder_of(ctx.world, item_id)
            if holder is None or holder.id != character_id:
                return rejected("you are not holding that item")
            remove_from_container(ctx.world, item_id)
            replace_component(item, DecorationComponent(kind=kind))
            _link_into_room(ctx.world, item, room.id)
            decoration = item
        else:
            decoration = spawn_decoration(ctx.world, room_id=room.id, kind=kind)

        return ok(
            RoomDecoratedEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=str(room.id),
                    target_ids=(str(decoration.id),),
                    room_id_decorated=str(room.id),
                    decoration_id=str(decoration.id),
                    kind=kind,
                )
            )
        )


DECORATE_DEF = ActionDefinition(
    command_type="decorate",
    title="Decorate",
    description="Hang a festive decoration in the room you are in.",
    lane=Lane.WORLD,
    cost=CommandCost(action=1),
    arguments={
        "kind": ActionArgument(
            title="Kind",
            description="What to hang (lantern, banner, garland…); defaults to a lantern.",
            kind="string",
        ),
        "item_id": ActionArgument(
            title="Item",
            description="Optional held item to hang as the decoration instead of a fresh one.",
            kind="entity",
        ),
    },
)

DECORATION_ACTION_DEFINITIONS = (DECORATE_DEF,)
DECORATION_ACTION_HANDLERS = (DecorateHandler,)


def decoration_fragments(world: World, character) -> list[str]:
    """Describe the decorations in the character's room."""
    if character is None:
        return []
    room = room_of(world, character.id)
    if room is None:
        return []
    lines: list[str] = []
    for entity_id in contents(room):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)
        if entity.has_component(DecorationComponent):
            ctx = ComponentPromptContext.for_entity(world, entity, room=room)
            lines.extend(entity.get_component(DecorationComponent).prompt_fragments(ctx))
    return sorted(dict.fromkeys(lines))


__all__ = [
    "DECORATE_DEF",
    "DECORATION_ACTION_DEFINITIONS",
    "DECORATION_ACTION_HANDLERS",
    "DecorateHandler",
    "RoomDecoratedEvent",
    "decoration_fragments",
    "room_festivity",
    "spawn_decoration",
]
