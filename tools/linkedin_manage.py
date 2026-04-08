from helpers.tool import Tool, Response


class LinkedInManage(Tool):
    """Manage LinkedIn posts."""

    async def execute(self, **kwargs) -> Response:
        action = self.args.get("action", "")
        post_urn = self.args.get("post_urn", "")
        text = self.args.get("text", None)

        from usr.plugins.linkedin.helpers.config import load_config
        from usr.plugins.linkedin.helpers.linkedin_client import LinkedInClient

        try:
            if not post_urn:
                return Response(
                    message=str({
                        "ok": False,
                        "action": action,
                        "message": "post_urn is required.",
                    }),
                    break_loop=False,
                )

            result = LinkedInClient(load_config()).manage_post(
                action=action,
                post_urn=post_urn,
                text=text,
            )
            result["action"] = action
            return Response(message=str(result), break_loop=False)

        except Exception as e:
            return Response(
                message=f"Error: {e}",
                break_loop=False,
            )
