#!/usr/bin/env python3
"""Generate benchmark submissions with a known correspondence from the stored sample solutions.

Every variant keeps the cell IDs of the reference, so the true counterpart of a reference object is
the submission object with the same ID. Each reference object gets a category that says what was
done to it (label variant, removed, moved, ...); `truth` lists the expectation per object.

Usage: python generate.py [--out cases]
"""

import argparse
import copy
import json
import random
import re
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEXICON = {key: value for key, value in json.loads((HERE / "lexicon.json").read_text(encoding="utf-8")).items() if not key.startswith("_")}
# Categories whose counterpart should be identified; "wrong_label" and "shuffled" may only be found through structure.
MATCHABLE = {"exact", "notation", "typo", "abbreviation", "synonym", "translation", "short_form", "moved"}


def clean(label):
    return " ".join(re.sub(r"-?\s*\n\s*(?=[a-zäöüß])", "", label or "").split())


class Diagram:
    """Language-neutral view on a maxGraph model: labelled vertices, owners and edges."""

    def __init__(self, xml):
        self.tree = ET.fromstring(xml)
        self.layer = next(cell for cell in self.tree.iter("Cell") if cell.get("parent") == "0")
        self.container = next(parent for parent in self.tree.iter() if self.layer in list(parent))

    @property
    def cells(self):
        return {cell.get("id"): cell for cell in self.tree.iter("Cell")}

    def kind(self, cell):
        return cell.get("diagramElementType") or ""

    def is_attribute(self, cell):
        return "attribute" in self.kind(cell) and self.kind(cell) != "serm-attribute-list" or self.kind(cell) == "uml-text-label"

    def edges(self):
        return [cell for cell in self.cells.values() if cell.get("edge") == "1"]

    def owner(self, identity):
        cells = self.cells
        cell = cells[identity]
        if cell.get("parent") == self.layer.get("id"):
            # ERM: an attribute is a top-level vertex linked to its owner by an attribute edge.
            if self.is_attribute(cell):
                link = next((edge for edge in self.edges() if edge.get("connectionId") == "erm-attribute-link"
                             and identity in (edge.get("source"), edge.get("target"))), None)
                if link is not None:
                    return link.get("target") if link.get("source") == identity else link.get("source")
            return None
        current = cells.get(cell.get("parent"))
        while current is not None and current.get("parent") != self.layer.get("id"):
            current = cells.get(current.get("parent"))
        return current.get("id") if current is not None else None

    def elements(self):
        return [cell for cell in self.cells.values() if cell.get("vertex") == "1" and clean(cell.get("value"))]

    def top(self):
        return [cell.get("id") for cell in self.elements() if self.owner(cell.get("id")) is None]

    def attributes(self, owner=None):
        return [cell.get("id") for cell in self.elements() if self.owner(cell.get("id")) is not None
                and (owner is None or self.owner(cell.get("id")) == owner)]

    def label(self, identity):
        return self.cells[identity].get("value") or ""

    def set_label(self, identity, text):
        cell = self.cells[identity]
        old = cell.get("value")
        cell.set("value", text)
        for child in cell:
            if child.get("as") == "diagramAttributes" and child.get("label") == old:
                child.set("label", text)

    def parent_of(self, cell):
        return next(parent for parent in self.tree.iter() if cell in list(parent))

    def remove(self, identities):
        cells = self.cells
        removed = set(identities)
        changed = True
        while changed:
            changed = False
            for identity, cell in cells.items():
                if identity in removed:
                    continue
                if cell.get("parent") in removed or (self.is_attribute(cell) and self.owner(identity) in removed) or (
                        cell.get("edge") == "1" and (cell.get("source") in removed or cell.get("target") in removed)):
                    removed.add(identity)
                    changed = True
        for identity in removed:
            cell = cells[identity]
            self.parent_of(cell).remove(cell)
        return removed

    def add_attribute(self, like, owner, label, identity):
        """Copy an existing attribute cell under another owner (container or attribute edge)."""
        cells = self.cells
        clone = copy.deepcopy(cells[like])
        clone.set("id", identity)
        clone.set("value", label)
        for child in clone:
            if child.get("as") == "diagramAttributes" and child.get("label") == cells[like].get("value"):
                child.set("label", label)
        self.parent_of(cells[like]).append(clone)
        self._place(identity, owner, like)
        return identity

    def move_attribute(self, identity, owner):
        self._place(identity, owner, identity)

    def _place(self, identity, owner, like):
        cells = self.cells
        link = next((edge for edge in self.edges() if edge.get("connectionId") == "erm-attribute-link"
                     and like in (edge.get("source"), edge.get("target"))), None)
        if link is not None:
            if like != identity:
                link = copy.deepcopy(link)
                link.set("id", f"{identity}-link")
                self.container.append(link)
            link.set("source", identity)
            link.set("target", owner)
            return
        sibling = next((cells[attr] for attr in self.attributes(owner)), None)
        container = cells[sibling.get("parent")] if sibling is not None else cells[owner]
        cells[identity].set("parent", container.get("id"))

    def xml(self):
        return ET.tostring(self.tree, encoding="unicode")


