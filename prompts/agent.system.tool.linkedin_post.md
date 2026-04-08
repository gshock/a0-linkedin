Use `linkedin_post` for LinkedIn post previews and create-post attempts.

Actions:
- `preview`: validate and preview text before posting
- `create`: submit a create-post request or dry-run payload

Notes:
- Prefer `preview` before `create`.
- In MVP scaffold, `create` usually returns a dry-run payload unless config disables `dry_run`.
