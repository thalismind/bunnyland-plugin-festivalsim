"""Host-your-own festivals: the v2 headline mechanic.

A character can **throw their own festival** anywhere, any day — no waiting for the seasonal
calendar. Hosting spawns a festival entity in the room and, crucially, wires it into the rest
of the world through core systems rather than reinventing them:

- The festival is **registered as a storyteller incident** (a core
  :class:`~bunnyland.foundation.storyteller.mechanics.IncidentComponent`), so a hosted festival is a
  paced, first-class world event the storyteller and other packs can see and react to. Ending
  the festival resolves that incident.
- The festival night is written to **world history** and marked for an **imagegen**
  illustration, so the museum/gossip-sheet can show the party later.
- Relationships use **typed edges**: :class:`Hosts` (host -> festival) and
  :class:`AttendsFestival` (attendee -> festival). *Affective* warmth from attending routes
  through the core :class:`~bunnyland.foundation.social.mechanics.SocialBond` and an affect thought.

Nothing here is random: outcomes are a pure function of the world state and the epoch.
"""

from __future__ import annotations

from dataclasses import replace

from bunnyland.core import (
    AffectDelta,
    ContainmentMode,
    Contains,
    HasThought,
    IdentityComponent,
    ThoughtComponent,
    spawn_entity,
)
from bunnyland.core.actions import ActionArgument, ActionDefinition, ActionEffort, effort_cost
from bunnyland.core.commands import Lane, SubmittedCommand
from bunnyland.core.ecs import entity_name, parse_entity_id, replace_component
from bunnyland.core.events import DomainEvent, EventVisibility
from bunnyland.core.handlers import (
    HandlerContext,
    HandlerResult,
    ok,
    rejected,
    require_character,
    require_entity,
)
from bunnyland.foundation.history.mechanics import record_world_history
from bunnyland.foundation.social.mechanics import adjust_bond
from bunnyland.foundation.storyteller.mechanics import (
    IncidentComponent,
    IncidentResolvedEvent,
    IncidentStartedEvent,
)
from bunnyland.imagegen import ImagePurpose, ImageRequestComponent
from bunnyland.prompts.context import ComponentPromptContext
from pydantic.dataclasses import dataclass
from relics import Edge, Entity, World

from .components import FestivalComponent
from .spatial import room_of

#: The per-tick valence lift a hosted festival contributes (mirrors the calendar festivals).
HOSTED_MOOD_LIFT = 0.7
#: Bond deltas an attendee and host exchange when someone shows up to the party.
ATTEND_AFFINITY = 0.15
ATTEND_FAMILIARITY = 0.1
#: The festive thought an attendee carries away from the party.
ATTEND_JOY = AffectDelta(valence=6.0, stress=-3.0, sociability=5.0)
_JOY_TTL_SECONDS = 4 * 3600
#: The storyteller-incident kind a hosted festival registers as.
FESTIVAL_INCIDENT_KIND = "festival"


@dataclass(frozen=True)
class Hosts(Edge):
    """host character -> the festival they are throwing."""

    theme: str = ""
    opened_epoch: int = 0


@dataclass(frozen=True)
class AttendsFestival(Edge):
    """attendee character -> a festival they have joined."""

    joined_epoch: int = 0


@dataclass(frozen=True)
class HostedFestivalComponent(FestivalComponent):
    """A player-hosted festival (a specialised :class:`FestivalComponent`).

    It reuses the festival singleton's fields but sits on its *own* entity in a room rather
    than the world clock, and adds the host, the storyteller incident it registered, and
    whether it has ended.
    """

    theme: str = "revel"
    host_id: str = ""
    incident_id: str = ""
    ended: bool = False

    def prompt_fragments(self, ctx: ComponentPromptContext) -> tuple[str, ...]:
        if self.ended:
            return (f"The {self.theme} festival here has wound down.",)
        return (f"A {self.theme} festival is in full swing here.",)


