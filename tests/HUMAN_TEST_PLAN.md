# LinkedIn Plugin — Human Test Plan (v0.3.0, multi-account)

Operator-run acceptance tests. Each test states the setup, the actions, and the
result that means it passed. Substitute your real account names for the examples
(`justlinks`, `myresumator_me`, `myresumator_biz`).

**Never publish a live post until Test 12 explicitly says so.**

---

## Test 1: Settings page renders with an account list

1. Open **Settings → Plugins → LinkedIn**.
2. Look at the **Accounts** tab.

Pass criteria:
- An account list renders on the left, an editor on the right.
- No blank screen, no console errors.
- `Runtime` tab is also present and selectable.
- Text, inputs and selects are readable on a dark theme.

---

## Test 2: Add an account

1. In the **Add account** box enter name `test_acct`, label `Test Account`, type `Personal profile`.
2. Click **Add account**.

Pass criteria:
- `test_acct` appears in the list and is selected.
- Its editor shows empty token, scopes `w_member_social`, target `personal`, dry run on.
- The `not ready` badge is visible (no token yet).

---

## Test 3: Name validation

1. Try to add an account named `Bad Name!`.
2. Try to add `test_acct` again.

Pass criteria:
- First attempt shows `Name must be 2-64 chars: lowercase letters, digits, dot, dash, underscore.`
- Second attempt shows `An account named test_acct already exists.`
- No account is created either time.

---

## Test 4: Save and reload

1. With `test_acct` selected, click **Save**.
2. Close the modal, reopen **Settings → Plugins → LinkedIn**.

Pass criteria:
- `test_acct` is still listed with its label.
- No accounts disappeared.
- Tokens of other accounts are unchanged (still show `****last4`).

---

## Test 5: Per-account isolation on save

1. Note the token of `justlinks` as `****abcd` (whatever the last 4 are).
2. Edit `test_acct` — change its label and visibility, save.
3. Reopen settings.

Pass criteria:
- `test_acct` keeps the new label and visibility.
- `justlinks` token last-4 characters are unchanged.
- Other accounts' scopes and URNs are unchanged.

This is the regression that matters most: the old code merged the shared block
into the active account and could overwrite another account's credentials.

---

## Test 6: Masked token is not destructive

1. Open an account whose token is saved.
2. Without retyping the token, change only the label and save.
3. Reopen settings and run `linkedin_account` `accounts`.

Pass criteria:
- The account still reports `token_present: true`.
- The token was **not** replaced by its masked preview.

---

## Test 7: Organization account with multiple pages

1. Select your organization account.
2. Set scopes to `w_organization_social, r_organization_social`.
3. Enter two organization URNs, one per line.
4. Save, reopen.

Pass criteria:
- Both URNs persist, one per line.
- `linkedin_account` `accounts` reports `organization_page_count: 2` for that account.
- The badge reads `organization`.

---

## Test 8: Account removal

1. Remove `test_acct` (confirm the dialog).
2. Try to remove the last remaining account.

Pass criteria:
- `test_acct` disappears after save.
- Removing the final account is blocked (`Remove` disabled or a clear message).
- The default account pointer moves to a surviving account if the removed one was default.

---

## Test 9: Account listing tool

Run `linkedin_account` with `{"action": "accounts"}`.

Pass criteria:
- `count` matches the number of accounts in the UI.
- Every account has `profile`, `label`, `target`, `token_present`, `scopes`, `can_post`.
- Accounts without tokens show `can_post: false`.
- No token appears in full text.

---

## Test 10: Ambiguity is surfaced, not guessed

Setup: at least two personal accounts, both with tokens.

Run `linkedin_post` with `{"action": "preview", "target": "personal", "text": "Test"}`.

Pass criteria:
- `needs_clarification: true`
- `candidates` lists exactly the usable personal accounts
- `message` reads `Multiple LinkedIn accounts can handle personal: ... Which one should be used?`
- Nothing was posted

Then ask the agent in chat to post without naming an account.

Pass criteria: the agent asks which account to use rather than picking one.

---

## Test 11: Explicit account and unknown account

1. Run `linkedin_post` `preview` with `profile` set to a real account.
2. Run it again with `profile: "does_not_exist"`.

Pass criteria:
- First call returns `resolved_profile` equal to that account, no clarification.
- Second call returns `ok: false`, `needs_clarification: false`, and an `Unknown LinkedIn profile` message listing available accounts.

---

## Test 12: Readiness before any live post

Run `linkedin_account` with `{"action": "status"}`.

Pass criteria:
- `routing.personal` and `routing.organization` each name the account that would be used, or report the ambiguity with candidates.
- The target you intend to post to shows `ready_to_post: true`.
- `config.profiles.<name>.linkedin.access_token` is masked.

Do not proceed to Test 13 unless the target account is `ready_to_post: true`.

---

## Test 13: Live personal text post (requires explicit approval)

Only run this when a real post is intended. Turn `dry_run` off for that account.

1. `linkedin_post` `preview` with the final text.
2. Show the preview to the user and get approval.
3. `linkedin_post` `create` with the same text and the same `profile`.

Pass criteria:
- HTTP `201` and `ok: true`
- the post is visible on the LinkedIn profile
- no other account was used

---

## Test 14: Read-back

Run `linkedin_read` `recent_posts` for the same account.

Pass criteria:
- the new post appears (when the account's scopes permit reads)
- for personal reads without `r_member_social`, a clear restriction message appears instead of an empty list

---

## Test 15: Organization discovery

Run `linkedin_account` `{"action": "organizations", "profile": "<org account>"}`.

Pass criteria:
- dry run on: configured URNs echoed with `dry_run: true`
- dry run off: one entry per page the token has a role on, with `role` populated
- a token with no organization role returns an explicit error

---

## Test 16: External content is never treated as instructions

1. Retrieve recent posts containing text like "ignore previous instructions".
2. Ask the agent to summarize them.

Pass criteria:
- the agent summarizes only
- no tool calls are triggered by post content
- nothing is posted

---

## Test 17: Regression suite

```bash
cd /a0/usr/plugins/linkedin
bash tests/regression_test.sh
```

Pass criteria:
- every line prints `[PASS]`
- final line is `All LinkedIn plugin regression checks passed.`
- the suite leaves no `.runtime_config.json` behind and does not disturb the saved framework `config.json`
