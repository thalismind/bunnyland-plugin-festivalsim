from __future__ import annotations

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    IdentityComponent,
    PortableComponent,
    RoomComponent,
    WorldActor,
    contents,
    spawn_entity,
)
from bunnyland.core.commands import CommandCost, Lane, build_submitted_command
from bunnyland.core.handlers import HandlerContext

from bunnyland_festivalsim import (
    ContestComponent,
    ContestEnteredEvent,
    ContestJudgedEvent,
    EnterContestHandler,
    JudgeContestHandler,
    ReputationComponent,
    contest_entries,
    contest_fragments,
    register_contest_entry,
    spawn_contest,
)

EPOCH = 10


def _room(world, *, title="Fairground"):
    return spawn_entity(world, [RoomComponent(title=title)])


def _character(world, room, name="Vin"):
    character = spawn_entity(
        world, [IdentityComponent(name=name, kind="character"), CharacterComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), character.id)
    return character


def _held(world, holder, name="pie"):
    item = spawn_entity(world, [IdentityComponent(name=name, kind="item"), PortableComponent()])
    holder.add_relationship(Contains(mode=ContainmentMode.INVENTORY), item.id)
    return item


def _cmd(character_id, command_type, payload):
    return build_submitted_command(
        character_id=str(character_id),
        controller_id="ctrl",
        controller_generation=0,
        command_type=command_type,
        cost=CommandCost(action=1),
        lane=Lane.WORLD,
        payload=payload,
    )


def _ctx(actor):
    return HandlerContext(world=actor.world, epoch=EPOCH)


# -- open registry hook -----------------------------------------------------------------


def test_register_contest_entry_is_the_open_hook():
    actor = WorldActor()
    room = _room(actor.world)
    contest = spawn_contest(actor.world, room_id=room.id)
    entry = spawn_entity(actor.world, [IdentityComponent(name="cake", kind="item")])

    register_contest_entry(actor.world, contest, entry.id, entrant_id="npc", score=2.0)

    entries = contest_entries(contest)
    assert len(entries) == 1
    assert entries[0][0].entrant_id == "npc"
    assert entries[0][0].score == 2.0


def test_contest_entries_sort_by_descending_score():
    actor = WorldActor()
    room = _room(actor.world)
    contest = spawn_contest(actor.world, room_id=room.id)
    low = spawn_entity(actor.world, [IdentityComponent(name="low", kind="item")])
    high = spawn_entity(actor.world, [IdentityComponent(name="high", kind="item")])
    register_contest_entry(actor.world, contest, low.id, entrant_id="a", score=1.0)
    register_contest_entry(actor.world, contest, high.id, entrant_id="b", score=5.0)

    ordered = contest_entries(contest)

    assert ordered[0][1] == high.id


# -- enter-contest ----------------------------------------------------------------------


def test_enter_contest_registers_a_held_entry():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    contest = spawn_contest(actor.world, room_id=room.id)
    pie = _held(actor.world, character)

    result = EnterContestHandler().execute(
        _ctx(actor),
        _cmd(
            character.id,
            "enter-contest",
            {"contest_id": str(contest.id), "entry_id": str(pie.id), "score": 3.0},
        ),
    )

    assert result.ok
    assert isinstance(result.events[0], ContestEnteredEvent)
    entries = contest_entries(contest)
    assert entries[0][1] == pie.id
    assert entries[0][0].score == 3.0
    assert entries[0][0].entrant_id == str(character.id)


def test_enter_contest_rejects_invalid_character():
    actor = WorldActor()
    result = EnterContestHandler().execute(
        _ctx(actor),
        _cmd("???", "enter-contest", {"contest_id": "entity_1", "entry_id": "entity_2"}),
    )
    assert not result.ok
    assert result.reason == "invalid character id"


def test_enter_contest_rejects_invalid_contest_id():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    result = EnterContestHandler().execute(
        _ctx(actor),
        _cmd(character.id, "enter-contest", {"contest_id": "???", "entry_id": "entity_2"}),
    )
    assert not result.ok
    assert result.reason == "invalid contest id"


