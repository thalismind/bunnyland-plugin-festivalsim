"""Bunnyland plugin entrypoint for the out-of-tree festivalsim expansion."""

from __future__ import annotations

from bunnyland.plugins import (
    CommandContribution,
    ContentContribution,
    EcsContribution,
    Plugin,
    RuntimeContribution,
)

from .calendar import (
    FestivalClosedEvent,
    FestivalOpenedEvent,
    festival_fragments,
)
from .components import ContestComponent, DecorationComponent, FestivalComponent
from .contests import (
    CONTEST_ACTION_DEFINITIONS,
    CONTEST_ACTION_HANDLERS,
    ContestEnteredEvent,
    ContestJudgedEvent,
    ReputationComponent,
    contest_fragments,
)
from .decorations import (
    DECORATION_ACTION_DEFINITIONS,
    DECORATION_ACTION_HANDLERS,
    RoomDecoratedEvent,
    decoration_fragments,
)
from .enrichment import FestivalWorldgenHook
from .gifts import GIFT_ACTION_DEFINITIONS, GIFT_ACTION_HANDLERS, GiftGivenEvent
from .install import install_festivalsim

PLUGIN_ID = "bunnyland_festivalsim"


def plugin() -> Plugin:
    return Plugin(
        id=PLUGIN_ID,
        name="Bunnyland Festivalsim",
        version="0.1.0",
        default_enabled=True,
        ecs=EcsContribution(
            components=(
                FestivalComponent,
                DecorationComponent,
                ContestComponent,
                ReputationComponent,
            ),
        ),
        commands=CommandContribution(
            action_handlers=(
                DECORATION_ACTION_HANDLERS
                + GIFT_ACTION_HANDLERS
                + CONTEST_ACTION_HANDLERS
            ),
            action_definitions=(
                DECORATION_ACTION_DEFINITIONS
                + GIFT_ACTION_DEFINITIONS
                + CONTEST_ACTION_DEFINITIONS
            ),
            typed_events=(
                FestivalOpenedEvent,
                FestivalClosedEvent,
                RoomDecoratedEvent,
                GiftGivenEvent,
                ContestEnteredEvent,
                ContestJudgedEvent,
            ),
        ),
        runtime=RuntimeContribution(
            service_factories=(install_festivalsim,),
        ),
        content=ContentContribution(
            prompt_fragments=(festival_fragments, decoration_fragments, contest_fragments),
            worldgen_hooks=(FestivalWorldgenHook,),
        ),
    )


def bunnyland_plugins() -> list[Plugin]:
    return [plugin()]


__all__ = ["PLUGIN_ID", "bunnyland_plugins", "plugin"]
