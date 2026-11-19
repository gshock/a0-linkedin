This plugin provides LinkedIn account management and approved posting workflows for Agent Zero.

Available tools:
- `linkedin_account` — list accounts and report readiness
- `linkedin_post` — preview and publish approved posts
- `linkedin_read` — recent posts and single-post lookups
- `linkedin_manage` — reserved for future edit/delete support

Design intent:
- API-first, official LinkedIn Posts API
- Multiple named accounts per installation (apps, members, and pages)
- Safe dry-run defaults; no post is published without user approval
- When several accounts can serve a request, ask the user instead of guessing
- Never print access tokens; confirmed values are masked except the last four characters
