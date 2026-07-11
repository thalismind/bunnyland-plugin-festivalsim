"""Declarative festival-ground generation enrichment."""

from bunnyland.core import ContainmentMode, Contains, IdentityComponent
from bunnyland.core.generation import GenerationChild, GenerationDelta, GenerationRequest

from .components import ContestComponent, DecorationComponent

SQUARE_TERMS = (
    "square",
    "plaza",
    "market",
    "marketplace",
    "green",
    "commons",
    "fairground",
    "festival",
    "town center",
    "town centre",
    "piazza",
)
SEEDED_DECORATIONS = ("lantern", "banner")


def _child(request, key, component):
    return GenerationChild(
        request=GenerationRequest(
            entity_kind="decoration" if isinstance(component, DecorationComponent) else "contest",
            description=key,
            source_seed=request.source_seed,
            source_key=f"{request.source_key}:{key}",
            tags=("festivalsim",),
        ),
        parent_edge=Contains(mode=ContainmentMode.ROOM_CONTENT),
        components=(
            IdentityComponent(
                name=key,
                kind="decoration" if isinstance(component, DecorationComponent) else "contest",
                tags=("festivalsim",),
            ),
            component,
        ),
    )


class FestivalGenerationEnricher:
    capabilities: tuple[str, ...] = ()

    def applies(self, request: GenerationRequest) -> bool:
        return request.entity_kind == "room"

    def enrich(self, request: GenerationRequest) -> GenerationDelta:
        text = " ".join((request.source_key, request.description, *request.tags)).casefold()
        if not any(term in text for term in SQUARE_TERMS):
            return GenerationDelta()
        return GenerationDelta(
            children=(
                *(
                    _child(request, kind, DecorationComponent(kind=kind))
                    for kind in SEEDED_DECORATIONS
                ),
                _child(
                    request,
                    "Village Bake-Off",
                    ContestComponent(kind="bake-off", title="Village Bake-Off"),
                ),
            )
        )


__all__ = ["FestivalGenerationEnricher", "SEEDED_DECORATIONS", "SQUARE_TERMS"]
