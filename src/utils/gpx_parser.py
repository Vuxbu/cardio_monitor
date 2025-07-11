import gpxpy
import json
import os
from geopy.distance import distance

def gpx_to_treadmill_profile(gpx_path, output_path=None, min_segment_length=5.0):
    """
    Convert GPX file to treadmill simulation profile.
    Args:
        gpx_path: Path to input GPX file
        output_path: Path for output JSON file (optional)
        min_segment_length: Minimum distance between points in meters (default: 5)
    Returns:
        Dictionary containing course profile data
    """
    with open(gpx_path, 'r') as f:
        gpx = gpxpy.parse(f)
    
    profile = []
    total_km = 0.0
    prev_point = None
    points_processed = 0
    points_skipped = 0
    
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                # Skip points without elevation data
                if not hasattr(point, 'elevation') or point.elevation is None:
                    points_skipped += 1
                    continue
                    
                if prev_point:
                    # Skip duplicate points
                    if (point.latitude == prev_point.latitude and 
                        point.longitude == prev_point.longitude):
                        points_skipped += 1
                        continue
                        
                    # Calculate distance
                    dist_km = distance(
                        (prev_point.latitude, prev_point.longitude),
                        (point.latitude, point.longitude)
                    ).km
                    
                    # Skip micro-movements
                    if dist_km < (min_segment_length / 1000):
                        points_skipped += 1
                        continue
                        
                    total_km += dist_km
                    ele_diff = point.elevation - prev_point.elevation
                    grade_pct = (ele_diff / (dist_km * 1000)) * 100
                else:
                    dist_km = 0.0
                    grade_pct = 0.0
                
                profile.append({
                    "km": round(total_km, 3),
                    "lat": round(point.latitude, 6),
                    "lon": round(point.longitude, 6),
                    "ele": round(point.elevation, 1),
                    "grade": round(grade_pct, 1)
                })
                prev_point = point
                points_processed += 1

    if not profile:
        raise ValueError("No valid points found in GPX file")
    
    # Calculate elevation gain
    elevation_gain = 0.0
    for i in range(1, len(profile)):
        diff = profile[i]["ele"] - profile[i-1]["ele"]
        if diff > 0:
            elevation_gain += diff

    output = {
        "metadata": {
            "name": track.name or os.path.basename(gpx_path),
            "total_distance_km": round(total_km, 3),
            "elevation_gain": round(elevation_gain, 1),
            "max_grade": round(max(abs(p["grade"]) for p in profile), 1),
            "points_processed": points_processed,
            "points_skipped": points_skipped
        },
        "profile": profile
    }

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        save_as_json(output, output_path)
        save_as_geojson(output, output_path.replace('.json', '.geojson'))
        
    return output

def save_as_json(data, output_path):
    """Save data in JSON format"""
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved JSON profile to {output_path}")

def save_as_geojson(data, output_path):
    """Generate GeoJSON with elevation data"""
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
                "name": data["metadata"]["name"],
                "distance_km": data["metadata"]["total_distance_km"],
                "elevation_gain": data["metadata"]["elevation_gain"],
                "max_grade": data["metadata"]["max_grade"],
                "style": {
                    "color": "#4285F4",
                    "weight": 4,
                    "opacity": 0.8
                }
            }
        }]
    }
    
    with open(output_path, 'w') as f:
        json.dump(geojson, f, indent=2)
    print(f"Saved GeoJSON to {output_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description='Convert GPX files to treadmill course profiles',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("input_gpx", help="Input GPX file path")
    parser.add_argument("output_json", help="Output JSON file path")
    parser.add_argument("--min_segment", type=float, default=5.0,
                      help="Minimum segment length in meters")
    parser.add_argument("-v", "--verbose", action="store_true",
                      help="Enable verbose output")
    args = parser.parse_args()
    
    try:
        result = gpx_to_treadmill_profile(
            args.input_gpx,
            args.output_json,
            min_segment_length=args.min_segment
        )
        
        if args.verbose:
            print("\n=== Conversion Summary ===")
            print(f"Course Name: {result['metadata']['name']}")
            print(f"Total Distance: {result['metadata']['total_distance_km']} km")
            print(f"Elevation Gain: {result['metadata']['elevation_gain']} m")
            print(f"Max Grade: {result['metadata']['max_grade']}%")
            print(f"Points Processed: {result['metadata']['points_processed']}")
            print(f"Points Skipped: {result['metadata']['points_skipped']}")
            print(f"\nOutput files generated:")
            print(f"- {args.output_json}")
            print(f"- {args.output_json.replace('.json', '.geojson')}")
            
    except Exception as e:
        print(f"\nError: {str(e)}")
        parser.print_help()
        exit(1)