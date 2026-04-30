# LinkedIn Image Support v0.2 Implementation Checklist

Use this checklist to add single-image LinkedIn post support to the plugin.

## 1. Scope and API decision

- [x] Confirm v0.2 scope is **single local image per post**
- [ ] Confirm v0.2 will support:
  - [ ] text-only posts
  - [ ] text + one image posts
- [ ] Confirm image support will be added to existing `linkedin_post`
- [ ] Confirm out-of-scope items remain deferred:
  - [ ] multi-image posts
  - [ ] video uploads
  - [ ] image URL ingestion
  - [ ] scheduling
  - [ ] analytics
- [ ] Confirm target order:
  - [ ] personal mode first
  - [ ] organization mode second, behind existing readiness checks
- [ ] Verify the exact LinkedIn media upload flow to implement
- [ ] Document the chosen upload flow before coding

## 2. Input and UX design

- [ ] Add new optional arguments to `linkedin_post`
  - [ ] `image_path`
  - [ ] optional `alt_text` if needed later
- [ ] Keep current text-post behavior unchanged when no image is provided
- [ ] Decide whether `message` and `text` fallback behavior stays the same for image posts
- [ ] Define preview behavior for image posts
- [ ] Define response shape for image post results
- [ ] Ensure ambiguous target handling still asks for clarification

## 3. File validation logic

### Update `/a0/usr/plugins/linkedin/helpers/sanitize.py`

- [ ] Add local image path existence check
- [ ] Add supported image extension validation
- [ ] Add file size validation
- [ ] Add clear error messages for invalid images
- [ ] Keep validation reusable by both preview and create flows

## 4. Tool interface update

### Update `/a0/usr/plugins/linkedin/tools/linkedin_post.py`

- [ ] Extend args schema to accept `image_path`
- [ ] Ensure existing text-only calls still work unchanged
- [ ] Add preview logic for text + image
- [ ] Add create logic for text + image
- [ ] Route personal vs organization exactly as current implementation does
- [ ] Preserve `resolved_profile` in results
- [ ] Keep `dry_run` behavior safe and explicit

## 5. LinkedIn media upload client work

### Update `/a0/usr/plugins/linkedin/helpers/linkedin_client.py`

- [ ] Add helper to initialize/register image upload
- [ ] Add helper to upload image bytes to LinkedIn or returned upload URL
- [ ] Add helper to create a post referencing uploaded media asset
- [ ] Handle personal author URN correctly
- [ ] Reuse existing target/profile resolution logic where possible

## 6. Formatting and result output

### Update `/a0/usr/plugins/linkedin/helpers/linkedin_format.py`

- [ ] Add compact preview formatter for image posts
- [ ] Add result formatting for successful media post creation
- [ ] Make output clearly distinguish text post vs image post

## 7. Config and compatibility review

- [ ] Confirm no new required config fields are needed for v0.2
- [ ] Reuse existing token/profile config model
- [ ] Confirm media posting works with current personal profile config
- [ ] Confirm organization mode remains gated by existing token/scope/role readiness checks

## 8. Personal-mode implementation first

- [ ] Implement full personal text + image post path first
- [ ] Test personal preview with image
- [ ] Test personal live create with image
- [ ] Confirm existing personal text-only posting still works
- [ ] Confirm correct `urn:li:person:*` author is used

## 9. Organization-mode handling

- [ ] Keep organization image posting behind the same readiness checks as text posts
- [ ] Do not bypass org approval/scope/role requirements
- [ ] If org live validation is still unavailable, document org image posting as provisional
- [ ] Ensure org mode failures are explicit and operator-friendly

## 10. Testing checklist

- [ ] Update `/a0/usr/plugins/linkedin/tests/regression_test.sh`
- [ ] Update `/a0/usr/plugins/linkedin/tests/smoke_examples.md`
- [ ] Update `/a0/usr/plugins/linkedin/tests/HUMAN_TEST_PLAN.md`
- [ ] Add manual tests for valid/invalid image inputs

## 11. Documentation updates

### Update `/a0/usr/plugins/linkedin/README.md`

- [ ] Add image posting to current supported scope
- [ ] Document one local image per post
- [ ] Add example usage with `image_path`
- [ ] Keep org-mode wording honest if still provisional

## 12. Release and versioning

- [ ] Bump plugin version to `0.2.0`
- [ ] Add release notes summary for image support
- [ ] Confirm public description still matches actual capability

## 13. Acceptance criteria

- [ ] Text-only posting still works
- [ ] Personal text + image posting works end-to-end
- [ ] Preview works for image posts
- [ ] Invalid image inputs fail clearly
- [ ] README documents image support accurately
- [ ] No secrets are introduced into tracked files
- [ ] Org image behavior is either validated or clearly documented as provisional

## 14. Final release checklist

- [ ] Code complete
- [ ] Manual tests passed
- [ ] Regression tests updated
- [ ] README updated
- [ ] Version bumped to `0.2.0`
- [ ] No local/generated secret files are tracked
- [ ] Ready for personal-mode image posting demo

## Recommended implementation order

1. Validate API flow
2. Add `image_path` input and validation
3. Implement personal upload + create
4. Add preview formatting
5. Update tests
6. Update README
7. Gate org mode behind existing readiness checks
8. Release as `v0.2.0`
