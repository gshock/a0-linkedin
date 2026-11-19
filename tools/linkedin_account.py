from helpers.tool import Tool, Response


class LinkedInAccount(Tool):
    """Inspect LinkedIn plugin auth/config readiness across all configured accounts."""

    async def execute(self, **kwargs) -> Response:
        action = self.args.get("action", "status")

        from usr.plugins.linkedin.helpers.config import (
            get_profile_config,
            list_accounts,
            load_config,
            mask_config,
            profile_capabilities,
            resolve_target_selection,
        )
        from usr.plugins.linkedin.helpers.linkedin_auth import LinkedInAuthError, LinkedInAuthHelper
        from usr.plugins.linkedin.helpers.linkedin_client import LinkedInClient

        config = load_config(agent=self.agent)

        def build_mode_summary(target: str) -> dict:
            """Resolve which account would serve a target and report its readiness."""
            selection = resolve_target_selection(config, target=target)
            profile_name = selection.get("profile")
            if not profile_name:
                return {
                    "profile": None,
                    "target": target,
                    "ready_to_post": False,
                    "ready_to_read": False,
                    "needs_clarification": bool(selection.get("needs_clarification")),
                    "candidates": selection.get("candidates", []),
                    "message": selection.get("error"),
                }
            capabilities = profile_capabilities(config, profile_name)
            resolved_linkedin = get_profile_config(config, profile_name)
            scoped_config = {
                "linkedin": resolved_linkedin,
                "active_profile": profile_name,
                "profiles": config.get("profiles", {}),
            }
            auth_state = LinkedInAuthHelper(scoped_config).get_auth_state()
            ready_to_post = bool(capabilities.get("can_post"))
            ready_to_read = bool(capabilities.get("can_read"))
            advisory = ""
            if target == "personal" and ready_to_post and not ready_to_read:
                advisory = "Personal posting is ready. Personal read is unavailable without r_member_social."
            elif target == "organization" and not capabilities.get("token_present"):
                advisory = "This organization account needs a valid access token before posting or reading can be used."
            elif target == "organization" and not capabilities.get("organization_urns"):
                advisory = "Add at least one organization URN before posting as this organization."
            return {
                "profile": profile_name,
                "label": capabilities.get("label"),
                "target": target,
                "token_present": capabilities.get("token_present"),
                "person_urn_present": capabilities.get("person_urn_present"),
                "organization_urns": capabilities.get("organization_urns", []),
                "organization_page_count": capabilities.get("organization_page_count", 0),
                "scopes": capabilities.get("scopes", []),
                "ready_to_post": ready_to_post,
                "ready_to_read": ready_to_read,
                "dry_run": capabilities.get("dry_run"),
                "advisory": advisory,
                "auth": auth_state,
            }

        try:
            if action == "accounts":
                accounts = list_accounts(config)
                return Response(
                    message=str({
                        "ok": True,
                        "action": action,
                        "count": len(accounts),
                        "active_profile": config.get("active_profile"),
                        "accounts": accounts,
                    }),
                    break_loop=False,
                )

            if action in {"status", "auth_status", "auth_summary", "info"}:
                current_profile = str(config.get("active_profile") or "default")
                active_linkedin = get_profile_config(config, current_profile) if current_profile else {}
                current_auth = LinkedInAuthHelper({
                    "linkedin": active_linkedin,
                    "active_profile": current_profile,
                    "profiles": config.get("profiles", {}),
                }).get_auth_state()
                personal = build_mode_summary("personal")
                organization = build_mode_summary("organization")
                return Response(
                    message=str({
                        "ok": True,
                        "action": action,
                        "auth": current_auth,
                        "active_profile": config.get("active_profile"),
                        "accounts": list_accounts(config),
                        "routing": {
                            "personal": personal,
                            "organization": organization,
                        },
                        "config": mask_config(config),
                    }),
                    break_loop=False,
                )

            if action == "organizations":
                profile = self.args.get("profile")
                selection = resolve_target_selection(config, target="organization", profile=profile)
                if not selection.get("profile"):
                    return Response(
                        message=str({
                            "ok": False,
                            "action": action,
                            "needs_clarification": bool(selection.get("needs_clarification")),
                            "candidates": selection.get("candidates", []),
                            "message": selection.get("error"),
                        }),
                        break_loop=False,
                    )
                resolved_profile = selection["profile"]
                client = LinkedInClient({
                    "linkedin": selection["linkedin"],
                    "active_profile": resolved_profile,
                    "profiles": config.get("profiles", {}),
                })
                result = client.discover_organizations()
                result["action"] = action
                result["resolved_profile"] = resolved_profile
                return Response(message=str(result), break_loop=False)

            return Response(
                message=f"Error: Unsupported action '{action}'. Use: accounts, status, auth_status, auth_summary, organizations, info.",
                break_loop=False,
            )

        except LinkedInAuthError as e:
            return Response(
                message=str({"ok": False, "action": action, "message": str(e)}),
                break_loop=False,
            )
        except Exception as e:
            return Response(
                message=f"Error: {e}",
                break_loop=False,
            )
