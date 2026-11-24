# Commit examples

## Feature
```
feat(skills): hot reload skill bodies between turns

Fingerprint every SKILL.md by mtime and size, rescan on change, and reuse the
cached snapshot when nothing moved. Editing a skill body now takes effect on
the next request instead of requiring a restart.
```

## Breaking change
```
feat(api)!: rename /skills/load to /skills/load_body

BREAKING CHANGE: the load endpoint now returns the body only; attached file
reads go through read_skill_file. Clients calling /skills/load must be updated.
```

Rejected subjects: `update`, `fix bug`, `wip`, `changes`, `stuff`.
