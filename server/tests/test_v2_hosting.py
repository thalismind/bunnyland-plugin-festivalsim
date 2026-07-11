from __future__ import annotations

from bunnyland.core import (
    AffectComponent,
    CharacterComponent,
    ContainmentMode,
    Contains,
    HasThought,
    IdentityComponent,
    RoomComponent,
    WorldActor,
    parse_entity_id,
    spawn_entity,
)
from bunnyland.core.commands import CommandCost, Lane, build_submitted_command
from bunnyland.core.handlers import HandlerContext
from bunnyland.foundation.history.mechanics import WorldHistoryRecordComponent
from bunnyland.foundation.social.mechanics import bond_between
from bunnyland.foundation.storyteller.mechanics import (
    IncidentComponent,
    IncidentResolvedEvent,
    IncidentStartedEvent,
)
from bunnyland.imagegen import ImageRequestComponent

from bunnyland_festivalsim.hosting import (
    AttendFestivalHandler,
    AttendsFestival,
    EndFestivalHandler,
    FestivalAttendedEvent,
    FestivalEndedEvent,
    FestivalHostedEvent,
    HostedFestivalComponent,
    HostFestivalHandler,
    Hosts,
    hosted_festivals,
    hosting_fragments,
)

EPOCH = 42


def _room(world, title="Square"):
    return spawn_entity(world, [RoomComponent(title=title)])


def _character(world, room=None, name="Vin"):
    character = spawn_entity(
        world,
        [
            IdentityComponent(name=name, kind="character"),
            CharacterComponent(),
            AffectComponent(),
        ],
    )
    if room is not None:
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


def _host_a_festival(actor, room, host, theme="revel"):
    result = HostFestivalHandler().execute(
        _ctx(actor), _cmd(host.id, "host-festival", {"theme": theme})
    )
    festival_id = result.events[0].festival_id
    return actor.world.get_entity(parse_entity_id(festival_id)), result


# -- host-festival -----------------------------------------------------------------------


def test_host_festival_spawns_festival_incident_and_history():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room)

    result = HostFestivalHandler().execute(
        _ctx(actor), _cmd(host.id, "host-festival", {"theme": "harvest"})
    )

    assert result.ok
    assert isinstance(result.events[0], FestivalHostedEvent)
    assert isinstance(result.events[1], IncidentStartedEvent)
    festivals = hosted_festivals(actor.world)
    assert len(festivals) == 1
    component = festivals[0].get_component(HostedFestivalComponent)
    assert component.theme == "harvest"
    assert component.host_id == str(host.id)
    assert not component.ended
    # host -> festival typed edge
    assert any(target == festivals[0].id for _edge, target in host.get_relationships(Hosts))
    # a storyteller incident was registered
    incidents = list(actor.world.query().with_all([IncidentComponent]).execute_entities())
    assert len(incidents) == 1
    assert incidents[0].get_component(IncidentComponent).kind == "festival"
    # a world-history record marked for an imagegen picture
    records = list(actor.world.query().with_all([WorldHistoryRecordComponent]).execute_entities())
    assert len(records) == 1
    assert records[0].has_component(ImageRequestComponent)


def test_host_festival_defaults_theme_to_revel():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room)
    result = HostFestivalHandler().execute(_ctx(actor), _cmd(host.id, "host-festival", {}))
    assert result.ok
    assert hosted_festivals(actor.world)[0].get_component(HostedFestivalComponent).theme == "revel"


def test_host_festival_rejects_invalid_character():
    actor = WorldActor()
    result = HostFestivalHandler().execute(_ctx(actor), _cmd("???", "host-festival", {}))
    assert not result.ok
    assert result.reason == "invalid character id"


def test_host_festival_rejects_when_not_in_a_room():
    actor = WorldActor()
    host = _character(actor.world)  # not placed in a room
    result = HostFestivalHandler().execute(_ctx(actor), _cmd(host.id, "host-festival", {}))
    assert not result.ok
    assert result.reason == "you are not in a room"


def test_host_festival_rejects_double_hosting():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room)
    _host_a_festival(actor, room, host)
    result = HostFestivalHandler().execute(_ctx(actor), _cmd(host.id, "host-festival", {}))
    assert not result.ok
    assert result.reason == "you are already hosting a festival"


# -- attend-festival ---------------------------------------------------------------------


def test_attend_festival_warms_the_bond_and_lifts_joy():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room, "Host")
    guest = _character(actor.world, room, "Guest")
    festival, _ = _host_a_festival(actor, room, host)

    result = AttendFestivalHandler().execute(
        _ctx(actor), _cmd(guest.id, "attend-festival", {"festival_id": str(festival.id)})
    )

    assert result.ok
    assert isinstance(result.events[0], FestivalAttendedEvent)
    assert any(target == festival.id for _e, target in guest.get_relationships(AttendsFestival))
    assert bond_between(actor.world, guest.id, host.id).affinity > 0
    assert bond_between(actor.world, host.id, guest.id).familiarity > 0
    assert list(guest.get_relationships(HasThought))


