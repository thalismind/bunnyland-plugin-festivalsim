"""Out-of-tree Bunnyland plugin: a calendar of seasonal festivals.

A Sims-4-expansion-sized social pack. A :class:`FestivalConsequence` hangs recurring
festivals on the world clock (spring bloom, high summer, harvest fair, midwinter), opening
and closing them on schedule. Around that calendar it adds decorations, gift-giving,
contests (an open hook other packs plug entries into), and a festive seasonal mood lift.
"""

from .calendar import (
    FESTIVAL_SCHEDULE,
    FestivalClosedEvent,
    FestivalConsequence,
    FestivalDefinition,
    FestivalOpenedEvent,
    active_festival,
    day_of_season,
    festival_fragments,
    scheduled_festival,
)
from .components import ContestComponent, DecorationComponent, FestivalComponent
from .contests import (
    CONTEST_ACTION_DEFINITIONS,
    CONTEST_ACTION_HANDLERS,
    WIN_REPUTATION,
    ContestEnteredEvent,
    ContestEntry,
    ContestJudgedEvent,
    EnterContestHandler,
    JudgeContestHandler,
    ReputationComponent,
    contest_entries,
    contest_fragments,
    register_contest_entry,
    spawn_contest,
)
from .decorations import (
    DECORATION_ACTION_DEFINITIONS,
    DECORATION_ACTION_HANDLERS,
    DecorateHandler,
    RoomDecoratedEvent,
    decoration_fragments,
    room_festivity,
    spawn_decoration,
)
from .enrichment import FestivalWorldgenHook
from .gifts import (
    GIFT_ACTION_DEFINITIONS,
    GIFT_ACTION_HANDLERS,
    GiftGivenEvent,
    GiveGiftHandler,
)
from .install import install_festivalsim
from .mood import SeasonalMoodConsequence
from .plugin import PLUGIN_ID, bunnyland_plugins, plugin
from .spatial import holder_of, room_of

__all__ = [
    "CONTEST_ACTION_DEFINITIONS",
    "CONTEST_ACTION_HANDLERS",
    "DECORATION_ACTION_DEFINITIONS",
    "DECORATION_ACTION_HANDLERS",
    "FESTIVAL_SCHEDULE",
    "GIFT_ACTION_DEFINITIONS",
    "GIFT_ACTION_HANDLERS",
    "PLUGIN_ID",
    "WIN_REPUTATION",
    "ContestComponent",
    "ContestEnteredEvent",
    "ContestEntry",
    "ContestJudgedEvent",
    "DecorateHandler",
    "DecorationComponent",
    "EnterContestHandler",
    "FestivalClosedEvent",
    "FestivalComponent",
    "FestivalConsequence",
    "FestivalDefinition",
    "FestivalOpenedEvent",
    "FestivalWorldgenHook",
    "GiftGivenEvent",
    "GiveGiftHandler",
    "JudgeContestHandler",
    "ReputationComponent",
    "RoomDecoratedEvent",
    "SeasonalMoodConsequence",
    "active_festival",
    "bunnyland_plugins",
    "contest_entries",
    "contest_fragments",
    "day_of_season",
    "decoration_fragments",
    "festival_fragments",
    "holder_of",
    "install_festivalsim",
    "plugin",
    "register_contest_entry",
    "room_festivity",
    "room_of",
    "scheduled_festival",
    "spawn_contest",
    "spawn_decoration",
]
