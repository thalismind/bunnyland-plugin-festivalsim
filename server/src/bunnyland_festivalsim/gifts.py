"""Gift-giving: hand an item to someone and warm the bond between you.

The ``give-gift`` verb transfers a held item from the giver to a recipient standing in the
same room and grows the reciprocal Foundation ``SocialBond`` between
them. During an active festival the bond boost is larger — gifts mean more on a feast day.

Validation order: invalid giver -> missing giver -> invalid item -> missing item -> not
held -> invalid recipient -> missing recipient -> not a character -> self-gift -> not in the
same room -> transfer.
"""

from __future__ import annotations

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
)
from bunnyland.core.actions import ActionArgument, ActionDefinition, ActionEffort, effort_cost
from bunnyland.core.commands import Lane, SubmittedCommand
from bunnyland.core.events import DomainEvent, EventVisibility
from bunnyland.core.handlers import (
    HandlerContext,
    HandlerResult,
    planned,
    rejected,
    require_character,
    require_entity,
)
from bunnyland.core.mutations import AddEdge, MutationPlan, RemoveEdge
from bunnyland.foundation.social.mechanics import adjusted_bond

from .calendar import active_festival
from .spatial import holder_of, room_of

#: Base bond deltas a gift applies each way (giver->receiver and receiver->giver).
GIFT_AFFINITY = 0.1
GIFT_FAMILIARITY = 0.05
#: Extra deltas applied on top while a festival is underway.
FESTIVAL_AFFINITY_BONUS = 0.1
FESTIVAL_TRUST_BONUS = 0.05


class GiftGivenEvent(DomainEvent):
    """A character gave an item to another character."""

    giver_id: str
    recipient_id: str
    gift_id: str
    festival_key: str = ""


class GiveGiftHandler:
    """Transfer a held item to another character in the room and warm their bond."""

    command_type = "give-gift"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        giver_id, _giver, rejection = require_character(ctx, command.character_id)
        if rejection is not None:
            return rejection
        item_id, item, rejection = require_entity(
            ctx,
            command.payload.get("item_id"),
            invalid_reason="invalid item id",
            missing_reason="item does not exist",
        )
        if rejection is not None:
            return rejection
        holder = holder_of(ctx.world, item_id)
        if holder is None or holder.id != giver_id:
            return rejected("you are not holding that gift")
        recipient_id, recipient, rejection = require_entity(
            ctx,
            command.payload.get("recipient_id"),
            invalid_reason="invalid recipient id",
            missing_reason="recipient does not exist",
        )
        if rejection is not None:
            return rejection
        if not recipient.has_component(CharacterComponent):
            return rejected("you can only give gifts to a character")
        if recipient_id == giver_id:
            return rejected("you cannot gift yourself")
        giver_room = room_of(ctx.world, giver_id)
        recipient_room = room_of(ctx.world, recipient_id)
        if giver_room is None or recipient_room is None or giver_room.id != recipient_room.id:
            return rejected("they are not here")

        festival = active_festival(ctx.world)
        deltas = {"affinity": GIFT_AFFINITY, "familiarity": GIFT_FAMILIARITY}
        if festival is not None:
            deltas = {
                "affinity": GIFT_AFFINITY + FESTIVAL_AFFINITY_BONUS,
                "familiarity": GIFT_FAMILIARITY,
                "trust": FESTIVAL_TRUST_BONUS,
            }
        return planned(
            MutationPlan(
                (
                    RemoveEdge(holder.id, item_id, Contains),
                    AddEdge(
                        recipient_id,
                        item_id,
                        Contains(mode=ContainmentMode.INVENTORY),
                    ),
                    AddEdge(
                        giver_id,
                        recipient_id,
                        adjusted_bond(ctx.world, giver_id, recipient_id, deltas),
                    ),
                    AddEdge(
                        recipient_id,
                        giver_id,
                        adjusted_bond(ctx.world, recipient_id, giver_id, deltas),
                    ),
                )
            ),
            GiftGivenEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(giver_id),
                    room_id=str(giver_room.id),
                    target_ids=(str(recipient_id), str(item_id)),
                    giver_id=str(giver_id),
                    recipient_id=str(recipient_id),
                    gift_id=str(item_id),
                    festival_key=festival.key if festival is not None else "",
                )
            ),
        )


GIVE_GIFT_DEF = ActionDefinition(
    command_type="give-gift",
    title="Give gift",
    description="Give a held item to another character in the room.",
    lane=Lane.WORLD,
    cost=effort_cost(action=ActionEffort.ROUTINE),
    arguments={
        "item_id": ActionArgument(
            title="Gift", description="The held item to give.", kind="entity", required=True
        ),
        "recipient_id": ActionArgument(
            title="Recipient",
            description="The character to give it to.",
            kind="entity",
            required=True,
        ),
    },
)

GIFT_ACTION_DEFINITIONS = (GIVE_GIFT_DEF,)
GIFT_ACTION_HANDLERS = (GiveGiftHandler,)


__all__ = [
    "FESTIVAL_AFFINITY_BONUS",
    "FESTIVAL_TRUST_BONUS",
    "GIFT_ACTION_DEFINITIONS",
    "GIFT_ACTION_HANDLERS",
    "GIFT_AFFINITY",
    "GIFT_FAMILIARITY",
    "GIVE_GIFT_DEF",
    "GiftGivenEvent",
    "GiveGiftHandler",
]
