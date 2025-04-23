import xml.etree.ElementTree as ET
import pandas as pd
import requests
import time

def estimate_capacity_from_name(name):
    if 'E4' in name or 'E18' in name or 'E20' in name:
        return 2000  # vehicles per hour for motorways
    elif name.startswith('27') or name.startswith('22'):
        return 1200  # secondary arterials
    elif name.startswith('75') or name.startswith('73'):
        return 800   # smaller urban roads
    else:
        return 1000  # fallback

# Path to your KML
kml_path = 'Main Edges.kml'

# Parse KML
tree = ET.parse(kml_path)
root = tree.getroot()
ns = {'kml': 'http://www.opengis.net/kml/2.2'}
placemarks = root.findall('.//kml:Placemark', ns)

rows = []
for pm in placemarks:
    line = pm.find('.//kml:LineString/kml:coordinates', ns)
    if line is None:
        continue
    coords = [
        tuple(map(float, c.split(',')[:2][::-1]))  # (lat, lon)
        for c in line.text.strip().split()
    ]
    origin, dest = coords[0], coords[-1]

    # OSRM API call
    url = f"http://router.project-osrm.org/route/v1/driving/{origin[1]},{origin[0]};{dest[1]},{dest[0]}?overview=false"
    resp = requests.get(url)
    resp.raise_for_status()
    leg = resp.json()['routes'][0]['legs'][0]

    rows.append({
        'edge_name': pm.find('kml:name', ns).text or '',
        'distance_m': leg['distance'],
        'duration_s': leg['duration']
    })
    time.sleep(0.5)

# Build DataFrame
df = pd.DataFrame(rows)
df['distance_km']   = df['distance_m'] / 1000
df['duration_min']  = df['duration_s'] / 60
df['avg_speed_kmh'] = df['distance_km'] / (df['duration_min'] / 60)
df['capacity_veh_per_hr'] = df['edge_name'].apply(estimate_capacity_from_name)

# Output
print(df[['edge_name','distance_km','duration_min','avg_speed_kmh']])
df.to_csv('edge_distances_osrm.csv', index=False)
print("Saved to edge_distances_osrm.csv")
