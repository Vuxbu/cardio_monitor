#!/usr/bin/env python3
import gpxpy
import json
import os
import sys
from geojson import Feature, FeatureCollection, LineString
from math import atan, degrees

def calculate_grade(distance, elevation_change):
    """Calculate incline percentage (grade)"""
    if distance == 0:
        return 0.0
    return (elevation_change / distance) * 100  # Correct grade calculation

def convert_gpx(input_path, output_path):
    try:
        # Verify input file exists
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
            
        with open(input_path, 'r') as f:
            gpx = gpxpy.parse(f)
        
        if not gpx.tracks:
            raise ValueError("GPX file contains no tracks")
            
        # Process points
        points = []
        for track in gpx.tracks:
            for segment in track.segments:
                points.extend(segment.points)
        
        # Calculate segments and elevation profile
        segments = []
        grade_profile = []
        total_distance = 0.0
        prev_point = None
        segment_start = None
        
        # Create 100m segments for grade profile
        SEGMENT_LENGTH = 100  # meters
        
        for point in points:
            if prev_point:
                distance = prev_point.distance_2d(point)
                time_diff = (point.time - prev_point.time).total_seconds()
                pace = (time_diff / 60) / (distance / 1000) if distance > 0 else 0
                elevation_change = point.elevation - prev_point.elevation
                
                # Create pace segments
                segments.append({
                    "start_m": round(total_distance, 2),
                    "end_m": round(total_distance + distance, 2),
                    "pace_min_km": round(pace, 1),
                    "elevation": round(point.elevation, 1)
                })
                
                # Create grade profile segments every 100m
                if segment_start is None:
                    segment_start = {
                        'distance': total_distance,
                        'elevation': prev_point.elevation,
                        'first_point': prev_point
                    }
                
                if (total_distance + distance) - segment_start['distance'] >= SEGMENT_LENGTH:
                    segment_distance = (total_distance + distance) - segment_start['distance']
                    elevation_diff = point.elevation - segment_start['elevation']
                    
                    grade_profile.append({
                        "start_km": round(segment_start['distance'] / 1000, 3),
                        "grade": round(calculate_grade(segment_distance, elevation_diff), 1),
                        "ele": round(point.elevation, 1)
                    })
                    
                    segment_start = {
                        'distance': total_distance + distance,
                        'elevation': point.elevation,
                        'first_point': point
                    }
                
                total_distance += distance
            prev_point = point
        
        # Add final segment if incomplete
        if segment_start and total_distance - segment_start['distance'] > 0:
            elevation_diff = points[-1].elevation - segment_start['elevation']
            segment_distance = total_distance - segment_start['distance']
            grade_profile.append({
                "start_km": round(segment_start['distance'] / 1000, 3),
                "grade": round(calculate_grade(segment_distance, elevation_diff), 1),
                "ele": round(points[-1].elevation, 1)
            })
        
        # Create output directory if needed
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Generate GeoJSON
        feature = Feature(
            geometry=LineString([[p.longitude, p.latitude] for p in points]),
            properties={
                "distance_km": round(total_distance / 1000, 3),
                "ghost_runs": {
                    "default": {
                        "segments": segments,
                        "color": "#FF0000"
                    }
                },
                "grade_profile": grade_profile
            }
        )
        
        with open(output_path, 'w') as f:
            json.dump(FeatureCollection([feature]), f, indent=2)
            
        print(f"Conversion successful!\n"
              f"Distance: {total_distance/1000:.2f} km\n"
              f"Elevation Points: {len(grade_profile)}\n"
              f"Max Grade: {max(p['grade'] for p in grade_profile):.1f}%\n"
              f"Min Grade: {min(p['grade'] for p in grade_profile):.1f}%")
    
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python gpx_to_geojson.py <input.gpx> <output.json>", file=sys.stderr)
        sys.exit(1)
        
    convert_gpx(sys.argv[1], sys.argv[2])