def test_attend_festival_survives_a_departed_host():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room, "Host")
    guest = _character(actor.world, room, "Guest")
    festival, _ = _host_a_festival(actor, room, host)
    actor.world.remove(host.id)  # the host wandered off before the guest arrived

    result = AttendFestivalHandler().execute(
        _ctx(actor), _cmd(guest.id, "attend-festival", {"festival_id": str(festival.id)})
    )

    assert result.ok
    assert any(target == festival.id for _e, target in guest.get_relationships(AttendsFestival))
    assert list(guest.get_relationships(HasThought))  # joy still lifted


def test_attend_festival_rejects_invalid_character():
    actor = WorldActor()
    result = AttendFestivalHandler().execute(
        _ctx(actor), _cmd("???", "attend-festival", {"festival_id": "entity_1"})
    )
    assert not result.ok
    assert result.reason == "invalid character id"


def test_attend_festival_rejects_invalid_festival_id():
    actor = WorldActor()
    room = _room(actor.world)
    guest = _character(actor.world, room)
    result = AttendFestivalHandler().execute(
        _ctx(actor), _cmd(guest.id, "attend-festival", {"festival_id": "???"})
    )
    assert not result.ok
    assert result.reason == "invalid festival id"


def test_attend_festival_rejects_missing_festival():
    actor = WorldActor()
    room = _room(actor.world)
    guest = _character(actor.world, room)
    result = AttendFestivalHandler().execute(
        _ctx(actor), _cmd(guest.id, "attend-festival", {"festival_id": "entity_9999"})
    )
    assert not result.ok
    assert result.reason == "festival does not exist"


def test_attend_festival_rejects_non_festival_target():
    actor = WorldActor()
    room = _room(actor.world)
    guest = _character(actor.world, room)
    crate = spawn_entity(actor.world, [IdentityComponent(name="crate", kind="item")])
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), crate.id)
    result = AttendFestivalHandler().execute(
        _ctx(actor), _cmd(guest.id, "attend-festival", {"festival_id": str(crate.id)})
    )
    assert not result.ok
    assert result.reason == "that is not a festival"


def test_attend_festival_rejects_ended_festival():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room, "Host")
    guest = _character(actor.world, room, "Guest")
    festival, _ = _host_a_festival(actor, room, host)
    EndFestivalHandler().execute(
        _ctx(actor), _cmd(host.id, "end-festival", {"festival_id": str(festival.id)})
    )
    result = AttendFestivalHandler().execute(
        _ctx(actor), _cmd(guest.id, "attend-festival", {"festival_id": str(festival.id)})
    )
    assert not result.ok
    assert result.reason == "that festival has ended"


def test_attend_festival_rejects_festival_in_another_room():
    actor = WorldActor()
    room = _room(actor.world)
    other = _room(actor.world, title="Hall")
    host = _character(actor.world, room, "Host")
    guest = _character(actor.world, other, "Guest")
    festival, _ = _host_a_festival(actor, room, host)
    result = AttendFestivalHandler().execute(
        _ctx(actor), _cmd(guest.id, "attend-festival", {"festival_id": str(festival.id)})
    )
    assert not result.ok
    assert result.reason == "that festival is not here"


def test_attend_festival_rejects_host_attending_own_party():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room, "Host")
    festival, _ = _host_a_festival(actor, room, host)
    result = AttendFestivalHandler().execute(
        _ctx(actor), _cmd(host.id, "attend-festival", {"festival_id": str(festival.id)})
    )
    assert not result.ok
    assert result.reason == "you are hosting that festival"


def test_attend_festival_rejects_double_attendance():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room, "Host")
    guest = _character(actor.world, room, "Guest")
    festival, _ = _host_a_festival(actor, room, host)
    attend = _cmd(guest.id, "attend-festival", {"festival_id": str(festival.id)})
    AttendFestivalHandler().execute(_ctx(actor), attend)
    result = AttendFestivalHandler().execute(_ctx(actor), attend)
    assert not result.ok
    assert result.reason == "you are already at that festival"


# -- end-festival ------------------------------------------------------------------------


def test_end_festival_resolves_the_incident():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room, "Host")
    festival, _ = _host_a_festival(actor, room, host)
    incident_id = festival.get_component(HostedFestivalComponent).incident_id

    result = EndFestivalHandler().execute(
        _ctx(actor), _cmd(host.id, "end-festival", {"festival_id": str(festival.id)})
    )

    assert result.ok
    assert isinstance(result.events[0], IncidentResolvedEvent)
    assert isinstance(result.events[1], FestivalEndedEvent)
    assert festival.get_component(HostedFestivalComponent).ended is True
    incident = actor.world.get_entity(parse_entity_id(incident_id))
    assert incident.get_component(IncidentComponent).resolved_at_epoch == EPOCH


