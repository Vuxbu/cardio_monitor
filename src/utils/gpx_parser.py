import gpxpy
import json
import os
from geopy.distance import distance

def gpx_to_treadmill_profile(gpx_path, output_path=None):
    """
    Converts GPX file to treadmill simulation profile.
    Handles duplicate points and missing elevation data.
    """
    with open(gpx_path, 'r') as f:
        gpx = gpxpy.parse(f)
    
    profile = []
    total_km = 0.0
    prev_point = None
    points_skipped = 0
    
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                if not hasattr(point, 'elevation') or point.elevation is None:
                    points_skipped += 1
                    continue
                    
                if prev_point:
                    try:
                        # Skip if points are identical
                        if (point.latitude == prev_point.latitude and 
                            point.longitude == prev_point.longitude):
                            points_skipped += 1
                            continue
                            
                        dist_km = distance(
                            (prev_point.latitude, prev_point.longitude),
                            (point.latitude, point.longitude)
                        ).km
                        
                        # Skip micro-movements (<1m) to avoid noise
                        if dist_km < 0.001:
                            points_skipped += 1
                            continue
                            
                        total_km += dist_km
                        ele_diff = point.elevation - prev_point.elevation
                        grade_pct = (ele_diff / (dist_km * 1000)) * 100
                        
                    except Exception as e:
                        print(f"Skipping point due to error: {str(e)}")
                        points_skipped += 1
                        continue
                else:
                    dist_km = 0.0
                    grade_pct = 0.0
                
                profile.append({
                    "km": round(total_km, 3),
                    "lat": round(point.latitude, 6),
                    "lon": round(point.longitude, 6),
                    "ele": round(point.elevation, 2),
                    "grade": round(grade_pct, 2)
                })
                prev_point = point
    
    if points_skipped > 0:
        print(f"Note: Skipped {points_skipped} invalid/duplicate points")
    
    output = {
        "name": track.name or os.path.basename(gpx_path),
        "total_km": round(total_km, 3),
        "profile": profile
    }

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # Generate both JSON and GeoJSON
        save_as_json(output, output_path)
        save_as_geojson(output, output_path.replace('.json', '.geojson'))
        
    return output

def save_as_json(data, output_path):
    """Save data in original JSON format"""
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved JSON profile to {output_path}")

# Update in gpx_parser.py
def save_as_geojson(data, output_path):
    """Generate GeoJSON with elevation-based coloring"""
    geojson = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [p["lon"], p["lat"], p["ele"]] 
                    for p in data["profile"]
                ]
            },
            "properties": {
                "name": data["name"],
                "distance_km": data["total_km"],
                "segments": [{
                    "start_km": p["km"],
                    "end_km": data["profile"][i+1]["km"] if i < len(data["profile"])-1 else p["km"],
                    "grade": p["grade"],
                    "elevation": p["ele"],
                    "color": get_color_for_elevation(p["ele"])  # NEW
                } for i, p in enumerate(data["profile"])]
            }
        }]
    }
    
    with open(output_path, 'w') as f:
        json.dump(geojson, f, indent=2)

def get_color_for_elevation(ele):
    """Return color gradient from blue (low) to red (high)"""
    normalized = min(max((ele - 50) / 100, 0), 1)  # Adjust 50/100 for your course
    return f"hsl({int(240 * (1 - normalized))}, 100%, 50%)"

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Convert GPX to treadmill profile')
    parser.add_argument("input_gpx", help="Path to input GPX file")
    parser.add_argument("output_json", help="Path to output JSON file")
    args = parser.parse_args()
    
    result = gpx_to_treadmill_profile(args.input_gpx, args.output_json)
    print(f"Course '{result['name']}': {result['total_km']}km with {len(result['profile'])} points")