"""
Real-Time Topographical Shadow Mapping Module
=============================================
Uses pysolar for astronomical sun positioning and Open-Elevation API
for terrain data to compute shadow masks via ray-casting.

Pipeline:
  1. Calculate sun altitude & azimuth for every hour (pysolar)
  2. Fetch terrain elevations in a 5 km radius (Open-Elevation API)
  3. Compute horizon angles via trigonometry
  4. Ray-cast: if sun_altitude < horizon_angle → shelter is in shadow
  5. Apply shadow mask to solar irradiance (shadowed hours → 10% diffuse only)
"""

import math
import numpy as np
import requests
from datetime import datetime, timezone, timedelta
from pysolar.solar import get_altitude, get_azimuth


# ─── Phase 2.1: Sun Position Calculator ───────────────────────────────────────

def get_sun_positions(lat, lon, date, tz_offset_hours=5.5):
    """
    Calculate the sun's altitude and azimuth for every hour of a given day.

    Args:
        lat: Latitude in degrees (e.g., 34.1526 for Leh)
        lon: Longitude in degrees (e.g., 77.5771 for Leh)
        date: A datetime.date object for the target day
        tz_offset_hours: Timezone offset from UTC (default 5.5 = IST)

    Returns:
        dict with keys:
            'hours': list of 24 ints (0-23)
            'altitudes': list of 24 floats (degrees above horizon, negative = below)
            'azimuths': list of 24 floats (degrees clockwise from North)
    """
    altitudes = []
    azimuths = []
    tz = timezone(timedelta(hours=tz_offset_hours))

    for hour in range(24):
        # Create timezone-aware datetime at the midpoint of each hour
        dt = datetime(date.year, date.month, date.day, hour, 30, 0, tzinfo=tz)
        alt = get_altitude(lat, lon, dt)
        azi = get_azimuth(lat, lon, dt)
        altitudes.append(alt)
        azimuths.append(azi % 360)  # Normalize to 0-360

    return {
        "hours": list(range(24)),
        "altitudes": altitudes,
        "azimuths": azimuths,
    }


# ─── Phase 2.2: Terrain Elevation Fetcher ─────────────────────────────────────

def _destination_point(lat, lon, distance_km, bearing_deg):
    """
    Calculate the GPS coordinate at a given distance and bearing from a start point.
    Uses the Haversine forward formula.

    Args:
        lat, lon: Starting coordinates in degrees
        distance_km: Distance in kilometers
        bearing_deg: Bearing in degrees clockwise from North

    Returns:
        (new_lat, new_lon) in degrees
    """
    R = 6371.0  # Earth radius in km
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    bearing_r = math.radians(bearing_deg)
    d = distance_km / R

    new_lat = math.asin(
        math.sin(lat_r) * math.cos(d) +
        math.cos(lat_r) * math.sin(d) * math.cos(bearing_r)
    )
    new_lon = lon_r + math.atan2(
        math.sin(bearing_r) * math.sin(d) * math.cos(lat_r),
        math.cos(d) - math.sin(lat_r) * math.sin(new_lat)
    )

    return math.degrees(new_lat), math.degrees(new_lon)


