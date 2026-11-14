"""Validate emitted JSON and the actual frontend adapter with installed tooling."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from test_analysis import SERVICES, build, case, contains, containment_evidence, endpoints, node
from test_facts import with_facts

ROOT = Path(__file__).resolve().parents[4]
CHECK = r"""
const fs = require('fs'), assert = require('node:assert/strict');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const Ajv = require('./web/node_modules/ajv');
const schema = JSON.parse(fs.readFileSync('dagu/workflow-services/analytical-feedback/schemas/output.schema.json'));
// This contract uses the common draft-07/2020-12 keywords supported by installed AJV.
const validate = new Ajv({validateSchema:false, meta:false, allErrors:true}).compile(schema);
for (const sample of input) {
  if (sample.envelope.result.contractVersion) assert.equal(validate(sample.envelope), true, JSON.stringify(validate.errors));
  const invalid = structuredClone(sample.envelope);
  invalid.result.annotations[0].status = 'incorrect';
  assert.equal(validate(invalid), false);
}
const ts = require('./web/node_modules/typescript');
const Module = require('node:module');
const file = require('node:path').resolve('web/src/utils/analysisFeedback.ts');
const compiled = new Module(file, module);
compiled._compile(ts.transpileModule(fs.readFileSync(file,'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText, file);
const {adaptAnalysisFeedback, analysisStatus, analysisHintText} = compiled.exports;
for (const sample of input) {
  const adapted = adaptAnalysisFeedback(sample.envelope, sample.context);
  assert.equal(adapted.report.annotations.length, sample.context.submissionObjects.length);
  if (sample.envelope.result.contractVersion === '1.2') {
    const invalidFact = structuredClone(sample.envelope);
    invalidFact.result.annotations[0].facts[0].status = 'incorrect';
    assert.equal(validate(invalidFact), false);
    assert.throws(() => adaptAnalysisFeedback(invalidFact, sample.context));
    const open = sample.envelope.result.annotations.find(item => item.facts.some(fact => ['unresolved', 'violated', 'not_evaluated'].includes(fact.status)));
    if (open) {
      const falseComplete = structuredClone(sample.envelope);
      falseComplete.result.annotations.find(item => item.target.id === open.target.id).consistency = 'fully_consistent';
      assert.throws(() => adaptAnalysisFeedback(falseComplete, sample.context));
    }
  }
  const invalid = structuredClone(sample.envelope);
  invalid.result.annotations[0].target.id = 'unknown-original-id';
  assert.throws(() => adaptAnalysisFeedback(invalid, sample.context));
  if (sample.envelope.result.contractVersion && sample.envelope.result.referenceHints.length) {
    const badHint = structuredClone(sample.envelope);
    badHint.result.referenceHints[0].targets[0].kind = 'connection';
    assert.throws(() => adaptAnalysisFeedback(badHint, sample.context));
  }
}
assert.equal(analysisStatus({status:'ambiguous'}), 'unresolved');
assert.match(analysisHintText({code:'future.unknown'}), /future.unknown/);
"""


def sample(store):
    report = build(store)
    path = f"analysis/ref/{report['analysisKey']}.json"
    envelope = {"schemaVersion": 1, "schema": "workflow-result/v1", "status": "ok", "mode": "aggregate",
                "capability": "analytical-feedback", "analysisPath": path, "analysisKey": report["analysisKey"],
                "metadata": {"analysisPath": path, "analysisKey": report["analysisKey"]}, "result": report}
    return {"envelope": envelope, "context": {"evaluationId": "evaluation", "referenceKey": "ref", "modelId": "model",
            "submissionObjects": list(store.indices["student"].nodes.values()),
            "referenceObjects": list(store.indices["reference"].nodes.values())}}


class SchemaAndFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node") and (ROOT / "web/node_modules/ajv").exists(), "installed frontend tooling required")
    def test_schema_and_frontend_consume_current_projection(self):
        baseline = case([node("a"), node("child"), node("container", "structuralElement")],
                        reference_edges=[contains("child", "a")])
        moved = case([node("a"), node("b"), node("child")], reference_edges=[contains("child", "a")],
                     submission_edges=[contains("child", "b")],
                     provisionalContainmentEvidence=[containment_evidence("child", "a", status="violated", studentParentIds=["b"])])
        missing = case([node("a"), node("child")], [node("a")], [contains("child", "a")], [], pairs=[("a", "a")])
        connection = case([node("a"), node("b"), node("e", "connection", directed=True)],
                          reference_edges=endpoints("e", "a", "b"), submission_edges=endpoints("e", "b", "a"))
        payload = [sample(store) for store in (baseline, moved, missing, connection)]
        payload += [sample(with_facts(store)) for store in (baseline, moved, missing, connection)]
        legacy = deepcopy(payload[2])
        legacy["envelope"]["result"].pop("contractVersion")
        payload.append(legacy)
        fixture = sample(case([node("parent"), node("attribute", native_type="property")]))
        fixture["envelope"] = json.loads((SERVICES / "analytical-feedback/examples/containment-role.json").read_text(encoding="utf-8"))
        payload.append(fixture)
        result = subprocess.run(["node", "-e", CHECK], input=json.dumps(payload),
                                cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
