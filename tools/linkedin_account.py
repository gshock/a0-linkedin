from helpers.tool import Tool, Response


class LinkedInAccount(Tool):
    """Inspect LinkedIn plugin auth/config readiness for personal and organization posting."""

    async def execute(self, **kwargs) -> Response:
        action = self.args.get("action", "status")

        from usr.plugins.linkedin.helpers.config import load_config, mask_config, resolve_linkedin_config
        from usr.plugins.linkedin.helpers.linkedin_auth import LinkedInAuthError, LinkedInAuthHelper
        from usr.plugins.linkedin.helpers.linkedin_client import LinkedInClient

        def build_mode_summary(config: dict, target: str) -> dict:
            resolved_linkedin, resolved_profile, resolve_error = resolve_linkedin_config(config, target=target)
            if resolve_error or not resolved_linkedin:
                return {
                    "profile": None,
                    "target": target,
                    "ready_to_post": False,
                    "ready_to_read": False,
                    "message": resolve_error or f"Could not resolve {target} profile.",
                }
            scoped_config = {
                "linkedin": resolved_linkedin,
                "active_profile": resolved_profile,
                "profiles": config.get("profiles", {}),
            }
            auth = LinkedInAuthHelper(scoped_config)
            auth_state = auth.get_auth_state()
            scopes = auth_state.get("scopes", [])
            token_present = bool(auth_state.get("access_token_configured"))
            person_urn_present = bool(auth_state.get("person_urn"))
            organization_urn_present = bool(auth_state.get("organization_urn") or auth_state.get("organization_urns"))
            required_post_scope_present = ("w_member_social" in scopes) if target == "personal" else ("w_organization_social" in scopes)
            required_read_scope_present = ("r_member_social" in scopes) if target == "personal" else ("r_organization_social" in scopes)
            ready_to_post = token_present and required_post_scope_present and (person_urn_present if target == "personal" else organization_urn_present)
            ready_to_read = token_present and required_read_scope_present and (person_urn_present if target == "personal" else organization_urn_present)
            advisory = ""
            if target == "personal" and ready_to_post and not required_read_scope_present:
                advisory = "Personal posting is ready. Personal read is unavailable without r_member_social."
            elif target == "organization" and not token_present:
                advisory = "Organization profile needs a valid access token before posting or reading can be used."
            missing = []
            if not token_present:
                missing.append("access_token")
            if target == "personal" and not person_urn_present:
                missing.append("person_urn")
            if target == "organization" and not organization_urn_present:
                missing.append("organization_urn")
            if not required_post_scope_present:
                missing.append("w_member_social" if target == "personal" else "w_organization_social")
            return {
                "profile": resolved_profile,
                "target": target,
                "token_present": token_present,
                "person_urn_present": person_urn_present,
                "organization_urn_present": organization_urn_present,
                "required_post_scope_present": required_post_scope_present,
                "required_read_scope_present": required_read_scope_present,
                "ready_to_post": ready_to_post,
                "ready_to_read": ready_to_read,
                "dry_run": bool(resolved_linkedin.get("dry_run", True)),
                "scopes": scopes,
                "missing_requirements": missing,
                "advisory": advisory,
                "auth": auth_state,
            }

        config = load_config()
        current_auth = LinkedInAuthHelper(config).get_auth_state()
        personal = build_mode_summary(config, "personal")
        organization = build_mode_summary(config, "organization")

        try:
            if action in {"status", "auth_status", "auth_summary", "info"}:
                return Response(
                    message=str({
                        "ok": True,
                        "action": action,
                        "auth": current_auth,
                        "active_profile": config.get("active_profile"),
                        "profiles": {
                            "personal": personal,
                            "organization": organization,
                        },
                        "routing": {
                            "personal_target_profile": personal.get("profile"),
                            "organization_target_profile": organization.get("profile"),
                        },
                        "config": mask_config(config),
                    }),
                    break_loop=False,
                )

            elif action == "organizations":
                client = LinkedInClient(config)
                result = client.discover_organizations()
                result["action"] = action
                return Response(message=str(result), break_loop=False)

            else:
                return Response(
                    message=f"Error: Unsupported action '{action}'. Use: status, auth_status, auth_summary, organizations, info.",
                    break_loop=False,
                )

        except LinkedInAuthError as e:
            return Response(
                message=str({
                    "ok": False,
                    "action": action,
                    "message": str(e),
                }),
                break_loop=False,
            )
        except Exception as e:
            return Response(
                message=f"Error: {e}",
                break_loop=False,
            )
