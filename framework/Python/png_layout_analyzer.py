#!/usr/bin/env python3
"""
PNG Layout Analyzer for Photonic Circuits

This module provides tools for analyzing PNG images generated from KLayout
photonic circuit layouts, specifically designed for grating couplers and
other photonic components.

Features:
- Color analysis of layout elements
- Shape detection and classification
- Text region identification
- Grating coupler arrow tip detection
- Coordinate conversion between image and layout coordinates

Author: AI Assistant
Date: 2024
"""

import numpy as np
import cv2
from PIL import Image
import argparse
import sys
from typing import List, Tuple, Dict, Any


class PNGLayoutAnalyzer:
    """Analyzer for PNG images of photonic circuit layouts."""
    
    def __init__(self, image_path: str):
        """Initialize the analyzer with a PNG image file.
        
        Args:
            image_path: Path to the PNG image file
        """
        self.image_path = image_path
        self.img = Image.open(image_path)
        self.img_array = np.array(self.img)
        self.gray = cv2.cvtColor(self.img_array, cv2.COLOR_RGB2GRAY)
        
        # Define color mappings for photonic layouts
        self.color_mappings = {
            'white': (255, 255, 255),
            'medium_blue': (0, 64, 128),
            'bright_blue': (0, 0, 255),
            'gray': (128, 128, 128),
            'pink_magenta': (255, 128, 168),
            'dark_blue': (0, 0, 128)
        }
        
    def analyze_colors(self) -> Dict[str, Any]:
        """Analyze the color distribution in the image.
        
        Returns:
            Dictionary containing color analysis results
        """
        print("=== COLOR ANALYSIS ===")
        
        # Get unique colors
        unique_colors = np.unique(self.img_array.reshape(-1, self.img_array.shape[-1]), axis=0)
        total_pixels = self.img_array.shape[0] * self.img_array.shape[1]
        
        print(f"Image dimensions: {self.img.size[0]} x {self.img.size[1]} pixels")
        print(f"Total pixels: {total_pixels:,}")
        print(f"Number of unique colors: {len(unique_colors)}")
        
        color_analysis = {
            'dimensions': self.img.size,
            'total_pixels': total_pixels,
            'unique_colors': len(unique_colors),
            'color_breakdown': {}
        }
        
        # Analyze each unique color
        for i, color in enumerate(unique_colors):
            mask = np.all(self.img_array == color, axis=2)
            pixel_count = np.sum(mask)
            percentage = (pixel_count / total_pixels) * 100
            
            # Try to identify the color
            color_name = self._identify_color(color)
            
            color_analysis['color_breakdown'][color_name] = {
                'rgb': color.tolist(),
                'pixel_count': int(pixel_count),
                'percentage': round(percentage, 2)
            }
            
            print(f"{color_name} {color.tolist()}: {pixel_count:,} pixels ({percentage:.1f}%)")
        
        return color_analysis
    
    def _identify_color(self, color: np.ndarray) -> str:
        """Identify a color based on RGB values.
        
        Args:
            color: RGB color array
            
        Returns:
            String name of the color
        """
        r, g, b = color
        
        # Check against known color mappings
        for name, rgb in self.color_mappings.items():
            if np.array_equal(color, rgb):
                return name
        
        # Generic identification based on RGB values
        if r == g == b:
            if r > 200:
                return f"light_gray_{r}"
            elif r > 100:
                return f"medium_gray_{r}"
            else:
                return f"dark_gray_{r}"
        elif r > g and r > b:
            return f"reddish_{r}_{g}_{b}"
        elif g > r and g > b:
            return f"greenish_{r}_{g}_{b}"
        elif b > r and b > g:
            return f"bluish_{r}_{g}_{b}"
        else:
            return f"unknown_{r}_{g}_{b}"
    
    def analyze_shapes(self) -> Dict[str, Any]:
        """Analyze shapes in the image.
        
        Returns:
            Dictionary containing shape analysis results
        """
        print("\n=== SHAPE ANALYSIS ===")
        
        # Find contours
        contours, _ = cv2.findContours(self.gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        print(f"Number of contours found: {len(contours)}")
        
        shape_analysis = {
            'total_contours': len(contours),
            'shapes': []
        }
        
        # Analyze each contour
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            
            if area > 100:  # Only consider significant shapes
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)
                
                # Approximate the contour
                epsilon = 0.02 * perimeter
                approx = cv2.approxPolyDP(contour, epsilon, True)
                vertices = len(approx)
                
                # Determine shape type
                shape_type = self._classify_shape(vertices, area, w, h)
                
                shape_info = {
                    'index': i,
                    'area': float(area),
                    'perimeter': float(perimeter),
                    'bounding_box': (x, y, w, h),
                    'vertices': vertices,
                    'shape_type': shape_type
                }
                
                shape_analysis['shapes'].append(shape_info)
                
                print(f"Shape {i}: {shape_type}, Area: {area:.0f}, Vertices: {vertices}")
        
        return shape_analysis
    
    def _classify_shape(self, vertices: int, area: float, width: int, height: int) -> str:
        """Classify a shape based on its properties.
        
        Args:
            vertices: Number of vertices
            area: Area of the shape
            width: Width of bounding box
            height: Height of bounding box
            
        Returns:
            String classification of the shape
        """
        if vertices == 3:
            return "Triangle"
        elif vertices == 4:
            aspect_ratio = width / height if height > 0 else 1
            if 0.8 <= aspect_ratio <= 1.2:
                return "Square"
            else:
                return "Rectangle"
        elif vertices > 8:
            aspect_ratio = width / height if height > 0 else 1
            if 0.8 <= aspect_ratio <= 1.2:
                return "Circle"
            else:
                return "Oval"
        else:
            return f"Polygon ({vertices} sides)"
    
    def analyze_text_regions(self) -> Dict[str, Any]:
        """Analyze text regions in the image.
        
        Returns:
            Dictionary containing text analysis results
        """
        print("\n=== TEXT REGION ANALYSIS ===")
        
        # Look for text regions (dark areas on light background)
        text_mask = self.gray < 100
        text_pixels = np.sum(text_mask)
        
        print(f"Text pixels (dark): {text_pixels}")
        
        # Find contours of text regions
        contours, _ = cv2.findContours(text_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        text_regions = []
        for i, contour in enumerate(contours):
            x, y, w, h = cv2.boundingRect(contour)
            if w > 10 and h > 10:  # Filter out noise
                text_regions.append({
                    'index': i,
                    'position': (x, y),
                    'size': (w, h),
                    'area': w * h
                })
                print(f"Text region {i}: position ({x}, {y}), size {w}x{h}")
        
        text_analysis = {
            'total_text_pixels': int(text_pixels),
            'text_regions': text_regions
        }
        
        return text_analysis
    
    def analyze_grating_couplers(self) -> Dict[str, Any]:
        """Analyze grating couplers in the image.
        
        Returns:
            Dictionary containing grating coupler analysis results
        """
        print("\n=== GRATING COUPLER ANALYSIS ===")
        
        # Create mask for blue regions (grating couplers)
        blue_mask = np.zeros(self.gray.shape, dtype=np.uint8)
        for y in range(self.img_array.shape[0]):
            for x in range(self.img_array.shape[1]):
                pixel = self.img_array[y, x]
                # Check for medium blue or bright blue
                if (pixel[0] == 0 and pixel[1] == 64 and pixel[2] == 128) or \
                   (pixel[0] == 0 and pixel[1] == 0 and pixel[2] == 255):
                    blue_mask[y, x] = 255
        
        # Find contours in blue regions
        contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Sort by area and filter for significant shapes
        significant_contours = [(i, c, cv2.contourArea(c)) for i, c in enumerate(contours) if cv2.contourArea(c) > 100]
        significant_contours.sort(key=lambda x: x[2], reverse=True)
        
        print(f"Found {len(contours)} blue contours")
        print(f"Found {len(significant_contours)} significant grating couplers")
        
        grating_couplers = []
        
        for idx, (contour_idx, contour, area) in enumerate(significant_contours[:4]):  # Analyze top 4
            print(f"\nGRATING COUPLER {idx+1}:")
            print(f"  Contour index: {contour_idx}")
            print(f"  Area: {area:.0f} pixels")
            
            # Get bounding box
            x, y, w, h = cv2.boundingRect(contour)
            print(f"  Bounding box: ({x}, {y}) to ({x+w}, {y+h})")
            print(f"  Size: {w} x {h} pixels")
            
            # Find center
            moments = cv2.moments(contour)
            if moments['m00'] != 0:
                cx = int(moments['m10'] / moments['m00'])
                cy = int(moments['m01'] / moments['m00'])
                print(f"  Center of mass: ({cx}, {cy})")
                
                # Analyze the grating coupler direction using the method from our analysis
                direction, tip, vector, confidence = self._analyze_grating_coupler_direction(contour, cx, cy)
                
                print(f"  Grating coupler direction: {direction}")
                print(f"  Arrow tip: {tip}")
                print(f"  Vector: {vector}")
                print(f"  Confidence: {confidence:.3f}")
                
                grating_coupler = {
                    'index': idx + 1,
                    'contour_index': contour_idx,
                    'area': float(area),
                    'bounding_box': (x, y, w, h),
                    'center': (cx, cy),
                    'arrow_tip': tip,
                    'arrow_direction': direction,
                    'arrow_vector': vector,
                    'confidence': confidence
                }
                
                grating_couplers.append(grating_coupler)
        
        grating_analysis = {
            'total_contours': len(contours),
            'significant_contours': len(significant_contours),
            'grating_couplers': grating_couplers
        }
        
        return grating_analysis
    
    def _analyze_grating_coupler_direction(self, contour, cx, cy):
        """Analyze the direction a grating coupler is facing.
        
        Based on our analysis, grating couplers have a triangular/arrow shape where:
        - The "tip" is where the width/height is maximum
        - For horizontal grating couplers: analyze height distribution across x-coordinates
        - For vertical grating couplers: analyze width distribution across y-coordinates
        
        Args:
            contour: OpenCV contour of the grating coupler
            cx, cy: Center coordinates of the contour
            
        Returns:
            Tuple of (direction, tip, vector, confidence)
        """
        # Get all contour points
        points = contour.reshape(-1, 2)
        
        # Get bounding box to determine orientation
        bbox = cv2.boundingRect(contour)
        x, y, w, h = bbox
        aspect_ratio = w / h if h > 0 else 1
        
        x_coords = points[:, 0]
        y_coords = points[:, 1]
        
        # Determine if this is a horizontal or vertical grating coupler
        if aspect_ratio > 1.2:  # Horizontal (wider than tall)
            direction, tip, vector, confidence = self._analyze_horizontal_gc(points, cx, cy)
        elif aspect_ratio < 0.8:  # Vertical (taller than wide)
            direction, tip, vector, confidence = self._analyze_vertical_gc(points, cx, cy)
        else:  # Square-ish, try both methods and pick the best
            h_dir, h_tip, h_vec, h_conf = self._analyze_horizontal_gc(points, cx, cy)
            v_dir, v_tip, v_vec, v_conf = self._analyze_vertical_gc(points, cx, cy)
            
            if h_conf > v_conf:
                direction, tip, vector, confidence = h_dir, h_tip, h_vec, h_conf
            else:
                direction, tip, vector, confidence = v_dir, v_tip, v_vec, v_conf
        
        return direction, tuple(tip), vector, confidence
    
    def _analyze_horizontal_gc(self, points, cx, cy):
        """Analyze horizontal grating coupler by looking at height distribution across x-coordinates."""
        x_coords = points[:, 0]
        y_coords = points[:, 1]
        
        # Find the range of x-coordinates
        x_min, x_max = np.min(x_coords), np.max(x_coords)
        
        # Calculate height at each x-coordinate
        heights = {}
        for x in range(x_min, x_max + 1):
            y_vals = y_coords[x_coords == x]
            if len(y_vals) > 0:
                height = np.max(y_vals) - np.min(y_vals)
                heights[x] = height
        
        if not heights:
            return self._fallback_direction_analysis(contour, cx, cy)
        
        max_height_x = max(heights, key=heights.get)
        max_height = heights[max_height_x]
        
        # Determine direction based on where the tip is relative to center
        if max_height_x < cx:
            direction = 'LEFT'
        else:
            direction = 'RIGHT'
        
        # Find the actual tip point
        tip_points = points[(x_coords == max_height_x)]
        if len(tip_points) > 0:
            tip_distances = [np.sqrt((p[0] - cx)**2 + (p[1] - cy)**2) for p in tip_points]
            tip_idx = np.argmin(tip_distances)
            tip = tip_points[tip_idx]
        else:
            tip = (max_height_x, cy)
        
        vector = (tip[0] - cx, tip[1] - cy)
        
        # Calculate confidence
        other_heights = [h for x, h in heights.items() if x != max_height_x]
        if other_heights:
            avg_other_height = np.mean(other_heights)
            confidence = max_height / avg_other_height if avg_other_height > 0 else 1.0
        else:
            confidence = 1.0
        
        return direction, tip, vector, confidence
    
    def _analyze_vertical_gc(self, points, cx, cy):
        """Analyze vertical grating coupler by looking at width distribution across y-coordinates."""
        x_coords = points[:, 0]
        y_coords = points[:, 1]
        
        # Find the range of y-coordinates
        y_min, y_max = np.min(y_coords), np.max(y_coords)
        
        # Calculate width at each y-coordinate
        widths = {}
        for y in range(y_min, y_max + 1):
            x_vals = x_coords[y_coords == y]
            if len(x_vals) > 0:
                width = np.max(x_vals) - np.min(x_vals)
                widths[y] = width
        
        if not widths:
            return self._fallback_direction_analysis(contour, cx, cy)
        
        max_width_y = max(widths, key=widths.get)
        max_width = widths[max_width_y]
        
        # Determine direction based on where the tip is relative to center
        if max_width_y < cy:
            direction = 'UP'
        else:
            direction = 'DOWN'
        
        # Find the actual tip point
        tip_points = points[(y_coords == max_width_y)]
        if len(tip_points) > 0:
            tip_distances = [np.sqrt((p[0] - cx)**2 + (p[1] - cy)**2) for p in tip_points]
            tip_idx = np.argmin(tip_distances)
            tip = tip_points[tip_idx]
        else:
            tip = (cx, max_width_y)
        
        vector = (tip[0] - cx, tip[1] - cy)
        
        # Calculate confidence
        other_widths = [w for y, w in widths.items() if y != max_width_y]
        if other_widths:
            avg_other_width = np.mean(other_widths)
            confidence = max_width / avg_other_width if avg_other_width > 0 else 1.0
        else:
            confidence = 1.0
        
        return direction, tip, vector, confidence
    
    def _fallback_direction_analysis(self, contour, cx, cy):
        """Fallback method using extreme points."""
        points = contour.reshape(-1, 2)
        
        # Find extreme points
        leftmost = points[np.argmin(points[:, 0])]
        rightmost = points[np.argmax(points[:, 0])]
        topmost = points[np.argmin(points[:, 1])]
        bottommost = points[np.argmax(points[:, 1])]
        
        # Calculate distances
        distances = {
            'LEFT': np.sqrt((leftmost[0] - cx)**2 + (leftmost[1] - cy)**2),
            'RIGHT': np.sqrt((rightmost[0] - cx)**2 + (rightmost[1] - cy)**2),
            'UP': np.sqrt((topmost[0] - cx)**2 + (topmost[1] - cy)**2),
            'DOWN': np.sqrt((bottommost[0] - cx)**2 + (bottommost[1] - cy)**2)
        }
        
        direction = max(distances, key=distances.get)
        
        if direction == 'LEFT':
            tip = leftmost
        elif direction == 'RIGHT':
            tip = rightmost
        elif direction == 'UP':
            tip = topmost
        else:
            tip = bottommost
        
        vector = (tip[0] - cx, tip[1] - cy)
        confidence = 0.5  # Lower confidence for fallback method
        
        return direction, tuple(tip), vector, confidence
    
    def convert_to_layout_coordinates(self, image_x: int, image_y: int, 
                                    layout_origin: Tuple[int, int] = (10000, 10000)) -> Tuple[int, int]:
        """Convert image coordinates to layout coordinates.
        
        Args:
            image_x: X coordinate in image
            image_y: Y coordinate in image
            layout_origin: Origin point in layout coordinates (nm)
            
        Returns:
            Tuple of (layout_x, layout_y) in nanometers
        """
        # Simple conversion - may need adjustment based on actual layout scaling
        layout_x = layout_origin[0] + (image_x - self.img.size[0] // 2)
        layout_y = layout_origin[1] + (image_y - self.img.size[1] // 2)
        
        return layout_x, layout_y
    
    def full_analysis(self) -> Dict[str, Any]:
        """Perform complete analysis of the layout image.
        
        Returns:
            Dictionary containing all analysis results
        """
        print("=== COMPLETE PNG LAYOUT ANALYSIS ===")
        print(f"Analyzing: {self.image_path}")
        
        results = {
            'image_path': self.image_path,
            'colors': self.analyze_colors(),
            'shapes': self.analyze_shapes(),
            'text': self.analyze_text_regions(),
            'grating_couplers': self.analyze_grating_couplers()
        }
        
        print("\n=== ANALYSIS COMPLETE ===")
        return results


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='Analyze PNG images of photonic circuit layouts')
    parser.add_argument('image_path', help='Path to the PNG image file')
    parser.add_argument('--output', '-o', help='Output file for analysis results (JSON)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    try:
        analyzer = PNGLayoutAnalyzer(args.image_path)
        results = analyzer.full_analysis()
        
        if args.output:
            import json
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\nResults saved to: {args.output}")
        
    except Exception as e:
        print(f"Error analyzing image: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
