"""Verify `storage/sigv4.py` against AWS's published SigV4 test vector.

Two layers are checked:

1. **The shared cryptographic core** (`derive_signing_key`, canonical-request
   hashing, string-to-sign) against AWS's literal `get-vanilla` fixture —
   access key `AKIDEXAMPLE`, secret
   `wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY`, region `us-east-1`, service
   `service`, date `20150830T123600Z`, host `example.amazonaws.com`,
   signed headers `host;x-amz-date` only. Expected values are taken
   verbatim from AWS's published SigV4 test suite (the canonical
   `get-vanilla` fixture referenced by
   https://docs.aws.amazon.com/IAM/latest/UserGuide/create-signed-request.html):
   canonical request hash
   `bb579772317eb040ac9ed261061d46c1f17a8133879d6129b6e1c25292927e63`,
   string-to-sign, and final signature
   `5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31`.
2. **`sign_request` itself**, which always adds `x-amz-content-sha256` to the
   signed headers (required by S3/R2, not part of the generic IAM example
   above) — verified by an independent hand-computation using the same
   AWS-published algorithm (recorded inline below) rather than against the
   `host;x-amz-date`-only vector, since that vector cannot apply once a
   third signed header is added.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

from storage.sigv4 import derive_signing_key, encode_uri_path, sign_request

ACCESS_KEY_ID = "AKIDEXAMPLE"
SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"  # noqa: S105 - AWS-published test fixture, not a real secret
REGION = "us-east-1"
SERVICE = "service"
HOST = "example.amazonaws.com"
DATE_STAMP = "20150830"
AMZ_DATE = "20150830T123600Z"
EMPTY_PAYLOAD_HASH = hashlib.sha256(b"").hexdigest()

# AWS-documented `get-vanilla` fixture (host;x-amz-date signed headers only).
DOCUMENTED_CANONICAL_REQUEST = (
    f"GET\n/\n\nhost:{HOST}\nx-amz-date:{AMZ_DATE}\n\nhost;x-amz-date\n{EMPTY_PAYLOAD_HASH}"
)
DOCUMENTED_CANONICAL_REQUEST_HASH = "bb579772317eb040ac9ed261061d46c1f17a8133879d6129b6e1c25292927e63"
DOCUMENTED_STRING_TO_SIGN = (
    f"AWS4-HMAC-SHA256\n{AMZ_DATE}\n{DATE_STAMP}/{REGION}/{SERVICE}/aws4_request\n"
    f"{DOCUMENTED_CANONICAL_REQUEST_HASH}"
)
DOCUMENTED_SIGNATURE = "5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31"

# Independent hand-computation of `sign_request`'s 3-header (S3/R2) variant,
# using the identical AWS-published algorithm with x-amz-content-sha256
# added to the canonical headers/signed-headers list, computed separately
# from `storage/sigv4.py` to avoid testing the implementation against itself.
R2_STYLE_CANONICAL_REQUEST = (
    f"GET\n/\n\nhost:{HOST}\nx-amz-content-sha256:{EMPTY_PAYLOAD_HASH}\nx-amz-date:{AMZ_DATE}\n\n"
    f"host;x-amz-content-sha256;x-amz-date\n{EMPTY_PAYLOAD_HASH}"
)
R2_STYLE_SIGNATURE = "726c5c4879a6b4ccbbd3b24edbd6b8826d34f87450fbbf4e85546fc7ba9c1642"


def test_should_match_documented_canonical_request_hash_when_hashing_get_vanilla():
    assert hashlib.sha256(DOCUMENTED_CANONICAL_REQUEST.encode()).hexdigest() == DOCUMENTED_CANONICAL_REQUEST_HASH


def test_should_derive_documented_signature_when_signing_vanilla_string_to_sign():
    signing_key = derive_signing_key(SECRET_ACCESS_KEY, DATE_STAMP, REGION, SERVICE)
    signature = hmac.new(signing_key, DOCUMENTED_STRING_TO_SIGN.encode(), hashlib.sha256).hexdigest()
    assert signature == DOCUMENTED_SIGNATURE


def test_should_produce_documented_amz_date_when_signing_get_request():
    result = sign_request(
        method="GET",
        host=HOST,
        canonical_uri="/",
        payload=b"",
        access_key_id=ACCESS_KEY_ID,
        secret_access_key=SECRET_ACCESS_KEY,
        region=REGION,
        service=SERVICE,
        now=datetime(2015, 8, 30, 12, 36, 0, tzinfo=timezone.utc),
    )
    assert result.headers["x-amz-date"] == AMZ_DATE


def test_should_produce_empty_payload_hash_when_body_is_empty():
    result = sign_request(
        method="GET",
        host=HOST,
        canonical_uri="/",
        payload=b"",
        access_key_id=ACCESS_KEY_ID,
        secret_access_key=SECRET_ACCESS_KEY,
        region=REGION,
        service=SERVICE,
        now=datetime(2015, 8, 30, 12, 36, 0, tzinfo=timezone.utc),
    )
    assert result.headers["x-amz-content-sha256"] == EMPTY_PAYLOAD_HASH


def test_should_sign_three_headers_matching_hand_computed_signature():
    """`sign_request` signs host;x-amz-content-sha256;x-amz-date (S3/R2 requirement);
    verify against the independently hand-computed R2-style signature above."""
    result = sign_request(
        method="GET",
        host=HOST,
        canonical_uri="/",
        payload=b"",
        access_key_id=ACCESS_KEY_ID,
        secret_access_key=SECRET_ACCESS_KEY,
        region=REGION,
        service=SERVICE,
        now=datetime(2015, 8, 30, 12, 36, 0, tzinfo=timezone.utc),
    )
    expected_authorization = (
        f"AWS4-HMAC-SHA256 Credential={ACCESS_KEY_ID}/{DATE_STAMP}/{REGION}/{SERVICE}/aws4_request, "
        f"SignedHeaders=host;x-amz-content-sha256;x-amz-date, Signature={R2_STYLE_SIGNATURE}"
    )
    assert result.headers["Authorization"] == expected_authorization


def test_should_hash_r2_style_canonical_request_to_known_value():
    """Sanity check that our hand-computed R2-style canonical request/signature
    pair is internally consistent (independent of `sign_request`)."""
    signing_key = derive_signing_key(SECRET_ACCESS_KEY, DATE_STAMP, REGION, SERVICE)
    creq_hash = hashlib.sha256(R2_STYLE_CANONICAL_REQUEST.encode()).hexdigest()
    string_to_sign = f"AWS4-HMAC-SHA256\n{AMZ_DATE}\n{DATE_STAMP}/{REGION}/{SERVICE}/aws4_request\n{creq_hash}"
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    assert signature == R2_STYLE_SIGNATURE


def test_should_leave_forward_slash_unescaped_when_encoding_root_path():
    assert encode_uri_path("/") == "/"


def test_should_encode_each_segment_when_encoding_multi_segment_path():
    assert encode_uri_path("/my bucket/resourceos.db") == "/my%20bucket/resourceos.db"


def test_should_change_signature_when_payload_differs():
    empty = sign_request(
        method="PUT",
        host=HOST,
        canonical_uri="/bucket/key",
        payload=b"",
        access_key_id=ACCESS_KEY_ID,
        secret_access_key=SECRET_ACCESS_KEY,
        region=REGION,
        service=SERVICE,
        now=datetime(2015, 8, 30, 12, 36, 0, tzinfo=timezone.utc),
    )
    non_empty = sign_request(
        method="PUT",
        host=HOST,
        canonical_uri="/bucket/key",
        payload=b"some-bytes",
        access_key_id=ACCESS_KEY_ID,
        secret_access_key=SECRET_ACCESS_KEY,
        region=REGION,
        service=SERVICE,
        now=datetime(2015, 8, 30, 12, 36, 0, tzinfo=timezone.utc),
    )
    assert empty.headers["Authorization"] != non_empty.headers["Authorization"]
    assert empty.headers["x-amz-content-sha256"] != non_empty.headers["x-amz-content-sha256"]
