from __future__ import annotations

from bunnyland.core import WorldActor, WorldClockComponent
from bunnyland.core.ecs import replace_component
from bunnyland.mechanics.environment import SECONDS_PER_DAY

from bunnyland_festivalsim import (
    FestivalClosedEvent,
    FestivalComponent,
    FestivalConsequence,
    FestivalOpenedEvent,
    active_festival,
    day_of_season,
    festival_fragments,
    scheduled_festival,
)

EPOCH = 500


def _set_day(actor, day):
    """Point the world clock at 00:00 of ``day`` (1-based, day 1 = spring)."""
    replace_component(
        actor._clock_entity, WorldClockComponent(game_time_seconds=(day - 1) * SECONDS_PER_DAY)
    )


def _clock(actor):
    return actor._clock_entity


# -- schedule ---------------------------------------------------------------------------


def test_day_of_season_wraps_every_28_days():
    assert day_of_season(1) == 1
    assert day_of_season(28) == 28
    assert day_of_season(29) == 1  # summer, day 1
    assert day_of_season(3 + 28 * 4) == 3  # next year's spring, same day-of-season


def test_scheduled_festival_hits_each_season():
    assert scheduled_festival(3, "spring").key == "spring-bloom"
    assert scheduled_festival(28 + 14, "summer").key == "high-summer"
    assert scheduled_festival(56 + 8, "autumn").key == "harvest-fair"
    assert scheduled_festival(84 + 24, "winter").key == "midwinter"


def test_scheduled_festival_none_before_window():
    assert scheduled_festival(1, "spring") is None


def test_scheduled_festival_none_after_window():
    # spring-bloom runs days 3..5; day 6 is past it.
    assert scheduled_festival(6, "spring") is None


def test_scheduled_festival_none_for_wrong_season():
    # The day-of-season would match harvest-fair, but the season is spring.
    assert scheduled_festival(8, "spring") is None


# -- consequence ------------------------------------------------------------------------


def test_no_clock_means_no_work():
    actor = WorldActor()
    actor.world.remove(actor._clock_entity.id)
    assert FestivalConsequence().process(actor.world, EPOCH) == []


def test_festival_opens_at_scheduled_date():
    actor = WorldActor()
    _set_day(actor, 3)  # spring-bloom opens

    events = FestivalConsequence().process(actor.world, EPOCH)

    assert len(events) == 1
    assert isinstance(events[0], FestivalOpenedEvent)
    assert events[0].key == "spring-bloom"
    festival = active_festival(actor.world)
    assert festival is not None and festival.key == "spring-bloom"


def test_festival_closes_after_its_window():
    actor = WorldActor()
    consequence = FestivalConsequence()
    _set_day(actor, 3)
    consequence.process(actor.world, EPOCH)  # opened
    _set_day(actor, 6)  # past the window

    events = consequence.process(actor.world, EPOCH + 1)

    assert len(events) == 1
    assert isinstance(events[0], FestivalClosedEvent)
    assert events[0].key == "spring-bloom"
    assert active_festival(actor.world) is None
    assert not _clock(actor).has_component(FestivalComponent)


def test_same_festival_across_ticks_is_idempotent():
    actor = WorldActor()
    consequence = FestivalConsequence()
    _set_day(actor, 3)
    consequence.process(actor.world, EPOCH)

    assert consequence.process(actor.world, EPOCH + 1) == []


def test_no_festival_scheduled_leaves_clock_clean():
    actor = WorldActor()
    _set_day(actor, 1)  # nothing scheduled

    assert FestivalConsequence().process(actor.world, EPOCH) == []
    assert not _clock(actor).has_component(FestivalComponent)


def test_switching_festivals_closes_old_and_opens_new():
    actor = WorldActor()
    # Seed a stale festival directly, then land on a day a real festival is active.
    replace_component(actor._clock_entity, FestivalComponent(key="stale", name="Stale"))
    _set_day(actor, 3)

    events = FestivalConsequence().process(actor.world, EPOCH)

    kinds = [type(event).__name__ for event in events]
    assert kinds == ["FestivalClosedEvent", "FestivalOpenedEvent"]
    assert events[0].key == "stale"
    assert events[1].key == "spring-bloom"


# -- active_festival + fragments --------------------------------------------------------


def test_active_festival_ignores_empty_marker():
    actor = WorldActor()
    replace_component(actor._clock_entity, FestivalComponent())  # key=""
    assert active_festival(actor.world) is None


def test_festival_fragment_announces_current_festival():
    actor = WorldActor()
    _set_day(actor, 3)
    FestivalConsequence().process(actor.world, EPOCH)

    lines = festival_fragments(actor.world, None)

    assert lines == ["The Spring Bloom festival is underway (spring)."]


def test_festival_fragment_empty_without_festival():
    actor = WorldActor()
    assert festival_fragments(actor.world, None) == []


def test_festival_fragment_empty_without_clock():
    actor = WorldActor()
    actor.world.remove(actor._clock_entity.id)
    assert festival_fragments(actor.world, None) == []
