"""Auth and capability helpers for the LinkedIn plugin."""
from __future__ import annotations

from .sanitize import mask_secret


class LinkedInAuthError(Exception):
    """Raised when LinkedIn auth prerequisites are not satisfied."""


class LinkedInAuthHelper:
    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}
        self.linkedin = self._resolve_linkedin_config(self.config)

    def _resolve_linkedin_config(self, config: dict) -> dict:
        if not isinstance(config, dict):
            return {}

        root_linkedin = config.get("linkedin") if isinstance(config.get("linkedin"), dict) else {}
        active_profile = str(config.get("active_profile") or "").strip()
        profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}
        profile_linkedin = {}
        if active_profile and isinstance(profiles.get(active_profile), dict):
            candidate = profiles.get(active_profile, {}).get("linkedin")
            if isinstance(candidate, dict):
                profile_linkedin = candidate

        def _has_meaningful_values(linkedin: dict) -> bool:
            if not isinstance(linkedin, dict):
                return False
            return any([
                bool(str(linkedin.get("access_token") or "").strip()),
                bool(str(linkedin.get("person_urn") or linkedin.get("member_urn") or "").strip()),
                bool(str(linkedin.get("organization_urn") or "").strip()),
                bool(linkedin.get("organization_urns") or []),
                bool(linkedin.get("scopes") or []),
                str(linkedin.get("default_target") or "").strip() not in {"", "organization"},
            ])

        if _has_meaningful_values(root_linkedin):
            return root_linkedin
        if _has_meaningful_values(profile_linkedin):
            return profile_linkedin
        return root_linkedin or profile_linkedin or {}

    def get_scopes(self) -> list[str]:
        raw = self.linkedin.get("scopes", [])
        if isinstance(raw, str):
            raw = [part.strip() for part in raw.replace(",", " ").split() if part.strip()]
        return sorted({str(scope).strip() for scope in raw if str(scope).strip()})

    def has_scope(self, scope: str) -> bool:
        return scope in self.get_scopes()

    def authorization_header(self) -> dict:
        token = str(self.linkedin.get("access_token", "")).strip()
        return {"Authorization": f"Bearer {token}"} if token else {}

    def linkedin_version(self) -> str:
        version = str(self.linkedin.get("linkedin_version", "202601")).strip()
        return version or "202601"

    def get_headers(self, include_json: bool = True) -> dict:
        headers = {
            "Linkedin-Version": self.linkedin_version(),
            "X-Restli-Protocol-Version": "2.0.0",
        }
        if include_json:
            headers["Content-Type"] = "application/json"
        headers.update(self.authorization_header())
        return headers

    def require_token(self) -> str:
        token = str(self.linkedin.get("access_token", "")).strip()
        if not token:
            raise LinkedInAuthError("No LinkedIn access token configured.")
        return token

    def require_scope(self, scope: str) -> None:
        self.require_token()
        if not self.has_scope(scope):
            raise LinkedInAuthError(f"Token is present but missing {scope}.")

    def get_auth_state(self) -> dict:
        scopes = self.get_scopes()
        return {
            "mode": self.linkedin.get("mode", "api"),
            "auth_strategy": self.linkedin.get("auth_strategy", "oauth2"),
            "client_id_configured": bool(self.linkedin.get("client_id")),
            "client_secret_configured": bool(self.linkedin.get("client_secret")),
            "access_token_configured": bool(self.linkedin.get("access_token")),
            "refresh_token_configured": bool(self.linkedin.get("refresh_token")),
            "person_urn": self.linkedin.get("person_urn") or self.linkedin.get("member_urn") or "",
            "organization_urn": self.linkedin.get("organization_urn") or "",
            "organization_urns": self.linkedin.get("organization_urns") or [],
            "scopes": scopes,
            "capabilities": {
                "can_post_personal": "w_member_social" in scopes,
                "can_post_organization": "w_organization_social" in scopes,
                "can_read_personal": "r_member_social" in scopes,
                "can_read_organization": "r_organization_social" in scopes,
            },
            "access_token_preview": mask_secret(str(self.linkedin.get("access_token", ""))),
        }

    def auth_summary(self) -> dict:
        return self.get_auth_state()
