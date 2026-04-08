from helpers.tool import Tool, Response


class LinkedInRead(Tool):
    """Read recent LinkedIn posts or a specific post for personal or organization targets."""

    async def execute(self, **kwargs) -> Response:
        action = self.args.get("action", "recent_posts")

        from usr.plugins.linkedin.helpers.config import load_config, resolve_linkedin_config
        from usr.plugins.linkedin.helpers.linkedin_auth import LinkedInAuthError
        from usr.plugins.linkedin.helpers.linkedin_client import LinkedInClient
        from usr.plugins.linkedin.helpers.sanitize import normalize_target

        config = load_config()
        raw_target = self.args.get("target")
        profile = self.args.get("profile")
        organization_urn = self.args.get("organization_urn", None)
        post_urn = self.args.get("post_urn", None)
        limit = int(self.args.get("limit", self.args.get("max_results", 10)))

        try:
            normalized_target = normalize_target(raw_target) if raw_target else None
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
            client = LinkedInClient(resolved_config)

            if action in {"recent_posts", "feed"}:
                result = client.list_recent_posts(
                    target=effective_target,
                    organization_urn=organization_urn,
                    limit=limit,
                )
                result["action"] = action
                result["resolved_profile"] = resolved_profile
                result["target"] = effective_target
                return Response(message=str(result), break_loop=False)

            elif action == "post":
                if not post_urn:
                    return Response(
                        message=str({
                            "ok": False,
                            "action": action,
                            "message": "post_urn is required for action='post'.",
                        }),
                        break_loop=False,
                    )
                result = client.get_post(post_urn=post_urn)
                result["action"] = action
                result["resolved_profile"] = resolved_profile
                result["target"] = effective_target
                return Response(message=str(result), break_loop=False)

            else:
                return Response(
                    message=f"Error: Unsupported action '{action}'. Use: recent_posts, feed, post.",
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
