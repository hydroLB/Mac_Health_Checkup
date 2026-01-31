from __future__ import annotations

import hashlib
import ssl
from pathlib import Path

from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/backend/tls.py"


def normalize_cert_sha256_fingerprint(value: str) -> str:
    """
    Summary
    Normalize a SHA-256 certificate fingerprint into lowercase hex.

    Inputs
    value: Fingerprint value that may include colons or spaces.

    Outputs
    Normalized 64-character lowercase hex fingerprint.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when the value is invalid.

    Ties to other methods
    Used by TLS configuration helpers and by pairing output formatting.

    Why this exists
    Users often paste fingerprints formatted with colons; normalization avoids fragile comparisons.
    """
    try:
        raw = (value or "").strip().lower().replace(":", "").replace(" ", "")
        if len(raw) != 64:
            raise ValueError("fingerprint must be 64 hex characters for sha256")
        allowed = set("0123456789abcdef")
        if any(ch not in allowed for ch in raw):
            raise ValueError("fingerprint must be hex")
        return raw
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "normalize_cert_sha256_fingerprint", "Invalid fingerprint", exc)
        ) from exc


def certificate_sha256_fingerprint_from_pem(cert_path: Path) -> str:
    """
    Summary
    Compute the SHA-256 fingerprint for a PEM certificate file.

    Inputs
    cert_path: Path to a PEM certificate file.

    Outputs
    Normalized SHA-256 fingerprint as lowercase hex.

    Side effects
    Reads a certificate file from disk.

    Error handling
    Raises `RuntimeError` with module and method context when reading or parsing fails.

    Ties to other methods
    Used by `SnapshotApiServer.start` to print pairing information and by docs for certificate pinning.

    Why this exists
    Certificate pinning on iOS needs a stable, copyable fingerprint for the leaf certificate.
    """
    try:
        pem_text = cert_path.read_text(encoding="utf-8")
        der = ssl.PEM_cert_to_DER_cert(pem_text)
        digest = hashlib.sha256(der).hexdigest()
        return normalize_cert_sha256_fingerprint(digest)
    except (OSError, ssl.SSLError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "certificate_sha256_fingerprint_from_pem",
                "Failed to compute certificate fingerprint",
                exc,
            )
        ) from exc


def build_tls_server_context(cert_path: Path, key_path: Path) -> ssl.SSLContext:
    """
    Summary
    Build a TLS server SSLContext for the agent API.

    Inputs
    cert_path: PEM certificate path.
    key_path: PEM private key path.

    Outputs
    Configured `ssl.SSLContext` for server-side sockets.

    Side effects
    Reads certificate and key files from disk.

    Error handling
    Raises `RuntimeError` with module and method context when context creation fails.

    Ties to other methods
    Used by the API server to wrap its listening socket when TLS is enabled.

    Why this exists
    Keeps TLS configuration explicit and centralized, reducing the chance of insecure defaults.
    """
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
        return context
    except (OSError, ssl.SSLError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "build_tls_server_context", "Failed to build TLS context", exc)
        ) from exc
