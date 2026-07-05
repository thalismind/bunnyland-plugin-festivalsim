"""The festival as a shared stage: consume other packs' achievements as contest entries.

Festivalsim owns the ``ContestEntry`` connector surface (see :mod:`.contests`). This module is
the *consuming* half: while a festival is live, notable achievements from sibling packs — an
anglersim derby catch, a hearthsim bake, a bardsim gig, a wildsim forage haul — are folded
into the festival's open contest automatically.

This is **light, optional synergy**. The reactor listens on the actor bus and recognises those
events purely by name, so festivalsim needs no import of and no hard dependency on any sibling
pack: with none loaded, none of these events ever fire and the festival simply runs with its
own local entries. Sibling packs are declared as ``recommends``, never ``requires``.
"""

from __future__ import annotations

from bunnyland.core import parse_entity_id
from bunnyland.core.events import DomainEvent
from bunnyland.core.world_actor import WorldActor

from .calendar import active_festival
from .components import ContestComponent
from .contests import register_contest_entry
from .hosting import HostedFestivalComponent

#: Sibling-pack event type names -> (matching contest kind, default entry score). Matching by
#: name keeps the connector import-free and safe when those packs are not loaded.
EXTERNAL_ENTRY_SOURCES: dict[str, tuple[str, float]] = {
    "LegendaryCatchEvent": ("derby", 3.0),  # anglersim
    "FishCaughtEvent": ("derby", 1.0),  # anglersim
    "MealCookedEvent": ("bake-off", 2.0),  # hearthsim
    "PerformedEvent": ("gig", 2.0),  # bardsim
    "ForagedEvent": ("biggest-game", 1.0),  # wildsim
}


def festival_is_live(world) -> bool:
    """True when a calendar festival or a hosted festival is currently underway."""
    if active_festival(world) is not None:
        return True
    return any(
        not entity.get_component(HostedFestivalComponent).ended
        for entity in world.query().with_all([HostedFestivalComponent]).execute_entities()
    )


def _open_contests(world) -> list:
    contests = [
        entity
        for entity in world.query().with_all([ContestComponent]).execute_entities()
        if entity.get_component(ContestComponent).is_open
    ]
    return sorted(contests, key=lambda entity: str(entity.id))


def _target_contest(world, kind: str):
    """The open contest for ``kind`` (or the first open contest), or ``None``."""
    contests = _open_contests(world)
    for contest in contests:
        if contest.get_component(ContestComponent).kind == kind:
            return contest
    return contests[0] if contests else None


class FestivalStageReactor:
    """Fold sibling packs' achievement events into a live festival's open contest."""

    def subscribe(self, actor: WorldActor) -> None:
        self._actor = actor
        actor.bus.subscribe(DomainEvent, self._on_event)

    def _on_event(self, event: DomainEvent) -> None:
        source = EXTERNAL_ENTRY_SOURCES.get(type(event).__name__)
        if source is None:
            return
        world = self._actor.world
        if not festival_is_live(world):
            return
        kind, score = source
        contest = _target_contest(world, kind)
        if contest is None:
            return
        entrant_id = event.actor_id or ""
        entry_raw = event.target_ids[0] if event.target_ids else event.actor_id
        entry_id = parse_entity_id(entry_raw) if entry_raw else None
        if entry_id is None or not world.has_entity(entry_id):
            return
        register_contest_entry(
            world, contest, entry_id, entrant_id=entrant_id, score=score, epoch=event.world_epoch
        )


__all__ = [
    "EXTERNAL_ENTRY_SOURCES",
    "FestivalStageReactor",
    "festival_is_live",
]
