Use `linkedin_account` to inspect LinkedIn plugin readiness.

Actions:
- `status`: return local-config based account/auth readiness summary
- `auth_summary`: return redacted auth configuration details

Notes:
- This MVP scaffold does not complete OAuth in-tool.
- Treat returned auth data as sensitive even when redacted.
