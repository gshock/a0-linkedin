from helpers.tool import Tool, Response


class LinkedInPost(Tool):
    """Create or preview LinkedIn posts for personal or organization targets."""

    async def execute(self, **kwargs) -> Response:
        action = self.args.get("action", "preview")
        text = self.args.get("text")
        if text in (None, ""):
            text = self.args.get("message", "")

        image_path = self.args.get("image_path") or ""
        image_paths = self.args.get("image_paths") or []
        alt_text = self.args.get("alt_text") or ""

        from usr.plugins.linkedin.helpers.config import load_config, resolve_linkedin_config
        from usr.plugins.linkedin.helpers.linkedin_auth import LinkedInAuthError
        from usr.plugins.linkedin.helpers.linkedin_client import LinkedInClient
        from usr.plugins.linkedin.helpers.linkedin_format import compact_post_preview
        from usr.plugins.linkedin.helpers.sanitize import (
            normalize_organization_urn,
            normalize_target,
            validate_image_path,
            validate_image_paths,
            validate_message,
        )

        config = load_config()
        target = self.args.get("target")
        profile = self.args.get("profile")
        organization_urn = self.args.get("organization_urn", None)
        visibility = self.args.get("visibility", None)

        try:
            cleaned = validate_message(text)
            normalized_target = normalize_target(target) if target else None
            resolved_linkedin, resolved_profile, resolve_error = resolve_linkedin_config(
                config,
                target=normalized_target,
                profile=profile,
            )
            if resolve_error:
                return Response(
                    message=str({
                        "ok": False,
                        "action": action,
                        "needs_clarification": True,
                        "message": resolve_error,
                    }),
                    break_loop=False,
                )

            effective_target = normalized_target or resolved_linkedin.get("default_target", "personal")
            resolved_config = {
                "linkedin": resolved_linkedin,
                "active_profile": resolved_profile,
                "profiles": config.get("profiles", {}),
            }

            if image_path and image_paths:
                raise ValueError("Provide either 'image_path' or 'image_paths', not both.")

            image_info = validate_image_path(image_path, required=False)
            images_info = validate_image_paths(image_paths, required=False)
            has_image = bool(image_info.get("present"))
            has_images = bool(images_info.get("present"))
            normalized_org_urn = normalize_organization_urn(organization_urn) if organization_urn else ""

            if action == "preview":
                preview = compact_post_preview(cleaned, visibility or resolved_linkedin.get("default_visibility", "PUBLIC"))
                preview.update({
                    "target": effective_target,
                    "resolved_profile": resolved_profile,
                    "organization_urn": normalized_org_urn,
                    "post_type": "images" if has_images else ("image" if has_image else "text"),
                    "image_path": image_info.get("path", ""),
                    "image_name": image_info.get("name", ""),
                    "image_extension": image_info.get("extension", ""),
                    "image_size_bytes": image_info.get("size_bytes", 0),
                    "image_paths": [item.get("path", "") for item in images_info.get("items", [])],
                    "image_names": [item.get("name", "") for item in images_info.get("items", [])],
                    "image_extensions": [item.get("extension", "") for item in images_info.get("items", [])],
                    "image_count": images_info.get("count", 0),
                    "needs_conversion": images_info.get("needs_conversion", False) or image_info.get("needs_conversion", False),
                    "alt_text": alt_text,
                })
                return Response(
                    message=str({"ok": True, "action": action, "resolved_profile": resolved_profile, "preview": preview}),
                    break_loop=False,
                )

            if action == "create":
                client = LinkedInClient(resolved_config)
                result = client.create_post(
                    text=cleaned,
                    target=effective_target,
                    organization_urn=organization_urn,
                    visibility=visibility,
                    image_path=image_info.get("path", "") if has_image else None,
                    image_paths=[item.get("path", "") for item in images_info.get("items", [])] if has_images else None,
                    alt_text=alt_text if (has_image or has_images) else None,
                )
                result["action"] = action
                result["resolved_profile"] = resolved_profile
                result["target"] = effective_target
                result["post_type"] = "images" if has_images else ("image" if has_image else "text")
                if has_image:
                    result["image_path"] = image_info.get("path", "")
                    result["image_name"] = image_info.get("name", "")
                    result["image_extension"] = image_info.get("extension", "")
                    result["image_size_bytes"] = image_info.get("size_bytes", 0)
                if has_images:
                    result["image_count"] = images_info.get("count", 0)
                    result["image_paths"] = [item.get("path", "") for item in images_info.get("items", [])]
                    result["image_names"] = [item.get("name", "") for item in images_info.get("items", [])]
                    result["image_extensions"] = [item.get("extension", "") for item in images_info.get("items", [])]
                if has_image or has_images:
                    result["alt_text"] = alt_text
                return Response(message=str(result), break_loop=False)

            return Response(
                message=f"Error: Unsupported action '{action}'. Use: preview, create.",
                break_loop=False,
            )

        except (LinkedInAuthError, ValueError) as e:
            return Response(
                message=str({"ok": False, "action": action, "message": str(e)}),
                break_loop=False,
            )
        except Exception as e:
            return Response(
                message=f"Error: {e}",
                break_loop=False,
            )
