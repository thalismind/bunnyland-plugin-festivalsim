"""Runtime wiring: register the per-tick festival consequences on a world actor."""

from __future__ import annotations

from bunnyland.core.world_actor import WorldActor

from .calendar import FestivalConsequence
from .mood import SeasonalMoodConsequence


def install_festivalsim(actor: WorldActor) -> None:
    """Register the calendar and seasonal-mood consequences (a ``service_factories`` entry)."""
    actor.register_consequence(FestivalConsequence())
    actor.register_consequence(SeasonalMoodConsequence())


__all__ = ["install_festivalsim"]
