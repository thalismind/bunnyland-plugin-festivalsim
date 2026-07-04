"""World-generation enrichment: dress a town square as a festival ground.

When the generator emits a room that reads like a gathering place (a square, plaza, market,
green, or commons), this hook seeds it with festival decorations and a contest so generated
worlds already have somewhere for a festival to happen — without the core generator knowing
this plugin exists. Detection is text-based and deterministic; nothing here is random.
"""

from __future__ import annotations

from bunnyland.core import contents
from bunnyland.core.ecs import parse_entity_id
from bunnyland.core.events import RoomGeneratedEvent
from bunnyland.core.world_actor import WorldActor

from .components import ContestComponent, DecorationComponent
from .contests import spawn_contest
from .decorations import spawn_decoration

#: Room text that marks a generated room as a gathering place / festival ground.
SQUARE_TERMS = (
    "square",
    "plaza",
    "market",
    "marketplace",
    "green",
    "commons",
    "fairground",
    "festival",
    "town center",
    "town centre",
    "piazza",
)

#: Decorations seeded into a town square, in a fixed order for determinism.
SEEDED_DECORATIONS = ("lantern", "banner")


class FestivalWorldgenHook:
    """Seed a festival ground (decorations + a contest) into generated town squares."""

    def subscribe(self, actor: WorldActor) -> None:
        self._actor = actor
        actor.bus.subscribe(RoomGeneratedEvent, self._on_room)

    def _on_room(self, event: RoomGeneratedEvent) -> None:
        entity_id = parse_entity_id(event.entity_id)
        if entity_id is None or not self._actor.world.has_entity(entity_id):
            return
        room = self._actor.world.get_entity(entity_id)
        if not _is_town_square(event):
            return
        world = self._actor.world
        # Idempotent: never dress the same room twice.
        for existing_id in contents(room):
            if not world.has_entity(existing_id):
                continue
            existing = world.get_entity(existing_id)
            if existing.has_component(DecorationComponent) or existing.has_component(
                ContestComponent
            ):
                return
        for kind in SEEDED_DECORATIONS:
            spawn_decoration(world, room_id=room.id, kind=kind)
        spawn_contest(world, room_id=room.id, kind="bake-off", title="Village Bake-Off")


def _is_town_square(event: RoomGeneratedEvent) -> bool:
    text = " ".join(
        (
            event.room_key,
            event.biome,
            event.generation.description,
            *event.generation.tags,
        )
    ).casefold()
    return any(term in text for term in SQUARE_TERMS)


__all__ = ["SEEDED_DECORATIONS", "SQUARE_TERMS", "FestivalWorldgenHook"]