def fetch_terrain_elevations(lat, lon, radius_km=5.0, n_azimuths=36, n_distances=6):
    """
    Fetch elevation data in a radial pattern around the deployment site
    using the Open-Elevation API.

    Samples n_azimuths directions × n_distances rings = total query points.
    Also fetches the site's own elevation.

    Args:
        lat, lon: Deployment GPS coordinates
        radius_km: Radius to scan (default 5 km)
        n_azimuths: Number of azimuth directions to sample (default 36 = every 10°)
        n_distances: Number of distance rings to sample per direction

    Returns:
        dict with keys:
            'site_elevation': float (meters above sea level)
            'profiles': dict mapping azimuth_deg -> list of
                        {'distance_km': float, 'elevation': float}
            'status': 'ok' or 'error'
            'error_msg': str (only if status == 'error')
    """
    # Build the list of sample points
    locations = [{"latitude": lat, "longitude": lon}]  # Site itself first

    azimuth_angles = np.linspace(0, 350, n_azimuths).tolist()
    distances = np.linspace(radius_km / n_distances, radius_km, n_distances).tolist()

    point_map = []  # Track (azimuth, distance) for each point
    for azi in azimuth_angles:
        for dist in distances:
            new_lat, new_lon = _destination_point(lat, lon, dist, azi)
            locations.append({
                "latitude": round(new_lat, 6),
                "longitude": round(new_lon, 6)
            })
            point_map.append((azi, dist))

    # Query the Open-Elevation API (batch request)
    try:
        response = requests.post(
            "https://api.open-elevation.com/api/v1/lookup",
            json={"locations": locations},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        return {
            "site_elevation": 0,
            "profiles": {},
            "status": "error",
            "error_msg": f"Open-Elevation API error: {str(e)}",
        }

    results = data.get("results", [])
    if len(results) < 1:
        return {
            "site_elevation": 0,
            "profiles": {},
            "status": "error",
            "error_msg": "No elevation data returned from API.",
        }

    # Extract site elevation
    site_elevation = results[0]["elevation"]

    # Build elevation profiles per azimuth
    profiles = {azi: [] for azi in azimuth_angles}
    for i, (azi, dist) in enumerate(point_map):
        idx = i + 1  # +1 because index 0 is the site itself
        if idx < len(results):
            profiles[azi].append({
                "distance_km": dist,
                "elevation": results[idx]["elevation"],
            })

    return {
        "site_elevation": site_elevation,
        "profiles": profiles,
        "status": "ok",
    }


# ─── Phase 2.3: Shadow Masking (Ray-Casting) ──────────────────────────────────

def calculate_horizon_angles(site_elevation, profiles):
    """
    Calculate the maximum horizon angle for each azimuth direction.

    For each sampled point, the horizon angle is:
        angle = arctan((point_elevation - site_elevation) / horizontal_distance)

    We take the maximum across all distances for each azimuth —
    this represents the tallest "mountain wall" blocking the sun.

    Args:
        site_elevation: Elevation of the deployment site (meters)
        profiles: dict from fetch_terrain_elevations — azimuth -> [{distance_km, elevation}]

    Returns:
        dict mapping azimuth_deg (float) -> max_horizon_angle (degrees)
    """
    horizon_angles = {}

    for azi, points in profiles.items():
        max_angle = 0.0
        for pt in points:
            height_diff = pt["elevation"] - site_elevation
            horizontal_dist = pt["distance_km"] * 1000  # Convert to meters
            if horizontal_dist > 0:
                angle = math.degrees(math.atan2(height_diff, horizontal_dist))
                max_angle = max(max_angle, angle)
        horizon_angles[azi] = max(max_angle, 0.0)  # Floor at 0 (no negative horizon)

    return horizon_angles


def compute_shadow_mask(sun_positions, horizon_angles):
    """
    Determine which hours the shelter is in topographical shadow.

    For each hour: if the sun's altitude is below the terrain's horizon angle
    at the sun's azimuth direction, the shelter is shadowed.

    Args:
        sun_positions: dict from get_sun_positions
        horizon_angles: dict from calculate_horizon_angles

    Returns:
        dict with keys:
            'is_shadowed': list of 24 bools
            'sun_altitudes': list of 24 floats
            'horizon_at_sun': list of 24 floats (interpolated horizon angle at sun azimuth)
    """
    azimuths_sorted = sorted(horizon_angles.keys())
    horizon_vals = [horizon_angles[a] for a in azimuths_sorted]

    is_shadowed = []
    horizon_at_sun = []

    for hour in range(24):
        sun_alt = sun_positions["altitudes"][hour]
        sun_azi = sun_positions["azimuths"][hour]

        if sun_alt <= 0:
            # Sun is below the geometric horizon (nighttime)
            is_shadowed.append(True)
            horizon_at_sun.append(0.0)
            continue

        # Interpolate the horizon angle at the sun's current azimuth
        h_angle = _interpolate_horizon(sun_azi, azimuths_sorted, horizon_vals)
        horizon_at_sun.append(h_angle)

        # Ray-cast: is the sun blocked by terrain?
        is_shadowed.append(sun_alt < h_angle)

    return {
        "is_shadowed": is_shadowed,
        "sun_altitudes": sun_positions["altitudes"],
        "horizon_at_sun": horizon_at_sun,
    }


def _interpolate_horizon(target_azi, azimuths_sorted, horizon_vals):
    """
    Linearly interpolate the horizon angle at a given azimuth
    from the sampled azimuth directions.
    """
    n = len(azimuths_sorted)
    if n == 0:
        return 0.0

    # Wrap-around interpolation for circular azimuths
    target_azi = target_azi % 360

    # Find the two bracketing azimuths
    for i in range(n):
        if azimuths_sorted[i] > target_azi:
            break
    else:
        i = 0  # Wrap around

    i_prev = (i - 1) % n
    azi_low = azimuths_sorted[i_prev]
    azi_high = azimuths_sorted[i % n]
    val_low = horizon_vals[i_prev]
    val_high = horizon_vals[i % n]

    # Handle wrap-around (e.g., 350° to 10°)
    span = (azi_high - azi_low) % 360
    if span == 0:
        return val_low

    frac = ((target_azi - azi_low) % 360) / span
    frac = max(0.0, min(1.0, frac))

    return val_low + frac * (val_high - val_low)


# ─── Phase 2.4: Irradiance Curve Modifier ─────────────────────────────────────

def apply_shadow_to_irradiance(base_irradiance, shadow_mask, diffuse_fraction=0.1):
    """
    Apply the shadow mask to modify the solar irradiance array.

    Shadowed hours receive only diffuse sky radiation (default 10% of direct).
    Unshadowed hours keep their full irradiance.

    Args:
        base_irradiance: numpy array of 24 solar irradiance values (W/m²)
        shadow_mask: dict from compute_shadow_mask
        diffuse_fraction: fraction of irradiance that penetrates as diffuse light (default 0.1)

    Returns:
        numpy array of 24 modified irradiance values
    """
    modified = np.copy(base_irradiance).astype(float)
    for hour in range(24):
        if shadow_mask["is_shadowed"][hour]:
            modified[hour] *= diffuse_fraction
    return modified


# ─── Full Pipeline ─────────────────────────────────────────────────────────────

def run_terrain_shadow_pipeline(lat, lon, date, base_irradiance,
                                 radius_km=5.0, tz_offset_hours=5.5):
    """
    Execute the complete terrain shadow mapping pipeline.

    1. Calculate sun positions for every hour
    2. Fetch terrain elevations in a radial pattern
    3. Compute horizon angles
    4. Ray-cast shadow mask
    5. Modify irradiance curve

    Args:
        lat, lon: GPS coordinates
        date: datetime.date
        base_irradiance: numpy array of 24 hourly irradiance values (W/m²)
        radius_km: Terrain scan radius (default 5 km)
        tz_offset_hours: Timezone offset from UTC (default 5.5 = IST)

    Returns:
        dict with keys:
            'status': 'ok' or 'error'
            'error_msg': str (only if error)
            'modified_irradiance': numpy array of 24 values
            'original_irradiance': numpy array of 24 values
            'shadow_mask': dict from compute_shadow_mask
            'sun_positions': dict from get_sun_positions
            'terrain_data': dict from fetch_terrain_elevations
            'horizon_angles': dict from calculate_horizon_angles
            'shadowed_hours': int (count of daylight hours lost to shadows)
    """
    # Step 1: Sun positions
    sun_positions = get_sun_positions(lat, lon, date, tz_offset_hours)

    # Step 2: Fetch terrain
    terrain_data = fetch_terrain_elevations(lat, lon, radius_km=radius_km)

    if terrain_data["status"] == "error":
        # Fallback: return unmodified irradiance with error info
        return {
            "status": "error",
            "error_msg": terrain_data.get("error_msg", "Unknown terrain fetch error"),
            "modified_irradiance": base_irradiance,
            "original_irradiance": base_irradiance,
            "shadow_mask": None,
            "sun_positions": sun_positions,
            "terrain_data": terrain_data,
            "horizon_angles": {},
            "shadowed_hours": 0,
        }

    # Step 3: Horizon angles
    horizon_angles = calculate_horizon_angles(
        terrain_data["site_elevation"], terrain_data["profiles"]
    )

    # Step 4: Shadow mask
    shadow_mask = compute_shadow_mask(sun_positions, horizon_angles)

    # Step 5: Modify irradiance
    modified_irradiance = apply_shadow_to_irradiance(base_irradiance, shadow_mask)

    # Count daylight hours lost to terrain shadow
    shadowed_daylight_hours = sum(
        1 for h in range(24)
        if shadow_mask["is_shadowed"][h] and sun_positions["altitudes"][h] > 0
    )

    return {
        "status": "ok",
        "modified_irradiance": modified_irradiance,
        "original_irradiance": np.copy(base_irradiance),
        "shadow_mask": shadow_mask,
        "sun_positions": sun_positions,
        "terrain_data": terrain_data,
        "horizon_angles": horizon_angles,
        "shadowed_hours": shadowed_daylight_hours,
    }
