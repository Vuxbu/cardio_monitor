#!/usr/bin/env python3
import gpxpy
import json
import os
import sys
from pathlib import Path
from math import atan, degrees, tan, radians
from time import perf_counter
from functools import wraps
from geojson import Feature, FeatureCollection, LineString

__version__ = "1.0.0"  # Define version

GPX_NS = {
    'ns3': 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1',
    'gpxtpx': 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1'
}

class GPXConversionError(Exception):
    """Base exception for conversion errors"""
    pass

class InvalidGPXError(GPXConversionError):
    """Raised when GPX file is invalid"""
    pass

def timed(func):
    """Timing decorator for performance metrics"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = perf_counter()
        result = func(*args, **kwargs)
        print(f"{func.__name__} executed in {perf_counter() - start:.3f}s")
        return result
    return wrapper

def calculate_pace(point_a, point_b, moving_threshold=1.0):
    """
    Robust pace calculation with movement detection
    Args:
        moving_threshold: Minimum speed (km/h) to consider as moving
                         (0.5 for strict, 1.0 for relaxed filtering)
    """
    if not (point_a and point_b and point_a.time and point_b.time):
        return None
        
    time_sec = (point_b.time - point_a.time).total_seconds()
    distance_km = point_a.distance_2d(point_b) / 1000
    
    if distance_km == 0 or time_sec == 0:
        return None
    
    speed_kmh = (distance_km / time_sec) * 3600
    if speed_kmh < moving_threshold:
        return None  # Filter stationary periods
        
    return round((time_sec / 60) / distance_km, 1)  # min/km

def get_hr(point):
    """Extracts heart rate from GPX point extensions with namespace support"""
    if not hasattr(point, 'extensions'):
        return None
    
    # Check both namespaced and non-namespaced variants
    hr_tags = [
        'hr',  # Non-namespaced
        '{http://www.garmin.com/xmlschemas/TrackPointExtension/v1}hr',  # Full ns
        'ns3:hr',  # Your prefix
        'gpxtpx:hr'  # Common alternative
    ]
    
    for tag in hr_tags:
        try:
            if tag in point.extensions:
                return int(point.extensions[tag])
        except (AttributeError, KeyError):
            continue
    
    # Deep search in nested extensions
    if hasattr(point.extensions[0], 'hr'):
        return int(point.extensions[0].hr)
    
    return None
# Remove the class-style methods and replace with standalone functions
def calculate_hr_zone(hr, max_hr=185):
    """Calculate zone based on max HR"""
    if not hr: return None
    return min((hr * 100) // max_hr, 5)  # 1-5 scale

def calculate_effort(pace, hr, expected_hr=None):
    """Quantify how hard you're working at a given pace"""
    if None in (pace, hr): return None
    
    # Default expected HR values if none provided
    if not expected_hr:
        expected_hr = {  
            5.0: 145,  # Fast pace
            6.0: 135,   # Moderate
            7.0: 125     # Easy
        }
    
    # Find nearest reference pace
    ref_pace = min(expected_hr.keys(), key=lambda x: abs(x - pace))
    hr_ratio = hr / expected_hr[ref_pace]
    return round(hr_ratio, 2)

def calculate_grade(distance, elevation_change):
    """Calculate incline percentage (grade) with trig precision"""
    if distance == 0:
        return 0.0
    angle = atan(elevation_change / distance)
    return tan(radians(degrees(angle))) * 100

@timed
def convert_gpx(input_path, output_path):
    """Optimized GPX to GeoJSON converter"""
    try:
        input_path = Path(input_path)
        output_path = Path(output_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
            
        with open(input_path, 'r') as f:
            gpx = gpxpy.parse(f)
            # Force namespace awareness
            if not hasattr(gpx, 'nsmap'):
               gpx.nsmap = GPX_NS
        
        if not gpx.tracks:
            raise InvalidGPXError("GPX file contains no tracks")
            
        # Process points as generator
        points = (point for track in gpx.tracks 
                 for segment in track.segments 
                 for point in segment.points)
        
        segments = []
        grade_profile = []
        total_distance = 0.0
        prev_point = None
        segment_start = None
        SEGMENT_LENGTH = 100  # meters
        
        for point in points:
            if prev_point:
                distance = prev_point.distance_2d(point)
                elevation_change = point.elevation - prev_point.elevation
                
                # Create segments
                segments.append({
                    "start_m": round(total_distance, 2),
                    "end_m": round(total_distance + distance, 2),
                    "pace_min_km": calculate_pace(prev_point, point) if prev_point and point.time and prev_point.time else None,
                    "grade": round(calculate_grade(distance, elevation_change), 1),
                    "elevation": round(point.elevation, 1),
                    "hr": get_hr(point),
                    "hr_zone": calculate_hr_zone(get_hr(point)),
                    "moving": calculate_pace(prev_point, point) is not None,  # Fixed pace reference
                    "effort_ratio": calculate_effort(calculate_pace(prev_point, point),get_hr(point))
                })
                
                # Handle 100m segments
                if segment_start is None:
                    segment_start = {
                        'distance': total_distance,
                        'elevation': prev_point.elevation
                    }
                
                segment_end_distance = total_distance + distance
                if segment_end_distance - segment_start['distance'] >= SEGMENT_LENGTH:
                    segment_distance = segment_end_distance - segment_start['distance']
                    elevation_diff = point.elevation - segment_start['elevation']
                    
                    grade_profile.append({
                        "start_km": round(segment_start['distance'] / 1000, 3),
                        "grade": round(calculate_grade(segment_distance, elevation_diff), 1),
                        "ele": round(point.elevation, 1)
                    })
                    
                    segment_start = {
                        'distance': segment_end_distance,
                        'elevation': point.elevation
                    }
                
                total_distance += distance
            prev_point = point
        
        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate GeoJSON
        feature = Feature(
            geometry=LineString([[p.longitude, p.latitude] for p in [prev_point]] if prev_point else []),
            properties={
                "distance_km": round(total_distance / 1000, 3),
                "grade_profile": grade_profile,
                "segments": segments
            }
        )
        
        with open(output_path, 'w') as f:
            json.dump(FeatureCollection([feature]), f, indent=2)
            
        return {
            "distance": total_distance / 1000,
            "points": len(segments),
            "max_grade": max((p['grade'] for p in grade_profile), default=0),
            "min_grade": min((p['grade'] for p in grade_profile), default=0)
        }
    
    except Exception as e:
        raise GPXConversionError(f"Failed to convert {input_path}: {str(e)}")

def convert_directory(input_dir, output_dir):
    """Batch convert all GPX files in directory"""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    results = []
    for gpx_file in input_dir.glob('*.gpx'):
        try:
            output_path = output_dir / f"{gpx_file.stem}.json"
            result = convert_gpx(gpx_file, output_path)
            results.append((gpx_file.name, result))
        except GPXConversionError as e:
            print(f"Skipped {gpx_file.name}: {str(e)}")
    
    return results

if __name__ == "__main__":
    if len(sys.argv) != 3:
      print(f"GPX to JSON Converter v{__version__}")
      print("Usage: python gpx_json_converter.py <input.gpx> <output.json>")
    sys.exit(1)
        
    convert_gpx(sys.argv[1], sys.argv[2])
        
    try:
        if len(sys.argv) == 3 and os.path.isdir(sys.argv[1]):
            convert_directory(sys.argv[1], sys.argv[2])
        else:
            convert_gpx(sys.argv[1], sys.argv[2])
    except GPXConversionError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)