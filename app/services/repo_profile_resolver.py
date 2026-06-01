from __future__ import annotations

from typing import Optional


def infer_repo_profile_id(
    *,
    explicit: Optional[str],
    path_prefix: str,
    default_profile_id: Optional[str],
    list_profiles_fn,
) -> Optional[str]:
    if explicit and explicit.strip():
        return explicit.strip()
    normalized = path_prefix.strip().replace("\\", "/")
    if normalized:
        for profile in list_profiles_fn():
            prefix = profile.path_prefix.strip().replace("\\", "/")
            if prefix and normalized.startswith(prefix):
                return profile.profile_id
    if default_profile_id and default_profile_id.strip():
        return default_profile_id.strip()
    return None
