from __future__ import annotations

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    IdentityComponent,
    RoomComponent,
    WorldActor,
    contents,
    spawn_entity,
)
from bunnyland.core.commands import CommandCost, Lane, build_submitted_command
from bunnyland.core.handlers import HandlerContext

from bunnyland_festivalsim.games import (
    GameBoothComponent,
    GamePlayedEvent,
    Participates,
    PlayGameHandler,
    game_fragments,
    game_roll,
    spawn_booth,
)

EPOCH = 10


def _room(world, title="Fairground"):
    return spawn_entity(world, [RoomComponent(title=title)])


def _character(world, room, name="Vin"):
    character = spawn_entity(
        world, [IdentityComponent(name=name, kind="character"), CharacterComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), character.id)
    return character


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


# -- determinism --------------------------------------------------------------------------


def test_game_roll_is_deterministic_and_bounded():
    a = game_roll("p1", "b1", 0)
    b = game_roll("p1", "b1", 0)
    assert a == b
    assert 0.0 <= a < 1.0
    # different attempt number gives a different, stable roll
    assert game_roll("p1", "b1", 1) == game_roll("p1", "b1", 1)


def test_spawn_booth_places_in_room_and_standalone():
    actor = WorldActor()
    room = _room(actor.world)
    placed = spawn_booth(actor.world, room_id=room.id, game="coconut shy")
    assert placed.id in contents(room)
    loose = spawn_booth(actor.world, game="ring toss")
    assert loose.has_component(GameBoothComponent)


# -- play-game happy paths ---------------------------------------------------------------


def test_play_game_win_awards_a_prize_and_records_the_play():
    actor = WorldActor()
    room = _room(actor.world)
    player = _character(actor.world, room)
    booth = spawn_booth(actor.world, room_id=room.id, difficulty=0.0, prize="ribbon")

    result = PlayGameHandler().execute(
        _ctx(actor), _cmd(player.id, "play-game", {"booth_id": str(booth.id)})
    )

    assert result.ok
    event = result.events[0]
    assert isinstance(event, GamePlayedEvent)
    assert event.won is True
    prizes = [
        actor.world.get_entity(i).get_component(IdentityComponent).name for i in contents(player)
    ]
    assert "ribbon" in prizes
    edge, target = next(iter(booth.get_relationships(Participates)))
    assert target == player.id
    assert edge.plays == 1
    assert edge.wins == 1


def test_play_game_loss_records_a_play_but_no_prize():
    actor = WorldActor()
    room = _room(actor.world)
    player = _character(actor.world, room)
    booth = spawn_booth(actor.world, room_id=room.id, difficulty=1.0)

    result = PlayGameHandler().execute(
        _ctx(actor), _cmd(player.id, "play-game", {"booth_id": str(booth.id)})
    )

    assert result.ok
    assert result.events[0].won is False
    assert contents(player) == []
    edge, _target = next(iter(booth.get_relationships(Participates)))
    assert edge.plays == 1
    assert edge.wins == 0


def test_play_game_second_play_increments_tally():
    actor = WorldActor()
    room = _room(actor.world)
    player = _character(actor.world, room)
    booth = spawn_booth(actor.world, room_id=room.id, difficulty=0.0)
    play = _cmd(player.id, "play-game", {"booth_id": str(booth.id)})

    PlayGameHandler().execute(_ctx(actor), play)
    PlayGameHandler().execute(_ctx(actor), play)

    edge, _target = next(iter(booth.get_relationships(Participates)))
    assert edge.plays == 2
    assert edge.wins == 2


def test_play_game_tracks_players_independently():
    actor = WorldActor()
    room = _room(actor.world)
    first = _character(actor.world, room, "Ada")
    second = _character(actor.world, room, "Bea")
    booth = spawn_booth(actor.world, room_id=room.id, difficulty=0.0)
    PlayGameHandler().execute(
        _ctx(actor), _cmd(first.id, "play-game", {"booth_id": str(booth.id)})
    )
    PlayGameHandler().execute(
        _ctx(actor), _cmd(second.id, "play-game", {"booth_id": str(booth.id)})
    )
    tallies = {target: edge.plays for edge, target in booth.get_relationships(Participates)}
    assert tallies[first.id] == 1
    assert tallies[second.id] == 1


# -- play-game rejections ----------------------------------------------------------------


def test_play_game_rejects_invalid_character():
    actor = WorldActor()
    result = PlayGameHandler().execute(
        _ctx(actor), _cmd("???", "play-game", {"booth_id": "entity_1"})
    )
    assert not result.ok
    assert result.reason == "invalid character id"


def test_play_game_rejects_invalid_booth_id():
    actor = WorldActor()
    room = _room(actor.world)
    player = _character(actor.world, room)
    result = PlayGameHandler().execute(
        _ctx(actor), _cmd(player.id, "play-game", {"booth_id": "???"})
    )
    assert not result.ok
    assert result.reason == "invalid booth id"


def test_play_game_rejects_missing_booth():
    actor = WorldActor()
    room = _room(actor.world)
    player = _character(actor.world, room)
    result = PlayGameHandler().execute(
        _ctx(actor), _cmd(player.id, "play-game", {"booth_id": "entity_9999"})
    )
    assert not result.ok
    assert result.reason == "booth does not exist"


def test_play_game_rejects_non_booth_target():
    actor = WorldActor()
    room = _room(actor.world)
    player = _character(actor.world, room)
    crate = spawn_entity(actor.world, [IdentityComponent(name="crate", kind="item")])
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), crate.id)
    result = PlayGameHandler().execute(
        _ctx(actor), _cmd(player.id, "play-game", {"booth_id": str(crate.id)})
    )
    assert not result.ok
    assert result.reason == "that is not a game booth"


def test_play_game_rejects_booth_in_another_room():
    actor = WorldActor()
    room = _room(actor.world)
    other = _room(actor.world, title="Hall")
    player = _character(actor.world, room)
    booth = spawn_booth(actor.world, room_id=other.id)
    result = PlayGameHandler().execute(
        _ctx(actor), _cmd(player.id, "play-game", {"booth_id": str(booth.id)})
    )
    assert not result.ok
    assert result.reason == "that booth is not here"


# -- fragments ---------------------------------------------------------------------------


def test_game_fragment_announces_booth():
    actor = WorldActor()
    room = _room(actor.world)
    player = _character(actor.world, room)
    spawn_booth(actor.world, room_id=room.id, game="coconut shy")
    lines = game_fragments(actor.world, player)
    assert "A coconut shy booth here is taking on players." in lines


def test_game_fragment_empty_for_none_character():
    actor = WorldActor()
    assert game_fragments(actor.world, None) == []


def test_game_fragment_empty_when_not_in_room():
    actor = WorldActor()
    loose = spawn_entity(
        actor.world, [IdentityComponent(name="Vin", kind="character"), CharacterComponent()]
    )
    assert game_fragments(actor.world, loose) == []
