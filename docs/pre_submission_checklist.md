# LinkedIn Plugin Pre-Submission Checklist (v0.3.1)

Audit state as of the v0.3.1 release. Boxes marked `[x]` were verified against
the real repository or the live LinkedIn API; `[ ]` items remain genuinely open.

Upstream rules live in https://github.com/agent0ai/a0-plugins — recheck them at
submission time, since limits and required fields can change.

## 1. Functional readiness

- [x] Personal posting flow is tested end-to-end (live post published)
- [x] Organization posting flow is verified end-to-end (app approved, live page post)
- [ ] Organization read flow is verified if supported
- [x] `linkedin_account status` reports expected readiness per account
- [x] Personal target routing works correctly
- [x] Organization target routing works correctly
- [x] Ambiguous requests trigger `needs_clarification` instead of guessing
- [x] `dry_run` behavior works as expected
- [x] Correct LinkedIn author URN format is used (`urn:li:person:<id>`)
- [x] Organization page discovery works via `rw_organization_admin`
- [x] Person URN lookup works via `/v2/userinfo`
- [x] In-browser OAuth connect completes and stores a token per account

## 2. Security and secret hygiene

- [x] No real access tokens exist in tracked files (`git grep` clean)
- [x] No real URNs or identifiers remain in tracked files
- [x] `.runtime_config.json` is ignored
- [x] `config.json` is ignored (generated locally)
- [x] `.toggle-*` files are ignored
- [x] `.env*` files are ignored
- [x] `.oauth_state.json` is ignored (holds live single-use nonces)
- [x] Any accidentally exposed token has been revoked or rotated (tokens were
      reissued via the OAuth connect flow; the old ones return 401)
- [x] Git history is clean of secrets - verified by scanning every revision:
      only 2 commits ever touched `config.json`, one had no non-empty secret
      fields and the other only deleted the file (parent blob held no
      token-like values). No `AQXUG`-style token strings in any revision.
- [x] No leftover backup files exist (`config.json.bak`, editor backups)

## 3. Repo hygiene

- [x] `.gitignore` reflects the generated-config model
- [x] `initialize.py` does not require generated local files
- [x] `plugin.yaml` exists at repo root
- [x] `default_config.yaml` exists at repo root
- [x] `README.md` exists at repo root
- [x] `LICENSE` exists at repo root (MIT)
- [x] No local-only runtime files are tracked
- [x] No test junk, caches, or temp files are tracked
- [x] Repo root contains only intentional plugin files
- [x] Repository is public and `plugin.yaml` is reachable at the root

## 4. Public documentation quality

- [x] README uses public/community-facing tone
- [x] README avoids diary-style development notes
- [x] README avoids absolute local paths like `/a0/usr/...`
- [x] README explains current scope clearly
- [x] README explains limitations honestly (all in-scope posting paths verified, including org image posting)
- [x] README includes example usage
- [x] README explains personal vs organization behavior
- [x] README explains required LinkedIn scopes and their defaults
- [x] README mentions organization permissions and app approval constraints
- [x] README lists verified features with their evidence

## 5. Plugin manifest consistency

- [x] `plugin.yaml` name is exactly `linkedin`
- [x] `plugin.yaml` name matches the intended index folder name (`plugins/linkedin/`)
- [x] `plugin.yaml` description is clear and public-facing
- [x] `plugin.yaml` version is current (`0.3.1`)
- [x] `always_enabled: false` is consistent with Agent Zero conventions

## 6. Config model consistency

- [x] `default_config.yaml` reflects the multi-account model (one entry per credential set)
- [x] `default_config.yaml` is safe and token-free (all tokens empty strings)
- [x] Generated config behavior is consistent with repo expectations
- [x] Personal and organization defaults are both represented
- [x] Shared/default fields are coherent with runtime behavior
- [x] Scope defaults match verified working accounts (personal and organization)

## 7. Tests and validation

- [x] `tests/regression_test.sh` passes and covers OAuth, discovery, masking, and routing
- [ ] `tests/HUMAN_TEST_PLAN.md` includes the OAuth connect flow (currently UI/multi-account only)
- [x] `tests/smoke_examples.md` reflects current tool behavior
- [x] Manual testing was rerun after config-model changes
- [x] Plugin still loads correctly after enable/configure cycle

## 8. Community index metadata

- [x] Plugin repo URL is public and correct: `https://github.com/gshock/a0-linkedin`
- [x] Runtime plugin name is `linkedin`
- [x] Index folder is `plugins/linkedin/`
- [x] Index file is `plugins/linkedin/index.yaml`
- [x] Thumbnail is square and within limits (`webui/thumbnail.jpg`, 256x256, 8.2 KB)
- [ ] `index.yaml` committed on a submission branch of the fork
- [ ] PR opened against `agent0ai/a0-plugins:main`

## 9. Planned `index.yaml` contents

Validated against the upstream rules: title <= 50 chars, description <= 500,
whole file <= 2000, tags <= 5 chosen from `TAGS.md`.

```yaml
title: LinkedIn
description: Publish approved LinkedIn posts from Agent Zero across multiple accounts and company pages, with account readiness checks, organization discovery, browser OAuth, and text or multi-image posting.
github: https://github.com/gshock/a0-linkedin
tags:
  - api
  - oauth
  - integration
  - automation
  - image
```

The thumbnail is copied beside `index.yaml` as `thumbnail.jpg`. Do not add
`screenshots` unless the URLs are live, public, and under 2 MB each.

## 10. PR submission workflow

- [x] Fork exists: `https://github.com/gshock/a0-plugins`
- [ ] Clone the fork and create a branch such as `add-linkedin-plugin`
- [ ] Create folder `plugins/linkedin/`
- [ ] Add `plugins/linkedin/index.yaml`
- [ ] Optionally add `plugins/linkedin/thumbnail.jpg`
- [ ] Commit the new index entry
- [ ] Push the branch to the fork
- [ ] Open a PR to `agent0ai/a0-plugins:main`
- [ ] Confirm CI validation passes

## 11. Final go/no-go gate

- [x] Organization app verification is complete
- [x] Organization text posting tested successfully
- [x] No secrets remain in current files
- [ ] Secret-bearing history has been cleaned if necessary
- [x] Repo is safe for public review
- [x] README and metadata accurately describe current capabilities

## 12. Short version

- [x] Organization app verified
- [x] Organization text posting tested
- [x] Repo secret-free in current files
- [ ] History verified clean of past secrets
- [x] README polished
- [x] LICENSE present
- [x] `plugin.yaml` name is `linkedin`
- [ ] Prepare `plugins/linkedin/index.yaml` in the fork
- [ ] Open PR to `agent0ai/a0-plugins`
