#!/usr/bin/env python3

import argparse
import csv
import difflib
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path


# Recognises Junos operational commands included in the supplied checklist.
COMMAND_PATTERN = re.compile(
    r"""
    ^.*?(?P<command>
        show\s+
        (?:
            configuration|
            version|
            chassis|
            bgp|
            bfd|
            system|
            interfaces?|
            isis|
            route|
            log
        )
        .*
    )$
    """,
    re.IGNORECASE | re.VERBOSE,
)


# Patterns that may change naturally between PRE and POST captures.
VOLATILE_LINE_PATTERNS = [
    re.compile(r"^\s*$"),
    re.compile(r"current time:", re.IGNORECASE),
    re.compile(r"system booted:", re.IGNORECASE),
    re.compile(r"protocols started:", re.IGNORECASE),
    re.compile(r"last reboot", re.IGNORECASE),
    re.compile(r"last configured", re.IGNORECASE),
]


# Severity indicators searched for in newly added POST lines.
CRITICAL_PATTERNS = [
    re.compile(r"\bdown\b", re.IGNORECASE),
    re.compile(r"\boffline\b", re.IGNORECASE),
    re.compile(r"\bfailed?\b", re.IGNORECASE),
    re.compile(r"\berror\b", re.IGNORECASE),
    re.compile(r"\bfault\b", re.IGNORECASE),
    re.compile(r"\balarm\b", re.IGNORECASE),
    re.compile(r"\bnot\s+running\b", re.IGNORECASE),
    re.compile(r"\bnot\s+established\b", re.IGNORECASE),
]


BENIGN_POST_PATTERNS = [
    re.compile(r"no alarms currently active", re.IGNORECASE),
    re.compile(r"no core files", re.IGNORECASE),
    re.compile(r"0 alarms", re.IGNORECASE),
    re.compile(r"down peers:\s*0", re.IGNORECASE),
]


def canonical_command(line):
    """
    Extract and normalise a Junos command from a CLI transcript line.

    Supports:
      user@router> show bgp summary | no-more
      {master}
      user@router> show bgp summary
      show bgp summary
    """
    stripped = line.strip()

    match = COMMAND_PATTERN.match(stripped)
    if not match:
        return None

    command = match.group("command")

    # Remove trailing output redirection, if present.
    command = re.sub(r"\s*>\s*\S+\s*$", "", command)

    # Normalise whitespace and case.
    command = re.sub(r"\s+", " ", command).strip().lower()

    return command


def normalise_line(line):
    """
    Normalise values that commonly create harmless differences.
    """
    line = line.rstrip()

    # ISO-style timestamps.
    line = re.sub(
        r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?\b",
        "<TIMESTAMP>",
        line,
    )

    # Junos log timestamps such as:
    # Oct 20 12:35:14
    line = re.sub(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\b",
        "<LOG_TIMESTAMP>",
        line,
        flags=re.IGNORECASE,
    )

    # Uptime values.
    line = re.sub(
        r"\b\d+\s+days?,\s+\d+:\d+(?::\d+)?\b",
        "<UPTIME>",
        line,
        flags=re.IGNORECASE,
    )

    # BGP/route age values such as 5d2h, 03:22:10, 12w3d.
    line = re.sub(
        r"\b(?:\d+w)?(?:\d+d)?(?:\d+h)?(?:\d+m)?(?:\d+s)?\b",
        lambda m: "<AGE>" if m.group(0) and re.search(
            r"[wdhms]", m.group(0), re.IGNORECASE
        ) else m.group(0),
        line,
    )

    # Collapse repeated spaces but preserve content.
    return re.sub(r"\s+", " ", line).strip()


def should_ignore_line(line):
    return any(pattern.search(line) for pattern in VOLATILE_LINE_PATTERNS)


def parse_capture(filename):
    """
    Split a CLI capture into:
        command -> output lines

    Repeated executions of the same command receive a sequence suffix.
    """
    path = Path(filename)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {filename}")

    lines = path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()

    sections = OrderedDict()
    occurrence_count = {}
    current_key = None

    for raw_line in lines:
        detected_command = canonical_command(raw_line)

        if detected_command:
            occurrence_count[detected_command] = (
                occurrence_count.get(detected_command, 0) + 1
            )

            occurrence = occurrence_count[detected_command]

            if occurrence == 1:
                current_key = detected_command
            else:
                current_key = f"{detected_command} [occurrence {occurrence}]"

            sections[current_key] = []
            continue

        if current_key is None:
            # Ignore banners and text before the first recognised command.
            continue

        if not should_ignore_line(raw_line):
            sections[current_key].append(normalise_line(raw_line))

    return sections


def contains_new_critical_state(added_lines):
    """
    Return True when added POST lines contain a negative state.
    """
    for line in added_lines:
        if any(pattern.search(line) for pattern in BENIGN_POST_PATTERNS):
            continue

        if any(pattern.search(line) for pattern in CRITICAL_PATTERNS):
            return True

    return False


