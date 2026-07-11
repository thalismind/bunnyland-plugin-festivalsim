from __future__ import annotations

import asyncio

from bunnyland.core import (
    ContainmentMode,
    Contains,
    IdentityComponent,
    RoomComponent,
    WorldActor,
    spawn_entity,
)
from bunnyland.core.components import WorldClockComponent
from bunnyland.core.events import DomainEvent, event_base

from bunnyland_festivalsim.calendar import FestivalComponent
from bunnyland_festivalsim.components import ContestComponent
from bunnyland_festivalsim.contests import contest_entries, spawn_contest
from bunnyland_festivalsim.hosting import HostedFestivalComponent
from bunnyland_festivalsim.stage import FestivalStageReactor, festival_is_live

EPOCH = 5


# Fakes standing in for sibling packs' achievement events. The reactor matches purely by the
# event's class name, so these need no real partner pack loaded.
class MealCookedEvent(DomainEvent):
    pass


class PerformedEvent(DomainEvent):
    pass


class UnrelatedEvent(DomainEvent):
    pass


def _room(world, title="Fairground"):
    return spawn_entity(world, [RoomComponent(title=title)])


def _entry_item(world, name="pie"):
    return spawn_entity(world, [IdentityComponent(name=name, kind="item")])


def _hosted_festival(world, room, *, ended=False):
    festival = spawn_entity(
        world,
        [
            IdentityComponent(name="revel festival", kind="festival"),
            HostedFestivalComponent(key="hosted", theme="revel", host_id="host", ended=ended),
        ],
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), festival.id)
    return festival


def _fake(cls, *, actor_id, target_ids=(), epoch=EPOCH):
    return cls(**event_base(epoch, actor_id=actor_id, target_ids=target_ids))


# -- festival_is_live --------------------------------------------------------------------


def test_festival_is_live_via_calendar_festival():
    actor = WorldActor()
    clock = list(actor.world.query().with_all([WorldClockComponent]).execute_entities())[0]
    clock.add_component(FestivalComponent(key="spring-bloom", name="Spring Bloom", season="spring"))
    assert festival_is_live(actor.world) is True


def test_festival_is_live_via_hosted_festival():
    actor = WorldActor()
    room = _room(actor.world)
    _hosted_festival(actor.world, room)
    assert festival_is_live(actor.world) is True


def test_festival_is_not_live_when_hosted_festival_ended():
    actor = WorldActor()
    room = _room(actor.world)
    _hosted_festival(actor.world, room, ended=True)
    assert festival_is_live(actor.world) is False


def test_festival_is_not_live_with_nothing_going_on():
    actor = WorldActor()
    assert festival_is_live(actor.world) is False


# -- reactor consumption -----------------------------------------------------------------


def test_reactor_folds_a_partner_achievement_into_the_open_contest():
    actor = WorldActor()
    room = _room(actor.world)
    _hosted_festival(actor.world, room)
    contest = spawn_contest(actor.world, room_id=room.id, kind="bake-off")
    meal = _entry_item(actor.world, "cake")

    reactor = FestivalStageReactor()
    reactor.subscribe(actor)
    reactor._on_event(_fake(MealCookedEvent, actor_id="chef", target_ids=(str(meal.id),)))

    entries = contest_entries(contest)
    assert len(entries) == 1
    edge, target = entries[0]
    assert target == meal.id
    assert edge.entrant_id == "chef"
    assert edge.score == 2.0  # MealCookedEvent -> bake-off, 2.0


def test_reactor_subscribes_and_receives_bus_events():
    actor = WorldActor()
    room = _room(actor.world)
    _hosted_festival(actor.world, room)
    contest = spawn_contest(actor.world, room_id=room.id, kind="gig")
    song = _entry_item(actor.world, "ballad")

    reactor = FestivalStageReactor()
    reactor.subscribe(actor)
    asyncio.run(
        actor.bus.publish(_fake(PerformedEvent, actor_id="bard", target_ids=(str(song.id),)))
    )

    assert len(contest_entries(contest)) == 1


def test_reactor_falls_back_to_first_open_contest_on_kind_mismatch():
    actor = WorldActor()
    room = _room(actor.world)
    _hosted_festival(actor.world, room)
    contest = spawn_contest(actor.world, room_id=room.id, kind="gig")  # no bake-off contest
    meal = _entry_item(actor.world, "cake")

    reactor = FestivalStageReactor()
    reactor.subscribe(actor)
    reactor._on_event(_fake(MealCookedEvent, actor_id="chef", target_ids=(str(meal.id),)))

    assert len(contest_entries(contest)) == 1


def test_reactor_ignores_unrelated_events():
    actor = WorldActor()
    room = _room(actor.world)
    _hosted_festival(actor.world, room)
    contest = spawn_contest(actor.world, room_id=room.id, kind="bake-off")

    reactor = FestivalStageReactor()
    reactor.subscribe(actor)
    reactor._on_event(_fake(UnrelatedEvent, actor_id="who", target_ids=("entity_1",)))

    assert contest_entries(contest) == []


def test_reactor_ignores_achievements_when_no_festival_is_live():
    actor = WorldActor()
    room = _room(actor.world)
    contest = spawn_contest(actor.world, room_id=room.id, kind="bake-off")
    meal = _entry_item(actor.world, "cake")

    reactor = FestivalStageReactor()
    reactor.subscribe(actor)
    reactor._on_event(_fake(MealCookedEvent, actor_id="chef", target_ids=(str(meal.id),)))

    assert contest_entries(contest) == []


def test_reactor_does_nothing_without_an_open_contest():
    actor = WorldActor()
    room = _room(actor.world)
    _hosted_festival(actor.world, room)
    # a closed contest is not a target
    contest = spawn_contest(actor.world, room_id=room.id, kind="bake-off")
    from bunnyland.core.ecs import replace_component

    replace_component(contest, ContestComponent(kind="bake-off", is_open=False))
    meal = _entry_item(actor.world, "cake")

    reactor = FestivalStageReactor()
    reactor.subscribe(actor)
    reactor._on_event(_fake(MealCookedEvent, actor_id="chef", target_ids=(str(meal.id),)))

    assert contest_entries(contest) == []


def test_reactor_skips_an_event_with_no_resolvable_entry():
    actor = WorldActor()
    room = _room(actor.world)
    _hosted_festival(actor.world, room)
    contest = spawn_contest(actor.world, room_id=room.id, kind="bake-off")

    reactor = FestivalStageReactor()
    reactor.subscribe(actor)
    # no target, and the actor id points at nothing in the world
    reactor._on_event(_fake(MealCookedEvent, actor_id="entity_9999", target_ids=()))
    # no target and no actor at all
    reactor._on_event(_fake(MealCookedEvent, actor_id=None, target_ids=()))

    assert contest_entries(contest) == []


def test_reactor_standalone_leaves_only_local_entries():
    actor = WorldActor()
    room = _room(actor.world)
    _hosted_festival(actor.world, room)
    contest = spawn_contest(actor.world, room_id=room.id, kind="bake-off")

    reactor = FestivalStageReactor()
    reactor.subscribe(actor)
    # With no partner pack loaded, no external achievement events ever fire, so the festival
    # runs purely on its own locally-entered items.
    from bunnyland_festivalsim.contests import register_contest_entry

    local = _entry_item(actor.world, "home pie")
    register_contest_entry(actor.world, contest, local.id, entrant_id="villager", score=1.0)

    assert len(contest_entries(contest)) == 1
