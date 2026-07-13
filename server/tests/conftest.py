from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from bunnyland.core.mutations import execute_mutation_plan

ROOT = Path(__file__).resolve().parents[2]
SERVER_SRC = ROOT / "server" / "src"

for path in (SERVER_SRC,):
    if path.exists():
        sys.path.insert(0, str(path))


def execute_handler(handler, ctx, command):
    result = handler.execute(ctx, command)
    if not result.ok:
        return result
    assert result.plan is not None
    _summary, deferred = execute_mutation_plan(
        ctx.world,
        result.plan,
        after_apply=lambda: tuple(factory() for factory in result.event_factories),
    )
    return replace(result, events=(*result.events, *deferred), event_factories=())
