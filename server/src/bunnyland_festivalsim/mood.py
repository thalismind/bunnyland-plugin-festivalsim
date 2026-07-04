"""Seasonal mood: an active festival lifts everyone's spirits.

While a festival is underway, :class:`SeasonalMoodConsequence` nudges every active
character's :class:`~bunnyland.core.components.AffectComponent` a little brighter each tick —
raising valence (pleasantness) and sociability toward a festive cap. The lift is capped so
mood does not grow without bound, and stops entirely once the festival closes. Suspended and
dead characters are left out, matching the rest of the engine's harmful/beneficial-tick
exclusions.
"""

from __future__ import annotations

from dataclasses import replace

from bunnyland.core import (
    AffectComponent,
    DeadComponent,
    SuspendedComponent,
)
from bunnyland.core.ecs import replace_component
from bunnyland.core.events import DomainEvent
from relics import World

from .calendar import active_festival

#: Festive ceilings the lift raises valence/sociability toward (in AffectVector units).
FESTIVE_VALENCE_CAP = 5.0
FESTIVE_SOCIABILITY_CAP = 5.0


class SeasonalMoodConsequence:
    """Brighten every active character's mood a little each tick while a festival runs."""

    def __init__(
        self,
        *,
        valence_cap: float = FESTIVE_VALENCE_CAP,
        sociability_cap: float = FESTIVE_SOCIABILITY_CAP,
    ):
        self.valence_cap = valence_cap
        self.sociability_cap = sociability_cap

    def process(self, world: World, epoch: int) -> list[DomainEvent]:
        festival = active_festival(world)
        if festival is None:
            return []
        lift = festival.mood_lift
        for character in list(world.query().with_all([AffectComponent]).execute_entities()):
            if character.has_component(SuspendedComponent) or character.has_component(
                DeadComponent
            ):
                continue
            self._lift(character, lift)
        return []

    def _lift(self, character, lift: float) -> None:
        affect = character.get_component(AffectComponent)
        current = affect.current
        new_valence = min(self.valence_cap, current.valence + lift)
        new_sociability = min(self.sociability_cap, current.sociability + lift)
        if new_valence == current.valence and new_sociability == current.sociability:
            return
        updated = replace(current, valence=new_valence, sociability=new_sociability)
        replace_component(character, replace(affect, current=updated))


__all__ = [
    "FESTIVE_SOCIABILITY_CAP",
    "FESTIVE_VALENCE_CAP",
    "SeasonalMoodConsequence",
]