# Label variant rules. The rules only build test data; the matcher never sees them.
def notation(label):
    text = clean(label)
    if text.endswith("."):
        return re.sub(r"([a-zäöü])(Nr)\.$", r"\1-\2", text)
    if re.search(r"[a-zäöü][A-Z]", text):
        return re.sub(r"([a-zäöü])([A-Z])", lambda m: f"{m.group(1)}_{m.group(2).lower()}", text)
    if " " in text:
        return text.replace(" ", "")
    return text.lower() if text[:1].isupper() else text[:1].upper() + text[1:]


def typo(label):
    text = clean(label)
    if len(text) < 5:
        return None
    middle = len(text) // 2
    return text[:middle] + text[middle + 1:]


def abbreviation(label):
    text = clean(label)
    rules = [(r"Nr\.?$", "nummer"), (r"Number$", "No"), (r"^quantity$", "qty"), (r"^Bezeichnung$", "Bez."),
             (r"^Beschreibung$", "Beschr."), (r"nummer$", "Nr.")]
    for pattern, replacement in rules:
        if re.search(pattern, text):
            result = re.sub(pattern, replacement, text)
            return result[:1] + result[1:] if result != text else None
    return None


def lexicon(field):
    return lambda label: LEXICON.get(clean(label), {}).get(field)


VARIANTS = {"notation": notation, "typo": typo, "abbreviation": abbreviation, "synonym": lexicon("synonym"),
            "translation": lexicon("translation"), "short_form": lexicon("short"), "wrong_label": lexicon("wrong")}


def relabel(diagram, truth, identities, variant):
    for identity in identities:
        new = VARIANTS[variant](diagram.label(identity))
        if new and clean(new) != clean(diagram.label(identity)):
            diagram.set_label(identity, new)
            truth[identity]["category"] = variant
            truth[identity]["submissionLabel"] = new


def sample(rng, items, share):
    items = sorted(items)
    return sorted(rng.sample(items, max(1, round(len(items) * share)))) if items else []


def build_case(name, reference, foreign=None):
    rng = random.Random(f"{reference['key']}:{name}")
    diagram = Diagram(reference["xml"])
    truth = {cell.get("id"): {"label": clean(cell.get("value")), "category": "exact", "submissionLabel": clean(cell.get("value")),
                              "owner": diagram.owner(cell.get("id"))} for cell in diagram.elements()}
    top, attributes = diagram.top(), diagram.attributes()
    extra = []

    def drop(share):
        kept = set(sample(rng, top, share))
        for identity in diagram.remove([item for item in top if item not in kept]):
            if identity in truth:
                truth[identity]["category"] = "removed"

    if name == "foreign_solution":
        diagram = Diagram(foreign["xml"])
        for item in truth.values():
            item["category"] = "removed"
        extra = [cell.get("id") for cell in diagram.elements()]
    elif name in VARIANTS and name not in ("typo", "wrong_label"):
        relabel(diagram, truth, top + attributes, name)
    elif name == "typo":
        relabel(diagram, truth, sample(rng, top + attributes, 0.4), "typo")
    elif name == "wrong_label":
        relabel(diagram, truth, sample(rng, top, 0.3) + sample(rng, attributes, 0.3), "wrong_label")
    elif name.startswith("subset_"):
        drop({"subset_small": 0.25, "subset_medium": 0.5, "subset_large": 0.85, "subset_medium_synonym": 0.5}[name])
        if name.endswith("_synonym"):
            relabel(diagram, truth, [item for item in top + attributes if truth[item]["category"] == "exact"], "synonym")
    elif name == "shuffled_labels":
        labels = [diagram.label(identity) for identity in top]
        order = labels[1:] + labels[:1]  # a cyclic shift: no object keeps its own label
        for identity, label in zip(top, order):
            diagram.set_label(identity, label)
            truth[identity]["category"] = "shuffled"
            truth[identity]["submissionLabel"] = clean(label)
    elif name == "distractors":
        for index, owner in enumerate(top):
            own = diagram.attributes(owner)
            like = own[0] if own else (attributes[0] if attributes else None)
            if like is None:
                continue
            extra.append(diagram.add_attribute(like, owner, f"{clean(diagram.label(like))} 2", f"decoy-{index}"))
    elif name == "moved_attributes":
        owners = [identity for identity in top if diagram.attributes(identity)]
        for identity in sample(rng, attributes, 0.3):
            current = truth[identity]["owner"]
            target = next((owner for owner in rng.sample(owners, len(owners)) if owner != current), None)
            if target is not None:
                diagram.move_attribute(identity, target)
                truth[identity]["category"] = "moved"
    elif name == "realistic_mix":
        drop(0.85)
        alive = [identity for identity in top + attributes if truth[identity]["category"] == "exact"]
        picks = rng.sample(alive, min(len(alive), 8))
        for variant, chosen in (("typo", picks[0:2]), ("synonym", picks[2:4]), ("abbreviation", picks[4:5]), ("wrong_label", picks[5:6])):
            relabel(diagram, truth, chosen, variant)
        movable = [identity for identity in picks[6:7] if truth[identity]["owner"]]
        targets = [identity for identity in diagram.top() if diagram.attributes(identity)]
        for identity in movable:
            target = next((owner for owner in targets if owner != truth[identity]["owner"]), None)
            if target:
                diagram.move_attribute(identity, target)
                truth[identity]["category"] = "moved"
        survivors = [identity for identity in diagram.top() if diagram.attributes(identity)]
        if survivors:
            like = diagram.attributes(survivors[0])[0]
            extra.append(diagram.add_attribute(like, survivors[0], f"{clean(diagram.label(like))} 2", "decoy-mix"))
    elif name != "identical":
        raise ValueError(f"unknown case {name}")
    for identity, item in truth.items():
        item["expected"] = identity if item["category"] in MATCHABLE else None
    return {"reference": reference["key"], "case": name, "xml": diagram.xml(), "truth": truth, "extra": extra}


