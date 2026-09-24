import hashlib


def compute_artifact_checksum(content: bytes) -> str:
    """Return the checksum recorded on an artifact for the given content."""
    return hashlib.md5(content, usedforsecurity=False).hexdigest()


def compute_file_object_checksum(content: bytes) -> str:
    """Return the checksum recorded on a file object for the given content."""
    return hashlib.sha1(content, usedforsecurity=False).hexdigest()
