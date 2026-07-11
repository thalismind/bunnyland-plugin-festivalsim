"""Shared festival components.

Three components carry the pack's persistent state:

- :class:`FestivalComponent` is the **singleton** current-festival marker. Like the core
  Foundation ``CalendarComponent``, it lives on the world clock
  entity and is set/cleared by :class:`~bunnyland_festivalsim.calendar.FestivalConsequence`
  as the calendar opens and closes festivals.
- :class:`DecorationComponent` sits on a placed decoration entity (a lantern, a banner)
  resting in a room and raises that room's festive mood.
- :class:`ContestComponent` sits on a contest entity (a bake-off, a biggest-fish, a
  best-song) resting in a room. It is the **open hook** other packs plug into: they attach
  :class:`~bunnyland_festivalsim.contests.ContestEntry` edges to it.

Components are immutable; handlers and consequences swap whole values with
``replace_component(entity, replace(component, ...))``.
"""

from __future__ import annotations

from bunnyland.prompts.context import ComponentPromptContext
from pydantic.dataclasses import dataclass
from relics import Component


@dataclass(frozen=True)
class FestivalComponent(Component):
    """The festival currently underway (a world singleton on the clock entity)."""

    key: str = ""
    name: str = ""
    season: str = ""
    #: Per-tick valence lift the festival grants every present character's mood.
    mood_lift: float = 0.0
    opened_day: int = 0

    def prompt_fragments(self, ctx: ComponentPromptContext) -> tuple[str, ...]:
        if not self.key:
            return ()
        return (f"The {self.name} festival is underway ({self.season}).",)


@dataclass(frozen=True)
class DecorationComponent(Component):
    """A festive decoration placed in a room. ``festive`` is its mood contribution."""

    kind: str = "lantern"
    festive: float = 1.0

    def prompt_fragments(self, ctx: ComponentPromptContext) -> tuple[str, ...]:
        return (f"A festive {self.kind} decorates the room.",)


@dataclass(frozen=True)
class ContestComponent(Component):
    """A contest accepting entries. Other packs register entries as ``ContestEntry`` edges."""

    kind: str = "bake-off"
    title: str = ""
    is_open: bool = True
    winner_id: str = ""

    def prompt_fragments(self, ctx: ComponentPromptContext) -> tuple[str, ...]:
        label = self.title or self.kind
        if self.is_open:
            return (f"A {label} contest here is accepting entries.",)
        if self.winner_id:
            return (f"The {label} contest here has been judged.",)
        return (f"The {label} contest here is closed.",)


__all__ = [
    "ContestComponent",
    "DecorationComponent",
    "FestivalComponent",
]
