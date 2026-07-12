"""Contests: the open hook other packs plug their loot into.

A :class:`~bunnyland_festivalsim.components.ContestComponent` sits on a contest entity in a
room (a bake-off, a biggest-fish, a best-song). Entries are :class:`ContestEntry` edges from
the contest to the entered item, carrying the entrant and a score. This is deliberately an
**open registry**: this pack ships the ``enter-contest`` verb and the
:func:`register_contest_entry` function, and any other pack (Hearthsim dishes, Anglersim
catches, Bardsim songs) can register an entry the same way without importing anything from
this module beyond the edge and the helper.

Judging closes the contest, crowns the highest-scoring entry (ties broken deterministically
by entity id), spawns a trophy into the winner's inventory, and bumps their
:class:`ReputationComponent`.
"""

from __future__ import annotations

from dataclasses import replace

from bunnyland.core import (
    ContainmentMode,
    Contains,
    HoldableComponent,
    IdentityComponent,
    PortableComponent,
    parse_entity_id,
    spawn_entity,
)
from bunnyland.core.actions import ActionArgument, ActionDefinition, ActionEffort, effort_cost
from bunnyland.core.commands import Lane, SubmittedCommand
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
from pydantic.dataclasses import dataclass
from relics import Component, Edge, Entity, World

from .components import ContestComponent
from .spatial import holder_of, room_of

#: Reputation granted to a contest winner.
WIN_REPUTATION = 1.0


@dataclass(frozen=True)
class ContestEntry(Edge):
    """A contest -> entered-item edge, recording who entered it and its score."""

    entrant_id: str = ""
    score: float = 0.0
    entered_at_epoch: int = 0


@dataclass(frozen=True)
class ReputationComponent(Component):
    """A character's standing, grown by winning contests."""

    score: float = 0.0

    def prompt_fragments(self, ctx: ComponentPromptContext) -> tuple[str, ...]:
        if not ctx.is_first_person or self.score <= 0.0:
            return ()
        return (f"You have won {self.score:.0f} contest(s) worth of renown.",)


class ContestEnteredEvent(DomainEvent):
    """An entry was registered into a contest."""

    contest_id: str
    entrant_id: str
    entry_id: str


class ContestJudgedEvent(DomainEvent):
    """A contest was judged and a winner crowned."""

    contest_id: str
    winner_id: str
    entry_id: str


def spawn_contest(world: World, *, room_id=None, kind: str = "bake-off", title: str = "") -> Entity:
    """Spawn a contest entity, optionally placed in ``room_id``."""
    contest = spawn_entity(
        world,
        [
            IdentityComponent(name=title or kind, kind="contest", tags=("festivalsim",)),
            ContestComponent(kind=kind, title=title),
        ],
    )
    if room_id is not None and world.has_entity(room_id):
        world.get_entity(room_id).add_relationship(
            Contains(mode=ContainmentMode.ROOM_CONTENT), contest.id
        )
    return contest


def contest_entries(contest: Entity) -> list[tuple[ContestEntry, object]]:
    """Return the ``(edge, entry_id)`` pairs for a contest, sorted deterministically."""
    entries = list(contest.get_relationships(ContestEntry))
    return sorted(entries, key=lambda pair: (-pair[0].score, str(pair[1])))


def register_contest_entry(
    world: World,
    contest: Entity,
    entry_id,
    *,
    entrant_id: str,
    score: float = 1.0,
    epoch: int = 0,
) -> ContestEntry:
    """Attach an entry to a contest (the open hook other packs call). Overwrites duplicates."""
    edge = ContestEntry(entrant_id=str(entrant_id), score=score, entered_at_epoch=epoch)
    contest.add_relationship(edge, entry_id)
    return edge


def _has_entry(contest: Entity, entry_id) -> bool:
    return any(target == entry_id for _edge, target in contest.get_relationships(ContestEntry))


def _resolve_open_contest(ctx: HandlerContext, character_id, command: SubmittedCommand):
    """Resolve (contest_entity, room) for a same-room open contest, or a rejection."""
    contest_id, contest, rejection = require_entity(
        ctx,
        command.payload.get("contest_id"),
        invalid_reason="invalid contest id",
        missing_reason="contest does not exist",
    )
    if rejection is not None:
        return None, rejection
    if not contest.has_component(ContestComponent):
        return None, rejected("that is not a contest")
    character_room = room_of(ctx.world, character_id)
    contest_room = room_of(ctx.world, contest_id)
    if character_room is None or contest_room is None or character_room.id != contest_room.id:
        return None, rejected("that contest is not here")
    if not contest.get_component(ContestComponent).is_open:
        return None, rejected("that contest is closed")
    return contest, None


