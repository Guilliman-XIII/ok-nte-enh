import time
from collections.abc import Iterable

from src.combat.planner.context import CombatContext
from src.combat.planner.types import FollowupStep, Planner


def _exact_team(chars, required_types) -> bool:
    chars = list(chars)
    return len(chars) == len(required_types) and all(
        sum(isinstance(char, char_type) for char in chars) == 1 for char_type in required_types
    )


def is_baicang_abyss_team(chars: Iterable) -> bool:
    from src.char.Baicang import Baicang
    from src.char.Daphneel import Daphneel
    from src.char.Hania import Hania
    from src.char.Sakiri import Sakiri

    return _exact_team(chars, (Baicang, Daphneel, Hania, Sakiri))


def is_chiz_abyss_team(chars: Iterable) -> bool:
    from src.char.Chiz import Chiz
    from src.char.Jiuyuan import Jiuyuan
    from src.char.Yi import Yi
    from src.char.Zero import Zero

    return _exact_team(chars, (Chiz, Jiuyuan, Yi, Zero))


def should_use_default_arc(char, chars: Iterable) -> bool:
    chars = list(chars)
    if is_baicang_abyss_team(chars):
        from src.char.Baicang import Baicang
        from src.char.Daphneel import Daphneel

        return isinstance(char, (Baicang, Daphneel))
    if is_chiz_abyss_team(chars):
        return False
    return True


def team_strategy_source(chars):
    chars = list(chars)
    if is_baicang_abyss_team(chars):
        from src.char.Baicang import Baicang

        return next(char for char in chars if isinstance(char, Baicang))
    if is_chiz_abyss_team(chars):
        from src.char.Chiz import Chiz

        return next(char for char in chars if isinstance(char, Chiz))
    return None


def publish_team_strategy(context: CombatContext) -> None:
    if is_baicang_abyss_team(context.chars):
        request_baicang_opener(context)
    elif is_chiz_abyss_team(context.chars):
        request_chiz_route(context, opener=True)


def _timeout_after(seconds):
    started_at = time.monotonic()

    def expired():
        duration = seconds() if callable(seconds) else seconds
        return time.monotonic() - started_at >= duration

    return expired


def request_baicang_opener(context: CombatContext) -> None:
    if not is_baicang_abyss_team(context.chars):
        return

    from src.char.Baicang import Baicang
    from src.char.Daphneel import Daphneel
    from src.char.Hania import Hania
    from src.char.Sakiri import Sakiri

    sakiri = next(char for char in context.chars if isinstance(char, Sakiri))
    hania = next(char for char in context.chars if isinstance(char, Hania))
    daphneel = next(char for char in context.chars if isinstance(char, Daphneel))
    baicang = next(char for char in context.chars if isinstance(char, Baicang))

    context.request_route(
        [
            FollowupStep.for_action(
                sakiri,
                Planner.ActionSlot.SKILL,
                reason="Sakiri holds skill to group enemies",
                optional=True,
            ),
            FollowupStep.for_action(
                hania,
                Planner.ActionSlot.ULTIMATE,
                reason="Hania opens the damage window",
                optional=True,
            ),
            FollowupStep.for_action(
                hania,
                Planner.ActionSlot.SKILL,
                reason="Hania deploys off-field damage",
                optional=True,
            ),
            FollowupStep.for_action(
                daphneel,
                Planner.ActionSlot.SKILL,
                reason="Daphneel primes dark damage",
                optional=True,
            ),
            FollowupStep.for_action(
                daphneel,
                Planner.ActionSlot.ULTIMATE,
                reason="Daphneel spends the burst before Baicang",
                optional=True,
            ),
        ],
        reason="Baicang abyss opener",
        until=_timeout_after(lambda: baicang.ABYSS_OPENER_TIMEOUT),
        return_to_source=False,
    )


def request_chiz_route(context: CombatContext, opener: bool) -> None:
    if not is_chiz_abyss_team(context.chars):
        return

    from src.char.Chiz import Chiz
    from src.char.Jiuyuan import Jiuyuan
    from src.char.Yi import Yi
    from src.char.Zero import Zero

    chiz = next(char for char in context.chars if isinstance(char, Chiz))
    jiuyuan = next(char for char in context.chars if isinstance(char, Jiuyuan))
    yi = next(char for char in context.chars if isinstance(char, Yi))
    zero = next(char for char in context.chars if isinstance(char, Zero))

    if opener:
        steps = [
            FollowupStep.for_action(
                jiuyuan,
                Planner.ActionSlot.SKILL,
                reason="Jiuyuan groups enemies for Yingxu",
                optional=True,
            ),
            FollowupStep.for_action(
                zero,
                Planner.ActionSlot.ULTIMATE,
                reason="Zero adds light setup",
                optional=True,
            ),
            FollowupStep.for_action(
                zero,
                Planner.ActionSlot.SKILL,
                reason="Zero primes the first element ring",
            ),
        ]
    else:
        steps = [
            FollowupStep.for_entry_reaction(
                jiuyuan,
                reason="Jiuyuan triggers Creation after Chiz field time",
            ),
            FollowupStep.for_action(
                jiuyuan,
                Planner.ActionSlot.ULTIMATE,
                reason="Jiuyuan adds off-field spirit damage",
                optional=True,
            ),
            FollowupStep.for_action(
                zero,
                Planner.ActionSlot.ULTIMATE,
                reason="Zero refreshes light setup",
                optional=True,
            ),
            FollowupStep.for_action(
                zero,
                Planner.ActionSlot.SKILL,
                reason="Zero primes the aspect reaction",
            ),
            FollowupStep.for_entry_reaction(
                yi,
                reason="Yi triggers Delay",
            ),
            FollowupStep.for_action(
                yi,
                Planner.ActionSlot.ULTIMATE,
                reason="Yi applies ultimate setup",
                optional=True,
            ),
            FollowupStep.for_action(
                yi,
                Planner.ActionSlot.SKILL,
                reason="Yi applies aspect setup",
            ),
            FollowupStep.for_action(
                jiuyuan,
                Planner.ActionSlot.SKILL,
                reason="Jiuyuan regroups before Chiz returns",
                optional=True,
            ),
        ]
    route_name = "opener" if opener else "cycle"
    context.request_route(
        steps,
        reason=f"Chiz Yingxu abyss {route_name}",
        until=_timeout_after(lambda: chiz.ABYSS_ROUTE_TIMEOUT),
        return_to_source=True,
    )