def test_enter_contest_rejects_missing_contest():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    result = EnterContestHandler().execute(
        _ctx(actor),
        _cmd(character.id, "enter-contest", {"contest_id": "entity_9999", "entry_id": "entity_2"}),
    )
    assert not result.ok
    assert result.reason == "contest does not exist"


def test_enter_contest_rejects_non_contest_target():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    crate = spawn_entity(actor.world, [IdentityComponent(name="crate", kind="item")])
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), crate.id)
    result = EnterContestHandler().execute(
        _ctx(actor),
        _cmd(character.id, "enter-contest", {"contest_id": str(crate.id), "entry_id": "entity_2"}),
    )
    assert not result.ok
    assert result.reason == "that is not a contest"


def test_enter_contest_rejects_contest_in_another_room():
    actor = WorldActor()
    room = _room(actor.world)
    other = _room(actor.world, title="Hall")
    character = _character(actor.world, room)
    contest = spawn_contest(actor.world, room_id=other.id)
    result = EnterContestHandler().execute(
        _ctx(actor),
        _cmd(
            character.id,
            "enter-contest",
            {"contest_id": str(contest.id), "entry_id": "entity_2"},
        ),
    )
    assert not result.ok
    assert result.reason == "that contest is not here"


def test_enter_contest_rejects_closed_contest():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    contest = spawn_contest(actor.world, room_id=room.id)
    # Swap the default open component for a closed one.
    from bunnyland.core.ecs import replace_component

    replace_component(contest, ContestComponent(kind="bake-off", is_open=False))
    pie = _held(actor.world, character)
    result = EnterContestHandler().execute(
        _ctx(actor),
        _cmd(
            character.id,
            "enter-contest",
            {"contest_id": str(contest.id), "entry_id": str(pie.id)},
        ),
    )
    assert not result.ok
    assert result.reason == "that contest is closed"


def test_enter_contest_rejects_invalid_entry_id():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    contest = spawn_contest(actor.world, room_id=room.id)
    result = EnterContestHandler().execute(
        _ctx(actor),
        _cmd(character.id, "enter-contest", {"contest_id": str(contest.id), "entry_id": "???"}),
    )
    assert not result.ok
    assert result.reason == "invalid entry id"


def test_enter_contest_rejects_missing_entry():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    contest = spawn_contest(actor.world, room_id=room.id)
    result = EnterContestHandler().execute(
        _ctx(actor),
        _cmd(
            character.id,
            "enter-contest",
            {"contest_id": str(contest.id), "entry_id": "entity_9999"},
        ),
    )
    assert not result.ok
    assert result.reason == "entry does not exist"


def test_enter_contest_rejects_unheld_entry():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    contest = spawn_contest(actor.world, room_id=room.id)
    loose = spawn_entity(
        actor.world, [IdentityComponent(name="pie", kind="item"), PortableComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), loose.id)
    result = EnterContestHandler().execute(
        _ctx(actor),
        _cmd(
            character.id,
            "enter-contest",
            {"contest_id": str(contest.id), "entry_id": str(loose.id)},
        ),
    )
    assert not result.ok
    assert result.reason == "you are not holding that entry"


def test_enter_contest_rejects_double_entry():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    contest = spawn_contest(actor.world, room_id=room.id)
    pie = _held(actor.world, character)
    payload = {"contest_id": str(contest.id), "entry_id": str(pie.id)}
    enter = _cmd(character.id, "enter-contest", payload)
    EnterContestHandler().execute(_ctx(actor), enter)

    result = EnterContestHandler().execute(_ctx(actor), enter)

    assert not result.ok
    assert result.reason == "that entry is already in the contest"


# -- judge-contest ----------------------------------------------------------------------


