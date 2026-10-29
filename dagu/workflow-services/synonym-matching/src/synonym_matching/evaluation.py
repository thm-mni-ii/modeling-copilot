"""Reproducible grouped benchmark runs; validation chooses thresholds, never test."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support

from .combiners import combine
from .engine import MatchingEngine, elements

SPLITS = {"train", "validation", "test"}
ANNOTATIONS = {"correct", "possible", "incorrect"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_dataset(data):
    if data.get("version") != 1 or not isinstance(data.get("tasks"), list) or not data["tasks"]:
        raise ValueError("dataset needs version 1 and nonempty tasks")
    groups, ids, pair_splits, family_splits = {}, set(), {}, {}
    seen_splits = set()
    for task in data["tasks"]:
        if task["id"] in ids:
            raise ValueError("duplicate task ID")
        ids.add(task["id"])
        split, group = task["split"], task["group"]
        if split not in SPLITS or not isinstance(group, str) or not group:
            raise ValueError("invalid split or group")
        seen_splits.add(split)
        if group in groups and groups[group] != split:
            raise ValueError("leakage: task group crosses splits")
        groups[group] = split
        refs, students = elements(task["reference"], "reference"), elements(task["student"], "student")
        if not refs or not students:
            raise ValueError("benchmark tasks need nonempty candidate sets")
        if any(not e["label"].strip() for e in refs + students):
            raise ValueError("benchmark labels must be nonempty; use unit tests for empty input")
        annotations = task["annotations"]
        if len(annotations) != len(refs) or any(len(row) != len(students) for row in annotations):
            raise ValueError("annotations must cover the complete reference × student matrix")
        if any(label not in ANNOTATIONS for row in annotations for label in row):
            raise ValueError("unknown annotation")
        # Families must include translations, typos and variants of the same concept.
        if not task.get("families") or any(not isinstance(f, str) or not f for f in task["families"]):
            raise ValueError("each task needs explicit concept families")
        for family in task["families"]:
            if family in family_splits and family_splits[family] != split:
                raise ValueError("leakage: concept family crosses splits")
            family_splits[family] = split
        for ref in refs:
            for student in students:
                # Detect repeated/reversed text pairs, irrespective of element IDs.
                key = tuple(sorted((" ".join(ref["label"].casefold().split()), " ".join(student["label"].casefold().split()))))
                if key in pair_splits and pair_splits[key] != split:
                    raise ValueError("leakage: normalized text pair crosses splits")
                pair_splits[key] = split
    if seen_splits != SPLITS:
        raise ValueError("train, validation and test splits are all required")
    for split in SPLITS:
        labels = {a for task in data["tasks"] if task["split"] == split for row in task["annotations"] for a in row}
        if not {"correct", "incorrect"} <= labels:
            raise ValueError(f"{split} needs both unambiguous classes")


def pair_metrics(records, scores, threshold, possible=None):
    chosen = [(r, s) for r, s in zip(records, scores, strict=True)
              if r["annotation"] != "possible" or possible is not None]
    if not chosen:
        return {"precision": None, "recall": None, "f1": None, "n": 0, "tp": 0, "fp": 0, "fn": 0, "tn": 0}
    y = np.array([r["annotation"] == "correct" or (r["annotation"] == "possible" and possible) for r, _ in chosen], dtype=bool)
    pred = np.array([s >= threshold for _, s in chosen])
    precision, recall, f1, _ = precision_recall_fscore_support(y, pred, average="binary", zero_division=0)
    return {"precision": float(precision), "recall": float(recall), "f1": float(f1), "n": len(y),
            "tp": int((y & pred).sum()), "fp": int((~y & pred).sum()),
            "fn": int((y & ~pred).sum()), "tn": int((~y & ~pred).sum())}


def metrics(records, scores, threshold):
    result = pair_metrics(records, scores, threshold)
    rows = defaultdict(list)
    for record, score in zip(records, scores, strict=True):
        rows[(record["task"], record["reference_index"])].append((record, float(score)))
    correct, queries, ties, covered, no_match, rejected = 0, 0, 0, 0, 0, 0
    margins = []
    for candidates in rows.values():
        ordered = sorted(candidates, key=lambda x: (-x[1], x[0]["student_index"]))
        covered += ordered[0][1] >= threshold
        if len(ordered) > 1:
            margins.append(ordered[0][1] - ordered[1][1])
        if any(r["annotation"] == "correct" for r, _ in ordered):
            queries += 1
            correct += ordered[0][0]["annotation"] == "correct"
            ties += sum(np.isclose(s, ordered[0][1], rtol=0, atol=1e-12) for _, s in ordered) > 1
        elif all(r["annotation"] == "incorrect" for r, _ in ordered):
            no_match += 1
            rejected += ordered[0][1] < threshold
    per_task = []
    for task_id in sorted({r["task"] for r in records}):
        ix = [i for i, r in enumerate(records) if r["task"] == task_id]
        m = pair_metrics([records[i] for i in ix], [scores[i] for i in ix], threshold)
        if m["f1"] is not None:
            per_task.append(m["f1"])
    result.update(top1_accuracy=correct / queries if queries else None, top1_queries=queries,
                  top1_ties=int(ties), query_coverage=float(covered / len(rows)) if rows else None,
                  no_match_queries=no_match, no_match_rejection=rejected / no_match if no_match else None,
                  mean_top1_top2_margin=float(np.mean(margins)) if margins else None,
                  macro_task_f1=float(np.mean(per_task)) if per_task else None,
                  possible_pairs=sum(r["annotation"] == "possible" for r in records))
    return result


def environment():
    packages = {}
    for distribution in importlib.metadata.distributions():
        packages[distribution.metadata["Name"]] = distribution.version
    try:
        root = Path(__file__).resolve().parents[5]
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    return {"python": platform.python_version(), "platform": platform.platform(),
            "machine": platform.machine(), "processor": platform.processor(),
            "packages": dict(sorted(packages.items())), "git_commit": commit, "git_dirty": dirty}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_csv(path, rows):
    if rows:
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def run(data, suite, output):
    validate_dataset(data)
    if suite.get("version") != 1 or not suite.get("variants"):
        raise ValueError("suite needs version 1 and variants")
    if len({v["name"] for v in suite["variants"]}) != len(suite["variants"]):
        raise ValueError("variant names must be unique")
    for variant in suite["variants"]:
        if not variant["name"] or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in variant["name"]):
            raise ValueError("variant names must be safe directory names")
    thresholds = suite.get("thresholds", [i / 20 for i in range(21)])
    if not thresholds or any(type(t) not in (float, int) or not np.isfinite(t) or not 0 <= t <= 1 for t in thresholds):
        raise ValueError("thresholds must be finite numbers in [0,1]")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "dataset.json", data)
    write_json(output / "suite.json", suite)
    write_json(output / "environment.json", environment())
    source = Path(__file__).parent
    write_json(output / "source_hashes.json", {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.glob("*.py"))})
    manifest = {"dataset_sha256": digest(data), "tasks": [{k: t[k] for k in ("id", "group", "split", "families")} for t in data["tasks"]]}
    write_json(output / "split_manifest.json", manifest)
    summary, sweeps, categories, errors = [], [], [], []
    for variant in suite["variants"]:
        directory = output / variant["name"]
        directory.mkdir()
        try:
            engine = MatchingEngine(variant["config"])
            records, features, task_results, warm_timings = [], [], [], []
            wall_start = time.perf_counter()
            for task in data["tasks"]:
                result = engine.match(task["reference"], task["student"])
                task_results.append({"task": task["id"], "result": result})
                for i, row in enumerate(task["annotations"]):
                    for j, annotation in enumerate(row):
                        records.append({"task": task["id"], "split": task["split"], "category": task.get("category", "unspecified"),
                                        "reference_index": i, "student_index": j,
                                        "reference_label": task["reference"][i]["label"], "student_label": task["student"][j]["label"],
                                        "language_pair": task["reference"][i].get("language", "unknown") + "-" + task["student"][j].get("language", "unknown"),
                                        "annotation": annotation})
                        features.append([result["scores"][n][i][j] for n in engine.config["methods"]])
            elapsed = time.perf_counter() - wall_start
            if suite.get("measure_warm_cache", True):
                for task in data["tasks"]:
                    warm = engine.match(task["reference"], task["student"])
                    warm_timings.append({"task": task["id"], **warm["metadata"]["timings"],
                                         "cacheHits": warm["metadata"]["cacheHits"], "cacheMisses": warm["metadata"]["cacheMisses"]})
            write_json(directory / "warm_timings.json", warm_timings)
            write_json(directory / "matrices.json", task_results)
            x = np.clip(np.array(features), 0, 1)
            names = engine.config["methods"]
            score_sets = {n: x[:, k] for k, n in enumerate(names)}
            matrices = {n: x[:, k].reshape(-1, 1) for k, n in enumerate(names)}
            configurations = {n: {"kind": "single", "methods": [n]} for n in names}
            for combiner in suite.get("combiners", [{"name": "mean", "kind": "mean"}, {"name": "max", "kind": "max"}]):
                name = combiner["name"]
                if name in score_sets:
                    raise ValueError("duplicate score name")
                config = {k: v for k, v in combiner.items() if k != "name"}
                score_sets[name] = combine(matrices, config).ravel()
                configurations[name] = config
            train = np.array([r["split"] == "train" and r["annotation"] != "possible" for r in records])
            y = np.array([r["annotation"] == "correct" for r in records], dtype=int)
            train_times = {}
            for kind in suite.get("learned", ["logistic_regression", "random_forest"]):
                if kind == "logistic_regression":
                    estimator = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000, random_state=engine.config["seed"])
                elif kind == "random_forest":
                    estimator = RandomForestClassifier(n_estimators=100, max_depth=4, min_samples_leaf=2,
                                                       class_weight="balanced", random_state=engine.config["seed"], n_jobs=1)
                else:
                    raise ValueError(f"unsupported learned combiner: {kind}")
                fit_start = time.perf_counter()
                estimator.fit(x[train], y[train])
                train_times[kind] = time.perf_counter() - fit_start
                score_sets[kind] = estimator.predict_proba(x)[:, 1]
                configurations[kind] = estimator.get_params()
            write_json(directory / "score_configurations.json", configurations)
            predictions = []
            selections = {}
            for method, scores in score_sets.items():
                val_ix = [i for i, r in enumerate(records) if r["split"] == "validation"]
                val_records, val_scores = [records[i] for i in val_ix], scores[val_ix]
                curve = [(t, pair_metrics(val_records, val_scores, t)) for t in thresholds]
                # Fixed tie break: higher validation precision, then higher threshold.
                threshold = max(curve, key=lambda p: (p[1]["f1"], p[1]["precision"], p[0]))[0]
                selections[method] = threshold
                for t, m in curve:
                    sweeps.append({"variant": variant["name"], "method": method, "split": "validation", "threshold": t, **m})
                for split in ("train", "validation", "test"):
                    ix = [i for i, r in enumerate(records) if r["split"] == split]
                    subset, s = [records[i] for i in ix], scores[ix]
                    summary.append({"variant": variant["name"], "method": method, "split": split, "threshold": threshold,
                                    **metrics(subset, s, threshold), "feature_run_seconds": elapsed,
                                    "fit_seconds": train_times.get(method, 0.0)})
                    for dimension in ("category", "language_pair"):
                        for category in sorted({r[dimension] for r in subset}):
                            indices = [k for k, r in enumerate(subset) if r[dimension] == category]
                            categories.append({"variant": variant["name"], "method": method, "split": split,
                                               "dimension": dimension, "value": category,
                                               **pair_metrics([subset[k] for k in indices], s[indices], threshold)})
                    for possible in (False, True):
                        categories.append({"variant": variant["name"], "method": method, "split": split,
                                           "dimension": "possible_policy", "value": "positive" if possible else "negative",
                                           **pair_metrics(subset, s, threshold, possible=possible)})
                for record, score in zip(records, scores, strict=True):
                    predictions.append({**record, "method": method, "score": float(score), "threshold": threshold,
                                        "predicted": bool(score >= threshold)})
            write_json(directory / "selected_thresholds.json", selections)
            write_csv(directory / "predictions.csv", predictions)
        except Exception as error:
            errors.append({"variant": variant["name"], "error": f"{type(error).__name__}: {error}"})
            write_json(directory / "error.json", errors[-1])
    write_csv(output / "summary.csv", summary)
    write_csv(output / "validation_thresholds.csv", sweeps)
    write_csv(output / "slices.csv", categories)
    write_json(output / "errors.json", errors)
    lines = ["# Benchmark run", "", f"Dataset SHA256: `{digest(data)}`", "",
             "Synthetic smoke data are not evidence of quality on real student models.",
             "Thresholds selected on validation F1, precision, then higher threshold. Test never selects parameters.",
             "Top-1 uses full candidate sets, original student order breaks ties; tie counts are reported.",
             "Feature runtime is shared by all derived score sets, not per-combiner runtime.", "",
             f"Successful metric rows: {len(summary)}; failed variants: {len(errors)}.", "",
             "See summary.csv, slices.csv, validation_thresholds.csv and per-variant predictions/matrices."]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--output", required=True, help="new directory; existing runs are never overwritten")
    args = parser.parse_args()
    errors = run(json.loads(Path(args.data).read_text()), json.loads(Path(args.suite).read_text()), args.output)
    print(json.dumps({"output": args.output, "failed_variants": errors}))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
