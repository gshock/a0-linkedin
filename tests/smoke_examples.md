# LinkedIn Plugin Smoke Examples

These examples reflect the current dual-profile, per-call routing behavior of the LinkedIn plugin.

## Notes

- Use `target: personal` to route to `personal_app`
- Use `target: organization` to route to `org_app`
- Optional `profile` can override target routing
- If neither `target` nor `profile` is supplied, the plugin should ask for clarification and must not guess
- `linkedin_post` accepts both `text` and `message`
- Personal live posting requires `person_urn` in `urn:li:person:*` format

## 1. Personal readiness check

```json
{
  "action": "status"
}
```

### Expected
- personal readiness summary visible
- organization readiness summary visible
- personal mode should show ready to post when token, scopes, and `person_urn` are valid

## 2. Personal preview using `message`

```json
{
  "action": "preview",
  "target": "personal",
  "message": "Hello from my personal LinkedIn profile"
}
```

### Expected
- preview succeeds
- no live post is created
- response includes `resolved_profile: personal_app`

## 3. Personal preview using `text`

```json
{
  "action": "preview",
  "target": "personal",
  "text": "Hello from my personal LinkedIn profile"
}
```

### Expected
- preview succeeds
- `text` is accepted directly
- response includes `resolved_profile: personal_app`

## 4. Personal live create

```json
{
  "action": "create",
  "target": "personal",
  "message": "Quick personal LinkedIn test post from Agent Zero. This is a temporary validation post."
}
```

### Expected
- live post succeeds when `dry_run` is off
- response includes:
  - `ok: true`
  - `status: 201`
  - `resolved_profile: personal_app`

## 5. Organization preview

```json
{
  "action": "preview",
  "target": "organization",
  "message": "Hello from our company page"
}
```

### Expected
- routes to `org_app`
- response includes `resolved_profile: org_app`
- actual org live use may still be blocked until org review/approval is complete

## 6. Explicit profile override

```json
{
  "action": "create",
  "profile": "personal_app",
  "message": "Hello from the explicit personal profile override"
}
```

### Expected
- plugin uses `personal_app` even if active profile is different

## 7. Ambiguous create request

```json
{
  "action": "create",
  "message": "Post this on LinkedIn"
}
```

### Expected
- plugin returns clarification-needed behavior
- plugin does not silently choose personal or organization

## 8. Personal recent posts read attempt

```json
{
  "action": "recent_posts",
  "target": "personal",
  "max_results": 5
}
```

### Expected
- if `r_member_social` is missing, plugin reports that personal read is unavailable
- this should be treated as a scope restriction, not a general plugin malfunction

## 9. Organization recent posts read attempt

```json
{
  "action": "recent_posts",
  "target": "organization",
  "max_results": 5
}
```

### Expected
- routes to `org_app`
- organization read remains dependent on org token, scopes, and LinkedIn approval

## 10. Single post read

```json
{
  "action": "post",
  "target": "organization",
  "post_urn": "urn:li:share:1234567890"
}
```

### Expected
- plugin attempts single-post retrieval using the resolved org profile
- success depends on org readiness and LinkedIn API permissions

## 11. dry_run safety example

```json
{
  "action": "create",
  "target": "personal",
  "message": "This post should not publish while dry_run is enabled"
}
```

### Expected
- when personal `dry_run` is on, payload is prepared but no live post is sent
- when personal `dry_run` is off, a live request is sent

## 12. URN correctness reminder

### Personal live posting must use
- `urn:li:person:*`

### Do not use
- `urn:li:member:*`

Using the wrong URN type can cause HTTP `422` validation failures.

## Current project note

- `org_app` is under LinkedIn review
- defer org-mode live testing until verification is complete
