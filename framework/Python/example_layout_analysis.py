#!/usr/bin/env python3
"""
Example script demonstrating how to use the PNG Layout Analyzer

This script shows how to use the PNGLayoutAnalyzer class to analyze
photonic circuit layouts and extract specific information.
"""

from png_layout_analyzer import PNGLayoutAnalyzer
import json


def analyze_grating_coupler_layout(image_path: str):
    """Analyze a grating coupler layout and extract key information.
    
    Args:
        image_path: Path to the PNG image file
    """
    print(f"Analyzing grating coupler layout: {image_path}")
    
    # Create analyzer instance
    analyzer = PNGLayoutAnalyzer(image_path)
    
    # Perform full analysis
    results = analyzer.full_analysis()
    
    # Extract key information
    grating_couplers = results['grating_couplers']['grating_couplers']
    
    print(f"\n=== GRATING COUPLER SUMMARY ===")
    print(f"Found {len(grating_couplers)} grating couplers")
    
    for i, gc in enumerate(grating_couplers):
        print(f"\nGrating Coupler {i+1}:")
        print(f"  Arrow tip position: {gc['arrow_tip']}")
        print(f"  Arrow direction: {gc['arrow_direction']}")
        print(f"  Arrow vector: {gc['arrow_vector']}")
        
        # Convert to layout coordinates
        layout_x, layout_y = analyzer.convert_to_layout_coordinates(
            gc['arrow_tip'][0], gc['arrow_tip'][1]
        )
        print(f"  Layout coordinates: ({layout_x}, {layout_y}) nm")
        print(f"  Layout coordinates: ({layout_x/1000:.1f}, {layout_y/1000:.1f}) μm")
    
    # Save detailed results
    output_file = image_path.replace('.png', '_analysis.json')
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed analysis saved to: {output_file}")
    
    return results


def main():
    """Main function."""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python example_layout_analysis.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    try:
        results = analyze_grating_coupler_layout(image_path)
        
        # Print color summary
        print(f"\n=== COLOR SUMMARY ===")
        for color_name, color_info in results['colors']['color_breakdown'].items():
            if color_info['percentage'] > 0.1:  # Only show significant colors
                print(f"{color_name}: {color_info['percentage']:.1f}%")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
