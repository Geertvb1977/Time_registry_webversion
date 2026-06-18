Customer API — Accessing Project Status
=====================================

What the customer receives
- The customer gets an email with a one-click link that already contains the API token and project id. Opening the link returns JSON with the project status.

One-click link format
- Example:

```
https://your.example.com/api/project_status?token=<TOKEN>&project_id=<PROJECT_ID>
```

Quick curl examples
- Using the token as a query parameter:

```bash
curl "https://your.example.com/api/project_status?token=THE_TOKEN&project_id=123"
```

- Using the `Authorization` header (preferred for scripts):

```bash
curl -H "Authorization: Token THE_TOKEN" "https://your.example.com/api/project_status?project_id=123"
```

Behavior notes
- Tokens are represented by the `APIToken` model; see `time_reg_web/models.py`.
- The endpoint validates that the token is active, not expired (if `expires_at` is set), and belongs to the requested project.
- If a token is single-use, the server deactivates it after the first successful request.

Where `single_use` and `expires_at` are specified
- The token generation endpoints accept an optional `single_use` parameter (true/false). The web UI endpoint is `generate_project_api_token` and the programmatic endpoint is `generate_project_api_token_api`.
- Currently, `expires_at` is a field on the model but is not accepted as an argument by the token-generation endpoints — you can set `expires_at` manually via the Django admin or by updating the database. If you want `expires_at` to be set at creation via the API, the server-side view will need to be extended.

Helpful tip for customers
- If you receive an unexpected email, ignore it — the email templates already instruct recipients to do so.

Client example script
- See `scripts/fetch_project_status.py` for a ready-to-run example.