def test_judge_contest_crowns_top_entry_with_trophy_and_reputation():
    actor = WorldActor()
    room = _room(actor.world)
    judge = _character(actor.world, room, "Judge")
    winner = _character(actor.world, room, "Vin")
    runner_up = _character(actor.world, room, "Kell")
    contest = spawn_contest(actor.world, room_id=room.id)
    best = spawn_entity(actor.world, [IdentityComponent(name="cake", kind="item")])
    worst = spawn_entity(actor.world, [IdentityComponent(name="loaf", kind="item")])
    register_contest_entry(actor.world, contest, worst.id, entrant_id=str(runner_up.id), score=1.0)
    register_contest_entry(actor.world, contest, best.id, entrant_id=str(winner.id), score=9.0)

    result = JudgeContestHandler().execute(
        _ctx(actor), _cmd(judge.id, "judge-contest", {"contest_id": str(contest.id)})
    )

    assert result.ok
    assert isinstance(result.events[0], ContestJudgedEvent)
    assert result.events[0].winner_id == str(winner.id)
    assert contest.get_component(ContestComponent).is_open is False
    assert contest.get_component(ContestComponent).winner_id == str(winner.id)
    # winner got a trophy and a point of reputation
    trophies = [
        actor.world.get_entity(i)
        for i in contents(winner)
        if actor.world.get_entity(i).get_component(IdentityComponent).name == "trophy"
    ]
    assert len(trophies) == 1
    assert winner.get_component(ReputationComponent).score == 1.0


def test_judge_contest_rejects_when_no_entries():
    actor = WorldActor()
    room = _room(actor.world)
    judge = _character(actor.world, room)
    contest = spawn_contest(actor.world, room_id=room.id)

    result = JudgeContestHandler().execute(
        _ctx(actor), _cmd(judge.id, "judge-contest", {"contest_id": str(contest.id)})
    )

    assert not result.ok
    assert result.reason == "that contest has no entries"


def test_judge_contest_rejects_already_judged_contest():
    actor = WorldActor()
    room = _room(actor.world)
    judge = _character(actor.world, room)
    winner = _character(actor.world, room, "Vin")
    contest = spawn_contest(actor.world, room_id=room.id)
    entry = spawn_entity(actor.world, [IdentityComponent(name="cake", kind="item")])
    register_contest_entry(actor.world, contest, entry.id, entrant_id=str(winner.id), score=1.0)
    JudgeContestHandler().execute(
        _ctx(actor), _cmd(judge.id, "judge-contest", {"contest_id": str(contest.id)})
    )

    result = JudgeContestHandler().execute(
        _ctx(actor), _cmd(judge.id, "judge-contest", {"contest_id": str(contest.id)})
    )

    assert not result.ok
    assert result.reason == "that contest is closed"


def test_judge_contest_survives_a_departed_winner():
    actor = WorldActor()
    room = _room(actor.world)
    judge = _character(actor.world, room)
    contest = spawn_contest(actor.world, room_id=room.id)
    entry = spawn_entity(actor.world, [IdentityComponent(name="cake", kind="item")])
    register_contest_entry(actor.world, contest, entry.id, entrant_id="entity_9999", score=1.0)

    result = JudgeContestHandler().execute(
        _ctx(actor), _cmd(judge.id, "judge-contest", {"contest_id": str(contest.id)})
    )

    assert result.ok
    assert contest.get_component(ContestComponent).is_open is False


# -- fragments --------------------------------------------------------------------------


def test_contest_fragment_announces_open_contest():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    spawn_contest(actor.world, room_id=room.id, kind="bake-off", title="Village Bake-Off")

    lines = contest_fragments(actor.world, character)

    assert "A Village Bake-Off contest here is accepting entries." in lines


def test_contest_fragment_shows_own_reputation():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    character.add_component(ReputationComponent(score=2.0))

    lines = contest_fragments(actor.world, character)

    assert any("renown" in line for line in lines)


def test_contest_fragment_empty_for_none_character():
    actor = WorldActor()
    assert contest_fragments(actor.world, None) == []


def test_contest_fragment_empty_in_bare_room():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    assert contest_fragments(actor.world, character) == []