class FestivalHostedEvent(DomainEvent):
    """A character threw their own festival."""

    festival_id: str
    host_id: str
    theme: str
    incident_id: str


class FestivalAttendedEvent(DomainEvent):
    """A character joined a hosted festival."""

    festival_id: str
    attendee_id: str
    host_id: str


class FestivalEndedEvent(DomainEvent):
    """A host wound down their festival, resolving its storyteller incident."""

    festival_id: str
    host_id: str
    incident_id: str


def hosted_festivals(world: World) -> list[Entity]:
    """Every hosted-festival entity, newest-id last (deterministic order)."""
    festivals = list(world.query().with_all([HostedFestivalComponent]).execute_entities())
    return sorted(festivals, key=lambda entity: str(entity.id))


def _host_has_open_festival(world: World, host_id) -> bool:
    for festival in hosted_festivals(world):
        component = festival.get_component(HostedFestivalComponent)
        if component.host_id == str(host_id) and not component.ended:
            return True
    return False


def _register_incident(world: World, room: Entity, epoch: int) -> Entity:
    """Register the festival as a first-class storyteller incident in ``room``."""
    incident = spawn_entity(
        world,
        [
            IdentityComponent(name="festival", kind="incident", tags=("festivalsim",)),
            IncidentComponent(
                kind=FESTIVAL_INCIDENT_KIND,
                budget_spent=0.0,
                started_at_epoch=epoch,
                room_id=str(room.id),
            ),
        ],
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), incident.id)
    return incident


def _remember_the_night(
    world: World, *, host: Entity, festival: Entity, room: Entity, event_id: str, epoch: int
) -> None:
    """Write the festival to world history and mark it for an imagegen illustration."""
    where = (
        room.get_component(IdentityComponent).name
        if room.has_component(IdentityComponent)
        else "the square"
    )
    summary = f"{entity_name(host, fallback='someone')} hosted a festival in {where}."
    record = record_world_history(
        world,
        summary=summary,
        source_event_id=event_id,
        event_type="FestivalHostedEvent",
        created_at_epoch=epoch,
        location_id=str(room.id),
        actor_ids=(str(host.id),),
        target_ids=(str(festival.id),),
        tags=("festival", "celebration"),
        salience=0.9,
    )
    if record is not None:
        record.add_component(
            ImageRequestComponent(
                purpose=ImagePurpose.EVENT.value,
                requested_at_epoch=epoch,
                requested_by=str(host.id),
            )
        )


class HostFestivalHandler:
    """Throw a festival in the room you stand in and register it as a world incident."""

    command_type = "host-festival"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        host_id, host, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        room = room_of(ctx.world, host_id)
        if room is None:
            return rejected("you are not in a room")
        if _host_has_open_festival(ctx.world, host_id):
            return rejected("you are already hosting a festival")
        theme = str(command.payload.get("theme", "revel"))

        incident = _register_incident(ctx.world, room, ctx.epoch)
        festival = spawn_entity(
            ctx.world,
            [
                IdentityComponent(name=f"{theme} festival", kind="festival", tags=("festivalsim",)),
                HostedFestivalComponent(
                    key="hosted",
                    name=f"{theme} festival",
                    theme=theme,
                    host_id=str(host_id),
                    incident_id=str(incident.id),
                    mood_lift=HOSTED_MOOD_LIFT,
                    opened_day=ctx.epoch,
                ),
            ],
        )
        room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), festival.id)
        host.add_relationship(Hosts(theme=theme, opened_epoch=ctx.epoch), festival.id)

        hosted = FestivalHostedEvent(
            **ctx.event_base(
                visibility=EventVisibility.ROOM,
                actor_id=str(host_id),
                room_id=str(room.id),
                target_ids=(str(festival.id), str(incident.id)),
                festival_id=str(festival.id),
                host_id=str(host_id),
                theme=theme,
                incident_id=str(incident.id),
            )
        )
        _remember_the_night(
            ctx.world,
            host=host,
            festival=festival,
            room=room,
            event_id=hosted.event_id,
            epoch=ctx.epoch,
        )
        started = IncidentStartedEvent(
            **ctx.event_base(
                visibility=EventVisibility.ROOM,
                actor_id=str(host_id),
                room_id=str(room.id),
                target_ids=(str(incident.id),),
                incident_id=str(incident.id),
                kind=FESTIVAL_INCIDENT_KIND,
                room_id_started=str(room.id),
            )
        )
        return ok(hosted, started)


