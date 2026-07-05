"""Fairground games and booths.

A :class:`GameBoothComponent` sits on a booth entity in a room (a ring toss, a coconut shy).
A character ``play-game`` at it; the outcome is **deterministic** — a stable hash of the
player, the booth, and how many times they have already played, compared against the booth's
difficulty — so a world replays identically and tests are exact. A win spawns a small prize
into the player's hands and lifts their mood; either way the attempt is recorded on a typed
:class:`Participates` edge (never a component list).
"""

from __future__ import annotations

from hashlib import sha256

from bunnyland.core import (
    AffectDelta,
    ContainmentMode,
    Contains,
    HasThought,
    HoldableComponent,
    IdentityComponent,
    PortableComponent,
    ThoughtComponent,
    contents,
    spawn_entity,
)
from bunnyland.core.actions import ActionArgument, ActionDefinition
from bunnyland.core.commands import CommandCost, Lane, SubmittedCommand
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

from .spatial import room_of

#: The little thrill of winning a fairground game.
WIN_JOY = AffectDelta(valence=4.0, confidence=3.0, sociability=2.0)
_JOY_TTL_SECONDS = 2 * 3600


@dataclass(frozen=True)
class GameBoothComponent(Component):
    """A fairground game booth accepting players."""

    game: str = "ring toss"
    difficulty: float = 0.5
    prize: str = "ribbon"

    def prompt_fragments(self, ctx: ComponentPromptContext) -> tuple[str, ...]:
        return (f"A {self.game} booth here is taking on players.",)


@dataclass(frozen=True)
class Participates(Edge):
    """participant character -> the booth they played, with their running tally."""

    plays: int = 0
    wins: int = 0


class GamePlayedEvent(DomainEvent):
    """A character played a booth game."""

    booth_id: str
    player_id: str
    game: str
    won: bool


def spawn_booth(world: World, *, room_id=None, game: str = "ring toss",
                difficulty: float = 0.5, prize: str = "ribbon") -> Entity:
    """Spawn a game booth, optionally placed in ``room_id``."""
    booth = spawn_entity(
        world,
        [
            IdentityComponent(name=f"{game} booth", kind="booth", tags=("festivalsim",)),
            GameBoothComponent(game=game, difficulty=difficulty, prize=prize),
        ],
    )
    if room_id is not None and world.has_entity(room_id):
        world.get_entity(room_id).add_relationship(
            Contains(mode=ContainmentMode.ROOM_CONTENT), booth.id
        )
    return booth


def _prior_play(booth: Entity, player_id) -> tuple[Participates | None, int]:
    for edge, target in booth.get_relationships(Participates):
        if target == player_id:
            return edge, edge.plays
    return None, 0


def game_roll(player_id: str, booth_id: str, play_number: int) -> float:
    """A deterministic roll in ``[0.0, 1.0)`` for the ``play_number``-th attempt."""
    digest = sha256(f"{player_id}:{booth_id}:{play_number}".encode()).hexdigest()
    return (int(digest[:8], 16) % 1000) / 1000.0


class PlayGameHandler:
    """Play a booth game in your room; win a prize on a good roll."""

    command_type = "play-game"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        player_id, player, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        booth_id, booth, rejection = require_entity(
            ctx,
            command.payload.get("booth_id"),
            invalid_reason="invalid booth id",
            missing_reason="booth does not exist",
        )
        if rejection is not None:
            return rejection
        if not booth.has_component(GameBoothComponent):
            return rejected("that is not a game booth")
        player_room = room_of(ctx.world, player_id)
        booth_room = room_of(ctx.world, booth_id)
        if player_room is None or booth_room is None or player_room.id != booth_room.id:
            return rejected("that booth is not here")

        component = booth.get_component(GameBoothComponent)
        prior, plays = _prior_play(booth, player_id)
        won = game_roll(str(player_id), str(booth_id), plays) >= component.difficulty
        edge = Participates(
            plays=plays + 1,
            wins=(prior.wins if prior is not None else 0) + (1 if won else 0),
        )
        booth.add_relationship(edge, player_id)
        if won:
            self._award(ctx.world, player, component.prize, ctx.epoch)
        return ok(
            GamePlayedEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(player_id),
                    room_id=str(player_room.id),
                    target_ids=(str(booth_id),),
                    booth_id=str(booth_id),
                    player_id=str(player_id),
                    game=component.game,
                    won=won,
                )
            )
        )

    def _award(self, world: World, player: Entity, prize: str, epoch: int) -> None:
        token = spawn_entity(
            world,
            [
                IdentityComponent(name=prize, kind="item", tags=("festivalsim", "prize")),
                PortableComponent(),
                HoldableComponent(slot="hand"),
            ],
        )
        player.add_relationship(Contains(mode=ContainmentMode.INVENTORY), token.id)
        thought = spawn_entity(
            world,
            [
                ThoughtComponent(
                    label="triumph",
                    text=f"I won a {prize}!",
                    affect_delta=WIN_JOY,
                    created_at_epoch=epoch,
                    expires_at_epoch=epoch + _JOY_TTL_SECONDS,
                )
            ],
        )
        player.add_relationship(HasThought(), thought.id)


PLAY_GAME_DEF = ActionDefinition(
    command_type="play-game",
    title="Play game",
    description="Try your luck at a fairground game booth in the room.",
    lane=Lane.WORLD,
    cost=CommandCost(action=1),
    arguments={
        "booth_id": ActionArgument(
            title="Booth", description="The booth to play.", kind="entity", required=True
        ),
    },
)

GAME_ACTION_DEFINITIONS = (PLAY_GAME_DEF,)
GAME_ACTION_HANDLERS = (PlayGameHandler,)


def game_fragments(world: World, character) -> list[str]:
    """Describe booths in the character's room."""
    if character is None:
        return []
    room = room_of(world, character.id)
    if room is None:
        return []
    lines: list[str] = []
    for entity_id in contents(room):
        if not world.has_entity(entity_id):
            continue
        entity = world.get_entity(entity_id)
        if entity.has_component(GameBoothComponent):
            ctx = ComponentPromptContext.for_entity(world, entity, room=room)
            lines.extend(entity.get_component(GameBoothComponent).prompt_fragments(ctx))
    return sorted(dict.fromkeys(lines))


__all__ = [
    "GAME_ACTION_DEFINITIONS",
    "GAME_ACTION_HANDLERS",
    "PLAY_GAME_DEF",
    "WIN_JOY",
    "GameBoothComponent",
    "GamePlayedEvent",
    "Participates",
    "PlayGameHandler",
    "game_fragments",
    "game_roll",
    "spawn_booth",
]
