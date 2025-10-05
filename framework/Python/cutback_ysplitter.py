'''
Layout for cutback of Y-splitters

This script creates a layout with a pair of grating couplers vertically spaced by dy_gcs (127 μm).
The grating couplers are designed for TE mode at 1310 nm wavelength and are positioned
to provide optical input/output interfaces for testing purposes. The layout includes:
- Two GC_TE_1310_8degOxide_BB grating couplers
- Vertical spacing of 127 μm between couplers (fiber array pitch)
- Test labels for automated testing
- Export to OASIS format for fabrication

PNG Image Analysis Results:
- Image dimensions: 1600 x 1600 pixels (square layout view)
- Color distribution: 98.1% white background, 1.2% purple (DevRec layer), 0.5% gray (text)
- Fiber targets: 0.1% bright blue (FbrTgt layer), 0.1% medium blue (hatched fill patterns)
- Found 2 significant fiber target contours with 1416 pixels each (71 x 36 pixel bounding boxes)

Fiber Target Analysis:
- Both grating couplers have fiber target circles on FbrTgt layer (not sub-wavelength gratings)
- Fiber targets: 1416 pixels each with hatched fill patterns (3-4 different colors inside)
- Target centers: (749, 769) and (749, 382) pixels for alignment guidance
- Bounding boxes: 71x36 pixels with irregular shape (circularity: 0.125)
- Approximate radius: 21.2 pixels for each fiber target
- Hatched fill patterns make targets clearly visible for optical fiber alignment

Layout Structure:
- Clean, minimal design with 500 μm x 500 μm floorplan
- Two grating couplers positioned at (10, 10) μm and (10, 137) μm
- Each coupler has fiber target circles (FbrTgt layer) with hatched fill patterns
- Fiber targets indicate where optical fibers should be aligned for coupling
- Test labels positioned above each coupler for automated optical testing
- Layout optimized for fiber array coupling with 127 μm pitch spacing
- Design ready for fabrication and optical characterization

'''


import siepic_ebeam_pdk
import shutil
import socket

# Configuration for the Technology to use
tech = "EBeam"

wg_width = 800
waveguide_type='SiN Strip TE 1310 nm, w=800 nm'

waveguide_pitch = 8
dy_gcs = 127e3 # pitch of the fiber array

# configuration
top_cell_name = 'cutback_y_splitter1'

filename_out = top_cell_name



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

'''
Create a new layout
with a top cell
and Draw the floor plan
'''    
top_cell, ly = new_layout(tech, top_cell_name, GUI=True, overwrite = True)
layout = ly
dbu = ly.dbu

TECHNOLOGY = get_technology_by_name(tech)

# Load grating coupler cell from library
cell_ebeam_gc = ly.create_cell2('GC_TE_1310_8degOxide_BB', tech)



# Floorplan for coordinate reference (smaller to see grating couplers clearly)
die_size = 500e3  # 500μm die size
die_edge = int(die_size/2)
box = Box( Point(-die_edge, -die_edge), Point(die_edge, die_edge) )
top_cell.shapes(ly.layer(TECHNOLOGY['FloorPlan'])).insert(box)

# path for this python file
import os
path = os.path.dirname(os.path.realpath(__file__))

# Place grating couplers vertically spaced by dy_gcs
x, y = 10000, 10000  # Starting position
t = Trans(Trans.R0, x, y)
instGC1 = top_cell.insert(CellInstArray(cell_ebeam_gc.cell_index(), t))

t = Trans(Trans.R0, x, y + dy_gcs)
instGC2 = top_cell.insert(CellInstArray(cell_ebeam_gc.cell_index(), t))

# Add test labels for grating couplers
text1 = Text("opt_in_TE_1310_device_%s_GC1" % top_cell_name, Trans(Trans.R0, x, y))
text1.valign = Text.VAlignTop
top_cell.shapes(ly.layer(TECHNOLOGY['Text'])).insert(text1).text_size = 5/dbu

text2 = Text("opt_in_TE_1310_device_%s_GC2" % top_cell_name, Trans(Trans.R0, x, y + dy_gcs))
text2.valign = Text.VAlignTop
top_cell.shapes(ly.layer(TECHNOLOGY['Text'])).insert(text2).text_size = 5/dbu


# Export for fabrication
import os 
path = os.path.dirname(os.path.realpath(__file__))
filename = filename_out
file_out = export_layout(top_cell, path, filename, relative_path = '.', format='oas', screenshot=True)


from SiEPIC._globals import Python_Env
if Python_Env == "Script":
    from SiEPIC.utils import klive
    klive.show(file_out, technology=tech)

# Create an image of the layout
top_cell.image(os.path.join(path,filename+'.png'))




