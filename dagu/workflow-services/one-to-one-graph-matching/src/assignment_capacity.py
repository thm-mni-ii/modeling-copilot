"""Compute maximum one-to-one capacity without choosing correspondences."""

from collections import defaultdict, deque


def _maximum_matching(reference_ids, adjacent):
    student_matches = {}
    reference_matches = {}
    for start in reference_ids:
        pending = deque([start])
        seen_references = {start}
        previous = {}
        free_student = None
        while pending and free_student is None:
            reference = pending.popleft()
            for student in adjacent[reference]:
                if student in previous:
                    continue
                previous[student] = reference
                if student not in student_matches:
                    free_student = student
                    break
                matched_reference = student_matches[student]
                if matched_reference not in seen_references:
                    seen_references.add(matched_reference)
                    pending.append(matched_reference)
        if free_student is not None:
            student = free_student
            while student is not None:
                reference = previous[student]
                displaced = reference_matches.get(reference)
                reference_matches[reference] = student
                student_matches[student] = reference
                student = displaced
    return len(reference_matches)


def maximum_assignment_for_references(candidate_pairs, reference_ids):
    """Compute capacity for selected references against all their candidates."""
    references = set(reference_ids)
    adjacent = {identity: set() for identity in references}
    for pair in candidate_pairs:
        reference = pair["referenceId"]
        if reference in adjacent:
            adjacent[reference].add(pair["studentId"])
    return _maximum_matching(sorted(references), {
        reference: sorted(students) for reference, students in adjacent.items()
    })


def analyze_assignment_capacity(state):
    """Return matching cardinalities, not a particular matching."""
    reference_components, student_components = {}, {}
    components = []
    for item in state["candidateComponents"]:
        references, students = sorted(item["referenceIds"]), sorted(item["studentIds"])
        if (not references or not students or len(references) != len(set(references))
                or len(students) != len(set(students))):
            raise ValueError("candidate components need unique reference and student IDs")
        component_id = len(components)
        for identity in references:
            if identity in reference_components:
                raise ValueError("reference belongs to multiple candidate components")
            reference_components[identity] = component_id
        for identity in students:
            if identity in student_components:
                raise ValueError("student belongs to multiple candidate components")
            student_components[identity] = component_id
        components.append((references, students, item["pairCount"]))

    isolated_references = state["noCandidateReferenceIds"]
    isolated_students = state["noCandidateStudentIds"]
    if (len(isolated_references) != len(set(isolated_references))
            or len(isolated_students) != len(set(isolated_students))
            or set(isolated_references) & reference_components.keys()
            or set(isolated_students) & student_components.keys()):
        raise ValueError("isolated IDs must be unique and outside candidate components")

    adjacent = defaultdict(set)
    seen_pairs = set()
    pair_counts = [0] * len(components)
    seen_students = set()
    for item in state["candidatePairs"]:
        reference, student = item["referenceId"], item["studentId"]
        pair = (reference, student)
        component_id = reference_components.get(reference)
        if (component_id is None or student_components.get(student) != component_id
                or pair in seen_pairs):
            raise ValueError("candidate pair does not belong to one unique component")
        seen_pairs.add(pair)
        adjacent[reference].add(student)
        seen_students.add(student)
        pair_counts[component_id] += 1

    results = []
    for component_id, (references, students, pair_count) in enumerate(components):
        if (pair_counts[component_id] != pair_count
                or any(not adjacent[reference] for reference in references)
                or any(student not in seen_students for student in students)):
            raise ValueError("candidate component does not match its candidate pairs")
        sorted_adjacent = {reference: sorted(adjacent[reference]) for reference in references}
        results.append({
            "referenceIds": references,
            "studentIds": students,
            "maximumMatches": _maximum_matching(references, sorted_adjacent),
        })
    results.sort(key=lambda item: (item["referenceIds"], item["studentIds"]))
    reference_count = len(reference_components) + len(isolated_references)
    student_count = len(student_components) + len(isolated_students)
    maximum_matches = sum(item["maximumMatches"] for item in results)
    return {
        "referenceCount": reference_count,
        "studentCount": student_count,
        "maximumMatches": maximum_matches,
        "minimumUnmatchedReference": reference_count - maximum_matches,
        "minimumUnmatchedStudent": student_count - maximum_matches,
        "components": results,
    }


def _forced_capacity(adjacent, forced_pairs):
    used_references = {reference for reference, _student in forced_pairs}
    used_students = {student for _reference, student in forced_pairs}
    remaining = {
        reference: [student for student in students if student not in used_students]
        for reference, students in adjacent.items() if reference not in used_references
    }
    return len(forced_pairs) + _maximum_matching(sorted(remaining), remaining)


def analyze_proposal_feasibility(state):
    """Assess capacity only; a compatible proposal is not a confirmed identity."""
    candidate_pairs = [(item["referenceId"], item["studentId"]) for item in state["candidatePairs"]]
    candidate_set = set(candidate_pairs)
    if len(candidate_set) != len(candidate_pairs):
        raise ValueError("candidate pairs must be unique")
    adjacent = defaultdict(list)
    for reference, student in sorted(candidate_pairs):
        adjacent[reference].append(student)
    baseline = _maximum_matching(sorted(adjacent), adjacent)

    conflicting = {(item["referenceId"], item["studentId"]) for item in state["conflictingProposals"]}
    blocked = {(item["referenceId"], item["studentId"]) for item in state["blockedProposals"]}
    excluded = conflicting | blocked
    proposals = [(item["referenceId"], item["studentId"]) for item in state["proposals"]]
    if len(set(proposals)) != len(proposals):
        raise ValueError("proposals must be unique")
    active = sorted(pair for pair in proposals if pair not in excluded)
    if any(pair not in candidate_set for pair in active):
        raise ValueError("proposal is not a candidate pair")
    if (len({reference for reference, _student in active}) != len(active)
            or len({student for _reference, student in active}) != len(active)):
        raise ValueError("active proposals must be one-to-one")

    def assessment(forced_pairs):
        capacity = _forced_capacity(adjacent, forced_pairs)
        return {
            "maximumMatchesIfForced": capacity,
            "status": "preserved" if capacity == baseline else "reduced",
        }

    def pair_ids(pairs):
        return [{"referenceId": reference, "studentId": student} for reference, student in sorted(pairs)]

    return {
        "baselineMaximumMatches": baseline,
        "individual": [
            {"referenceId": reference, "studentId": student, **assessment([(reference, student)])}
            for reference, student in active
        ],
        "joint": {"pairs": pair_ids(active), **assessment(active)},
        "conflictingProposals": pair_ids(conflicting),
        "blockedProposals": pair_ids(blocked),
    }
