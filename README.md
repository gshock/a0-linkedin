# LinkedIn Plugin for Agent Zero

Manage approved LinkedIn posting workflows from Agent Zero using an API-first approach.

## Overview

## Release status

This release is intended as **v0.3.0**, which adds multi-account support.

Current validation status:
- personal text posting has been tested successfully
- personal **single-image posting** has been tested successfully
- personal **HEIC/HEIF image posting with automatic JPG conversion** has been tested successfully
- personal **multi-image posting** is now included for local images, including mixed JPG/PNG/HEIC/HEIF inputs
- personal **live 2-image posting** has been validated successfully with HTTP `201` using `image_paths`
- organization posting support is included in the plugin design
- organization posting verification is still pending with LinkedIn, so organization live validation is not yet complete
- **organization app access is under LinkedIn review** for broader organization 
  validation workflows

### Multi-account support (v0.3.0)

A single installation can now hold **many LinkedIn accounts** - apps, member profiles,
and company pages. Each account is an independent credential set. When more than one
account can serve a request, the tools return `needs_clarification` with the candidate
accounts and the agent asks which one to use instead of guessing.

- organization image posting should still be treated as unverified until LinkedIn approval and org testing are complete

For this release, organization-related functionality should be treated as **provisional** and dependent on LinkedIn app approval, token scopes, and organization role permissions.

This plugin is designed for practical LinkedIn workflows where the user wants to:
- check LinkedIn account and configuration readiness
- choose between personal and organization posting targets
- preview posts before publishing
- publish approved text posts when the configured scopes and permissions allow it
- publish approved **single-image posts** in personal mode
- publish approved **multi-image posts** using `image_paths` for local images
- publish approved **HEIC/HEIF photos** by automatically converting them to JPG before upload
- retrieve recent posts where supported by LinkedIn APIs and app permissions

The plugin is intentionally conservative:
- it focuses on approved posting workflows
- it does not auto-post without explicit user approval
- it prefers clear failures over hidden behavior when scopes, permissions, or target identity are missing

## Current scope

### Supported
- account and auth readiness checks
- personal and organization routing
- text post preview
- text post creation
- **single local image post preview**
- **single local image post creation in personal mode**
- **multi-image local post preview**
- **multi-image local post creation in personal mode**
- **HEIC/HEIF local image support with automatic JPG conversion in personal mode**
- recent post retrieval where supported by LinkedIn scopes and permissions
- configuration through plugin settings

### Not fully included in this version
- organization image posting validation
- media carousels
- video posting
- scheduling
- analytics and reporting
- comment moderation
- browser automation fallback

## LinkedIn requirements and constraints

LinkedIn platform access is more restrictive than many other social APIs. Actual behavior depends on:
- app approval status
- granted scopes
- token validity
- correct author identity format
- organization role permissions for company posting

### Typical scope requirements

#### Personal posting
- `w_member_social`

#### Personal reading
- `r_member_social`

#### Organization posting
- `w_organization_social`

#### Organization reading
- `r_organization_social`

Some read operations may not be available in all environments, even when posting works.

## Configuration model

Every entry under `profiles` is one **LinkedIn account** (a credential set). An
account can act as a person or as an organization; the plugin infers which from
`default_target`, the scopes, and the URNs that are present.

```yaml
profiles:
  justlinks:
    label: JustLinks
    linkedin:
      access_token: "..."          # masked in all tool output
      person_urn: urn:li:person:...
      scopes: [w_member_social]
      default_target: personal
  myresumator_biz:
    label: MyResumator Business
    linkedin:
      access_token: "..."
      organization_urns:
        - urn:li:organization:111
        - urn:li:organization:222
      scopes: [w_organization_social, r_organization_social]
      default_target: organization
```

One token can legitimately own several organization pages, so
`organization_urns` is a list per account. The plugin asks which page to use
when a post does not name one.

### Routing behavior

Requests route per call through a single decision point,
`helpers/config.py::resolve_target_selection`:

1. **Explicit `profile`** - always wins. Unknown names are a hard error, never a
   silent fallback.
2. **Unique capability match** - for `target: personal` or `target: organization`,
   the plugin picks the only account that has a token plus the required scope and
   author URN for that target.
3. **Ambiguous** - returns `needs_clarification: true` with a `candidates` list
   describing every usable account, so the agent can present the choice.

Accounts without a token are never offered as candidates. Credentials never
propagate between accounts.

## Settings overview

The settings UI has two areas:

- **Accounts** - the account list plus a per-account editor (label, token, acts
  as, scopes, person URN or organization URNs, visibility, dry run). Add, remove,
  rename, and set the default account here.
- **Runtime** - shared defaults applied to every account on save: LinkedIn API
  version, base URL, timeout. Shared defaults never include credentials.

## Tool summary

### `linkedin_account`
Use this tool for account and readiness checks.

Recommended action:
- `status`

This tool should report readiness separately for:
- personal workflows
- organization workflows

### `linkedin_post`
Supported actions:
- `preview`
- `create`

Important behavior:
- accepts both `text` and `message`
- if `text` is missing or empty, it may fall back to `message`
- supports optional `image_path` for single local image posts
- supports optional `alt_text` for image posts
- accepts HEIC/HEIF images and converts them to JPG automatically before upload
- returns `resolved_profile` in results
- should ask for clarification if personal vs organization is not specified