def compare_sections(pre_sections, post_sections):
    results = []

    commands = list(
        OrderedDict.fromkeys(
            list(pre_sections.keys()) + list(post_sections.keys())
        )
    )

    for command in commands:
        pre_output = pre_sections.get(command)
        post_output = post_sections.get(command)

        if pre_output is None:
            results.append({
                "command": command,
                "status": "REVIEW",
                "reason": "Command exists only in POST capture",
                "added": post_output or [],
                "removed": [],
                "diff": [],
            })
            continue

        if post_output is None:
            results.append({
                "command": command,
                "status": "FAIL",
                "reason": "Command is missing from POST capture",
                "added": [],
                "removed": pre_output,
                "diff": [],
            })
            continue

        if pre_output == post_output:
            results.append({
                "command": command,
                "status": "PASS",
                "reason": "No material difference",
                "added": [],
                "removed": [],
                "diff": [],
            })
            continue

        diff_lines = list(
            difflib.unified_diff(
                pre_output,
                post_output,
                fromfile="PRE",
                tofile="POST",
                lineterm="",
            )
        )

        added = [
            line[1:]
            for line in diff_lines
            if line.startswith("+") and not line.startswith("+++")
        ]

        removed = [
            line[1:]
            for line in diff_lines
            if line.startswith("-") and not line.startswith("---")
        ]

        if contains_new_critical_state(added):
            status = "FAIL"
            reason = "POST contains a new potentially critical state"
        else:
            status = "CHANGED"
            reason = "PRE and POST outputs are different"

        results.append({
            "command": command,
            "status": status,
            "reason": reason,
            "added": added,
            "removed": removed,
            "diff": diff_lines,
        })

    return results


def write_text_report(results, output_file):
    status_symbol = {
        "PASS": "[PASS]",
        "CHANGED": "[CHANGED]",
        "REVIEW": "[REVIEW]",
        "FAIL": "[FAIL]",
    }

    counts = {
        status: sum(1 for item in results if item["status"] == status)
        for status in status_symbol
    }

    lines = [
        "=" * 90,
        "JUNOS PRE/POST ACTIVITY COMPARISON",
        "=" * 90,
        "",
        f"PASS    : {counts['PASS']}",
        f"CHANGED : {counts['CHANGED']}",
        f"REVIEW  : {counts['REVIEW']}",
        f"FAIL    : {counts['FAIL']}",
        "",
        "SUMMARY",
        "-" * 90,
    ]

    for item in results:
        lines.append(
            f"{status_symbol[item['status']]:<12} "
            f"{item['command']} - {item['reason']}"
        )

    for item in results:
        if item["status"] == "PASS":
            continue

        lines.extend([
            "",
            "=" * 90,
            f"COMMAND : {item['command']}",
            f"STATUS  : {item['status']}",
            f"REASON  : {item['reason']}",
            "-" * 90,
        ])

        if item["diff"]:
            lines.extend(item["diff"])
        else:
            if item["removed"]:
                lines.append("Removed from POST:")
                lines.extend(f"- {line}" for line in item["removed"])

            if item["added"]:
                lines.append("Added in POST:")
                lines.extend(f"+ {line}" for line in item["added"])

    Path(output_file).write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def write_csv_report(results, output_file):
    with open(output_file, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "command",
                "status",
                "reason",
                "removed_lines",
                "added_lines",
            ],
        )
        writer.writeheader()

        for item in results:
            writer.writerow({
                "command": item["command"],
                "status": item["status"],
                "reason": item["reason"],
                "removed_lines": " || ".join(item["removed"]),
                "added_lines": " || ".join(item["added"]),
            })


def write_json_report(results, output_file):
    Path(output_file).write_text(
        json.dumps(results, indent=2),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Compare Junos PRE and POST CLI output files."
    )

    parser.add_argument(
        "--pre",
        required=True,
        help="PRE-activity CLI output file",
    )
    parser.add_argument(
        "--post",
        required=True,
        help="POST-activity CLI output file",
    )
    parser.add_argument(
        "--output-prefix",
        default="junos_pre_post_report",
        help="Output filename prefix",
    )
    parser.add_argument(
        "--fail-on-change",
        action="store_true",
        help="Return failure for any changed output",
    )

    args = parser.parse_args()

    pre_sections = parse_capture(args.pre)
    post_sections = parse_capture(args.post)

    if not pre_sections:
        print(
            "ERROR: No recognised Junos commands found in PRE file.",
            file=sys.stderr,
        )
        return 2

    if not post_sections:
        print(
            "ERROR: No recognised Junos commands found in POST file.",
            file=sys.stderr,
        )
        return 2

    results = compare_sections(pre_sections, post_sections)

    text_file = f"{args.output_prefix}.txt"
    csv_file = f"{args.output_prefix}.csv"
    json_file = f"{args.output_prefix}.json"

    write_text_report(results, text_file)
    write_csv_report(results, csv_file)
    write_json_report(results, json_file)

    print(f"Text report : {text_file}")
    print(f"CSV report  : {csv_file}")
    print(f"JSON report : {json_file}")
    print()

    for item in results:
        print(
            f"{item['status']:<8} "
            f"{item['command']}: {item['reason']}"
        )

    fail_count = sum(
        1 for item in results if item["status"] == "FAIL"
    )
    changed_count = sum(
        1 for item in results if item["status"] == "CHANGED"
    )

    if fail_count:
        return 2

    if args.fail_on_change and changed_count:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())