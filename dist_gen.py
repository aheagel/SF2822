import xml.etree.ElementTree as ET
import pandas as pd
import requests
import time
from math import sqrt

def estimate_capacity_from_name(name):
    if 'E4' in name or 'E18' in name or 'E20' in name:
        return 2000  # vehicles per hour for motorways
    elif name.startswith('27') or name.startswith('22'):
        return 1200  # secondary arterials
    elif name.startswith('75') or name.startswith('73'):
        return 800   # smaller urban roads
    else:
        return 1000  # fallback

def haversine_distance(coord1, coord2):
    """Calculate approximate distance between two (lat, lon) points in meters."""
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    R = 6371000  # Earth's radius in meters
    dlat = (lat2 - lat1) * (3.141592653589793 / 180)
    dlon = (lon2 - lon1) * (3.141592653589793 / 180)
    a = (dlat / 2) ** 2 + (dlon / 2) ** 2 * 0.5  # Simplified for small angles
    return 2 * R * sqrt(a)

def find_closest_node(coord, nodes):
    """Find the node with the closest coordinates to the given coord."""
    min_dist = float('inf')
    closest_node = None
    for node_name, node_coord in nodes.items():
        dist = haversine_distance(coord, node_coord)
        if dist < min_dist:
            min_dist = dist
            closest_node = node_name
    return closest_node

# Paths to KML files
edges_kml_path = 'Main Edges.kml'
nodes_kml_path = 'Nodes.kml'

# Parse nodes KML
tree_nodes = ET.parse(nodes_kml_path)
root_nodes = tree_nodes.getroot()
ns = {'kml': 'http://www.opengis.net/kml/2.2'}

# Extract node coordinates and names
nodes = {}
for pm in root_nodes.findall('.//kml:Placemark', ns):
    point = pm.find('.//kml:Point/kml:coordinates', ns)
    name_elem = pm.find('kml:name', ns)
    if point is None or name_elem is None:
        continue
    coord = tuple(map(float, point.text.strip().split(',')[:2][::-1]))  # (lat, lon)
    node_name = name_elem.text.strip()
    nodes[node_name] = coord

# Parse edges KML
tree_edges = ET.parse(edges_kml_path)
root_edges = tree_edges.getroot()
placemarks = root_edges.findall('.//kml:Placemark', ns)

rows = []
for pm in placemarks:
    line = pm.find('.//kml:LineString/kml:coordinates', ns)
    name_elem = pm.find('kml:name', ns)
    if line is None or name_elem is None:
        continue
    coords = [
        tuple(map(float, c.split(',')[:2][::-1]))  # (lat, lon)
        for c in line.text.strip().split()
    ]
    origin, dest = coords[0], coords[-1]

    # Find closest nodes for origin and destination
    from_node = find_closest_node(origin, nodes)
    to_node = find_closest_node(dest, nodes)

    # OSRM API call
    url = f"http://router.project-osrm.org/route/v1/driving/{origin[1]},{origin[0]};{dest[1]},{dest[0]}?overview=false"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        leg = resp.json()['routes'][0]['legs'][0]
    except (requests.RequestException, KeyError) as e:
        print(f"Error fetching OSRM data for {name_elem.text}: {e}")
        continue

    rows.append({
        'edge_name': name_elem.text.strip(),
        'distance_m': leg['distance'],
        'duration_s': leg['duration'],
        'from_node': from_node,
        'to_node': to_node
    })
    time.sleep(0.5)  # Avoid overwhelming OSRM server

# Build final DataFrame
df = pd.DataFrame(rows)
df['distance_km'] = df['distance_m'] / 1000
df['duration_min'] = df['duration_s'] / 60
df['avg_speed_kmh'] = df['distance_km'] / (df['duration_min'] / 60)
df['u_ij'] = df['edge_name'].apply(estimate_capacity_from_name)
df['a_ij'] = df['u_ij'] / (df['duration_min'] * 60)  # vehicles per second

# Output
print(df[['edge_name', 'distance_km', 'duration_min', 'avg_speed_kmh', 'from_node', 'to_node', 'u_ij']])
df.to_csv('edge_distances_osrm.csv', index=False)
print("Saved to edge_distances_osrm.csv")