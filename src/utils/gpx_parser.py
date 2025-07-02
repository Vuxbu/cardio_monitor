import gpxpy
import json
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
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"Successfully processed {len(profile)} points to {output_path}")
    return output

if __name__ == "__main__":
    import argparse, os
    parser = argparse.ArgumentParser(description='Convert GPX to treadmill profile')
    parser.add_argument("input_gpx", help="Path to input GPX file")
    parser.add_argument("output_json", help="Path to output JSON file")
    args = parser.parse_args()
    
    result = gpx_to_treadmill_profile(args.input_gpx, args.output_json)
    print(f"Course '{result['name']}': {result['total_km']}km with {len(result['profile'])} points")