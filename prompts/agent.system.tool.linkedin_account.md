Use `linkedin_account` to inspect LinkedIn plugin readiness across every configured LinkedIn account.

Actions:
- `accounts`: list every configured account with its inferred target type (`personal`/`organization`), token presence, scopes, organization page count, and `can_post`/`can_read` readiness
- `status`: readiness summary plus the account that personal and organization requests would route to
- `auth_summary`: redacted auth configuration details
- `organizations`: discover organization pages available to one account

Notes:
- One plugin installation can hold many LinkedIn accounts (apps, members, and pages).
- Start here when the user has not said which LinkedIn account to use — `accounts` is the list you present.
- Pass `profile: "<name>"` to scope `organizations` to one account.
- Never expose access tokens. Confirmed values are masked except the last four characters.
- The MVP scaffold does not complete OAuth in-tool; tokens are configured in the plugin settings UI.