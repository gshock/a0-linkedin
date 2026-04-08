# LinkedIn Plugin Human Test Plan

This plan verifies the current API-first LinkedIn plugin behavior in Agent Zero.

## Scope

### In scope now
- personal posting
- personal preview vs live create behavior
- dual-profile config UI behavior
- dry_run toggle behavior
- personal vs organization routing behavior
- readiness/status inspection

### Deferred
- organization live posting
- organization live reading

Reason:
- **org_app is under LinkedIn review**
- defer org-mode testing until verification is complete

## Preconditions

Before running tests, confirm:

- LinkedIn plugin is enabled
- plugin settings UI loads correctly
- Personal / Organization / Runtime tabs are visible
- personal profile has a valid personal access token
- personal profile has a valid `person_urn` in `urn:li:person:*` format
- org profile may remain incomplete while review is pending

## Test 1: Config UI renders the dual-profile layout

### Goal
Verify the plugin settings UI shows the new dual-profile structure.

### Steps
1. Open LinkedIn plugin settings
2. Confirm visible tabs:
   - Personal
   - Organization
   - Runtime

### Expected result
- old tabs like Credentials / Targets / Defaults are no longer the main UI model
- dual-profile tabs are visible
- settings body is not blank

## Test 2: Personal values persist in the Personal tab

### Goal
Verify personal config values load and save correctly.

### Steps
1. Open the Personal tab
2. Confirm these fields are populated or enter them:
   - access token
   - scopes
   - person URN
   - default visibility
   - dry_run
3. Save
4. Reopen plugin settings
5. Return to the Personal tab

### Expected result
- values persist after reopen
- no unexpected overwrite from organization settings

## Test 3: Organization values remain isolated from personal values

### Goal
Verify profile isolation in the config UI.

### Steps
1. Open Personal tab and note current values
2. Open Organization tab
3. Edit one harmless org-only value such as:
   - organization URN
   - org scopes text
4. Save
5. Reopen plugin settings
6. Return to Personal tab

### Expected result
- personal values remain unchanged
- org values persist independently
- editing org does not overwrite personal

## Test 4: Personal readiness check

### Goal
Verify the plugin reports that personal mode is ready when configured correctly.

### Steps
1. Run `linkedin_account` with:
   - `action: status`
2. Review readiness output

### Expected result
- personal mode shows token present
- personal mode shows `person_urn` present
- personal mode shows personal posting ready when `w_member_social` is present
- organization mode may still report not ready

## Test 5: Personal preview using approved text

### Goal
Verify preview works safely without publishing.

### Steps
1. Run `linkedin_post` with:
   - `action: preview`
   - `target: personal`
   - approved text in `message`
2. Review tool output

### Expected result
- preview succeeds
- no live LinkedIn post is created
- response includes:
   - `resolved_profile = personal_app`
   - `target = personal`

## Test 6: Personal live create with approved text

### Goal
Verify live personal posting works end-to-end.

### Steps
1. Ensure personal `dry_run` is off
2. Run `linkedin_post` with:
   - `action: create`
   - `target: personal`
   - approved text in `message`
3. Check LinkedIn
4. Delete temporary test post manually after verification

### Expected result
- tool returns `ok: True`
- HTTP status is `201`
- response includes:
   - `resolved_profile = personal_app`
   - `target = personal`
- post appears on LinkedIn

## Test 7: `message` fallback compatibility

### Goal
Verify `linkedin_post` still accepts `message` when `text` is not supplied.

### Steps
1. Run preview with:
   - `message`
   - no `text`
2. Run create with:
   - `message`
   - no `text`

### Expected result
- both paths work
- no argument mismatch occurs

## Test 8: dry_run on/off immediate behavior

### Goal
Verify runtime behavior changes immediately when dry_run changes.

### Steps
1. Enable personal `dry_run`
2. Save settings
3. Run `linkedin_account status`
4. Confirm personal dry_run is true
5. Run `linkedin_post create` with `target: personal`
6. Confirm no live post is created
7. Disable personal `dry_run`
8. Save settings
9. Run `linkedin_account status`
10. Confirm personal dry_run is false
11. Run `linkedin_post create` again
12. Confirm a real post is created
13. Delete the test post manually

### Expected result
- dry_run on returns payload-only behavior
- dry_run off results in a live post
- behavior changes immediately after save

## Test 9: Personal read restriction handling

### Goal
Verify the plugin reports scope restrictions clearly when personal read is unavailable.

### Steps
1. Use a token that supports posting but not `r_member_social`
2. Run `linkedin_read` with:
   - `action: recent_posts`
   - `target: personal`
3. Review output

### Expected result
- plugin reports missing `r_member_social`
- failure is presented as a scope restriction
- this is not misdiagnosed as a generic runtime failure

## Test 10: Ambiguous target behavior

### Goal
Verify the plugin does not guess between personal and organization mode.

### Steps
1. Run `linkedin_post` create without:
   - `target`
   - `profile`
2. Or ask the agent:
   - "Post this on LinkedIn"

### Expected result
- plugin/agent asks for clarification
- it does not silently choose personal or organization

## Test 11: Explicit organization routing readiness only

### Goal
Verify organization mode is recognized but intentionally deferred.

### Steps
1. Run `linkedin_account` with:
   - `action: status`
2. Inspect organization mode readiness

### Expected result
- organization mode may show not ready or partially configured
- missing token/scope/role requirements are explicit
- no org live post test is attempted while review is pending

## Test 12: Person URN validation awareness

### Goal
Verify operators understand the required URN format for live personal posting.

### Steps
1. Confirm personal author URN is in this format:
   - `urn:li:person:*`
2. Do not use:
   - `urn:li:member:*`

### Expected result
- live posting uses person URN format
- known HTTP `422` author mismatch issue is avoided

## Test 13: UI reload resilience

### Goal
Verify plugin settings recover correctly after UI/plugin reloads.

### Steps
1. Disable plugin
2. Re-enable plugin
3. Hard refresh the UI
4. Reopen LinkedIn plugin settings

### Expected result
- config UI still renders
- Personal / Organization / Runtime tabs remain visible
- saved values persist

## Pass criteria summary

The current plugin state should be considered healthy if all of the following are true:

- Personal tab values persist
- Organization tab does not overwrite personal values
- `linkedin_account status` reports personal readiness accurately
- preview works for personal mode
- live personal post succeeds with HTTP `201`
- dry_run changes behavior immediately
- personal read restriction is clearly reported when `r_member_social` is missing
- ambiguous target requests trigger clarification instead of guessing
- organization live testing remains deferred until LinkedIn review completes

## Current expected project status

### Verified working
- personal posting
- personal preview
- dry_run toggle behavior
- per-call routing to `personal_app`
- explicit dual-profile UI structure

### Not yet verified for live use
- organization live posting
- organization live readback

### Intentionally deferred
- org-mode live validation until LinkedIn review is complete
