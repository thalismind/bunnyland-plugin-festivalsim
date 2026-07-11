from __future__ import annotations

from bunnyland.core.world_actor import WorldActor
from bunnyland.plugins import apply_plugins

from bunnyland_festivalsim import (
    ContestComponent,
    DecorationComponent,
    FestivalComponent,
    FestivalGenerationEnricher,
    GameBoothComponent,
    HostedFestivalComponent,
    ReputationComponent,
    SpectacleComponent,
    contest_fragments,
    decoration_fragments,
    festival_fragments,
    game_fragments,
    hosting_fragments,
    spectacle_fragments,
)
from bunnyland_festivalsim.contests import ContestEntry
from bunnyland_festivalsim.games import Participates
from bunnyland_festivalsim.hosting import AttendsFestival, Hosts
from bunnyland_festivalsim.plugin import PLUGIN_ID
from bunnyland_festivalsim.plugin import bunnyland_plugins as _plugins


def test_plugin_loads_with_module_qualified_id():
    plugins = _plugins()
    assert [p.id for p in plugins] == [PLUGIN_ID]


def test_plugin_declares_its_components():
    plugin = _plugins()[0]
    for component in (
        FestivalComponent,
        DecorationComponent,
        ContestComponent,
        ReputationComponent,
    ):
        assert component in plugin.ecs.components


def test_plugin_declares_content_contributions():
    plugin = _plugins()[0]
    assert FestivalGenerationEnricher in [
        type(item) for item in plugin.content.generation_enrichers
    ]
    for fragment in (
        festival_fragments,
        decoration_fragments,
        contest_fragments,
        hosting_fragments,
        game_fragments,
        spectacle_fragments,
    ):
        assert fragment in plugin.content.prompt_fragments


def test_plugin_is_v2():
    plugin = _plugins()[0]
    assert plugin.version == "0.2.0"
    for component in (
        HostedFestivalComponent,
        GameBoothComponent,
        SpectacleComponent,
    ):
        assert component in plugin.ecs.components
    for edge in (ContestEntry, Hosts, AttendsFestival, Participates):
        assert edge in plugin.ecs.edges


def test_plugin_recommends_partner_packs_but_requires_none():
    plugin = _plugins()[0]
    # Optional synergy partners are recommendations, never hard requirements: a festival runs
    # standalone with none of them loaded.
    assert plugin.dependencies.recommends == (
        "bunnyland.anglersim",
        "bunnyland.bardsim",
        "bunnyland.hearthsim",
        "bunnyland.starsim",
        "bunnyland.wildsim",
    )
    assert plugin.dependencies.requires == ()


def test_plugin_applies_and_registers_verbs():
    actor = WorldActor()
    applied = apply_plugins(_plugins(), actor)
    assert applied[0].id == PLUGIN_ID
    command_types = {definition.command_type for definition in actor.action_definitions()}
    assert {
        "decorate",
        "give-gift",
        "enter-contest",
        "judge-contest",
        "host-festival",
        "attend-festival",
        "end-festival",
        "play-game",
        "launch-fireworks",
    } <= command_types
