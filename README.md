# LinkedIn Plugin for Agent Zero

Manage approved LinkedIn posting workflows from Agent Zero using an API-first approach.

## Overview

## Release status

**v0.3.1** adds human-readable organization page labels, a default-page picker,
and label-aware page selection, on top of v0.3.0's multi-account support, in-browser
OAuth connect flow, and verified organization posting.

### Verified features

Every item below was exercised against the live LinkedIn API, not just written.

| Feature | Status | Evidence |
|---|---|---|
| Personal text posting | Verified | live post published |
| Personal single-image posting | Verified | API accepted image upload |
| Personal multi-image posting (`image_paths`) | Verified | live 2-image post, HTTP `201` |
| HEIC/HEIF auto-conversion to JPG | Verified | conversion then successful upload |
| **Organization text posting** | **Verified** | org app approved, live post published |
| Organization page discovery (`rw_organization_admin`) | Verified | returned page URN + role |
| Person URN lookup (`/v2/userinfo`) | Verified | resolved `urn:li:person:<sub>` |
| Browser OAuth connect flow | Verified | code exchanged, token stored per account |
| Per-account token masking in config API | Verified | regression suite |
| Multi-account routing + `needs_clarification` | Verified | regression suite |
| Scope defaults per target | Verified | personal and organization fallbacks |
| Retired-scope pre-flight check | Verified | blocks `r_basicprofile` etc. before LinkedIn |
| Actionable OAuth error page | Verified | names the offending scope + fix |
| Organization page names (`/rest/organizations/{id}`) | Verified | resolved 3 live pages to real names |
| URN legend + **Show page names** button | Verified | live lookup, names persisted per account |
| **Default page picker** | **Verified** | org post landed on the pinned page with no URN given |
| Label-aware page selection | Verified | explicit URN overrode the pinned default |

Organization **image** posting is the remaining unverified path: text posting to a
page is confirmed, images to a page are not yet exercised end to end.

### Multi-account support (v0.3.1)

A single installation can now hold **many LinkedIn accounts** - apps, member profiles,
and company pages. Each account is an independent credential set. When more than one
account can serve a request, the tools return `needs_clarification` with the candidate
accounts and the agent asks which one to use instead of guessing.

- organization **text** posting is verified end to end with an approved LinkedIn app
- organization **image** posting remains unverified and should be treated as provisional

Organization text workflows need: an approved app product set, the scopes above, and
a page role for the authenticated member. Organization image workflows additionally
need that upload path exercised against a live page, which has not been done yet.

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
- many accounts per installation, each an independent credential set
- account and auth readiness checks, including per-account capability summaries
- personal and organization routing, with `needs_clarification` instead of guessing
- **organization discovery** - list pages a member administers via `rw_organization_admin`
- **in-browser OAuth connect** - authorize URL, single-use `state` nonce, token written per account
- **URN lookup buttons** - `GET /v2/userinfo` for the person URN, `organizationAcls` for pages
- text post preview and creation for personal and organization targets
- **single local image post preview**
- **single local image post creation in personal mode**
- **multi-image local post preview**
- **multi-image local post creation in personal mode**
- **HEIC/HEIF local image support with automatic JPG conversion in personal mode**
- recent post retrieval where supported by LinkedIn scopes and permissions
- configuration through plugin settings, split into Accounts and Runtime tabs

### Not fully included in this version
- organization **image** posting validation (organization text posting is verified)
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

### Default scopes

A new account starts with the same set the shipped profiles use, chosen by
`default_target`. Only request scopes the LinkedIn app actually has products
for: LinkedIn rejects the entire authorization request with
`unauthorized_scope_error` when one scope is not enabled.

#### Personal (`default_target: personal`)

```
openid profile w_member_social
```

`openid` + `profile` power the **Get Person URN** lookup via `/v2/userinfo`
(the *Sign In with LinkedIn using OpenID Connect* product). `w_member_social`
posts.

`r_member_social` is deliberately **not** a default. It reads member posts and is
gated behind separate LinkedIn approval, and LinkedIn rejects the *entire*
authorization when one requested scope is not granted. Shipping it by default
would break connecting for any app without that approval, blocking posting over a
scope only reading needs. Add it to the Scopes box only when your app holds it.

#### Organization (`default_target: organization`)

```
r_organization_social w_organization_social rw_organization_admin
```

`w_organization_social` posts, `r_organization_social` reads the page feed, and
`rw_organization_admin` (the *Organization Access Control* product) enables
discovering which pages the member administers. Without it, paste organization
URNs manually.

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
      scopes: [openid, profile, w_member_social]
      default_target: personal
  myresumator_biz:
    label: MyResumator Business
    linkedin:
      access_token: "..."
      organization_urns:
        - urn:li:organization:111
        - urn:li:organization:222
      scopes: [r_organization_social, w_organization_social, rw_organization_admin]
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

