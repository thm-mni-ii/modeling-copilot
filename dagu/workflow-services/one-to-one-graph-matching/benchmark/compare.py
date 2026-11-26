#!/usr/bin/env python3
"""Compare two benchmark summaries (evaluate.py --summary) pair by pair.

Lists per case the certain pairs gained and lost, new wrong pairs, connection changes and hint changes.
Exit code 1 when a certain correct pair is lost or a new wrong certain pair appears; that is the
acceptance rule of every development step.

Usage: python compare.py OLD_SUMMARY NEW_SUMMARY
"""

import json
import sys
from collections import Counter


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    old, new = (json.loads(open(path, encoding="utf-8").read()) for path in sys.argv[1:3])
    totals, failing, lines = Counter(), False, []
    for case in sorted(old.keys() | new.keys()):
        if case not in old or case not in new:
            lines.append(f"{case}: only in {'new' if case in new else 'old'}")
            continue
        a, b = old[case], new[case]
        changes = []
        for identity in sorted(a["elements"].keys() | b["elements"].keys()):
            before, after = a["elements"].get(identity, {}), b["elements"].get(identity, {})
            was, now = before.get("outcome"), after.get("outcome")
            if was == now and before.get("matchedTo") == after.get("matchedTo"):
                continue
            label = f"{identity} ({after.get('category') or before.get('category')})"
            if was in ("certain", "structural") and now not in ("certain", "structural"):
                changes.append(f"  LOST {label}: {was} -> {now}")
                totals["lost"] += 1
                failing = True
            elif now == "wrong" and was != "wrong":
                changes.append(f"  WRONG {label}: {was} -> wrong ({after.get('matchedTo')})")
                totals["wrong"] += 1
                failing = True
            elif now in ("certain", "structural") and was not in ("certain", "structural"):
                changes.append(f"  gained {label}: {was} -> {now}")
                totals["gained"] += 1
            else:
                changes.append(f"  changed {label}: {was} -> {now}")
                totals["changed"] += 1
        for identity in sorted(a["connections"].keys() | b["connections"].keys()):
            was, now = a["connections"].get(identity), b["connections"].get(identity)
            if was == now:
                continue
            if was == identity:
                changes.append(f"  LOST connection {identity}: -> {now}")
                totals["connections_lost"] += 1
                failing = True
            elif now == identity:
                totals["connections_gained"] += 1
            elif now is not None:
                changes.append(f"  WRONG connection {identity}: {was} -> {now}")
                totals["connections_wrong"] += 1
                failing = True
        hints_before, hints_after = {tuple(item) for item in a["hints"]}, {tuple(item) for item in b["hints"]}
        totals["hints_added"] += len(hints_after - hints_before)
        totals["hints_removed"] += len(hints_before - hints_after)
        if changes or a["recognition"] != b["recognition"]:
            lines.append(f"{case}: recognition {a['recognition'][0]}/{a['recognition'][1]} -> {b['recognition'][0]}/{b['recognition'][1]}")
            lines.extend(changes)
    print("\n".join(lines))
    print("totals", dict(totals))
    print("FAIL" if failing else "OK")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
