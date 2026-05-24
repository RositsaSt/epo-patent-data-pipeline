from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, TypeAlias, Iterator, Tuple
import zipfile

import requests

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIG
# =============================================================================

BASE_URL = "https://publication-bdds.apps.epo.org/bdds/bdds-bff-service/prod/api"
PRODUCT_ID = 32

DEFAULT_HEADERS: Mapping[str, str] = {
    "Accept": "application/json",
    "User-Agent": "bdfs-downloader/1.0",
}

CHUNK_SIZE = 1024 * 1024  # 1 MB


# =============================================================================
# TYPES
# =============================================================================

Validator: TypeAlias = Callable[[Path], None]


# =============================================================================
# URL + JSON HELPERS
# =============================================================================

def build_bdds_download_url(delivery_id: str, file_id: str,base_url: str = BASE_URL, product_id: int = PRODUCT_ID) -> str:
    """Build the EPO BDDS download URL for product 32 (EP full text)."""
    bdds_download_url = f"{base_url}/products/{product_id}/delivery/{delivery_id}/file/{file_id}/download"
    return bdds_download_url

def get_json(session: requests.Session, url: str, headers: Mapping[str, str] = DEFAULT_HEADERS) -> Any:
    """GET JSON with basic error handling."""
    response = session.get(url, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()


def get_first_available_metadata_field(
    metadata: Mapping[str, Any],
    possible_field_names: Iterable[str],
) -> Optional[Any]:
    """
    Return the value of the first key found in `possible_field_names`
    that exists in `metadata` and is not None.

    This is added because the key of the dict is sometimes called 'id',
    'fileId', 'deliveryId', etc. depending on what you are downloading
    """
    for key in possible_field_names:
        value = metadata.get(key)
        if value is not None:
            return value
    return None


# =============================================================================
# METADATA ITERATION
# =============================================================================

def iter_archive_refs(product_metadata: Mapping[str, Any]) -> Iterator[Tuple[str, str, str, Optional[int]]]:
    """
    Yield (delivery_id, file_id, filename, expected_size_bytes) from BDDS product metadata JSON.
    """
    deliveries = product_metadata.get("deliveries", [])
    if not isinstance(deliveries, list):
        return

    for delivery in deliveries:
        if not isinstance(delivery, Mapping):
            continue

        delivery_id = get_first_available_metadata_field(
            delivery, ("id", "deliveryId", "delivery_id", "uuid")
        )
        if delivery_id is None:
            continue

        files = delivery.get("files", [])
        if not isinstance(files, list) or not files:
            continue

        for file_obj in files:
            if not isinstance(file_obj, Mapping):
                continue

            file_id = get_first_available_metadata_field(
                file_obj, ("id", "fileId", "file_id", "uuid")
            )
            filename = get_first_available_metadata_field(
                file_obj, ("name", "fileName", "filename", "originalName")
            )
            size = get_first_available_metadata_field(
                file_obj, ("size", "fileSize", "expectedSize", "expected_size")
            )

            if file_id is None or filename is None:
                continue

            expected_size: Optional[int] = None
            if isinstance(size, int):
                expected_size = size
            elif isinstance(size, str) and size.isdigit():
                expected_size = int(size)

            yield (str(delivery_id), str(file_id), str(filename), expected_size)


# =============================================================================
# VALIDATORS
# =============================================================================

def validate_zip_crc(path: Path, *, cleanup_on_error: bool = True) -> None:
    """
    Validate that a file is a readable ZIP and that members pass CRC checks.

    Raises RuntimeError on failure.
    """
    try:
        if not zipfile.is_zipfile(path):
            raise RuntimeError("Invalid ZIP (missing central directory or not a ZIP)")

        with zipfile.ZipFile(path) as zf:
            bad_member = zf.testzip()
            if bad_member is not None:
                raise RuntimeError(f"ZIP CRC failure in member: {bad_member}")

    except Exception:
        if cleanup_on_error:
            path.unlink(missing_ok=True)
        raise


# =============================================================================
# DOWNLOADER
# =============================================================================

def download_stream(
    session: requests.Session,
    url: str,
    destination: Path,
    *,
    headers: Mapping[str, str] = DEFAULT_HEADERS,
    chunk_size: int = CHUNK_SIZE,
    expected_size: Optional[int] = None,
    validators: Iterable[Validator] = (),
    cleanup_on_error: bool = True,
    timeout: tuple[float, float] = (30.0, 300.0),  # (connect, read)
) -> int:
    """
    Stream-download `url` to `destination` via a temporary `.part` file.

    The remote size is inferred from the actual streamed GET response when
    Content-Length is available. After download, optional validators run and
    the `.part` file is atomically renamed to the final raw archive path.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    temp_path = destination.with_suffix(destination.suffix + ".part")
    temp_path.unlink(missing_ok=True)

    bytes_written = 0

    download_headers = {
        **dict(headers),
        "Accept": "application/octet-stream",
        "Accept-Encoding": "identity",
    }

    try:
        with session.get(
            url,
            headers=download_headers,
            stream=True,
            timeout=timeout,
        ) as response:
            response.raise_for_status()

            content_length = response.headers.get("Content-Length")

            logger.info(
                "GET download response: status=%s filename=%s content_length=%s "
                "cf_ray=%s upstream_time=%s",
                response.status_code,
                destination.name,
                content_length,
                response.headers.get("CF-RAY"),
                response.headers.get("x-envoy-upstream-service-time"),
            )

            if expected_size is None and content_length and content_length.isdigit():
                expected_size = int(content_length)
                logger.info(
                    "Temporary raw archive size: %d bytes (%.2f GiB)",
                    expected_size,
                    expected_size / (1024**3),
                )

            if expected_size is None:
                logger.warning(
                    "GET response did not provide Content-Length for %s; "
                    "continuing with ZIP validation only.",
                    destination.name,
                )

            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    f.write(chunk)
                    bytes_written += len(chunk)

                    if bytes_written % (1024 ** 3) < chunk_size:
                        logger.info(
                            "Downloaded %.2f GiB of %s",
                            bytes_written / (1024 ** 3),
                            destination.name,
                        )


        # Size verification (best-effort: only if expected size is known)
        if expected_size is not None and bytes_written != expected_size:
            raise RuntimeError(
                f"Incomplete download: wrote {bytes_written} bytes, expected {expected_size} bytes"
            )

        # Validation stage (Open/Closed: add validators without changing this function)
        for validate in validators:
            validate(temp_path)

        # Finalize (atomic)
        temp_path.replace(destination)

        logger.info(
            "Download completed successfully: %s (%d bytes)",
            destination,
            bytes_written,
        )

        return bytes_written

    except Exception:
        if cleanup_on_error:
            temp_path.unlink(missing_ok=True)
        raise
