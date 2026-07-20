"""Extract concise abyss-team traces from an OKNTE log file."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROUTE_MARKERS = ("Baicang abyss opener", "Chiz Yingxu abyss opener", "Chiz Yingxu abyss cycle")
TIMESTAMP_PATTERN = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})")
LOCK_PATTERN = re.compile(r"strict route locked: (?P<route>.+?) / (?P<step>.+)$")
ACTION_PATTERN = re.compile(r"planner action (?P<char>\w+) -> (?P<action>[^,]+)")
SWITCH_PATTERN = re.compile(
    r"planner switch (?P<source>\w+) -> (?P<target>\w+).+?reason (?P<reason>.+)$"
)
KEEP_PATTERN = re.compile(r"planner keep (?P<char>\w+).+?reason (?P<reason>.+)$")
REACTION_PATTERN = re.compile(
    r"strict route completed entry reaction (?P<source>\w+) -> (?P<target>\w+):"
)
NOT_IN_TEAM_PATTERN = re.compile(r"\) not in team (?P<seconds>\d+(?:\.\d+)?)s$")
TEAM_HANDOFF_PATTERN = re.compile(
    r"队伍交接确认：(?P<source>.+?) -> (?P<target>.+)$"
)


@dataclass(slots=True)
class TraceEvent:
    timestamp: str
    kind: str
    detail: str


@dataclass(slots=True)
class AbyssTrace:
    route: str
    started_at: str
    status: str = "pending"
    events: list[TraceEvent] = field(default_factory=list)

    def add(self, timestamp: str, kind: str, detail: str) -> None:
        self.events.append(TraceEvent(timestamp, kind, detail))

    def action_sequence(self) -> list[str]:
        return [event.detail for event in self.events if event.kind == "action"]

    def reaction_sequence(self) -> list[str]:
        return [event.detail for event in self.events if event.kind == "reaction"]

    def sound_interrupt_count(self) -> int:
        return sum(event.kind == "sound" for event in self.events)

    def diagnosis(self) -> list[str]:
        issues = []
        if self.status != "fulfilled":
            issues.append(f"route status is {self.status}")

        if "Baicang abyss opener" in self.route:
            returned = any(
                event.kind == "switch" and event.detail.startswith("Daphneel->Baicang")
                for event in self.events
            )
            if not returned:
                issues.append("no Daphneel->Baicang return switch recorded")

        if "Chiz Yingxu abyss" in self.route:
            action_counts = Counter(self.action_sequence())
            for action in ("Zero:Zero_skill", "Zero:Zero_ultimate", "Chiz:Chiz_ultimate"):
                if action_counts[action] >= 10:
                    issues.append(f"{action} retried {action_counts[action]} times")

            zero_waits = sum(
                event.kind == "wait" and event.detail.startswith("Zero:") for event in self.events
            )
            if zero_waits >= 5:
                issues.append(f"Zero held field for {zero_waits} strict-route wait ticks")

        if "Chiz Yingxu abyss cycle" in self.route:
            reactions = set(self.reaction_sequence())
            for required in ("Chiz->Jiuyuan", "Zero->Yi"):
                if required not in reactions:
                    issues.append(f"missing reaction {required}")

        wait_count = sum(
            event.kind == "action" and "wait_for_strict_route_action" in event.detail
            for event in self.events
        )
        if wait_count >= 20:
            issues.append(f"strict route waited {wait_count} action ticks")
        sound_timeouts = sum(event.kind == "sound_timeout" for event in self.events)
        if sound_timeouts:
            issues.append(f"{sound_timeouts} sound actions discarded after timeout")
        team_gaps = [
            float(event.detail)
            for event in self.events
            if event.kind == "team_gap"
        ]
        if team_gaps and max(team_gaps) >= 2.0:
            issues.append(f"team UI unavailable for {max(team_gaps):.2f}s during route")
        return issues


def _timestamp(line: str) -> str:
    match = TIMESTAMP_PATTERN.search(line)
    return match.group("timestamp") if match else "unknown-time"


def _is_target_route(route: str) -> bool:
    return any(marker in route for marker in ROUTE_MARKERS)


def parse_abyss_traces(lines: list[str]) -> list[AbyssTrace]:
    traces: list[AbyssTrace] = []
    current: AbyssTrace | None = None

    for line in lines:
        timestamp = _timestamp(line)
        lock = LOCK_PATTERN.search(line)
        if lock and _is_target_route(lock.group("route")):
            if current is not None:
                traces.append(current)
            current = AbyssTrace(lock.group("route"), timestamp)
            current.add(timestamp, "step", lock.group("step"))
            continue

        if current is None:
            continue

        team_gap = NOT_IN_TEAM_PATTERN.search(line)
        if team_gap:
            current.add(timestamp, "team_gap", team_gap.group("seconds"))
            continue

        handoff = TEAM_HANDOFF_PATTERN.search(line)
        if handoff:
            current.add(
                timestamp,
                "handoff",
                f"{handoff.group('source')}->{handoff.group('target')}",
            )
            continue

        action = ACTION_PATTERN.search(line)
        if action:
            current.add(
                timestamp,
                "action",
                f"{action.group('char')}:{action.group('action')}",
            )
            continue

        reaction = REACTION_PATTERN.search(line)
        if reaction:
            current.add(
                timestamp,
                "reaction",
                f"{reaction.group('source')}->{reaction.group('target')}",
            )
            continue

        switch = SWITCH_PATTERN.search(line)
        if switch:
            detail = (
                f"{switch.group('source')}->{switch.group('target')} ({switch.group('reason')})"
            )
            current.add(timestamp, "switch", detail)
            if (
                current.status == "fulfilled"
                and "Baicang abyss opener" in current.route
                and switch.group("target") == "Baicang"
            ):
                traces.append(current)
                current = None
            continue

        keep = KEEP_PATTERN.search(line)
        if keep and "strict route" in keep.group("reason"):
            current.add(
                timestamp,
                "wait",
                f"{keep.group('char')}:{keep.group('reason')}",
            )
            continue

        if "strict route skips" in line:
            current.add(timestamp, "skip", line.split("strict route skips", 1)[1].strip())
            continue

        if "strict route deadline expired" in line:
            current.status = "expired"
            current.add(timestamp, "deadline", "route deadline expired")
            traces.append(current)
            current = None
            continue

        if "strict route fulfilled:" in line and current.route in line:
            current.status = "fulfilled"
            current.add(timestamp, "status", "route fulfilled")
            continue

        if "Combat sleep interrupted by sound action" in line:
            current.add(timestamp, "sound", "combat yielded to sound action")
            continue

        if "Sound action discarded after timeout" in line:
            current.add(timestamp, "sound_timeout", "sound action timed out")
            continue

        if "Executing dodge" in line or "Executing counter attack" in line:
            current.add(timestamp, "sound", line.rsplit(":", 1)[-1].strip())

    if current is not None:
        traces.append(current)
    return traces


def analyze_log(path: Path) -> list[AbyssTrace]:
    return parse_abyss_traces(path.read_text(encoding="utf-8", errors="replace").splitlines())


def format_trace_report(traces: list[AbyssTrace]) -> str:
    if not traces:
        return "No abyss team route traces found."

    sections = []
    for index, trace in enumerate(traces, start=1):
        actions = " -> ".join(trace.action_sequence()) or "none"
        reactions = " -> ".join(trace.reaction_sequence()) or "none"
        skips = sum(event.kind == "skip" for event in trace.events)
        switches = sum(event.kind == "switch" for event in trace.events)
        diagnosis = "; ".join(trace.diagnosis()) or "ok"
        sections.append(
            "\n".join(
                [
                    f"[{index}] {trace.route}",
                    f"start: {trace.started_at}",
                    f"status: {trace.status}",
                    f"actions: {actions}",
                    f"reactions: {reactions}",
                    f"switches: {switches}, optional_skips: {skips}, "
                    f"sound_events: {trace.sound_interrupt_count()}",
                    f"diagnosis: {diagnosis}",
                ]
            )
        )
    return "\n\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_path", type=Path, help="Path to ok-script.log")
    args = parser.parse_args()
    print(format_trace_report(analyze_log(args.log_path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
