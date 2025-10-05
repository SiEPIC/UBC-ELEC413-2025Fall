#!/usr/bin/env python3
"""
Test script for grating coupler rotation detection

This script places grating couplers in all four rotations (0°, 90°, 180°, 270°)
and tests the PNG layout analyzer's ability to correctly detect their directions.
"""

import siepic_ebeam_pdk
import shutil
import socket
import os

# Configuration for the Technology to use
tech = "EBeam"

# SiEPIC-Tools initialization
import pya
from pya import *
import SiEPIC
from packaging.version import Version
from SiEPIC._globals import Python_Env, KLAYOUT_VERSION, KLAYOUT_VERSION_3
if Version(SiEPIC.__version__) < Version('0.5.14'):
    raise Exception ('This PDK requires SiEPIC-Tools v0.5.14 or greater.')
from SiEPIC import scripts  
from SiEPIC.utils import get_layout_variables
from SiEPIC.scripts import connect_pins_with_waveguide, connect_cell, zoom_out, export_layout
from SiEPIC.utils.layout import new_layout, floorplan
from SiEPIC.utils import get_technology_by_name
from SiEPIC.extend import to_itype
from pya import Trans, CellInstArray, Text

def create_test_layout():
    """Create a test layout with grating couplers in all four rotations."""
    
    top_cell_name = 'test_gc_rotations'
    filename_out = top_cell_name

    # Create a new layout
    top_cell, ly = new_layout(tech, top_cell_name, GUI=True, overwrite = True)
    layout = ly
    dbu = ly.dbu

    TECHNOLOGY = get_technology_by_name(tech)

    # Load grating coupler cell from library
    cell_ebeam_gc = ly.create_cell2('GC_TE_1310_8degOxide_BB', tech)

    # Floorplan for coordinate reference
    die_size = 1000e3  # 1mm die size
    die_edge = int(die_size/2)
    box = Box( Point(-die_edge, -die_edge), Point(die_edge, die_edge) )
    top_cell.shapes(ly.layer(TECHNOLOGY['FloorPlan'])).insert(box)

    # Place grating couplers in all four rotations
    positions = [
        (0, 0, "R0", "RIGHT"),      # 0° rotation - should face RIGHT
        (200e3, 0, "R90", "UP"),    # 90° rotation - should face UP  
        (0, 200e3, "R180", "LEFT"), # 180° rotation - should face LEFT
        (200e3, 200e3, "R270", "DOWN") # 270° rotation - should face DOWN
    ]
    
    expected_directions = ["RIGHT", "UP", "LEFT", "DOWN"]
    
    for i, (x, y, rotation, expected) in enumerate(positions):
        # Create transformation
        if rotation == "R0":
            t = Trans(Trans.R0, x, y)
        elif rotation == "R90":
            t = Trans(Trans.R90, x, y)
        elif rotation == "R180":
            t = Trans(Trans.R180, x, y)
        elif rotation == "R270":
            t = Trans(Trans.R270, x, y)
        
        # Place grating coupler
        instGC = top_cell.insert(CellInstArray(cell_ebeam_gc.cell_index(), t))
        
        # Add test label
        text = Text(f"GC_{i+1}_{rotation}_{expected}", Trans(Trans.R0, x, y))
        text.valign = Text.VAlignTop
        top_cell.shapes(ly.layer(TECHNOLOGY['Text'])).insert(text).text_size = 5/dbu

    # Export for fabrication
    path = os.path.dirname(os.path.realpath(__file__))
    filename = filename_out
    file_out = export_layout(top_cell, path, filename, relative_path = '.', format='oas', screenshot=True)

    from SiEPIC._globals import Python_Env
    if Python_Env == "Script":
        from SiEPIC.utils import klive
        klive.show(file_out, technology=tech)

    # Create an image of the layout
    top_cell.image(os.path.join(path,filename+'.png'))
    
    return file_out

def test_direction_detection():
    """Test the direction detection on the generated layout."""
    
    print("=== TESTING GRATING COUPLER DIRECTION DETECTION ===")
    
    # Create test layout
    print("Creating test layout with 4 grating couplers in different rotations...")
    layout_file = create_test_layout()
    
    # Analyze the generated PNG
    print("\nAnalyzing generated PNG...")
    from png_layout_analyzer import PNGLayoutAnalyzer
    
    png_file = layout_file.replace('.oas', '.png')
    analyzer = PNGLayoutAnalyzer(png_file)
    results = analyzer.full_analysis()
    
    # Check results
    grating_couplers = results['grating_couplers']['grating_couplers']
    expected_directions = ["RIGHT", "UP", "LEFT", "DOWN"]
    
    print(f"\n=== DIRECTION DETECTION RESULTS ===")
    print(f"Expected directions: {expected_directions}")
    print(f"Detected {len(grating_couplers)} grating couplers")
    
    correct_detections = 0
    for i, gc in enumerate(grating_couplers):
        detected_direction = gc['arrow_direction']
        expected_direction = expected_directions[i] if i < len(expected_directions) else "UNKNOWN"
        confidence = gc['confidence']
        
        is_correct = detected_direction == expected_direction
        if is_correct:
            correct_detections += 1
        
        status = "✓ CORRECT" if is_correct else "✗ WRONG"
        print(f"GC {i+1}: {detected_direction} (expected: {expected_direction}) - {status} (confidence: {confidence:.3f})")
    
    accuracy = correct_detections / len(grating_couplers) * 100
    print(f"\nOverall accuracy: {correct_detections}/{len(grating_couplers)} = {accuracy:.1f}%")
    
    if accuracy == 100:
        print("🎉 All directions detected correctly!")
    else:
        print("⚠️  Some directions were detected incorrectly. Check the algorithm.")
    
    return accuracy == 100

if __name__ == "__main__":
    success = test_direction_detection()
    exit(0 if success else 1)