class EnterContestHandler:
    """Enter a held item into an open contest in the room."""

    command_type = "enter-contest"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        character_id, _character, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        contest, rejection = _resolve_open_contest(ctx, character_id, command)
        if rejection is not None:
            return rejection
        entry_id, _entry, rejection = require_entity(
            ctx,
            command.payload.get("entry_id"),
            invalid_reason="invalid entry id",
            missing_reason="entry does not exist",
        )
        if rejection is not None:
            return rejection
        holder = holder_of(ctx.world, entry_id)
        if holder is None or holder.id != character_id:
            return rejected("you are not holding that entry")
        if _has_entry(contest, entry_id):
            return rejected("that entry is already in the contest")
        score = float(command.payload.get("score", 1.0))
        register_contest_entry(
            ctx.world,
            contest,
            entry_id,
            entrant_id=str(character_id),
            score=score,
            epoch=ctx.epoch,
        )
        return ok(
            ContestEnteredEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=str(contest.id),
                    target_ids=(str(contest.id), str(entry_id)),
                    contest_id=str(contest.id),
                    entrant_id=str(character_id),
                    entry_id=str(entry_id),
                )
            )
        )


class JudgeContestHandler:
    """Judge an open contest: crown the top entry, award a trophy and reputation."""

    command_type = "judge-contest"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        character_id, _character, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        contest, rejection = _resolve_open_contest(ctx, character_id, command)
        if rejection is not None:
            return rejection
        entries = contest_entries(contest)
        if not entries:
            return rejected("that contest has no entries")
        winning_edge, winning_entry_id = entries[0]
        winner_id = winning_edge.entrant_id

        component = contest.get_component(ContestComponent)
        replace_component(contest, replace(component, is_open=False, winner_id=winner_id))
        self._award(ctx.world, winner_id)
        return ok(
            ContestJudgedEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=str(contest.id),
                    target_ids=(str(contest.id), str(winning_entry_id)),
                    contest_id=str(contest.id),
                    winner_id=str(winner_id),
                    entry_id=str(winning_entry_id),
                )
            )
        )

    def _award(self, world: World, winner_id: str) -> None:
        parsed = parse_entity_id(winner_id)
        if parsed is None or not world.has_entity(parsed):
            return
        winner = world.get_entity(parsed)
        trophy = spawn_entity(
            world,
            [
                IdentityComponent(name="trophy", kind="item", tags=("festivalsim",)),
                PortableComponent(),
                HoldableComponent(slot="hand"),
            ],
        )
        winner.add_relationship(Contains(mode=ContainmentMode.INVENTORY), trophy.id)
        current = (
            winner.get_component(ReputationComponent)
            if winner.has_component(ReputationComponent)
            else ReputationComponent()
        )
        replace_component(winner, replace(current, score=current.score + WIN_REPUTATION))


ENTER_CONTEST_DEF = ActionDefinition(
    command_type="enter-contest",
    title="Enter contest",
    description="Enter a held item into an open contest in the room.",
    lane=Lane.WORLD,
    cost=effort_cost(action=ActionEffort.ROUTINE),
    arguments={
        "contest_id": ActionArgument(
            title="Contest", description="The contest to enter.", kind="entity", required=True
        ),
        "entry_id": ActionArgument(
            title="Entry", description="The held item to enter.", kind="entity", required=True
        ),
        "score": ActionArgument(
            title="Score",
            description="The entry's judged score (default 1.0).",
            kind="number",
        ),
    },
)

JUDGE_CONTEST_DEF = ActionDefinition(
    command_type="judge-contest",
    title="Judge contest",
    description="Judge an open contest and crown its top entry.",
    lane=Lane.WORLD,
    cost=effort_cost(action=ActionEffort.ROUTINE),
    arguments={
        "contest_id": ActionArgument(
            title="Contest", description="The contest to judge.", kind="entity", required=True
        ),
    },
)

CONTEST_ACTION_DEFINITIONS = (ENTER_CONTEST_DEF, JUDGE_CONTEST_DEF)
CONTEST_ACTION_HANDLERS = (EnterContestHandler, JudgeContestHandler)


def contest_fragments(world: World, character) -> list[str]:
    """Describe contests (and the viewer's own renown) in the character's room."""
    if character is None:
        return []
    lines: list[str] = []
    room = room_of(world, character.id)
    if room is not None:
        for entity_id in _contents(room):
            if not world.has_entity(entity_id):
                continue
            entity = world.get_entity(entity_id)
            if entity.has_component(ContestComponent):
                ctx = ComponentPromptContext.for_entity(world, entity, room=room)
                lines.extend(entity.get_component(ContestComponent).prompt_fragments(ctx))
    if character.has_component(ReputationComponent):
        ctx = ComponentPromptContext.for_entity(world, character)
        lines.extend(character.get_component(ReputationComponent).prompt_fragments(ctx))
    return sorted(dict.fromkeys(lines))


def _contents(entity: Entity):
    return [target for _edge, target in entity.get_relationships(Contains)]


__all__ = [
    "CONTEST_ACTION_DEFINITIONS",
    "CONTEST_ACTION_HANDLERS",
    "ENTER_CONTEST_DEF",
    "JUDGE_CONTEST_DEF",
    "WIN_REPUTATION",
    "ContestEnteredEvent",
    "ContestEntry",
    "ContestJudgedEvent",
    "EnterContestHandler",
    "JudgeContestHandler",
    "ReputationComponent",
    "contest_entries",
    "contest_fragments",
    "register_contest_entry",
    "spawn_contest",
]
