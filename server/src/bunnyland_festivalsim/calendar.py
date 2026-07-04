"""The calendar of festivals.

A :class:`FestivalConsequence` reads the world clock every tick, derives the current day
and season with the core :func:`~bunnyland.mechanics.environment.time_of_day` helper, and
**opens and closes festivals on a fixed schedule**. The current festival is stored as the
singleton :class:`~bunnyland_festivalsim.components.FestivalComponent` on the world clock
entity (the same place the core calendar/time-of-day singletons live), and each transition
emits a world-visible :class:`FestivalOpenedEvent` or :class:`FestivalClosedEvent`.

The schedule is **deterministic**: it is a function of the day number alone, never of wall
clock time or randomness, so a world replays identically. Festivals are keyed to a season
and a day-of-season window, so they recur every game-year.
"""

from __future__ import annotations

from functools import partial

from bunnyland.core.components import WorldClockComponent
from bunnyland.core.ecs import replace_component
from bunnyland.core.events import DomainEvent, EventVisibility, event_base
from bunnyland.mechanics.environment import DAYS_PER_SEASON, time_of_day
from bunnyland.prompts.context import ComponentPromptContext
from pydantic.dataclasses import dataclass
from relics import Entity, World

from .components import FestivalComponent

_event_base = partial(event_base, default_visibility=EventVisibility.PUBLIC)


@dataclass(frozen=True)
class FestivalDefinition:
    """One recurring festival: it opens on ``start_day`` of ``season`` for ``duration`` days."""

    key: str
    name: str
    season: str
    start_day: int
    duration: int
    mood_lift: float


#: The recurring festival calendar. Sorted by key so lookups are order-independent. Windows
#: within a season never overlap, so at most one festival is active on any given day.
FESTIVAL_SCHEDULE: tuple[FestivalDefinition, ...] = (
    FestivalDefinition("harvest-fair", "Harvest Fair", "autumn", start_day=8, duration=4,
                       mood_lift=0.8),
    FestivalDefinition("high-summer", "High Summer", "summer", start_day=14, duration=3,
                       mood_lift=0.7),
    FestivalDefinition("midwinter", "Midwinter", "winter", start_day=24, duration=5,
                       mood_lift=1.0),
    FestivalDefinition("spring-bloom", "Spring Bloom", "spring", start_day=3, duration=3,
                       mood_lift=0.6),
)


class FestivalOpenedEvent(DomainEvent):
    """A scheduled festival opened."""

    key: str
    name: str
    season: str


class FestivalClosedEvent(DomainEvent):
    """A festival's window ended and it closed."""

    key: str


def day_of_season(day: int) -> int:
    """The 1-based day within the current season for an absolute day number."""
    return (day - 1) % DAYS_PER_SEASON + 1


def scheduled_festival(day: int, season: str) -> FestivalDefinition | None:
    """The festival scheduled for ``(day, season)``, or ``None`` if none is active."""
    within = day_of_season(day)
    for definition in sorted(FESTIVAL_SCHEDULE, key=lambda d: d.key):
        if definition.season != season:
            continue
        if definition.start_day <= within < definition.start_day + definition.duration:
            return definition
    return None


def _clock_entity(world: World) -> Entity | None:
    clocks = list(world.query().with_all([WorldClockComponent]).execute_entities())
    return clocks[0] if clocks else None


def active_festival(world: World) -> FestivalComponent | None:
    """The festival currently underway, read off the world clock singleton, or ``None``."""
    clock = _clock_entity(world)
    if clock is None or not clock.has_component(FestivalComponent):
        return None
    festival = clock.get_component(FestivalComponent)
    return festival if festival.key else None


class FestivalConsequence:
    """Open and close festivals as the world clock crosses their scheduled windows."""

    def process(self, world: World, epoch: int) -> list[DomainEvent]:
        clock = _clock_entity(world)
        if clock is None:
            return []
        seconds = clock.get_component(WorldClockComponent).game_time_seconds
        day, _hour, _phase, season = time_of_day(seconds)
        desired = scheduled_festival(day, season)
        current = (
            clock.get_component(FestivalComponent)
            if clock.has_component(FestivalComponent)
            else None
        )
        current_key = current.key if current is not None else ""
        desired_key = desired.key if desired is not None else ""
        if desired_key == current_key:
            return []

        events: list[DomainEvent] = []
        if current_key:
            events.append(FestivalClosedEvent(**_event_base(epoch, key=current_key)))
        if desired is not None:
            replace_component(
                clock,
                FestivalComponent(
                    key=desired.key,
                    name=desired.name,
                    season=desired.season,
                    mood_lift=desired.mood_lift,
                    opened_day=day,
                ),
            )
            events.append(
                FestivalOpenedEvent(
                    **_event_base(epoch, key=desired.key, name=desired.name, season=desired.season)
                )
            )
        else:
            clock.remove_component(FestivalComponent)
        return events


def festival_fragments(world: World, character) -> list[str]:
    """Announce the current festival in every prompt."""
    clock = _clock_entity(world)
    if clock is None or not clock.has_component(FestivalComponent):
        return []
    ctx = ComponentPromptContext.for_entity(world, clock)
    return sorted(clock.get_component(FestivalComponent).prompt_fragments(ctx))


__all__ = [
    "FESTIVAL_SCHEDULE",
    "FestivalClosedEvent",
    "FestivalConsequence",
    "FestivalDefinition",
    "FestivalOpenedEvent",
    "active_festival",
    "day_of_season",
    "festival_fragments",
    "scheduled_festival",
]
