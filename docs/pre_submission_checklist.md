# LinkedIn Plugin Pre-Submission Checklist

Use this checklist before submitting the plugin to the Agent Zero community index.

## 1. Functional readiness

- [ ] Personal posting flow is tested end-to-end
- [ ] Organization posting flow is verified end-to-end
- [ ] Organization read flow is verified if supported
- [ ] `linkedin_account status` reports expected readiness
- [ ] Personal target routing works correctly
- [ ] Organization target routing works correctly
- [ ] Ambiguous requests trigger clarification instead of guessing
- [ ] `dry_run` behavior works as expected
- [ ] Correct LinkedIn author URN format is used:
  - [ ] `urn:li:person:<id>` for personal posting

## 2. Security and secret hygiene

- [ ] No real access tokens exist in tracked files
- [ ] No real URNs or identifiers remain in tracked files unless intentionally public/safe
- [ ] `.runtime_config.json` is ignored
- [ ] `config.json` is ignored if it is generated locally
- [ ] `.toggle-*` files are ignored
- [ ] `.env*` files are ignored
- [ ] Any accidentally exposed token has been revoked or rotated
- [ ] Git history has been cleaned if secrets were ever pushed
- [ ] No leftover backup files exist such as:
  - [ ] `config.json.bak`
  - [ ] editor backup files

## 3. Repo hygiene

- [ ] `.gitignore` reflects the generated-config model
- [ ] `initialize.py` does not require generated local files
- [ ] `plugin.yaml` exists at repo root
- [ ] `default_config.yaml` exists at repo root
- [ ] `README.md` exists at repo root
- [ ] `LICENSE` exists at repo root
- [ ] No local-only runtime files are tracked
- [ ] No test junk, caches, or temp files are tracked
- [ ] Repo root contains only intentional plugin files

## 4. Public documentation quality

- [ ] README uses public/community-facing tone
- [ ] README avoids diary-style development notes
- [ ] README avoids absolute local paths like `/a0/usr/...`
- [ ] README explains current scope clearly
- [ ] README explains limitations honestly
- [ ] README includes example usage
- [ ] README explains personal vs organization behavior
- [ ] README explains required LinkedIn scopes
- [ ] README mentions organization permissions and app approval constraints

## 5. Plugin manifest consistency

- [ ] `plugin.yaml` name is exactly `linkedin`
- [ ] `plugin.yaml` name matches the intended index folder name
- [ ] `plugin.yaml` description is clear and public-facing
- [ ] `plugin.yaml` version is current
- [ ] `always_enabled` usage is consistent with Agent Zero conventions

## 6. Config model consistency

- [ ] `default_config.yaml` matches the dual-profile model
- [ ] `default_config.yaml` is safe and token-free
- [ ] Generated config behavior is consistent with repo expectations
- [ ] Personal and organization defaults are both represented appropriately
- [ ] Shared/default fields are coherent with runtime behavior

## 7. Tests and validation

- [ ] `tests/HUMAN_TEST_PLAN.md` is still accurate
- [ ] `tests/regression_test.sh` still reflects current plugin behavior
- [ ] `tests/smoke_examples.md` is still accurate
- [ ] Manual testing was rerun after major config-model changes
- [ ] Plugin still loads correctly after a clean enable/configure cycle

## 8. Community index metadata

- [ ] Plugin repo URL is public and correct: `https://github.com/gshock/a0-linkedin`
- [ ] Runtime plugin name is `linkedin`
- [ ] Planned index folder is `plugins/linkedin/`
- [ ] Planned index file is `plugins/linkedin/index.yaml`
- [ ] `index.yaml` title is ready
- [ ] `index.yaml` description is ready
- [ ] `index.yaml` GitHub URL is correct
- [ ] `index.yaml` tags are selected
- [ ] Optional screenshot URL is available if desired

## 9. Planned `index.yaml` contents

```yaml
title: LinkedIn
description: Manage approved LinkedIn posting workflows in Agent Zero, including account checks, text post publishing, and recent post retrieval.
github: https://github.com/gshock/a0-linkedin
tags:
  - social
  - linkedin
  - publishing
  - marketing
  - api
```

Optional later:

```yaml
screenshots:
  - https://raw.githubusercontent.com/gshock/a0-linkedin/main/webui/thumbnail.png
```

## 10. PR submission workflow

- [ ] Fork `https://github.com/agent0ai/a0-plugins`
- [ ] Clone your fork
- [ ] Create a branch such as `add-linkedin-plugin`
- [ ] Create folder `plugins/linkedin/`
- [ ] Add file `plugins/linkedin/index.yaml`
- [ ] Commit the new index entry
- [ ] Push the branch to your fork
- [ ] Open a PR to `agent0ai/a0-plugins:main`

## 11. Final go/no-go gate

Before opening the PR, confirm:

- [ ] Organization app verification is complete
- [ ] Organization mode has been tested successfully
- [ ] No secrets remain in current files
- [ ] Secret-bearing history has been cleaned if necessary
- [ ] Repo is safe for public review
- [ ] README and metadata accurately describe current capabilities

## 12. Short version

- [ ] Organization app verified
- [ ] Organization posting tested
- [ ] Repo secret-free
- [ ] History cleaned if needed
- [ ] README polished
- [ ] LICENSE present
- [ ] `plugin.yaml` name is `linkedin`
- [ ] Prepare `plugins/linkedin/index.yaml`
- [ ] Open PR to `agent0ai/a0-plugins`
