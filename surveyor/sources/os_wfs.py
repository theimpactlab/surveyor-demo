"""OS Features API WFS fallback client.

The original Surveyor demo targets OS NGD API - Features. Some OS Data Hub
accounts expose only the older WFS OS Features API, so this module provides a
bounded compatibility path for the Greater Manchester demo.
"""

from __future__ import annotations

from typing import Any

import httpx

_BASE = "https://api.os.uk/features/v1/wfs"
_TIMEOUT = httpx.Timeout(30.0, connect=5.0)
_PAGE_LIMIT = 100


class OSWFSError(RuntimeError):
    pass


def fetch_zoomstack_sites(
    *,
    api_key: str,
    bbox: tuple[float, float, float, float],
    site_type: str,
    max_features: int = 2000,
) -> dict[str, Any]:
    """Fetch Zoomstack sites in ``bbox`` and filter locally by the coarse ``Type`` field.

    WFS 2.0's EPSG:4326 bbox axis order is lat/lon. The manifest stores CRS84
    bbox values as lon/lat, so the order is flipped here.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    wfs_bbox = f"{min_lat},{min_lon},{max_lat},{max_lon},EPSG:4326"
    collected: list[dict[str, Any]] = []
    start = 0

    with httpx.Client(timeout=_TIMEOUT) as client:
        while True:
            params = {
                "key": api_key,
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": "osfeatures:Zoomstack_Sites",
                "count": str(_PAGE_LIMIT),
                "startIndex": str(start),
                "outputFormat": "GEOJSON",
                "bbox": wfs_bbox,
            }
            data = _get_json(client, params)
            page = data.get("features", [])
            for feature in page:
                if feature.get("properties", {}).get("Type") == site_type:
                    collected.append(feature)
                    if len(collected) > max_features:
                        raise OSWFSError(
                            f"WFS feature fetch exceeded the cap of {max_features}; narrow the bbox"
                        )
            if len(page) < _PAGE_LIMIT:
                break
            start += _PAGE_LIMIT

    return {"type": "FeatureCollection", "features": collected}


def _get_json(client: httpx.Client, params: dict[str, str]) -> dict[str, Any]:
    try:
        resp = client.get(_BASE, params=params, headers={"Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise OSWFSError(
            f"OS WFS {exc.response.status_code}: {exc.response.text[:200]}"
        ) from exc
    except (ValueError, httpx.TransportError) as exc:
        raise OSWFSError(f"OS WFS request failed: {exc}") from exc
