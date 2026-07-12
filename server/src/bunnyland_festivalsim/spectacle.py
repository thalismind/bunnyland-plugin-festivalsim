"""Spectacle: fireworks, and a meteor-shower tie-in to starsim.

Fireworks are wholly self-contained: a character ``launch-fireworks`` in their room, everyone
present is lifted by the sight (affect), and the display is written to world history and
marked for an imagegen picture.

The **meteor-shower spectacle** is a *light, optional* synergy with ``starsim``. When starsim
is loaded, a meteor shower overhead during a hosted festival becomes a shared spectacle;
when it is not loaded the feature simply stays off (and says so once, in the log). starsim is
declared as a ``recommends`` — never a hard dependency — so festivalsim runs standalone.
"""

from __future__ import annotations

import logging

from bunnyland.core import (
    AffectComponent,
    AffectDelta,
    ContainmentMode,
    Contains,
    HasThought,
    IdentityComponent,
    RoomComponent,
    ThoughtComponent,
    contents,
    spawn_entity,
)
from bunnyland.core.actions import ActionDefinition, ActionEffort, effort_cost
from bunnyland.core.commands import Lane, SubmittedCommand
from bunnyland.core.components import WorldClockComponent
from bunnyland.core.events import DomainEvent, EventVisibility, event_base
from bunnyland.core.handlers import (
    HandlerContext,
    HandlerResult,
    ok,
    rejected,
    require_character,
)
from bunnyland.foundation.environment.mechanics import time_of_day
from bunnyland.foundation.history.mechanics import record_world_history
from bunnyland.imagegen import ImagePurpose, ImageRequestComponent
from bunnyland.prompts.context import ComponentPromptContext
from pydantic.dataclasses import dataclass
from relics import Component, Entity, World

from .hosting import HostedFestivalComponent
from .spatial import room_of

LOG = logging.getLogger(__name__)

#: The name starsim gives its meteor-shower celestial event.
METEOR_SHOWER = "meteor shower"
#: The wonder a spectacle stirs in everyone who sees it.
SPECTACLE_JOY = AffectDelta(valence=5.0, arousal=3.0, stress=-2.0, curiosity=4.0)
_JOY_TTL_SECONDS = 2 * 3600


@dataclass(frozen=True)
class SpectacleComponent(Component):
    """A dazzling display resting over a room (fireworks, a meteor shower)."""

    kind: str = "fireworks"
    brilliance: float = 1.0
    day: int = 0

    def prompt_fragments(self, ctx: ComponentPromptContext) -> tuple[str, ...]:
        return (f"A {self.kind} dazzles overhead.",)


class FireworksLaunchedEvent(DomainEvent):
    """A character set off fireworks."""

    spectacle_id: str
    launcher_id: str


class MeteorShowerSpectacleEvent(DomainEvent):
    """A meteor shower became a festival spectacle."""

    spectacle_id: str
    festival_id: str
    day: int


def _starsim_celestial_resolver():
    """Return starsim's ``celestial_event_for``, or ``None`` when starsim is not loaded."""
    try:
        from bunnyland_starsim.celestial import celestial_event_for
    except ImportError:
        return None
    return celestial_event_for  # pragma: no cover - exercised only with starsim installed


def meteor_shower_overhead(day: int, *, resolver=None) -> bool:
    """Whether a meteor shower is overhead on ``day`` (always ``False`` without starsim)."""
    resolve = resolver if resolver is not None else _starsim_celestial_resolver()
    if resolve is None:
        return False
    return resolve(day) == METEOR_SHOWER


def spawn_spectacle(
    world: World, *, room_id, kind: str = "fireworks", brilliance: float = 1.0, day: int = 0
) -> Entity:
    """Spawn a spectacle over ``room_id``."""
    spectacle = spawn_entity(
        world,
        [
            IdentityComponent(name=kind, kind="spectacle", tags=("festivalsim",)),
            SpectacleComponent(kind=kind, brilliance=brilliance, day=day),
        ],
    )
    if world.has_entity(room_id):
        world.get_entity(room_id).add_relationship(
            Contains(mode=ContainmentMode.ROOM_CONTENT), spectacle.id
        )
    return spectacle


def _dazzle_room(world: World, room: Entity, epoch: int) -> None:
    """Lift the mood of every character present in ``room``."""
    for entity_id in contents(room):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)
        if not entity.has_component(AffectComponent):
            continue
        thought = spawn_entity(
            world,
            [
                ThoughtComponent(
                    label="wonder",
                    text="The lights bloom across the sky.",
                    affect_delta=SPECTACLE_JOY,
                    created_at_epoch=epoch,
                    expires_at_epoch=epoch + _JOY_TTL_SECONDS,
                )
            ],
        )
        entity.add_relationship(HasThought(), thought.id)


