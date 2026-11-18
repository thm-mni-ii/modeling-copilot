"""Validate compact JSON and its actual frontend consumer with installed tooling."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from copy import deepcopy

from test_analysis import SERVICES, build, case, contains, endpoints, node, rehash
from analysis_contract import validate_analysis
from test_identity_feedback import with_identity_facts

ROOT = Path(__file__).resolve().parents[4]
CHECK = r"""
const fs = require('fs'), assert = require('node:assert/strict');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const Ajv = require('./web/node_modules/ajv');
const schema = JSON.parse(fs.readFileSync('dagu/workflow-services/analytical-feedback/schemas/output.schema.json'));
const ajv = new Ajv({validateSchema:false, meta:false, allErrors:true});
const validate = ajv.compile(schema);
const candidateSchema = JSON.parse(fs.readFileSync('dagu/workflow-services/synonym-matching/schemas/output.schema.json'));
const validateCandidates = ajv.compile(candidateSchema);
const validateFeedback = ajv.getSchema('analysis-feedback/v3#/$defs/feedbackReportV4');
const ts = require('./web/node_modules/typescript'), Module = require('node:module');
const file = require('node:path').resolve('web/src/utils/analysisFeedback.ts'), compiled = new Module(file, module);
compiled._compile(ts.transpileModule(fs.readFileSync(file,'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText, file);
const {adaptAnalysisFeedback, adaptRecognition, recognitionReportsFromEvaluation, analysisStatus, analysisHintText, analysisFactEvidence} = compiled.exports;
for (const sample of input) {
  if (sample.candidates) {
    assert.equal(validateCandidates(sample.candidates), true, JSON.stringify(validateCandidates.errors));
    if (sample.candidates.result.candidatePairCount) {
      const deferred = structuredClone(sample.candidates);
      const pair = deferred.result.synonymMatrix.find(row => row.matches.length).matches[0];
      pair.scoreStatus = 'not_scored'; pair.scores = null; pair.notScoredReason = 'deferred_computation';
      deferred.result.scoredPairCount--; deferred.result.notScoredPairCount = 1;
      assert.equal(validateCandidates(deferred), true, JSON.stringify(validateCandidates.errors));
      pair.scores = {test:0};
      assert.equal(validateCandidates(deferred), false);
    }
  }
  if (sample.feedback) {
    assert.equal(validateFeedback(sample.feedback), true, JSON.stringify(validateFeedback.errors));
    assert.deepEqual(sample.feedback.feedback, [{type:'recognition', recognition:sample.envelope.result.recognition}]);
  }
  if (sample.envelope.result.schema === 'analysis-feedback/v3') {
    assert.equal(validate(sample.envelope), true, JSON.stringify(validate.errors));
    const invalid = structuredClone(sample.envelope);
    invalid.result.annotations.find(item => item.facts.length).facts[0].status = 'invalid';
    assert.equal(validate(invalid), false);
    assert.throws(() => adaptAnalysisFeedback(invalid, sample.context));
    const badPercent = structuredClone(sample.envelope.result.recognition);
    badPercent.overall.percent = null;
    assert.throws(() => adaptRecognition(badPercent));
    const detail = {id:sample.context.evaluationId, steps:[{status:'succeeded', result:{schema:'feedback-report/v4',
      evaluationId:sample.context.evaluationId, pair:{studentKey:'submission',referenceKey:'ref'}, feedback:[{type:'recognition', recognition:sample.envelope.result.recognition}]}}]};
    assert.deepEqual(recognitionReportsFromEvaluation(detail)[0].recognition, sample.envelope.result.recognition);
    detail.steps.push(detail.steps[0]);
    assert.throws(() => recognitionReportsFromEvaluation(detail));
  }
  const adapted = adaptAnalysisFeedback(sample.envelope.result.schema === "analysis-feedback/v3" ? sample.envelope : sample.envelope.result, sample.context);
  assert.equal(adapted.report.annotations.length, sample.context.submissionObjects.length);
  const invalid = structuredClone(sample.envelope);
  invalid.result.annotations[0].target.id = 'unknown-original-id';
  assert.throws(() => adaptAnalysisFeedback(invalid.result, sample.context));
}
assert.equal(analysisStatus({identity:{status:'supported'}, facts:[]}), 'supported');
assert.equal(analysisStatus({identity:{status:'uniquely_supported'}, facts:[{code:'owner.different',status:'violated'}]}), 'warning');
assert.equal(analysisStatus({identity:{status:'uniquely_supported'}, facts:[{code:'label.equal',status:'satisfied'}]}), 'recognized');
assert.match(analysisHintText({code:'future.unknown'}), /future.unknown/);
assert.match(analysisFactEvidence({evidence:{basis:'direct_observation',reason:'text_unavailable',unavailableReason:'missing_text'}}), /Beschriftung fehlt/);
assert.match(analysisFactEvidence({evidence:{basis:'direct_observation',reason:'text_unavailable',unavailableReason:'unsupported_text'}}), /Format|format/);
"""


def sample(store):
    report = build(with_identity_facts(store))
    return {"envelope": {"schemaVersion": 1, "schema": "workflow-result/v1", "status": "ok", "mode": "aggregate",
                         "capability": "analytical-feedback", "analysisPath": f"analysis/ref/{report['analysisKey']}.json",
                         "analysisKey": report["analysisKey"], "result": report},
            "context": {"evaluationId": "evaluation", "referenceKey": "ref", "modelId": "model",
                        "submissionObjects": list(store.indices["student"].nodes.values()),
                        "referenceObjects": list(store.indices["reference"].nodes.values())}}


class SchemaAndFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node") and (ROOT / "web/node_modules/ajv").exists(), "installed frontend tooling required")
    def test_current_projection_and_stored_legacy_revisions(self):
        nodes = [node("a", label="A"), node("b", label="B"), node("child", label="Child")]
        links = nodes + [node("e", "connection", directed=True), node("parallel", "connection", directed=True)]
        payload = [sample(store) for store in (
            case(nodes, reference_edges=[contains("child", "a")]),
            case(nodes, reference_edges=[contains("child", "a")], submission_edges=[contains("child", "b")]),
            case(nodes, nodes[:2], [contains("child", "a")], [], pairs=[]),
            case(links, reference_edges=endpoints("e", "a", "b") + endpoints("parallel", "a", "b"),
                 submission_edges=endpoints("e", "b", "a") + endpoints("parallel", "a", "b")),
        )]
        legacy_v2 = deepcopy(payload[0])
        report = legacy_v2["envelope"]["result"]
        report["schema"] = "analysis-feedback/v2"
        for item in report["annotations"]:
            item["category"] = "nodes"
        report["recognition"] = {"basis": "uniquely_supported", "overall": report["recognition"]["overall"],
            "categories": {category: {"recognized": 3 if category == "nodes" else 0, "expected": 3 if category == "nodes" else 0,
                "percent": 100.0 if category == "nodes" else None, "evaluationStatus": "evaluated" if category == "nodes" else "not_applicable"}
                for category in ("nodes", "attributes", "connections", "other")}, "unmatchedSubmission": []}
        rehash(report)
        legacy_v2["envelope"]["analysisKey"] = report["analysisKey"]
        validate_analysis(report)
        payload.append(legacy_v2)
        for fixture in json.loads((SERVICES / "analytical-feedback/tests/fixtures/legacy-analysis.json").read_text()):
            payload.append({"envelope": {"result": fixture["report"]}, "context": {
                "evaluationId": "evaluation", "referenceKey": "ref", "modelId": "model",
                "submissionObjects": fixture["objects"], "referenceObjects": fixture["objects"]}})
        result = subprocess.run(["node", "-e", CHECK], input=json.dumps(payload), cwd=ROOT,
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
