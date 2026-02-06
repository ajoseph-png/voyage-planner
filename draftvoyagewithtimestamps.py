import searoute as sr
import folium
from datetime import datetime, timezone, timedelta
from geographiclib.geodesic import Geodesic
from global_land_mask import globe
import pandas as pd
from geopy.distance import geodesic

# 1. Define your points [longitude, latitude]
origin = [18.91501112425493, 72.84342356746767]
destination = [14.23945351267364, 66.0599130997813]
days_input = 1  # Change this to your desired duration

# 2. Generate the sea route
route = sr.searoute(origin, destination)

# Extract coordinates as [longitude, latitude]
lon_lat_coords = route['geometry']['coordinates']

def get_path_points(start_lat, start_lon, end_lat, end_lon, num_points=50):
    # Initialize the WGS84 ellipsoid
    geod = Geodesic.WGS84

    # Solve the inverse problem to get the path (line) between points
    line = geod.InverseLine(start_lat, start_lon, end_lat, end_lon)

    path = []
    # We use num_points + 1 to create even segments
    # i.e., 11 segments create 10 intermediate points
    for i in range(1, num_points + 1):
        # Calculate the position at a specific distance along the line
        # line.s13 is the total distance between the two points
        point = line.Position(line.s13 * i / (num_points + 1))
        path.append((point['lat2'], point['lon2']))

    return path

# 2. Generate the sea route
route = sr.searoute(origin, destination)
lon_lat_coords = route['geometry']['coordinates']


# 3. Validation Logic
import numpy as np
from global_land_mask import globe


def find_water_nearby(lat, lon, radius_km=0.2, search_points=50):
    """
    Scans a circle around a land point to find the nearest water.
    """
    # 1 degree lat is approx 111km; 2km is ~0.018 degrees
    # We use a rough approximation for the search offset
    offset = radius_km / 111.0

    for i in range(search_points):
        # Calculate angle for radial search
        angle = 40+(100/search_points)*i
        search_lat = lat + (offset * np.cos(angle))
        search_lon = lon + (offset * np.sin(angle))

        if not globe.is_land(search_lat, search_lon):
            return (search_lat, search_lon)
    return None


def repair_route_with_water_check(route_coords):
    repaired_path = []
    land_markers = []

    for i in range(len(route_coords) - 1):
        p1 = route_coords[i]
        p2 = route_coords[i + 1]

        # Add the starting waypoint
        repaired_path.append((p1[1], p1[0]))

        # Check intermediate points (interpolation)
        sub_points = get_path_points(p1[1], p1[0], p2[1], p2[0], num_points=50)

        for pt in sub_points:
            lat, lon = pt
            if globe.is_land(lat, lon):
                # We hit land! Mark it and try to find water within 2km
                land_markers.append(pt)
                water_waypoint = find_water_nearby(lat, lon, radius_km=0.2)

                if water_waypoint:
                    # Found water! Add this new waypoint to the route
                    repaired_path.append(water_waypoint)
            else:
                # It's water, keep moving forward
                repaired_path.append(pt)

    # Add final destination
    repaired_path.append((route_coords[-1][1], route_coords[-1][0]))
    return repaired_path, land_markers

## Generate Timestamp and make CSV file


def generate_timed_csv(repaired_path, total_days, filename="voyage_plan.csv"):
    # 1. Set Start Time to current UTC time
    # This ensures the 'Z' suffix is geographically accurate
    start_time_utc = datetime.now(timezone.utc)

    # 2. Distance and Speed Calculations
    total_distance_km = 0
    segment_distances = []
    for i in range(len(repaired_path) - 1):
        dist = geodesic(repaired_path[i], repaired_path[i + 1]).km
        total_distance_km += dist
        segment_distances.append(dist)

    total_seconds = int(total_days * 24 * 60 * 60)
    speed_km_s = total_distance_km / total_seconds

    # 3. Interpolate and Generate Standard UTC Timestamps
    data = []
    current_segment_idx = 0
    accumulated_dist_at_segment_start = 0

    # Step by 60 seconds (1 minute intervals)
    for second in range(0, total_seconds + 1, 60):
        target_dist = second * speed_km_s

        while (current_segment_idx < len(segment_distances) and
               target_dist > (accumulated_dist_at_segment_start + segment_distances[current_segment_idx] + 1e-9)):
            accumulated_dist_at_segment_start += segment_distances[current_segment_idx]
            current_segment_idx += 1

        if current_segment_idx >= len(segment_distances):
            lat, lon = repaired_path[-1]
        else:
            seg_start = repaired_path[current_segment_idx]
            seg_end = repaired_path[current_segment_idx + 1]
            seg_len = segment_distances[current_segment_idx]
            ratio = (target_dist - accumulated_dist_at_segment_start) / seg_len if seg_len > 0 else 0
            lat = seg_start[0] + (seg_end[0] - seg_start[0]) * ratio
            lon = seg_start[1] + (seg_end[1] - seg_start[1]) * ratio

        # Create Standard ISO 8601 UTC Timestamp
        # Result looks like: 2026-02-06T12:00:00Z
        current_timestamp = start_time_utc + timedelta(seconds=second)
        iso_string = current_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')

        data.append([iso_string, round(lat, 6), round(lon, 6)])

    # 4. Save to CSV
    df = pd.DataFrame(data, columns=['Timestamp_UTC', 'Latitude', 'Longitude'])
    df.to_csv(filename, index=False)
    print(f"Success: {filename} generated with {len(df)} standardized waypoints.")

# Execute
new_route, land_hits = repair_route_with_water_check(lon_lat_coords)

# 4. Visualization
m = folium.Map(location=[45, -40], zoom_start=3)

# 1. Draw the repaired route (The "Smooth" path)
folium.PolyLine(new_route, color="green", weight=4, opacity=0.7, tooltip="Repaired Route").add_to(m)

# 2. Mark the Land Hits in Red
for pt in land_hits:
    folium.CircleMarker(
        location=pt,
        radius=4,
        color='red',
        fill=True,
        popup="Land Hit - Redirected"
    ).add_to(m)

# --- EXECUTION ---


generate_timed_csv(new_route, days_input)

m.save("repaired_sea_route.html")