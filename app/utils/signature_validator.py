import hashlib
import hmac


def validate_github_signature(
    body: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    if not signature_header:
        raise ValueError("Missing X-Hub-Signature-256 header")
    if not signature_header.startswith("sha256="):
        raise ValueError("Invalid signature format: expected 'sha256=' prefix")

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)