### Page selection for organization posts

Once an account is chosen, organization posts still need one specific page. That
is a second, separate decision (`helpers/config.py::resolve_organization_page`):

1. **Explicit `organization_urn`** - always wins, even over a pinned default, so
   pinning a page never traps you into posting only there.
2. **Pinned default page** - the **Default page** setting, used silently.
3. **Only one page known** - used silently.
4. **Several pages, none named** - returns `needs_clarification: true` with
   labelled candidates (page name plus id) instead of guessing.
5. **No pages known** - a clear error telling you to discover or paste a URN.

Page labels come from `organization_names`, populated by **Show page names** or by
discovery. A page without a label falls back to its raw URN.

## Settings overview

The settings UI has two areas:

- **Accounts** - the account list plus a per-account editor (label, token, acts
  as, scopes, person URN or organization URNs, visibility, dry run). Add, remove,
  rename, and set the default account here.

### Connecting an account in the browser

The settings page can run the full OAuth 2.0 flow, so the token never has to be
copied by hand:

1. Fill **LinkedIn app client id** and **client secret** for the account.
2. Click **Connect account**. The plugin saves those app credentials, issues a
   single-use `state` nonce, and opens LinkedIn's authorize page in a new tab.
3. Sign in and approve. LinkedIn redirects to
   `/api/plugins/linkedin/linkedin_oauth_callback`, which validates `state`,
   exchanges the code for a token, and writes it into that account only.
4. Close the tab and reload the settings page.

Register the redirect URI shown after clicking **Connect account** (or your own
override in **Redirect URI**) in the LinkedIn app's authorized redirect URLs.
That one URL is what LinkedIn compares against during the exchange.

The callback accepts `GET` and skips CSRF because it is a top-level browser
navigation, but it still requires a logged-in operator session. The `state`
nonce expires after 15 minutes and is deleted on first use, so a replayed or
stale callback cannot overwrite credentials. Tokens are stored server-side and
only a masked preview is ever shown.

### Looking up the URN from the settings page

Both URN fields have a lookup button, so the identifier never has to be pasted by
hand:

- **Get Person URN** calls `GET /v2/userinfo` and writes `urn:li:person:<sub>`.
  It needs the `openid` scope on the token, otherwise LinkedIn answers 401.
- **Get Organization URNs** calls `GET /rest/organizationAcls?q=roleAssignee`
  and writes every page URN with its name and role. It needs the **Organization
  Access Control** product, i.e. the `rw_organization_admin` scope. Neither
  `w_organization_social` nor `r_organization_social` is enough: without
  `rw_organization_admin` LinkedIn answers `403 ACCESS_DENIED` on
  `partnerApiOrganizationAcls.FINDER-roleAssignee`. In that case paste the
  organization URN manually; it is the numeric id in the page's LinkedIn admin
  URL (`urn:li:organization:<id>`).

  The legacy `projection` query parameter is rejected by `/rest` endpoints with
  `400 ILLEGAL_ARGUMENT`, so the plugin never sends it.
- **Show page names** resolves each URN in the box to its real page name via
  `GET /rest/organizations/{id}`. `organizationAcls` returns no name fields, so
  this is the only way to turn an id into something readable. Resolved names are
  stored per account in `organization_names` and shown as a legend under the box.
- **Default page** picks the page organization posts use when a request does not
  name one. Leave it on *Ask me which page* to be prompted whenever several pages
  exist.

The lookup uses the token typed in the form, so it works before the account is
saved. Only click **Save** to persist the result. Tokens are never echoed back in
the response.
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
3. Confirm the target page: set a **Default page** in settings, or name
   `organization_urn` in the request. With several pages and neither set, the tool
   returns `needs_clarification` with labelled candidates and the agent asks.
4. Preview the post
5. Create the post only after readiness is confirmed
6. Verify the result on LinkedIn

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

Organization **text** posting is verified. Organization **image** posting is the
only remaining unvalidated organization path.

## Troubleshooting

| Problem | Meaning | Likely fix |
|---|---|---|
| `REVOKED_ACCESS_TOKEN` | token is stale or revoked | generate a fresh token and save it again |
| HTTP `422` on author | wrong URN type | use `urn:li:person:*` for personal author |
| missing `r_member_social` | personal read unavailable | do not rely on personal read for MVP |
| organization workflow unavailable | missing token, scope, URN, app approval, or role | verify configuration and LinkedIn app permissions |
| `needs_clarification` on an org post | several pages known and none named | pass `organization_urn`, or set a **Default page** in settings |
| page names missing in the legend | names not resolved yet for that account | click **Show page names**, then **Save** |
| HEIC conversion unavailable | no local converter installed | install `libheif-examples` to provide `heif-convert` |
| config UI looks stale | cached or outdated state | refresh the UI or reload the plugin |