def test_end_festival_without_a_live_incident_still_ends():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room, "Host")
    festival = spawn_entity(
        actor.world,
        [
            IdentityComponent(name="revel festival", kind="festival"),
            HostedFestivalComponent(
                key="hosted", theme="revel", host_id=str(host.id), incident_id=""
            ),
        ],
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), festival.id)

    result = EndFestivalHandler().execute(
        _ctx(actor), _cmd(host.id, "end-festival", {"festival_id": str(festival.id)})
    )

    assert result.ok
    assert [type(e).__name__ for e in result.events] == ["FestivalEndedEvent"]
    assert festival.get_component(HostedFestivalComponent).ended is True


def test_end_festival_ignores_a_non_incident_reference():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room, "Host")
    decoy = spawn_entity(actor.world, [IdentityComponent(name="decoy", kind="item")])
    festival = spawn_entity(
        actor.world,
        [
            IdentityComponent(name="revel festival", kind="festival"),
            HostedFestivalComponent(
                key="hosted", theme="revel", host_id=str(host.id), incident_id=str(decoy.id)
            ),
        ],
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), festival.id)
    result = EndFestivalHandler().execute(
        _ctx(actor), _cmd(host.id, "end-festival", {"festival_id": str(festival.id)})
    )
    assert result.ok
    assert [type(e).__name__ for e in result.events] == ["FestivalEndedEvent"]


def test_end_festival_rejects_invalid_character():
    actor = WorldActor()
    result = EndFestivalHandler().execute(
        _ctx(actor), _cmd("???", "end-festival", {"festival_id": "entity_1"})
    )
    assert not result.ok
    assert result.reason == "invalid character id"


def test_end_festival_rejects_invalid_festival_id():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room)
    result = EndFestivalHandler().execute(
        _ctx(actor), _cmd(host.id, "end-festival", {"festival_id": "???"})
    )
    assert not result.ok
    assert result.reason == "invalid festival id"


def test_end_festival_rejects_missing_festival():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room)
    result = EndFestivalHandler().execute(
        _ctx(actor), _cmd(host.id, "end-festival", {"festival_id": "entity_9999"})
    )
    assert not result.ok
    assert result.reason == "festival does not exist"


def test_end_festival_rejects_non_festival_target():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room)
    crate = spawn_entity(actor.world, [IdentityComponent(name="crate", kind="item")])
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), crate.id)
    result = EndFestivalHandler().execute(
        _ctx(actor), _cmd(host.id, "end-festival", {"festival_id": str(crate.id)})
    )
    assert not result.ok
    assert result.reason == "that is not a festival"


def test_end_festival_rejects_already_ended():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room, "Host")
    festival, _ = _host_a_festival(actor, room, host)
    end = _cmd(host.id, "end-festival", {"festival_id": str(festival.id)})
    EndFestivalHandler().execute(_ctx(actor), end)
    result = EndFestivalHandler().execute(_ctx(actor), end)
    assert not result.ok
    assert result.reason == "that festival has already ended"


def test_end_festival_rejects_non_host():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room, "Host")
    stranger = _character(actor.world, room, "Stranger")
    festival, _ = _host_a_festival(actor, room, host)
    result = EndFestivalHandler().execute(
        _ctx(actor), _cmd(stranger.id, "end-festival", {"festival_id": str(festival.id)})
    )
    assert not result.ok
    assert result.reason == "only the host can end that festival"


# -- fragments & ordering ----------------------------------------------------------------


def test_hosting_fragment_announces_a_live_party():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room, "Host")
    _host_a_festival(actor, room, host, theme="harvest")
    lines = hosting_fragments(actor.world, host)
    assert "A harvest festival is in full swing here." in lines


def test_hosting_fragment_reports_a_wound_down_party():
    actor = WorldActor()
    room = _room(actor.world)
    host = _character(actor.world, room, "Host")
    festival, _ = _host_a_festival(actor, room, host, theme="harvest")
    EndFestivalHandler().execute(
        _ctx(actor), _cmd(host.id, "end-festival", {"festival_id": str(festival.id)})
    )
    lines = hosting_fragments(actor.world, host)
    assert "The harvest festival here has wound down." in lines


def test_hosting_fragment_empty_for_none_character():
    actor = WorldActor()
    assert hosting_fragments(actor.world, None) == []


def test_hosting_fragment_empty_when_not_in_room():
    actor = WorldActor()
    loose = _character(actor.world)
    assert hosting_fragments(actor.world, loose) == []


def test_hosted_festivals_are_sorted_by_id():
    actor = WorldActor()
    room = _room(actor.world)
    host_a = _character(actor.world, room, "A")
    host_b = _character(actor.world, room, "B")
    _host_a_festival(actor, room, host_a)
    _host_a_festival(actor, room, host_b)
    festivals = hosted_festivals(actor.world)
    assert [str(f.id) for f in festivals] == sorted(str(f.id) for f in festivals)
