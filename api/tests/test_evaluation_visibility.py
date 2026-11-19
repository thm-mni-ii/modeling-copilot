"""Student results expose published counts without protected reference detail."""
from modeling_api.core.auth import User
from modeling_api.services.evaluations import can_view_analysis, student_step_results, _enrich_step_output


def test_existing_admin_and_moderator_boundaries_remain_explicit():
    assert can_view_analysis(User(id="admin", global_role="ADMIN"))
    assert can_view_analysis(User(id="moderator", global_role="MODERATOR"))
    assert can_view_analysis(User(id="moderator", roles=["MODERATOR"]))
    assert not can_view_analysis(User(id="student", global_role="STUDENT"))
    assert not can_view_analysis(User(id="student"))


def test_students_receive_only_aggregate_recognition_and_own_unmatched_ids():
    row = {"recognized": 1, "expected": 2, "percent": 50, "evaluationStatus": "evaluated", "referenceNames": ["protected"]}
    recognition = {"basis": "uniquely_supported", "categories": {category: row for category in ("nodes", "attributes", "connections", "other")},
                   "overall": row, "unmatchedSubmission": [{"id": "own", "kind": "modelElement", "category": "nodes", "referenceId": "protected"}], "diagnostics": "protected"}
    steps = [{"id": "analysis", "status": "succeeded", "description": "protected", "resultSummary": "protected", "result": {"schema": "analysis-feedback/v2", "referenceHints": ["protected"]}},
             {"id": "graph", "status": "succeeded", "result": {"schema": "graph-result/v1", "graph": "protected"}},
             {"id": "feedback", "status": "succeeded", "result": {"schema": "feedback-report/v2", "evaluationId": "evaluation", "pair": {"referenceKey": "reference_1"}, "recognition": recognition, "diagnostics": "protected"}}]
    public = student_step_results(steps)
    assert public[0]["result"] is None and public[1]["result"] is None
    assert "protected" not in str(public)
    assert public[2]["result"]["recognition"]["categories"]["nodes"]["recognized"] == 1
    assert public[2]["result"]["recognition"]["unmatchedSubmission"] == [{"id": "own", "kind": "modelElement", "category": "nodes"}]
    assert steps[0]["result"]["referenceHints"] == ["protected"]


def test_full_new_analysis_stdout_remains_available_to_authorized_consumers():
    envelope = {"schemaVersion": 1, "schema": "workflow-result/v1", "status": "ok", "capability": "analytical-feedback", "result": {"schema": "analysis-feedback/v2", "annotations": []}}
    step = {"id": "generate_analytical_feedback_reference_1", "resultSummary": envelope}
    assert _enrich_step_output([step])[0]["result"] == envelope["result"]


def test_grouped_recognition_preserves_public_type_labels_without_reference_details():
    counts = {"recognized": 2, "expected": 3, "percent": 200 / 3, "evaluationStatus": "evaluated"}
    bucket = {"id": "bucket", "label": "Declared group", "kind": "modelElement", "grouped": True, **counts, "referenceNames": ["protected"]}
    report = {"schema": "feedback-report/v3", "evaluationId": "evaluation", "pair": {"referenceKey": "ref"},
              "recognition": {"basis": "uniquely_supported", "buckets": [bucket], "overall": counts,
                              "unmatchedSubmission": [{"id": "own", "kind": "connection", "referenceId": "protected"}]}}
    public = student_step_results([{"id": "feedback", "result": report}])[0]["result"]
    assert public["recognition"]["buckets"][0]["label"] == "Declared group"
    assert public["recognition"]["buckets"][0]["recognized"] == 2
    assert "protected" not in str(public)
