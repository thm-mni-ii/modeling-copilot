# Language evaluation configuration

The **Evaluation** tab in the Diagram Language Editor manages comparison groups.
Each matrix row is a group; columns show the language's element previews. Click
a cell to include or exclude a type, edit the group name inline, or delete a row.
Groups belong to `LanguageVersion.data` and use the existing save, restore,
model package import and export mechanisms.

```json
{
  "evaluation": {
    "comparisonGroups": [
      {
        "id": "entity-variants",
        "name": "Entity variants",
        "elementTypes": ["entity", "weak-entity"]
      }
    ]
  }
}
```

- Models must use the same language or compatible versions of that language.
- Identical type identifiers are always matching candidates. Different types
  are candidates only when they share at least one group.
- Permission is symmetric; it does not imply an automatic match or semantic
  equivalence. Overlapping groups are not transitive: `[A, B]` and `[B, C]`
  do not allow the pair `A, C`.
- Type identifiers refer to the language's own declarations, including recursive
  child types. Connections cannot be group members.
- Each group has a unique identifier, a name and at least two distinct types.
  A type can belong to multiple groups.
- Renamed or deleted types remain visible as removable missing-type chips.
  Replace or remove them before saving the language version.
- An absent `evaluation` field or an empty group list allows only identical types.
  Loading older definitions does not add configuration or mark them as changed.

This feature declares the configuration. Consuming it in the matching pipeline
is a separate implementation step.