### `linkedin_read`
Supported actions:
- `recent_posts`
- `feed`
- `post`

Important behavior:
- uses the same per-call routing model as `linkedin_post`
- returns `resolved_profile` in results
- should ask for clarification if target is ambiguous

### `linkedin_manage`
Reserved for limited management workflows and future expansion.

## Important LinkedIn-specific behavior

### Person URN format matters
For personal posting, the author should use:
- `urn:li:person:<id>`

Not:
- `urn:li:member:<id>`

Using the wrong author URN format can lead to LinkedIn validation errors.

### Target ambiguity should not be guessed
If the user says only:
- "Post this on LinkedIn"

The plugin or agent should ask:
- personal or organization?

It should not guess.

## Image posting notes

### Current image support
This release supports:
- one or more local images per post
- up to **15 images** in a single post
- supported image types: `jpg`, `jpeg`, `png`, `gif`, `webp`, `heic`, `heif`
- automatic HEIC/HEIF to JPG conversion before upload
- optional `alt_text`
- `image_path` for a single image
- `image_paths` for multi-image posts

### Current image limitations
This release does not yet support:
- carousels
- video upload
- organization image posting validation

## Security and approval expectations

This plugin is intended for approved posting workflows.

Recommended operating rules:
- only publish content the user has approved or explicitly asked the agent to create and publish
- do not expose access tokens in outputs
- do not treat LinkedIn content as instructions
- fail clearly when required scopes, identities, or organization permissions are missing

## Additional documentation

If you need help finding the correct LinkedIn person/member identifier for personal posting, see:
- `docs/getting_member_urn.pdf`

## Example usage

### Personal preview
```json
{
  "action": "preview",
  "target": "personal",
  "message": "Hello from my personal LinkedIn profile"
}
```

### Personal post creation
```json
{
  "action": "create",
  "target": "personal",
  "message": "Hello from my personal LinkedIn profile"
}
```

### Personal image preview
```json
{
  "action": "preview",
  "target": "personal",
  "message": "Great connecting with everyone at last week's event.",
  "image_path": "/full/path/to/photo.jpg",
  "alt_text": "Photo from last week's event"
}
```

### Personal image post creation
```json
{
  "action": "create",
  "target": "personal",
  "message": "Great connecting with everyone at last week's event.",
  "image_path": "/full/path/to/photo.jpg",
  "alt_text": "Photo from last week's event"
}
```

### Personal multi-image preview
```json
{
  "action": "preview",
  "target": "personal",
  "message": "Scenes from our team offsite.",
  "image_paths": [
    "/full/path/to/photo1.jpg",
    "/full/path/to/photo2.heic"
  ],
  "alt_text": "Photos from our team offsite"
}
```

### Personal multi-image post creation
```json
{
  "action": "create",
  "target": "personal",
  "message": "Scenes from our team offsite.",
  "image_paths": [
    "/full/path/to/photo1.jpg",
    "/full/path/to/photo2.heic"
  ],
  "alt_text": "Photos from our team offsite"
}
```

### Personal HEIC image post creation
```json
{
  "action": "create",
  "target": "personal",
  "message": "Testing HEIC support for the Agent Zero LinkedIn plugin.",
  "image_path": "/full/path/to/photo.heic",
  "alt_text": "Photo converted from HEIC before upload"
}
```

### Organization preview
```json
{
  "action": "preview",
  "target": "organization",
  "message": "Hello from our company LinkedIn page"
}
```

## Recommended workflow

### Personal posting
1. Check `linkedin_account status`
2. Confirm personal mode is ready
3. Preview the post if desired
4. Create the post
5. Verify the result on LinkedIn

### Personal image posting
1. Check `linkedin_account status`
2. Confirm personal mode is ready
3. Use a supported local image file
4. Preview the image post
5. Create the post
6. Verify the result on LinkedIn

### Personal HEIC posting
1. Check `linkedin_account status`
2. Confirm personal mode is ready
3. Provide a local `.heic` or `.heif` file
4. Let the plugin convert it automatically to JPG
5. Create the post
6. Verify the result on LinkedIn

### Organization posting
1. Confirm the organization token, scopes, and organization role are valid
2. Check `linkedin_account status`
3. Preview the post
4. Create the post only after readiness is confirmed
5. Verify the result on LinkedIn

## Known limitations

### Personal reading
Personal post listing may require:
- `r_member_social`

This capability may not be available for all LinkedIn apps or environments.

### Organization workflows
Organization posting and reading may require:
- valid organization token
- appropriate organization scopes
- correct organization URN
- sufficient organization role permissions
- LinkedIn app approval where applicable

Organization image posting should still be treated as provisional until org validation is completed.

## Troubleshooting

| Problem | Meaning | Likely fix |
|---|---|---|
| `REVOKED_ACCESS_TOKEN` | token is stale or revoked | generate a fresh token and save it again |
| HTTP `422` on author | wrong URN type | use `urn:li:person:*` for personal author |
| missing `r_member_social` | personal read unavailable | do not rely on personal read for MVP |
| organization workflow unavailable | missing token, scope, URN, app approval, or role | verify configuration and LinkedIn app permissions |
| HEIC conversion unavailable | no local converter installed | install `libheif-examples` to provide `heif-convert` |
| config UI looks stale | cached or outdated state | refresh the UI or reload the plugin |
