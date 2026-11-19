# LinkedIn Plugin — Smoke Examples (v0.3.0)

Copy-paste checks for a multi-account installation. The account names below are
examples; substitute the names actually configured in the plugin settings.

## 0. Prerequisites

- Plugin enabled and at least one account configured in **Settings → Plugins → LinkedIn → Accounts**.
- `dry_run` left **on** until a live post is explicitly intended.
- Access tokens are never printed; confirmed values show only the last 4 characters.

---

## 1. List accounts

**Tool:** `linkedin_account`

```json
{ "action": "accounts" }
```

Expected:

- `count` matches the number of configured accounts.
- Each entry carries `profile`, `label`, `target` (`personal`/`organization`), `token_present`, `scopes`, `organization_page_count`, `can_post`, `can_read`.
- An account with no token shows `token_present: false` and `can_post: false`.

---

## 2. Readiness summary with routing

**Tool:** `linkedin_account`

```json
{ "action": "status" }
```

Expected:

- `accounts` lists every configured account.
- `routing.personal.profile` names the account a personal post would use, or `null` with `needs_clarification: true` and a `candidates` list when several personal accounts exist.
- `routing.organization.profile` behaves the same way for organization targets.
- `config.profiles.<name>.linkedin.access_token` is masked.

---

## 3. Ambiguity — two personal accounts, no profile named

**Tool:** `linkedin_post`

```json
{ "action": "preview", "target": "personal", "text": "Hello from Agent Zero." }
```

Expected when `justlinks` and `myresumator_me` both exist:

```json
{
  "ok": false,
  "needs_clarification": true,
  "message": "Multiple LinkedIn accounts can handle personal: justlinks, myresumator_me. Which one should be used?",
  "candidates": [
    { "profile": "justlinks", "label": "JustLinks", "target": "personal", "can_post": true },
    { "profile": "myresumator_me", "label": "MyResumator Personal", "target": "personal", "can_post": true }
  ]
}
```

The agent must present that list and ask — never pick one silently.

---

## 4. Explicit account wins

**Tool:** `linkedin_post`

```json
{
  "action": "preview",
  "profile": "myresumator_me",
  "target": "personal",
  "text": "Hello from MyResumator."
}
```

Expected:

- `resolved_profile: "myresumator_me"`
- no clarification request

---

## 5. Unknown account is a hard error

**Tool:** `linkedin_post`

```json
{ "action": "preview", "profile": "not_a_real_account", "text": "test" }
```

Expected:

- `ok: false`
- `message` starts with `Unknown LinkedIn profile 'not_a_real_account'.`
- `needs_clarification: false` — this is a mistake, not a choice.

---

## 6. Unique organization account resolves without asking

**Tool:** `linkedin_read`

```json
{ "action": "recent_posts", "target": "organization", "limit": 5 }
```

Expected:

- `resolved_profile: "myresumator_biz"` (when it is the only usable organization account)
- no clarification request
- if `r_organization_social` is absent from the account scopes, a clear scope error instead of an empty list

---

## 7. Organization discovery for one account

**Tool:** `linkedin_account`

```json
{ "action": "organizations", "profile": "myresumator_biz" }
```

Expected:

- with `dry_run` on: the configured organization URNs are echoed back with `dry_run: true`
- with `dry_run` off: `count` plus one entry per page the token has a role on
- a token without organization roles yields an explicit failure, not a silent empty list

---

## 8. Text post preview

**Tool:** `linkedin_post`

```json
{ "action": "preview", "profile": "justlinks", "text": "Shipping a small update today." }
```

Expected:

- `preview.text_preview` holds the sanitized text
- `preview.target`, `preview.visibility`, `preview.post_type: "text"`
- `resolved_profile: "justlinks"`

---

## 9. Text post create in dry run

**Tool:** `linkedin_post`

```json
{ "action": "create", "profile": "justlinks", "text": "Shipping a small update today." }
```

Expected:

- `dry_run: true`
- the payload contains `author`, `commentary`, `visibility`, `distribution`, `lifecycleState`
- no network write occurs

---

## 10. Single-image post preview

**Tool:** `linkedin_post`

```json
{
  "action": "preview",
  "profile": "justlinks",
  "text": "Now with a picture.",
  "image_path": "/a0/usr/uploads/example.jpg",
  "alt_text": "A short description"
}
```

Expected: `preview.post_type: "image"`, plus `image_name`, `image_size_bytes`, `alt_text`.

---

## 11. Multi-image post preview

**Tool:** `linkedin_post`

```json
{
  "action": "preview",
  "profile": "justlinks",
  "text": "Three shots.",
  "image_paths": ["/a0/usr/uploads/a.jpg", "/a0/usr/uploads/b.png", "/a0/usr/uploads/c.heic"]
}
```

Expected:

- `preview.post_type: "images"`, `preview.image_count: 3`
- `preview.needs_conversion: true` because of the HEIC file

---

## 12. Conflicting image arguments are rejected

**Tool:** `linkedin_post`

```json
{ "action": "preview", "text": "x", "image_path": "/a.jpg", "image_paths": ["/b.jpg"] }
```

Expected: `ok: false` with `Provide either 'image_path' or 'image_paths', not both.`

---

## 13. Missing token is reported plainly

Configure an account with empty `access_token`, then:

**Tool:** `linkedin_post`

```json
{ "action": "preview", "profile": "that_account", "text": "test" }
```

Expected: the account is absent from `accounts` candidates and the tool reports that no configured account can act — with `can_post: false` visible on that account in `linkedin_account`.

---

## 14. Personal read restriction

**Tool:** `linkedin_read`

```json
{ "action": "recent_posts", "profile": "justlinks", "limit": 5 }
```

Expected when `r_member_social` is not granted (normal for most apps):

- a clear message that personal reads require `r_member_social`, which LinkedIn restricts
- no retry loop, no fabricated results

---

## 15. Token masking in every response

Any `linkedin_account` action, plus the settings page:

Expected:

- access tokens appear only as `****last4`
- no tool output ever contains a full token, even on failure paths
