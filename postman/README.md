# postman/

| File | What it is | Safe to commit? |
|---|---|---|
| `o2c-integration-hub.postman_collection.json` | The requests (no secrets: all values are `{{variables}}`) | Yes |
| `o2c-local.postman_environment.template.json` | Variable names with empty values | Yes |
| Any `*.postman_environment.json` you export | May contain real tokens | **No**, and git ignores these files |

How to import and run: see [docs/00-setup-guide.md](../docs/00-setup-guide.md), Step 7.

Phase 6 expands this into a full test collection with separate mock and live environments.
