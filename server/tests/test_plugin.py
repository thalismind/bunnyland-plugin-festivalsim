from __future__ import annotations

from bunnyland.core.world_actor import WorldActor
from bunnyland.plugins import apply_plugins, load_modules

from bunnyland_festivalsim import (
    ContestComponent,
    DecorationComponent,
    FestivalComponent,
    FestivalWorldgenHook,
    ReputationComponent,
    contest_fragments,
    decoration_fragments,
    festival_fragments,
)
from bunnyland_festivalsim.plugin import PLUGIN_ID


def test_plugin_loads_with_module_qualified_id():
    plugins = load_modules(["bunnyland_festivalsim"])
    assert [p.id for p in plugins] == [PLUGIN_ID]


def test_plugin_declares_its_components():
    plugin = load_modules(["bunnyland_festivalsim"])[0]
    for component in (
        FestivalComponent,
        DecorationComponent,
        ContestComponent,
        ReputationComponent,
    ):
        assert component in plugin.ecs.components


def test_plugin_declares_content_contributions():
    plugin = load_modules(["bunnyland_festivalsim"])[0]
    assert FestivalWorldgenHook in plugin.content.worldgen_hooks
    for fragment in (festival_fragments, decoration_fragments, contest_fragments):
        assert fragment in plugin.content.prompt_fragments


def test_plugin_version():
    plugin = load_modules(["bunnyland_festivalsim"])[0]
    assert plugin.version == "0.1.0"


def test_plugin_applies_and_registers_verbs():
    actor = WorldActor()
    applied = apply_plugins(load_modules(["bunnyland_festivalsim"]), actor)
    assert applied[0].id == PLUGIN_ID
    command_types = {definition.command_type for definition in actor.action_definitions()}
    assert {"decorate", "give-gift", "enter-contest", "judge-contest"} <= command_types
