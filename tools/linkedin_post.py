from helpers.tool import Tool, Response
import importlib


class LinkedInPost(Tool):
    """Create or preview LinkedIn posts for personal or organization targets."""

    async def execute(self, **kwargs) -> Response:
        action = self.args.get("action", "preview")
        text = self.args.get("text")
        if text in (None, ""):
            text = self.args.get("message", "")

        config_mod = importlib.import_module("usr.plugins.linkedin.helpers.config")
        config_mod = importlib.reload(config_mod)
        load_config = getattr(config_mod, "load_config")
        resolve_linkedin_config = getattr(config_mod, "resolve_linkedin_config")

        from usr.plugins.linkedin.helpers.linkedin_auth import LinkedInAuthError
        from usr.plugins.linkedin.helpers.linkedin_client import LinkedInClient
        from usr.plugins.linkedin.helpers.linkedin_format import compact_post_preview
        from usr.plugins.linkedin.helpers.sanitize import normalize_organization_urn, normalize_target, validate_message

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

            if action == "preview":
                preview = compact_post_preview(cleaned, visibility or resolved_linkedin.get("default_visibility", "PUBLIC"))
                preview.update({
                    "target": effective_target,
                    "resolved_profile": resolved_profile,
                    "organization_urn": normalize_organization_urn(organization_urn) if organization_urn else "",
                })
                return Response(
                    message=str({"ok": True, "action": action, "resolved_profile": resolved_profile, "preview": preview}),
                    break_loop=False,
                )

            elif action == "create":
                client = LinkedInClient(resolved_config)
                result = client.create_post(
                    text=cleaned,
                    target=effective_target,
                    organization_urn=organization_urn,
                    visibility=visibility,
                )
                result["action"] = action
                result["resolved_profile"] = resolved_profile
                result["target"] = effective_target
                return Response(message=str(result), break_loop=False)

            else:
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
