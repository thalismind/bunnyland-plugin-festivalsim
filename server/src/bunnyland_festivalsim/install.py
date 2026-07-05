"""Runtime wiring: register the per-tick festival consequences on a world actor."""

from __future__ import annotations

from bunnyland.core.world_actor import WorldActor

from .calendar import FestivalConsequence
from .mood import SeasonalMoodConsequence
from .spectacle import MeteorShowerSpectacleConsequence
from .stage import FestivalStageReactor


def install_festivalsim(actor: WorldActor) -> None:
    """Register the festival consequences and the shared-stage reactor (a ``service_factories``
    entry)."""
    actor.register_consequence(FestivalConsequence())
    actor.register_consequence(SeasonalMoodConsequence())
    actor.register_consequence(MeteorShowerSpectacleConsequence())
    FestivalStageReactor().subscribe(actor)


__all__ = ["install_festivalsim"]