class AttendFestivalHandler:
    """Join a hosted festival in your room, warming your bond with the host."""

    command_type = "attend-festival"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        guest_id, guest, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        festival_id, festival, rejection = require_entity(
            ctx,
            command.payload.get("festival_id"),
            invalid_reason="invalid festival id",
            missing_reason="festival does not exist",
        )
        if rejection is not None:
            return rejection
        if not festival.has_component(HostedFestivalComponent):
            return rejected("that is not a festival")
        component = festival.get_component(HostedFestivalComponent)
        if component.ended:
            return rejected("that festival has ended")
        guest_room = room_of(ctx.world, guest_id)
        festival_room = room_of(ctx.world, festival_id)
        if guest_room is None or festival_room is None or guest_room.id != festival_room.id:
            return rejected("that festival is not here")
        if component.host_id == str(guest_id):
            return rejected("you are hosting that festival")
        if any(target == festival_id for _edge, target in guest.get_relationships(AttendsFestival)):
            return rejected("you are already at that festival")

        guest.add_relationship(AttendsFestival(joined_epoch=ctx.epoch), festival_id)
        host_entity_id = parse_entity_id(component.host_id)
        if host_entity_id is not None and ctx.world.has_entity(host_entity_id):
            deltas = {"affinity": ATTEND_AFFINITY, "familiarity": ATTEND_FAMILIARITY}
            adjust_bond(ctx.world, guest_id, host_entity_id, deltas)
            adjust_bond(ctx.world, host_entity_id, guest_id, deltas)
        _lift_joy(ctx.world, guest, ctx.epoch)
        return ok(
            FestivalAttendedEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(guest_id),
                    room_id=str(guest_room.id),
                    target_ids=(str(festival_id),),
                    festival_id=str(festival_id),
                    attendee_id=str(guest_id),
                    host_id=component.host_id,
                )
            )
        )


class EndFestivalHandler:
    """End the festival you are hosting, resolving its storyteller incident."""

    command_type = "end-festival"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        host_id, _host, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        festival_id, festival, rejection = require_entity(
            ctx,
            command.payload.get("festival_id"),
            invalid_reason="invalid festival id",
            missing_reason="festival does not exist",
        )
        if rejection is not None:
            return rejection
        if not festival.has_component(HostedFestivalComponent):
            return rejected("that is not a festival")
        component = festival.get_component(HostedFestivalComponent)
        if component.ended:
            return rejected("that festival has already ended")
        if component.host_id != str(host_id):
            return rejected("only the host can end that festival")

        replace_component(festival, replace(component, ended=True))
        events: list[DomainEvent] = []
        resolved = _resolve_incident(ctx, component.incident_id, host_id)
        if resolved is not None:
            events.append(resolved)
        events.append(
            FestivalEndedEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(host_id),
                    room_id=str(festival.id),
                    target_ids=(str(festival_id),),
                    festival_id=str(festival_id),
                    host_id=str(host_id),
                    incident_id=component.incident_id,
                )
            )
        )
        return ok(*events)


