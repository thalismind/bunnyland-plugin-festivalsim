"""Bunnyland plugin entrypoint for the out-of-tree festivalsim expansion."""

from __future__ import annotations

from bunnyland.plugins import (
    CommandContribution,
    ContentContribution,
    DependencyContribution,
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
    ContestEntry,
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
from .enrichment import FestivalGenerationEnricher
from .games import (
    GAME_ACTION_DEFINITIONS,
    GAME_ACTION_HANDLERS,
    GameBoothComponent,
    GamePlayedEvent,
    Participates,
    game_fragments,
)
from .gifts import GIFT_ACTION_DEFINITIONS, GIFT_ACTION_HANDLERS, GiftGivenEvent
from .hosting import (
    HOSTING_ACTION_DEFINITIONS,
    HOSTING_ACTION_HANDLERS,
    AttendsFestival,
    FestivalAttendedEvent,
    FestivalEndedEvent,
    FestivalHostedEvent,
    HostedFestivalComponent,
    Hosts,
    hosting_fragments,
)
from .install import install_festivalsim
from .spectacle import (
    SPECTACLE_ACTION_DEFINITIONS,
    SPECTACLE_ACTION_HANDLERS,
    FireworksLaunchedEvent,
    MeteorShowerSpectacleEvent,
    SpectacleComponent,
    spectacle_fragments,
)

PLUGIN_ID = "bunnyland.festivalsim"


def plugin() -> Plugin:
    return Plugin(
        id=PLUGIN_ID,
        name="Bunnyland Festivalsim",
        version="0.2.0",
        default_enabled=True,
        # Optional synergy: sibling packs feed the festival's contests (their derby/bake-off/
        # gig/game achievements become ContestEntry) and starsim's meteor showers become a
        # spectacle. All are recommendations, never hard requirements — a festival runs solo.
        dependencies=DependencyContribution(
            recommends=(
                "bunnyland.anglersim",
                "bunnyland.bardsim",
                "bunnyland.hearthsim",
                "bunnyland.starsim",
                "bunnyland.wildsim",
            ),
        ),
        ecs=EcsContribution(
            components=(
                FestivalComponent,
                DecorationComponent,
                ContestComponent,
                ReputationComponent,
                HostedFestivalComponent,
                GameBoothComponent,
                SpectacleComponent,
            ),
            edges=(ContestEntry, Hosts, AttendsFestival, Participates),
        ),
        commands=CommandContribution(
            action_handlers=(
                *DECORATION_ACTION_HANDLERS,
                *GIFT_ACTION_HANDLERS,
                *CONTEST_ACTION_HANDLERS,
                *HOSTING_ACTION_HANDLERS,
                *GAME_ACTION_HANDLERS,
                *SPECTACLE_ACTION_HANDLERS,
            ),
            action_definitions=(
                *DECORATION_ACTION_DEFINITIONS,
                *GIFT_ACTION_DEFINITIONS,
                *CONTEST_ACTION_DEFINITIONS,
                *HOSTING_ACTION_DEFINITIONS,
                *GAME_ACTION_DEFINITIONS,
                *SPECTACLE_ACTION_DEFINITIONS,
            ),
            typed_events=(
                FestivalOpenedEvent,
                FestivalClosedEvent,
                RoomDecoratedEvent,
                GiftGivenEvent,
                ContestEnteredEvent,
                ContestJudgedEvent,
                FestivalHostedEvent,
                FestivalAttendedEvent,
                FestivalEndedEvent,
                GamePlayedEvent,
                FireworksLaunchedEvent,
                MeteorShowerSpectacleEvent,
            ),
        ),
        runtime=RuntimeContribution(
            service_factories=(install_festivalsim,),
        ),
        content=ContentContribution(
            prompt_fragments=(
                festival_fragments,
                decoration_fragments,
                contest_fragments,
                hosting_fragments,
                game_fragments,
                spectacle_fragments,
            ),
            generation_enrichers=(FestivalGenerationEnricher(),),
        ),
    )


def bunnyland_plugins() -> list[Plugin]:
    return [plugin()]


__all__ = ["PLUGIN_ID", "bunnyland_plugins", "plugin"]