CASES = ["identical", "notation", "typo", "abbreviation", "synonym", "translation", "short_form", "wrong_label",
         "shuffled_labels", "distractors", "moved_attributes", "subset_small", "subset_medium", "subset_large",
         "subset_medium_synonym", "realistic_mix", "foreign_solution"]


def serm_to_erm(reference, templates):
    """Express a SERM sample solution in ERM: entities and relationships stay, attributes become linked ellipses."""
    source = Diagram(reference["xml"])
    target = Diagram(reference["xml"])
    for cell in list(target.container):
        if cell.get("id") != "0" and cell.get("parent") != "0":  # keep the root and every canvas layer
            target.container.remove(cell)
    layer = target.layer.get("id")

    def cell_from(kind, identity, label, x, y, **attrs):
        cell = ET.fromstring(templates["cells"][kind])
        cell.set("id", identity)
        cell.set("value", label)
        cell.set("parent", layer)
        for key, value in attrs.items():
            cell.set(key, value)
        geometry = next((child for child in cell if child.tag == "Geometry"), None)
        if geometry is not None and cell.get("vertex") == "1":
            geometry.set("_x", str(x))
            geometry.set("_y", str(y))
        target.container.append(cell)

    def position(identity):
        geometry = next((child for child in source.cells[identity] if child.tag == "Geometry"), None)
        return (int(float(geometry.get("_x", 0))), int(float(geometry.get("_y", 0)))) if geometry is not None else (0, 0)

    for identity in source.top():
        kind = "erm-relationship" if source.kind(source.cells[identity]) == "serm-relationship" else "erm-entity"
        x, y = position(identity)
        cell_from(kind, identity, source.label(identity), x * 2, y * 2)
        for index, attribute in enumerate(source.attributes(identity)):
            style = next((child for child in source.cells[attribute] if child.get("as") == "style"), None)
            key = style is not None and style.get("fontStyle") == "4"
            cell_from("erm-key-attribute" if key else "erm-attribute", attribute, source.label(attribute),
                      x * 2 + 140, y * 2 + 70 * index)
            cell_from("erm-attribute-link", f"{attribute}-link", "", 0, 0, source=attribute, target=identity)
    for edge in source.edges():
        if edge.get("source") in source.cells and edge.get("target") in source.cells:
            cell_from("erm-association", edge.get("id"), "", 0, 0, source=edge.get("source"), target=edge.get("target"))
    language = {"languageId": templates["languageId"], "versionId": templates["versionId"], "source": "required"}
    return {**reference, "key": "erm-laboratory", "xml": target.xml(),
            "task": {**reference["task"], "workspaceLanguages": [language],
                     "data": {"sampleSolutions": [{"modelId": "benchmark-erm-laboratory", "versionId": "benchmark-erm-laboratory-1"}]}},
            "reference": {**reference["reference"], "modelId": "benchmark-erm-laboratory", "versionId": "benchmark-erm-laboratory-1",
                          "workspaceLanguages": [language]}}


def references():
    loaded = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in (HERE / "references").glob("*.json")
              if path.stem not in ("languages", "erm-cell-templates")}
    loaded["erm-laboratory"] = serm_to_erm(loaded["serm-laboratory"], json.loads((HERE / "references/erm-cell-templates.json").read_text(encoding="utf-8")))
    return loaded


FOREIGN = {"serm-laboratory": "serm-game-studio", "serm-game-studio": "serm-laboratory",
           "uml-order-management": "serm-laboratory", "erm-laboratory": "uml-order-management"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(HERE / "cases"))
    args = parser.parse_args()
    refs = references()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for key, reference in sorted(refs.items()):
        (out / f"{key}.reference.json").write_text(json.dumps(reference, ensure_ascii=False), encoding="utf-8")
        for name in CASES:
            case = build_case(name, reference, refs[FOREIGN[key]])
            (out / f"{key}__{name}.json").write_text(json.dumps(case, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(refs)} references x {len(CASES)} cases -> {out}")


if __name__ == "__main__":
    main()
