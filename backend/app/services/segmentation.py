from ..schemas import Segment, SegmentRuleGroup


def condition_matches(customer, condition) -> bool:
    actual = getattr(customer, condition.field)
    expected = condition.value
    if condition.operator == "contains":
        return str(expected).lower() in str(actual).lower()
    if condition.operator == "in":
        values = expected if isinstance(expected, list) else [expected]
        return any(str(actual).lower() == str(value).lower() for value in values)
    try:
        if condition.operator in {"gt", "gte", "lt", "lte"}:
            actual, expected = float(actual), float(expected)
    except (TypeError, ValueError):
        return False
    return {
        "eq": actual == expected,
        "neq": actual != expected,
        "gt": actual > expected if isinstance(actual, (int, float)) else False,
        "gte": actual >= expected if isinstance(actual, (int, float)) else False,
        "lt": actual < expected if isinstance(actual, (int, float)) else False,
        "lte": actual <= expected if isinstance(actual, (int, float)) else False,
    }.get(condition.operator, False)


def matches(customer, group: SegmentRuleGroup) -> bool:
    outcomes = [condition_matches(customer, condition) for condition in group.conditions]
    outcomes.extend(matches(customer, child) for child in group.groups)
    if not outcomes:
        return True
    return all(outcomes) if group.combinator == "AND" else any(outcomes)


def segment_members(segment: Segment, customers: list) -> list:
    if segment.mode == "Static" and segment.estimate_basis == "synthetic_sample":
        member_ids = set(segment.sample_customer_ids)
        return [customer for customer in customers if customer.id in member_ids]
    if segment.estimate_basis == "seed_estimate" and not segment.rules.conditions and not segment.rules.groups:
        return [customer for customer in customers if customer.segment.casefold() == segment.name.casefold()]
    return [customer for customer in customers if matches(customer, segment.rules)]