def _resolve_incident(
    ctx: HandlerContext, incident_id: str, host_id
) -> IncidentResolvedEvent | None:
    parsed = parse_entity_id(incident_id)
    if parsed is None or not ctx.world.has_entity(parsed):
        return None
    incident_entity = ctx.world.get_entity(parsed)
    if not incident_entity.has_component(IncidentComponent):
        return None
    incident = incident_entity.get_component(IncidentComponent)
    replace_component(incident_entity, replace(incident, resolved_at_epoch=ctx.epoch))
    return IncidentResolvedEvent(
        **ctx.event_base(
            visibility=EventVisibility.ROOM,
            actor_id=str(host_id),
            room_id=incident.room_id,
            target_ids=(str(incident_entity.id),),
            incident_id=str(incident_entity.id),
            kind=incident.kind,
        )
    )


def _lift_joy(world: World, character: Entity, epoch: int) -> None:
    thought = spawn_entity(
        world,
        [
            ThoughtComponent(
                label="festive",
                text="What a wonderful party this is.",
                affect_delta=ATTEND_JOY,
                created_at_epoch=epoch,
                expires_at_epoch=epoch + _JOY_TTL_SECONDS,
            )
        ],
    )
    character.add_relationship(HasThought(), thought.id)


def hosting_fragments(world: World, character) -> list[str]:
    """Describe any hosted festival in the character's room."""
    if character is None:
        return []
    room = room_of(world, character.id)
    if room is None:
        return []
    lines: list[str] = []
    for _edge, target in room.get_relationships(Contains):
        if not world.has_entity(target):
            continue
        entity = world.get_entity(target)
        if entity.has_component(HostedFestivalComponent):
            ctx = ComponentPromptContext.for_entity(world, entity, room=room)
            lines.extend(entity.get_component(HostedFestivalComponent).prompt_fragments(ctx))
    return sorted(dict.fromkeys(lines))


HOST_FESTIVAL_DEF = ActionDefinition(
    command_type="host-festival",
    title="Host festival",
    description="Throw your own festival in the room you are in.",
    lane=Lane.WORLD,
    cost=effort_cost(action=ActionEffort.MAJOR),
    arguments={
        "theme": ActionArgument(
            title="Theme",
            description="What the festival celebrates (a revel, a harvest, a wedding…).",
            kind="string",
        ),
    },
)

ATTEND_FESTIVAL_DEF = ActionDefinition(
    command_type="attend-festival",
    title="Attend festival",
    description="Join a hosted festival in your room.",
    lane=Lane.WORLD,
    cost=effort_cost(action=ActionEffort.ROUTINE),
    arguments={
        "festival_id": ActionArgument(
            title="Festival", description="The festival to join.", kind="entity", required=True
        ),
    },
)

END_FESTIVAL_DEF = ActionDefinition(
    command_type="end-festival",
    title="End festival",
    description="Wind down a festival you are hosting.",
    lane=Lane.WORLD,
    cost=effort_cost(action=ActionEffort.MAJOR),
    arguments={
        "festival_id": ActionArgument(
            title="Festival", description="The festival to end.", kind="entity", required=True
        ),
    },
)

HOSTING_ACTION_DEFINITIONS = (HOST_FESTIVAL_DEF, ATTEND_FESTIVAL_DEF, END_FESTIVAL_DEF)
HOSTING_ACTION_HANDLERS = (HostFestivalHandler, AttendFestivalHandler, EndFestivalHandler)


__all__ = [
    "ATTEND_AFFINITY",
    "ATTEND_FAMILIARITY",
    "ATTEND_FESTIVAL_DEF",
    "ATTEND_JOY",
    "END_FESTIVAL_DEF",
    "FESTIVAL_INCIDENT_KIND",
    "HOSTED_MOOD_LIFT",
    "HOSTING_ACTION_DEFINITIONS",
    "HOSTING_ACTION_HANDLERS",
    "HOST_FESTIVAL_DEF",
    "AttendFestivalHandler",
    "AttendsFestival",
    "EndFestivalHandler",
    "FestivalAttendedEvent",
    "FestivalEndedEvent",
    "FestivalHostedEvent",
    "HostFestivalHandler",
    "HostedFestivalComponent",
    "Hosts",
    "hosted_festivals",
    "hosting_fragments",
]
