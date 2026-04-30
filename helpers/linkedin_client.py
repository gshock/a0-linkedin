"""LinkedIn REST client for the Agent Zero LinkedIn plugin MVP."""
from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from urllib.parse import quote
import urllib.error
import urllib.request

from .linkedin_auth import LinkedInAuthError, LinkedInAuthHelper
from .linkedin_format import normalize_visibility
from .sanitize import normalize_organization_urn, sanitize_text, validate_image_path, validate_message


class LinkedInClient:
    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}
        self.linkedin = self.config.get("linkedin", {}) if isinstance(self.config, dict) else {}
        self.auth = LinkedInAuthHelper(self.config)
        self.base_url = str(self.linkedin.get("api_base_url") or "https://api.linkedin.com").rstrip("/")
        self.timeout = int(self.linkedin.get("timeout_seconds") or 30)
        self.user_agent = self.linkedin.get("user_agent") or "AgentZero-LinkedIn-Plugin/0.2.0"
        self.dry_run = bool(self.linkedin.get("dry_run", True))

    def _headers(self, include_json: bool = True, extra: dict | None = None) -> dict:
        headers = self.auth.get_headers(include_json=include_json)
        headers["User-Agent"] = self.user_agent
        if extra:
            headers.update(extra)
        return headers

    def _request(self, method: str, path: str, payload: dict | None = None, query: str = "") -> dict:
        url = f"{self.base_url}{path}{query}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method, headers=self._headers(include_json=True))
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                parsed = json.loads(body) if body.strip() else {}
                return {"ok": 200 <= response.status < 300, "status": response.status, "url": url, "data": parsed}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body) if body.strip() else {}
            except Exception:
                parsed = {"raw": body}
            return {"ok": False, "status": exc.code, "url": url, "error": parsed}
        except Exception as exc:
            return {"ok": False, "status": 0, "url": url, "error": {"message": str(exc)}}

    def _binary_upload(self, upload_url: str, file_path: str, mime_type: str) -> dict:
        try:
            data = Path(file_path).read_bytes()
            request = urllib.request.Request(
                upload_url,
                data=data,
                method="PUT",
                headers={
                    "Content-Type": mime_type,
                    "Content-Length": str(len(data)),
                    "User-Agent": self.user_agent,
                },
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                parsed = json.loads(body) if body.strip() else {}
                return {"ok": 200 <= response.status < 300, "status": response.status, "url": upload_url, "data": parsed}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body) if body.strip() else {}
            except Exception:
                parsed = {"raw": body}
            return {"ok": False, "status": exc.code, "url": upload_url, "error": parsed}
        except Exception as exc:
            return {"ok": False, "status": 0, "url": upload_url, "error": {"message": str(exc)}}

    def _author_for_target(self, target: str, organization_urn: str | None = None) -> str:
        if target == "organization":
            org = normalize_organization_urn(organization_urn or self.linkedin.get("organization_urn") or "")
            if not org:
                raise LinkedInAuthError("No organization URN configured for organization posting.")
            return org
        person = str(self.linkedin.get("person_urn") or self.linkedin.get("member_urn") or "").strip()
        if not person:
            raise LinkedInAuthError(
                "No personal person URN configured for personal posting. Personal mode is enabled, but live personal posting requires person_urn in the form urn:li:person:<id>."
            )
        return person

    def _build_text_post_payload(self, author: str, text: str, visibility: str | None = None) -> dict:
        return {
            "author": author,
            "commentary": sanitize_text(text),
            "visibility": normalize_visibility(visibility, self.linkedin.get("default_visibility", "PUBLIC")),
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

    def _build_image_post_payload(self, author: str, text: str, media_urn: str, visibility: str | None = None, alt_text: str | None = None) -> dict:
        payload = self._build_text_post_payload(author=author, text=text, visibility=visibility)
        media_content = {
            "id": media_urn,
            "title": "Uploaded image",
        }
        if alt_text:
            media_content["altText"] = sanitize_text(alt_text)
        payload["content"] = {
            "media": media_content,
        }
        return payload

    def get_account_summary(self) -> dict:
        auth = self.auth.get_auth_state()
        return {"ok": True, "auth": auth}

    def discover_organizations(self) -> dict:
        self.auth.require_token()
        if self.dry_run:
            configured = self.linkedin.get("organization_urns") or []
            fallback = [self.linkedin.get("organization_urn")] if self.linkedin.get("organization_urn") else []
            items = [item for item in configured or fallback if item]
            return {
                "ok": True,
                "dry_run": True,
                "organizations": [{"organization": org, "localizedName": "Configured organization", "role": "UNKNOWN"} for org in items],
                "message": "Dry run mode enabled; returning configured organization targets only.",
            }
        query = "?q=roleAssignee&projection=(elements*(organization~(localizedName,id),role,organization))"
        result = self._request("GET", "/rest/organizationAcls", payload=None, query=query)
        if not result.get("ok"):
            return result
        organizations = []
        for item in result.get("data", {}).get("elements", []):
            organization = item.get("organization") or ""
            enriched = item.get("organization~", {})
            organizations.append({
                "organization": organization,
                "id": enriched.get("id"),
                "localizedName": enriched.get("localizedName", ""),
                "role": item.get("role", ""),
            })
        return {"ok": True, "count": len(organizations), "organizations": organizations}

    def register_image_upload(self, author: str) -> dict:
        self.auth.require_token()
        payload = {
            "initializeUploadRequest": {
                "owner": author,
            }
        }
        if self.dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "author": author,
                "endpoint": f"{self.base_url}/rest/images?action=initializeUpload",
                "payload": payload,
                "uploadUrl": "https://example.invalid/linkedin-upload",
                "image": "urn:li:image:DRY_RUN",
                "message": "Dry run enabled; image upload registration prepared but not sent.",
            }
        return self._request("POST", "/rest/images", payload=payload, query="?action=initializeUpload")

    def upload_image_binary(self, upload_url: str, image_path: str) -> dict:
        image_info = validate_image_path(image_path, required=True)
        mime_type = mimetypes.guess_type(image_info["path"])[0] or "application/octet-stream"
        if self.dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "upload_url": upload_url,
                "image_path": image_info["path"],
                "mime_type": mime_type,
                "size_bytes": image_info["size_bytes"],
                "message": "Dry run enabled; image binary upload not sent.",
            }
        return self._binary_upload(upload_url, image_info["path"], mime_type)

    def create_image_post(
        self,
        text: str,
        image_path: str,
        target: str | None = None,
        organization_urn: str | None = None,
        visibility: str | None = None,
        alt_text: str | None = None,
    ) -> dict:
        validate_message(text)
        image_info = validate_image_path(image_path, required=True)
        resolved_target = str(target or self.linkedin.get("default_target") or "personal").strip().lower()
        scope = "w_organization_social" if resolved_target == "organization" else "w_member_social"
        self.auth.require_scope(scope)
        try:
            author = self._author_for_target(target=resolved_target, organization_urn=organization_urn)
        except LinkedInAuthError as exc:
            if resolved_target == "personal":
                return {
                    "ok": False,
                    "target": resolved_target,
                    "dry_run": self.dry_run,
                    "pending_person_urn": True,
                    "message": str(exc),
                    "next_step": "Configure linkedin.person_urn as urn:li:person:<id> before attempting live personal posting.",
                    "image": image_info,
                }
            raise

        registration = self.register_image_upload(author)
        if not registration.get("ok"):
            registration["message"] = registration.get("message") or "LinkedIn image upload registration failed."
            return registration

        reg_data = registration.get("data", {}) if isinstance(registration.get("data"), dict) else {}
        upload_url = registration.get("uploadUrl") or reg_data.get("uploadUrl") or reg_data.get("uploadUrlExpiresAt") and reg_data.get("uploadUrl")
        media_urn = registration.get("image") or reg_data.get("image") or reg_data.get("value", {}).get("image")

        # Support nested response forms if LinkedIn wraps under value
        if not upload_url:
            upload_url = reg_data.get("value", {}).get("uploadUrl") or reg_data.get("uploadMechanism", {}).get("com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest", {}).get("uploadUrl")
        if not media_urn:
            media_urn = reg_data.get("value", {}).get("image") or reg_data.get("image")

        if not upload_url:
            return {
                "ok": False,
                "status": registration.get("status", 0),
                "message": "LinkedIn image upload registration succeeded but did not return an upload URL.",
                "registration": registration,
            }
        if not media_urn:
            return {
                "ok": False,
                "status": registration.get("status", 0),
                "message": "LinkedIn image upload registration succeeded but did not return an image asset URN.",
                "registration": registration,
            }

        upload_result = self.upload_image_binary(upload_url, image_info["path"])
        if not upload_result.get("ok"):
            return {
                "ok": False,
                "message": "LinkedIn image binary upload failed.",
                "registration": registration,
                "upload": upload_result,
            }

        payload = self._build_image_post_payload(
            author=author,
            text=text,
            media_urn=media_urn,
            visibility=visibility,
            alt_text=alt_text,
        )
        if self.dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "target": resolved_target,
                "author": author,
                "image": image_info,
                "media_urn": media_urn,
                "registration": registration,
                "upload": upload_result,
                "endpoint": f"{self.base_url}/rest/posts",
                "payload": payload,
                "message": "Dry run enabled; image post payload prepared but not sent.",
            }

        result = self._request("POST", "/rest/posts", payload=payload)
        if result.get("ok"):
            result["author"] = author
            result["target"] = resolved_target
            result["media_urn"] = media_urn
            result["image"] = image_info
        return result

    def create_post(
        self,
        text: str,
        target: str | None = None,
        organization_urn: str | None = None,
        visibility: str | None = None,
        image_path: str | None = None,
        alt_text: str | None = None,
    ) -> dict:
        if image_path:
            return self.create_image_post(
                text=text,
                image_path=image_path,
                target=target,
                organization_urn=organization_urn,
                visibility=visibility,
                alt_text=alt_text,
            )
        validate_message(text)
        resolved_target = str(target or self.linkedin.get("default_target") or "personal").strip().lower()
        scope = "w_organization_social" if resolved_target == "organization" else "w_member_social"
        self.auth.require_scope(scope)
        payload = self._build_text_post_payload(author="", text=text, visibility=visibility)
        try:
            author = self._author_for_target(target=resolved_target, organization_urn=organization_urn)
            payload["author"] = author
        except LinkedInAuthError as exc:
            if resolved_target == "personal":
                return {
                    "ok": False,
                    "target": resolved_target,
                    "dry_run": self.dry_run,
                    "pending_person_urn": True,
                    "message": str(exc),
                    "next_step": "Configure linkedin.person_urn as urn:li:person:<id> before attempting live personal posting.",
                    "payload": payload if self.dry_run else None,
                }
            raise
        if self.dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "target": resolved_target,
                "author": author,
                "endpoint": f"{self.base_url}/rest/posts",
                "payload": payload,
                "message": "Dry run enabled; post payload prepared but not sent.",
            }
        result = self._request("POST", "/rest/posts", payload=payload)
        if result.get("ok"):
            result["author"] = author
            result["target"] = resolved_target
        return result

    def list_recent_posts(self, target: str | None = None, organization_urn: str | None = None, limit: int = 10) -> dict:
        limit = max(1, min(int(limit), 50))
        resolved_target = str(target or self.linkedin.get("default_target") or "personal").strip().lower()
        scope = "r_organization_social" if resolved_target == "organization" else "r_member_social"
        self.auth.require_scope(scope)
        try:
            author = self._author_for_target(target=resolved_target, organization_urn=organization_urn)
        except LinkedInAuthError as exc:
            if resolved_target == "personal":
                return {
                    "ok": False,
                    "target": resolved_target,
                    "dry_run": self.dry_run,
                    "pending_person_urn": True,
                    "items": [],
                    "limit": limit,
                    "message": str(exc),
                    "next_step": "Configure linkedin.person_urn as urn:li:person:<id> before attempting personal read operations.",
                }
            raise
        if self.dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "target": resolved_target,
                "author": author,
                "items": [],
                "limit": limit,
                "message": "Dry run enabled; read request not sent.",
            }
        query = f"?q=author&author={quote(author, safe=':(),')}&count={limit}&sortBy=LAST_MODIFIED"
        result = self._request("GET", "/rest/posts", payload=None, query=query)
        if not result.get("ok"):
            return result
        items = []
        for item in result.get("data", {}).get("elements", []):
            items.append({
                "id": item.get("id", ""),
                "author": item.get("author", ""),
                "commentary": item.get("commentary", ""),
                "visibility": item.get("visibility", ""),
                "lifecycleState": item.get("lifecycleState", ""),
                "publishedAt": item.get("publishedAt") or item.get("created", {}).get("time"),
            })
        return {"ok": True, "target": resolved_target, "author": author, "count": len(items), "items": items}

    def get_post(self, post_urn: str) -> dict:
        self.auth.require_token()
        if self.dry_run:
            return {"ok": True, "dry_run": True, "post_urn": post_urn, "message": "Dry run enabled; single post read not sent."}
        encoded = quote(post_urn, safe=':(),')
        return self._request("GET", f"/rest/posts/{encoded}", payload=None)

    def manage_post(self, action: str, post_urn: str, text: str | None = None) -> dict:
        return {
            "ok": False,
            "action": action,
            "post_urn": post_urn,
            "text": sanitize_text(text or "") if text else "",
            "message": "linkedin_manage is not implemented in the v1 API-first MVP.",
        }
