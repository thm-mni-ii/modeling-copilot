"""Record decisions at their source without changing matching behavior."""

from artifacts import content_hash


def record(events, phase, rule, reference_id, student_id, outcome, reasons, *, depends_on=(), **details):
    if events is None:
        return
    event = {"phase": phase, "rule": rule, "referenceId": reference_id, "studentId": student_id,
             "outcome": outcome, "reasonCodes": list(reasons), "dependsOn": list(depends_on),
             "details": details}
    event["id"] = "decision:" + content_hash(event)
    events.append(event)
