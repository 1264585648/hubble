from __future__ import annotations

from copy import deepcopy
from typing import Any

from hubble.events.models import EventEnvelope
from hubble.intake.models import IntakeDecision, IntakeRule


class IntakeRuleEngine:
    """Evaluate pre-alert rules before events enter Alert Core.

    This layer owns filtering, lightweight rewriting and tagging. It must not create alerts,
    incidents, analyses or notifications.
    """

    def __init__(self, rules: list[IntakeRule] | None = None) -> None:
        self._rules: dict[str, IntakeRule] = {}
        for rule in rules or []:
            self.upsert_rule(rule)

    def list_rules(self) -> list[IntakeRule]:
        return sorted(self._rules.values(), key=lambda item: item.priority)

    def upsert_rule(self, rule: IntakeRule) -> IntakeRule:
        self._rules[rule.id] = rule
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None

    def evaluate(self, event: EventEnvelope) -> IntakeDecision:
        current_event = _mark_ingested(event)

        for rule in self.list_rules():
            if not rule.enabled or not _matches(rule.match, current_event):
                continue

            rewritten = _apply_rule(rule, current_event)
            allowed = rule.action != "drop"
            return IntakeDecision(
                allowed=allowed,
                action=rule.action,
                matched_rule_id=rule.id,
                matched_rule_name=rule.name,
                reason=rule.reason or f"matched intake rule: {rule.name}",
                event=rewritten,
            )

        return IntakeDecision(event=current_event)


def _mark_ingested(event: EventEnvelope) -> EventEnvelope:
    payload = event.model_dump(mode="python")
    payload["type"] = "alert.ingested"
    return EventEnvelope(**payload)


def _apply_rule(rule: IntakeRule, event: EventEnvelope) -> EventEnvelope:
    if rule.action == "drop":
        return event

    payload = event.model_dump(mode="python")
    data = deepcopy(payload.get("data") or {})

    if rule.action in {"rewrite", "tag"}:
        labels = data.setdefault("labels", {})
        for key, value in rule.add_labels.items():
            labels[key] = value

    if rule.action == "rewrite":
        for key, value in rule.set_fields.items():
            _set_path(data, key, value)

    payload["data"] = data
    extensions = dict(payload.get("extensions") or {})
    extensions["intake_rule_id"] = rule.id
    extensions["intake_rule_name"] = rule.name
    payload["extensions"] = extensions
    return EventEnvelope(**payload)


def _matches(match: dict[str, Any], event: EventEnvelope) -> bool:
    if not match:
        return True

    for key, expected in match.items():
        if key == "source":
            actual = event.source
        elif key == "type":
            actual = event.type
        elif key == "subject_contains":
            actual = event.subject or ""
            if str(expected) not in actual:
                return False
            continue
        elif key.startswith("data."):
            actual = _get_path(event.data, key.removeprefix("data."))
        elif key.startswith("labels."):
            actual = _get_path(event.data, f"labels.{key.removeprefix('labels.')}")
        elif key.startswith("annotations."):
            actual = _get_path(event.data, f"annotations.{key.removeprefix('annotations.')}")
        else:
            actual = _get_path(event.data, key)

        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False

    return True


def _get_path(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _set_path(data: dict[str, Any], path: str, value: Any) -> None:
    current: dict[str, Any] = data
    parts = path.split(".")
    for part in parts[:-1]:
        next_value = current.setdefault(part, {})
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value