class LaunchFireworksHandler:
    """Set off fireworks in your room, dazzling everyone present."""

    command_type = "launch-fireworks"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        launcher_id, launcher, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        room = room_of(ctx.world, launcher_id)
        if room is None:
            return rejected("you are not in a room")

        spectacle = spawn_spectacle(ctx.world, room_id=room.id, kind="fireworks")
        _dazzle_room(ctx.world, room, ctx.epoch)
        event = FireworksLaunchedEvent(
            **ctx.event_base(
                visibility=EventVisibility.ROOM,
                actor_id=str(launcher_id),
                room_id=str(room.id),
                target_ids=(str(spectacle.id),),
                spectacle_id=str(spectacle.id),
                launcher_id=str(launcher_id),
            )
        )
        record = record_world_history(
            ctx.world,
            summary=f"{_name(launcher)} lit up the sky with fireworks.",
            source_event_id=event.event_id,
            event_type="FireworksLaunchedEvent",
            created_at_epoch=ctx.epoch,
            location_id=str(room.id),
            actor_ids=(str(launcher_id),),
            target_ids=(str(spectacle.id),),
            tags=("fireworks", "spectacle", "celebration"),
            salience=0.8,
        )
        if record is not None:
            record.add_component(
                ImageRequestComponent(
                    purpose=ImagePurpose.EVENT.value,
                    requested_at_epoch=ctx.epoch,
                    requested_by=str(launcher_id),
                )
            )
        return ok(event)


class MeteorShowerSpectacleConsequence:
    """Turn a meteor shower overhead into a spectacle over each hosted festival.

    Optional starsim synergy: with starsim absent, ``meteor_shower_overhead`` is always
    ``False`` and this consequence quietly does nothing but note the disabled feature once.
    """

    def __init__(
        self, *, overhead=meteor_shower_overhead, resolver_probe=_starsim_celestial_resolver
    ):
        self._overhead = overhead
        self._resolver_probe = resolver_probe
        self._warned = False

    def process(self, world: World, epoch: int) -> list[DomainEvent]:
        clock = _clock(world)
        if clock is None:
            return []
        day, _hour, _phase, _season = time_of_day(
            clock.get_component(WorldClockComponent).game_time_seconds
        )
        if not self._overhead(day):
            self._note_disabled()
            return []
        events: list[DomainEvent] = []
        for festival in _open_hosted_festivals(world):
            room = room_of(world, festival.id)
            if room is None or _has_meteor_spectacle(world, room, day):
                continue
            spectacle = spawn_spectacle(world, room_id=room.id, kind=METEOR_SHOWER, day=day)
            _dazzle_room(world, room, epoch)
            events.append(
                MeteorShowerSpectacleEvent(
                    **event_base(
                        epoch,
                        visibility=EventVisibility.ROOM,
                        room_id=str(room.id),
                        target_ids=(str(spectacle.id),),
                        spectacle_id=str(spectacle.id),
                        festival_id=str(festival.id),
                        day=day,
                    )
                )
            )
        return events

    def _note_disabled(self) -> None:
        if self._warned:
            return
        self._warned = True
        if self._resolver_probe() is None:
            LOG.warning("starsim not loaded: meteor-shower festival spectacle stays disabled")


def _clock(world: World) -> Entity | None:
    clocks = list(world.query().with_all([WorldClockComponent]).execute_entities())
    return clocks[0] if clocks else None


def _open_hosted_festivals(world: World) -> list[Entity]:
    festivals = [
        entity
        for entity in world.query().with_all([HostedFestivalComponent]).execute_entities()
        if not entity.get_component(HostedFestivalComponent).ended
    ]
    return sorted(festivals, key=lambda entity: str(entity.id))


def _has_meteor_spectacle(world: World, room: Entity, day: int) -> bool:
    for entity_id in contents(room):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)
        if entity.has_component(SpectacleComponent):
            spectacle = entity.get_component(SpectacleComponent)
            if spectacle.kind == METEOR_SHOWER and spectacle.day == day:
                return True
    return False


def _name(entity: Entity) -> str:
    if entity.has_component(IdentityComponent):
        return entity.get_component(IdentityComponent).name
    return "someone"


LAUNCH_FIREWORKS_DEF = ActionDefinition(
    command_type="launch-fireworks",
    title="Launch fireworks",
    description="Set off a fireworks display in the room you are in.",
    lane=Lane.WORLD,
    cost=effort_cost(action=ActionEffort.EXTENDED),
    arguments={},
)

SPECTACLE_ACTION_DEFINITIONS = (LAUNCH_FIREWORKS_DEF,)
SPECTACLE_ACTION_HANDLERS = (LaunchFireworksHandler,)


def spectacle_fragments(world: World, character) -> list[str]:
    """Describe any spectacle over the character's room."""
    if character is None:
        return []
    room = room_of(world, character.id)
    if room is None or not room.has_component(RoomComponent):
        return []
    lines: list[str] = []
    for entity_id in contents(room):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)
        if entity.has_component(SpectacleComponent):
            ctx = ComponentPromptContext.for_entity(world, entity, room=room)
            lines.extend(entity.get_component(SpectacleComponent).prompt_fragments(ctx))
    return sorted(dict.fromkeys(lines))


__all__ = [
    "LAUNCH_FIREWORKS_DEF",
    "METEOR_SHOWER",
    "SPECTACLE_ACTION_DEFINITIONS",
    "SPECTACLE_ACTION_HANDLERS",
    "SPECTACLE_JOY",
    "FireworksLaunchedEvent",
    "LaunchFireworksHandler",
    "MeteorShowerSpectacleConsequence",
    "MeteorShowerSpectacleEvent",
    "SpectacleComponent",
    "meteor_shower_overhead",
    "spawn_spectacle",
    "spectacle_fragments",
]
