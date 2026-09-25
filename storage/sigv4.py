"""AWS Signature Version 4 request signing, implemented from scratch.

No `boto3`/`botocore` — the API runs on a 512 MB Render instance and only
needs to sign simple GET/PUT requests to one R2 bucket. Verified against
the AWS-documented `get-vanilla` SigV4 test vector (access key
`AKIDEXAMPLE`, region `us-east-1`, service `service`) in
`storage/tests/test_sigv4.py`.

Reference: https://docs.aws.amazon.com/IAM/latest/UserGuide/create-signed-request.html
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

_ALGORITHM = "AWS4-HMAC-SHA256"
_TERMINATOR = "aws4_request"
EMPTY_PAYLOAD_HASH = hashlib.sha256(b"").hexdigest()


@dataclass(frozen=True)
class SigningResult:
    """The headers a signed request must carry, plus the timestamp used."""

    headers: dict[str, str]
    amz_date: str


def sha256_hex(payload: bytes) -> str:
    """Lowercase hex SHA-256 digest of `payload` (the `x-amz-content-sha256` value)."""
    return hashlib.sha256(payload).hexdigest()


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def derive_signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    """Derive the SigV4 signing key: secret -> date -> region -> service -> request.

    Exposed (not underscore-prefixed) so tests can verify this shared
    cryptographic core against AWS's literally-published test vector,
    independent of the extra `x-amz-content-sha256` header `sign_request`
    always adds (required by S3/R2, not part of the generic IAM example).
    """
    k_date = _hmac(f"AWS4{secret_key}".encode(), date_stamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, service)
    return _hmac(k_service, _TERMINATOR)


def _canonical_request(
    method: str, canonical_uri: str, host: str, amz_date: str, payload_hash: str
) -> tuple[str, str]:
    """Build the canonical request and its `host;x-amz-content-sha256;x-amz-date`
    signed-headers list. Query string is always empty for our GET/PUT object calls."""
    canonical_headers = (
        f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join(
        [method, canonical_uri, "", canonical_headers, signed_headers, payload_hash]
    )
    return canonical_request, signed_headers


def _string_to_sign(amz_date: str, credential_scope: str, canonical_request: str) -> str:
    hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    return "\n".join([_ALGORITHM, amz_date, credential_scope, hashed_canonical_request])


def sign_request(
    *,
    method: str,
    host: str,
    canonical_uri: str,
    payload: bytes,
    access_key_id: str,
    secret_access_key: str,
    region: str,
    service: str,
    now: datetime | None = None,
) -> SigningResult:
    """Compute the `Authorization`, `x-amz-date` and `x-amz-content-sha256`
    headers for one request. `canonical_uri` must already be URI-encoded
    (each path segment, `/` preserved) per the SigV4 spec.
    """
    moment = now or datetime.now(tz=timezone.utc)
    amz_date = moment.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = moment.strftime("%Y%m%d")
    payload_hash = sha256_hex(payload)

    canonical_request, signed_headers = _canonical_request(
        method, canonical_uri, host, amz_date, payload_hash
    )
    credential_scope = f"{date_stamp}/{region}/{service}/{_TERMINATOR}"
    string_to_sign = _string_to_sign(amz_date, credential_scope, canonical_request)

    signing_key = derive_signing_key(secret_access_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"{_ALGORITHM} Credential={access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return SigningResult(
        headers={
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "Authorization": authorization,
        },
        amz_date=amz_date,
    )


def encode_uri_path(path: str) -> str:
    """URI-encode a path per SigV4 rules: encode every segment, keep `/` separators."""
    return "/".join(quote(segment, safe="-._~") for segment in path.split("/"))
