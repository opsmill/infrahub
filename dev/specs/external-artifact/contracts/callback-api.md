# Contract: Render result callback

The external engine calls this endpoint once per render request to submit the rendered content or report a failure.

## Request

```text
POST /api/artifact/render/{render_id}
X-Infrahub-Render-Token: <render token>
Content-Type: application/json
```

Success body:

```json
{
  "status": "success",
  "content": "hostname edge-01\n...",
  "content_type": "text/plain"
}
```

Failure body:

```json
{
  "status": "failure",
  "message": "template variable mtu undefined"
}
```

| Field | Required | Rules |
|-------|----------|-------|
| `status` | yes | `success` or `failure`. |
| `content` | when `status = success` | UTF-8 text. JSON content types accept a JSON value, which is serialized as internal artifacts are today. Size at most `StorageSettings.max_file_size`. |
| `content_type` | no | When present, it must equal the artifact definition's `content_type`. |
| `message` | when `status = failure` | At most 4096 characters, stored on the artifact check. |

## Authentication

- Only the render token is accepted. Account sessions, JWT access tokens and `X-INFRAHUB-KEY` API keys are refused on this endpoint.
- The token is a JWT signed with `SecuritySettings.secret_key`. Its claims are `type = "render"`, `render_id`, `artifact_id`, `branch` and `exp`.
- `render_id` in the path must equal the token's `render_id`, and must equal the artifact's current `render_request_id`.

## Responses

| Status | When |
|--------|------|
| `204 No Content` | Result accepted. The artifact is `Ready` (success) or `Error` (failure). |
| `400 Bad Request` | Body invalid: missing `content` or `message`, or a mismatched `content_type`. |
| `401 Unauthorized` | Token missing, badly signed, wrong `type` or expired. |
| `403 Forbidden` | Token valid, but its `render_id` does not match the path. |
| `409 Conflict` | The render request was replaced by a newer one, or already ended (timeout, or an earlier callback). The artifact is unchanged. |
| `413 Payload Too Large` | `content` larger than `StorageSettings.max_file_size`. |
| `429 Too Many Requests` | Shed by admission control. The engine retries after `Retry-After`. |

Error bodies follow the existing REST error format and do not expose internal details (constitution VI).

## Effects of an accepted result

1. **Success**:
   - Content is stored in the object store with the same checksum logic as internal renders. An unchanged checksum skips the upload.
   - The artifact gets `status = Ready`, `checksum`, `storage_id` and `content_type`, and `render_deadline` is cleared.
   - `ArtifactCreatedEvent` or `ArtifactUpdatedEvent` is emitted when the content changed.
2. **Failure**: the artifact gets `status = Error`, and `render_deadline` is cleared.
3. **Proposed change**: if the request came from a proposed change, the artifact check is updated and the validator is recomputed.
