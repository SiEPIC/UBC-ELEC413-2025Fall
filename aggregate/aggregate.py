
'''
Script to create a layout:

DFB Laser integrated with Photonic Wire Bonds
Splitter tree using 1x2 splitters
Aggregating submitted designs

by Lukas Chrostowski, Sheri, 2022-2025
 
using SiEPIC-Tools

For more information on scripting:
  https://github.com/SiEPIC/SiEPIC-Tools/wiki/Scripted-Layout
  
usage:
 - run this script, inside KLayout Application, or externally using PyPI package
   - requires siepicfab_ebeam_zep PyPI package 

Install the PDK for develpers:
# cd ... GitHub/SiEPICfab-EBeam-ZEP-PDK
# pip install -e .

DESCRIPTION:
============

This script creates a multi-laser photonic integrated circuit layout by:

1. LOADING SUBMISSIONS:
   - Loads all GDS/OAS files from the submissions folder
   - Categorizes designs by course (ELEC413, edXphot1x, openEBL, SiEPIC_Passives)
   - Processes each design and creates sub-cells with proper layer filtering
   - Handles DBU correction and scaling if needed

2. POWER MONITOR INTEGRATION:
   - Finds the ELEC413_power_monitor.gds file in submissions
   - Reorganizes the course_cells list to include power monitor copies
   - Places one power monitor per laser circuit at calculated positions:
     * Laser circuit 0: position 0
     * Laser circuit 1: position 16 (1 * tree_depth^2)
     * Laser circuit 2: position 32 (2 * tree_depth^2)

3. LASER CIRCUIT CREATION:
   - Creates individual sub-cells for each laser circuit (laser_circuit_0, laser_circuit_1, laser_circuit_2)
   - Each laser circuit contains:
     * DFB laser with heater and bond pads
     * Metal routing for electrical connections
     * 1x2 splitter tree (depth 4, 16 outputs)
     * Student designs (up to 16 per laser circuit)
     * Power monitor (1 per laser circuit)
     * Terminators for unused splitter outputs

4. WAVEGUIDE CONNECTIONS:
   - Connects laser to heater with waveguide
   - Connects heater to splitter tree input
   - Routes waveguides from splitter outputs to student designs
   - Uses SiN waveguides (800 nm width) for routing
   - Implements proper waveguide routing with turtle graphics

5. LAYOUT ORGANIZATION:
   - Arranges student designs in a 2D grid (4x4 per laser circuit)
   - Handles chip cutouts for PCM (Process Control Monitor)
   - Manages proper spacing and positioning
   - Creates final aggregated layout with all components

CONFIGURATION:
==============

Key parameters:
- n_lasers: Number of laser circuits (default: 3)
- tree_depth: Splitter tree depth (default: 4, gives 16 outputs)
- die_size: Chip size (default: 8.78e6 nm)
- cell_Width/Height: Individual design cell size (800k x 500k nm)
- wg_width: Waveguide width for routing (800 nm)
- waveguide_type: Technology-specific waveguide types

OUTPUT:
=======

- Shuksan.oas: Main layout file
- Shuksan.png: Layout screenshot
- Shuksan.txt: Processing log
- Individual laser circuit cells for debugging

The script automatically copies output files to the SiEPIC_Shuksan_ANT_SiN_2025_08 
submissions folder when running on the designated development machine.

RECENT MODIFICATIONS:
====================

- Added power monitor integration (one per laser circuit)
- Implemented laser circuit sub-cell architecture
- Added waveguide width configuration variable
- Improved pin placement for student designs
- Enhanced logging and error handling

 
'''

import siepic_ebeam_pdk
import shutil
import socket

# Debugging run, or complete
draw_waveguides = True
run_number_designs = 100

# Configuration for the Technology to use
tech = "EBeam"

# Configuration for the arrangement
n_lasers = 3
tree_depth = 4 
die_size = 8.78e6
die_edge = die_size/2

wg_width = 800
waveguide_type={'SiEPICfab_Shuksan_PDK':'Strip TE 1310 nm, w=350 nm', 
                'SiEPICfab_EBeam_ZEP':'Strip TE 1310 nm, w=350 nm (core-clad)',
                'EBeam':'SiN Strip TE 1310 nm, w=800 nm'}
waveguide_type_routing=f'SiN Strip TE 1310 nm, w={wg_width} nm'

blank_design = "ELEC413_lukasc"  # Python design file, otherwise None for terminator.

waveguide_pitch = 8
dy_gcs = 127e3 # pitch of the fiber array
pad_pitch = 250000
metal_width = 20000
metal_width_laser = 50000
metal_width_laser_heater = 20000
laser_heater_distance = 500e3
wg_heater_length = 500
# Default port position - will be dynamically determined for each design
student_laser_in_y = 250e3
laser_pad_distance = 400e3

def find_port_sin_cell_and_position(cell, log_func=None, visited_cells=None):
    """
    Find the first port_SiN instance in a cell and return both the cell and its y-coordinate.
    Searches recursively through all levels of the cell hierarchy.
    
    Args:
        cell: The cell to search for port_SiN instances
        log_func: Optional logging function
        visited_cells: Set to track visited cells and prevent infinite recursion
        
    Returns:
        tuple: (port_cell, y_position) or (None, None) if not found
    """
    if visited_cells is None:
        visited_cells = set()
    
    # Prevent infinite recursion by tracking visited cells
    if cell.cell_index() in visited_cells:
        return None, None
    visited_cells.add(cell.cell_index())
    
    if log_func:
        log_func(f"Searching for port_SiN instances in cell: {cell.name}")
    
    # Search through all direct cell instances
    for inst in cell.each_inst():
        # Check if the cell name contains "port_SiN"
        if "port_SiN" in inst.cell.name:
            # Get the transformed bounding box to find the y position
            bbox = inst.bbox()
            y_position = bbox.center().y
            if log_func:
                log_func(f"Found port_SiN instance '{inst.cell.name}' at y={y_position}")
            return inst.cell, y_position
    
    # If no port_SiN found in direct instances, recursively search in sub-cells
    for inst in cell.each_inst():
        # Recursively search in the sub-cell
        port_cell, y_position = find_port_sin_cell_and_position(inst.cell, log_func, visited_cells)
        if port_cell is not None:
            return port_cell, y_position
    
    if log_func:
        log_func(f"No port_SiN instances found in cell: {cell.name}")
    return None, None
ground_wire_width = 20e3  # on the edge of the chip
trench_bondpad_offset = 20e3

# configuration
top_cell_name = 'Shuksan_2025_10_SiN'
cell_Width = 800000
cell_Height = 500000
cell_Gap_Width = 8000
cell_Gap_Height = 8000
cells_rows_per_laser = 4 
cells_columns_per_laser = 4
height_PCM = 1.5e6  # reserve this space at the bottom of the chip
laser_dy = (die_size-height_PCM) / (n_lasers) # spread out evenly
laser_y = -die_size/2 + height_PCM  + 1250e3
laser_x = -die_edge  # Align laser left edge with die left edge
laser_design_offset = 3e6 # distance from the laser to the student design
chip_Width = 8650000
chip_Height1 = 8490000
chip_Height2 = 8780000
br_cutout_x = 7484000
br_cutout_y = 898000
br_cutout2_x = 7855000
br_cutout2_y = 5063000
tr_cutout_x = 7037000
tr_cutout_y = 8494000

filename_out = 'Shuksan'
layers_keep = ['1/99', '4/0', '11/0', '12/0', '13/0','1/10', '68/0', '81/0', '10/0', '99/0', '200/0', '131/155', '201/0', '998/0']

def is_running_on_lukasc_air():
    """Check if the script is running on lukasc@Lukass-Air computer."""
    try:
        hostname = socket.gethostname()
        print(f"Hostname: {hostname}")
        return "Lukass-" in hostname
    except:
        return False

is_running_on_lukasc_air()

def copy_to_shuksan_designs_folder(file_path):
    """Copy the output file to SiEPIC_Shuksan_ANT_SiN_2025_08/designs folder if running on specific computer."""
    if not is_running_on_lukasc_air():
        return
    
    target_dir = "/Users/lukasc/Documents/GitHub/SiEPIC_Shuksan_ANT_SiN_2025_08/submissions/9x9"
    
    if not os.path.exists(target_dir):
        print(f"Warning: Target directory {target_dir} does not exist")
        return
    
    try:
        # Copy the file
        shutil.copy2(file_path, target_dir)
        
        print(f"Copied {filename} to {target_dir}")
                
    except Exception as e:
        print(f"Error copying files to Shuksan designs folder: {e}")
        
layer_text = '10/0'
layer_SEM = '200/0'
layer_SEM_allow = ['edXphot1x', 'ELEC413','SiEPIC_Passives']  # which submission folder is allowed to include SEM images
layers_move = [[[31,0],[1,0]]] # move shapes from layer 1 to layer 2
dbu = 0.001
log_siepictools = True
framework_file =  'shuksan_pcm'
ubc_file = None # 'UBC_static.oas'


# record processing time
import time
start_time = time.time()
from datetime import datetime
now = datetime.now()




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

'''
Create a new layout
with a top cell
and Draw the floor plan
'''    
top_cell, ly = new_layout(tech, top_cell_name, GUI=True, overwrite = True)
layout = ly
dbu = ly.dbu
layerText = pya.LayerInfo(int(layer_text.split('/')[0]), int(layer_text.split('/')[1]))
layerTextN = top_cell.layout().layer(layerText)

TECHNOLOGY = get_technology_by_name(tech)
if TECHNOLOGY['technology_name'] not in tech or not tech in pya.Technology.technology_names():
    raise Exception ('This example needs to be executed in a layout with Technology = %s' % tech)
else:
    waveguide_type = waveguide_type[tech]


'''
# Floorplan
die_edge = int(die_size/2)
box = Box( Point(-die_edge, -die_edge), Point(die_edge, die_edge) )
top_cell.shapes(ly.layer(TECHNOLOGY['FloorPlan'])).insert(box)
'''

def disable_libraries():
    print('Disabling KLayout libraries')
    for l in pya.Library().library_ids():
        print(' - %s' % pya.Library().library_by_id(l).name())
        pya.Library().library_by_id(l).delete()
def enable_libraries():
    import siepic_ebeam_pdk
    from importlib import reload  
    siepic_ebeam_pdk = reload(siepic_ebeam_pdk)
    siepic_ebeam_pdk.pymacros = reload(siepic_ebeam_pdk.pymacros)



# path for this python file
import os
path = os.path.dirname(os.path.realpath(__file__))

# Log file
global log_file
log_file = open(os.path.join(path,filename_out+'.txt'), 'w')
def log(text):
    global log_file
    log_file.write(text)
    log_file.write('\n')

log('SiEPIC-Tools %s, layout merge, running KLayout 0.%s.%s ' % (SiEPIC.__version__, KLAYOUT_VERSION,KLAYOUT_VERSION_3) )
current_time = now.strftime("%Y-%m-%d, %H:%M:%S local time")
log("Date: %s" % current_time)

# Load all the GDS/OAS files from the "submissions" folder:
path2 = os.path.abspath(os.path.join(path,"../submissions"))
files_in = []
_, _, files = next(os.walk(path2), (None, None, []))
for f in sorted(files):
    files_in.append(os.path.join(path2,f))

# Load all the GDS/OAS files from the "framework" folder:
path2 = os.path.abspath(os.path.join(path,"../framework"))
_, _, files = next(os.walk(path2), (None, None, []))
for f in sorted(files):
    files_in.append(os.path.join(path2,f))

# Create course cells using the folder name under the top cell
cell_edXphot1x = layout.create_cell("edX")
t = Trans(Trans.R0, 0,0)
top_cell.insert(CellInstArray(cell_edXphot1x.cell_index(), t))
cell_ELEC413 = layout.create_cell("ELEC413")
top_cell.insert(CellInstArray(cell_ELEC413.cell_index(), t))
cell_SiEPIC_Passives = layout.create_cell("SiEPIC_Passives")
top_cell.insert(CellInstArray(cell_SiEPIC_Passives.cell_index(), t))
cell_openEBL = layout.create_cell("openEBL")
top_cell.insert(CellInstArray(cell_openEBL.cell_index(), t))

# Create a date	stamp cell, and add a text label
merge_stamp = '.merged:'+now.strftime("%Y-%m-%d-%H:%M:%S")
cell_date = layout.create_cell(merge_stamp)
text = Text (merge_stamp, Trans(Trans.R0, 0, 0) )
shape = cell_date.shapes(layout.layer(10,0)).insert(text)
top_cell.insert(CellInstArray(cell_date.cell_index(), t))   


# Load all the layouts, without the libraries (no PCells)
disable_libraries()
# Origins for the layouts
x,y = 2.5e6,cell_Height+cell_Gap_Height
design_count = 0
subcell_instances = []
course_cells = []  # list of each of the student designs
cells_course = []  # into which course cell the design should go into
student_port_positions = []  # list of port y-positions for each student design
import subprocess
import pandas as pd
for f in [f for f in files_in if '.oas' in f.lower() or '.gds' in f.lower()]:
    basefilename = os.path.basename(f)

    # GitHub Action gets the actual time committed.  This can be done locally
    # via git restore-mtime.  Then we can load the time from the file stamp

    filedate = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y%m%d_%H%M")
    log("\nLoading: %s, dated %s" % (os.path.basename(f), filedate))

    # Tried to get it from GitHub but that didn't work:
    # get the time the file was last updated from the Git repository 
    # a = subprocess.run(['git', '-C', os.path.dirname(f), 'log', '-1', '--pretty=%ci',  basefilename], stdout = subprocess.PIPE) 
    # filedate = pd.to_datetime(str(a.stdout.decode("utf-8"))).strftime("%Y%m%d_%H%M")
    #filedate = os.path.getctime(os.path.dirname(f)) # .strftime("%Y%m%d_%H%M")
    
  
    # Load layout  
    layout2 = pya.Layout()
    layout2.read(f)

    if 'elec413' in basefilename.lower():
        course = 'ELEC413'
    elif 'ebeam' in basefilename.lower():
        course = 'edXphot1x'
    elif 'openebl' in basefilename.lower():
        course = 'openEBL'
    elif 'siepic_passives' in basefilename.lower():
        course = 'SiEPIC_Passives'
    else:
        course = 'openEBL'

    cell_course = eval('cell_' + course)
    log("  - course name: %s" % (course) )

    # Check the DBU Database Unit, in case someone changed it, e.g., 5 nm, or 0.1 nm.
    if round(layout2.dbu,10) != dbu:
        log('  - WARNING: The database unit (%s dbu) in the layout does not match the required dbu of %s.' % (layout2.dbu, dbu))
        print('  - WARNING: The database unit (%s dbu) in the layout does not match the required dbu of %s.' % (layout2.dbu, dbu))
        # Step 1: change the DBU to match, but that magnifies the layout
        wrong_dbu = layout2.dbu
        layout2.dbu = dbu
        # Step 2: scale the layout
        try:
            # determine the scaling required
            scaling = round(wrong_dbu / dbu, 10)
            layout2.transform (pya.ICplxTrans(scaling, 0, False, 0, 0))
            log('  - WARNING: Database resolution has been corrected and the layout scaled by %s' % scaling) 
        except:
            print('ERROR IN EBeam_merge.py: Incorrect DBU and scaling unsuccessful')
    
    # check that there is one top cell in the layout
    num_top_cells = len(layout2.top_cells())
    if num_top_cells > 1:
        log('  - layout should only contain one top cell; contains (%s): %s' % (num_top_cells, [c.name for c in layout2.top_cells()]) )
    if num_top_cells == 0:
        log('  - layout does not contain a top cell')

    # Find the top cell
    for cell in layout2.top_cells():
        if framework_file in os.path.basename(f) :
            # Create sub-cell using the filename under top cell
            subcell2 = layout.create_cell(os.path.basename(f)+"_"+filedate)
            t = Trans(Trans.M90, 0,0)
            top_cell.insert(CellInstArray(subcell2.cell_index(), t))
            # copy
            subcell2.copy_tree(layout2.cell(cell.name)) 
            break

        if os.path.basename(f) == ubc_file:
            # Create sub-cell using the filename under top cell
            subcell2 = layout.create_cell(os.path.basename(f)+"_"+filedate)
            t = Trans(Trans.R0, 8780000,8780000)      
            top_cell.insert(CellInstArray(subcell2.cell_index(), t))
            # copy
            subcell2.copy_tree(layout2.cell(cell.name)) 
            break


        if num_top_cells == 1 or cell.name.lower() == 'top' or cell.name.lower() == 'EBeam_':
            log("  - top cell: %s" % cell.name)

            # check layout height
            if cell.bbox().top < cell.bbox().bottom:
                log(' - WARNING: empty layout. Skipping.')
                break
                
            # Create sub-cell using the filename under course cell
            subcell2 = layout.create_cell(os.path.basename(f)+"_"+filedate)
            course_cells.append(subcell2)

            
            # Clear extra layers
            layers_keep2 = [layer_SEM] if course in layer_SEM_allow else []
            for li in layout2.layer_infos():
                if li.to_s() in layers_keep + layers_keep2:
                    log('  - loading layer: %s' % li.to_s())
                else:
                    log('  - deleting layer: %s' % li.to_s())
                    layer_index = layout2.find_layer(li)
                    layout2.delete_layer(layer_index)
                    
            # Delete non-text geometries in the Text layer
            layer_index = layout2.find_layer(int(layer_text.split('/')[0]), int(layer_text.split('/')[1]))
            if type(layer_index) != type(None):
                s = cell.begin_shapes_rec(layer_index)
                shapes_to_delete = []
                while not s.at_end():
                    if s.shape().is_text():
                        text = s.shape().text.string
                        if text.startswith('SiEPIC-Tools'):
                            if log_siepictools:
                                log('  - %s' % s.shape() )
                            s.shape().delete()
                            subcell2.shapes(layerTextN).insert(pya.Text(text, 0, 0))
                        elif text.startswith('opt_in'):
                            log('  - measurement label: %s' % text )
                    else:
                        shapes_to_delete.append( s.shape() )
                    s.next()
                for s in shapes_to_delete:
                    s.delete()

            # bounding box of the cell
            bbox = cell.bbox()
            log('  - bounding box: %s' % bbox.to_s() )
                            
            # Create sub-cell under subcell cell, using user's cell name
            subcell = layout.create_cell(cell.name)
            t = Trans(Trans.R0, -bbox.left,-bbox.bottom)
            subcell_inst = subcell2.insert(CellInstArray(subcell.cell_index(), t)) 
            subcell_instances.append (subcell_inst)
        
            # clip cells
            cell2 = layout2.clip(cell.cell_index(), pya.Box(bbox.left,bbox.bottom,bbox.left+cell_Width,bbox.bottom+cell_Height))
            bbox2 = layout2.cell(cell2).bbox()
            if bbox != bbox2:
                log('  - WARNING: Cell was clipped to maximum size of %s X %s' % (cell_Width, cell_Height) )
                log('  - clipped bounding box: %s' % bbox2.to_s() )

            # copy
            subcell.copy_tree(layout2.cell(cell2))  
            
            log('  - Placed at position: %s, %s' % (x,y) )
            
            # Find the actual port cell and position in the student design
            port_cell, port_y = find_port_sin_cell_and_position(subcell, log_func=log)
            if port_cell is not None and port_y is not None:
                # Use the actual port position relative to the cell origin
                actual_port_y = int(port_y - bbox.bottom)  # Adjust for cell origin
                log(f"  - Using dynamic port position: y={actual_port_y}")
                
                # Add pin directly to the port cell
                from SiEPIC.utils.layout import make_pin
                # Calculate pin position relative to the port cell's origin
                port_bbox = port_cell.bbox()
                pin_x = int(port_bbox.left - port_bbox.left)  # Left edge of the cell (x=0)
                pin_y = int(0)  # Middle vertically (y=0)
                make_pin(port_cell, 'opt_laser', [pin_x, pin_y], wg_width, 'PinRec', 180, debug=False)
                log(f"  - Added pin to port cell '{port_cell.name}' at left edge, middle vertically [{pin_x}, {pin_y}]")
            else:
                # Fall back to default position in the subcell2
                actual_port_y = int(student_laser_in_y)
                log(f"  - No port_SiN found, using default position: y={actual_port_y}")
                
                # add a pin so we can connect a waveguide from the laser tree  
                from SiEPIC.utils.layout import make_pin
                make_pin(subcell2, 'opt_laser', [0, actual_port_y], wg_width, 'PinRec', 180, debug=False)
            
            # Store the port position for later use in waveguide connections
            student_port_positions.append(actual_port_y)
                          
            design_count += 1
            cells_course.append (cell_course)
         

# Enable libraries, to create waveguides, laser, etc
enable_libraries()

# Find the cell with "power_monitor" in name, where cell names are course_cells[d].name, 
# move it to position 0 in course_cells[],
# then copy and insert the cell in course_cells[] so that it appears at positions:
# row*tree_depth**2
# Find power monitor cell and reorganize course_cells list
power_monitor_index = None
for i, cell in enumerate(course_cells):
    if "power_monitor" in cell.name.lower():
        power_monitor_index = i
        log("Found power monitor cell at index %d: %s" % (i, cell.name))
        break

if power_monitor_index is not None:
    # Move power monitor to position 0
    power_monitor_cell = course_cells.pop(power_monitor_index)
    power_monitor_port_pos = student_port_positions.pop(power_monitor_index)
    #course_cells.insert(0, power_monitor_cell)
    log("Popped power monitor cell")
    
    # Create copies of power monitor for each laser circuit
    for row in range(n_lasers):
        course_cells.insert(row * tree_depth**2, power_monitor_cell)
        student_port_positions.insert(row * tree_depth**2, power_monitor_port_pos)
        log("Created power monitor copy for laser circuit %d at position %d" % (row, row * tree_depth**2))
else:
    log("WARNING: No power monitor cell found in course_cells")


# load the cells from the PDK
if tech == "EBeam":
    library = "EBeam-SiN"
    library_beta = "SiEPICfab_EBeam_ZEP_Beta"
    library_dream = "EBeam-Dream"
    # library_ubc = "SiEPICfab_EBeam_ZEP_UBC"
    from SiEPIC.utils import create_cell2
    
    cell_y = create_cell2(ly, 'ebeam_YBranch_te1310', library)
    #cell_splitter = ly.create_cell('splitter_2x2_1310', library)
    cell_heater = ly.create_cell('wg_heater', library, 
                                 {'length': wg_heater_length,
                                  'waveguide_type': waveguide_type,
                                      })
    #cell_waveguide = ly.create_cell('ebeam_pcell_taper',library, {
        #'wg_width1': 0.35,
        #'wg_width2': 0.352})
    #cell_waveguide = ly.create_cell('Waveguide_Straight',library_beta, {
    #    'wg_length': 40,
    #    'wg_width': 350})
    # cell_waveguide = ly.create_cell('w_straight',library)
    cell_pad = ly.create_cell('ebeam_BondPad', library)
    #cell_gcA = ly.create_cell('GC_Air_te1310_BB', library)
    #cell_gcB = ly.create_cell('GC_Air_te1310_BB', library)
    cell_terminator = create_cell2(ly, 'ebeam_terminator_SiN_1310', library)
    cell_laser = create_cell2(ly, 'ebeam_dream_Laser_SiN_1310_Bond_BB', library_dream)
    metal_layer = "M2_router"
    #cell_taper = ly.create_cell('ebeam_taper_350nm_2000nm_te1310', library_beta)

if not cell_y:
    raise Exception ('Cannot load 1x2 splitter cell; please check the script carefully.')
if not cell_heater:
    raise Exception ('Cannot load waveguide heater cell; please check the script carefully.')
#if not cell_splitter:
#    raise Exception ('Cannot load 2x2 splitter cell; please check the script carefully.')
#if not cell_taper:
#    raise Exception ('Cannot load taper cell; please check the script carefully.')
#if not cell_gcA:
#    raise Exception ('Cannot load grating coupler cell; please check the script carefully.')
#if not cell_gcB:
#    raise Exception ('Cannot load grating coupler cell; please check the script carefully.')
if not cell_terminator:
    raise Exception ('Cannot load terminator cell; please check the script carefully.')
if not cell_laser:
    raise Exception ('Cannot load laser cell; please check the script carefully.')
if not cell_pad:
    raise Exception ('Cannot load bond pad cell; please check the script carefully.')
#if not cell_waveguide:
#    raise Exception ('Cannot load Waveguide Straight cell; please check the script carefully.')

# Waveguide type:
waveguides = ly.load_Waveguide_types()
waveguide1 = [w for w in waveguides if w['name']==waveguide_type]
if type(waveguide1) == type([]) and len(waveguide1)>0:
    waveguide = waveguide1[0]
else:
    waveguide = waveguides[0]
    print('error: waveguide type not found in PDK waveguides')
    raise Exception('error: waveguide type (%s) not found in PDK waveguides: \n%s' % (waveguide_type, [w['name'] for w in waveguides]))
radius_um = float(waveguide['radius'])
print('*** radius_um: %s' % radius_um)
radius = to_itype(waveguide['radius'],ly.dbu)


# laser_height = cell_laser.bbox().height()

# Laser circuits:
inst_tree_out_all = []
laser_circuit_cells = []

for row in range(0, n_lasers):
    
    # Create sub-cell for each laser circuit
    laser_circuit_cell = layout.create_cell("laser_circuit_%d" % row)
    laser_circuit_cells.append(laser_circuit_cell)
    
    # laser, place at absolute position in the laser circuit sub-cell
    # Align laser left edge with die left edge
    laser_x_aligned = laser_x - cell_laser.bbox().left
    t = pya.Trans.from_s('r0 %s,%s' % (int(laser_x_aligned), int(laser_y)) )
    inst_laser = laser_circuit_cell.insert(pya.CellInstArray(cell_laser.cell_index(), t))
    
    # heater, attach to the laser, then move it slight away from the laser
    inst_heater =connect_cell(inst_laser, 'opt1', cell_heater, 'opt1')
    inst_heater.transform(pya.Trans(laser_heater_distance, 0))
    connect_pins_with_waveguide(inst_laser, 'opt1', inst_heater, 'opt1', waveguide_type=waveguide_type, turtle_A=[radius_um,90]) #turtle_B=[10,-90, 100, 90])

    # Bond pad parameters
    pad_pitch = 150e3
    laser_pad_distance = 200e3
    metal_width = 20e3
    
    # Calculate bond pad positions aligned to left edge
    bondpads_x_offset = inst_laser.bbox().left + cell_pad.bbox().width()/2 + ground_wire_width + trench_bondpad_offset
    bondpads_y = inst_laser.bbox().top + laser_pad_distance + cell_pad.bbox().height()/2
    
    # Bond pad for the laser top contact, and route to the left edge
    x_laser_top_contact = -380e3  # Position relative to laser cell right edge
    t = pya.Trans(inst_laser.trans.disp.x + x_laser_top_contact, bondpads_y)
    inst_padL1 = laser_circuit_cell.insert(pya.CellInstArray(cell_pad.cell_index(), t))
    t = pya.Trans(bondpads_x_offset, bondpads_y)
    inst_padL2 = laser_circuit_cell.insert(pya.CellInstArray(cell_pad.cell_index(), t))
    
    # Metal routing to connect the two laser bond pads
    pts = [
        inst_padL1.find_pin('m_pin_left').center,
        inst_padL2.find_pin('m_pin_right').center,
    ]
    path = pya.Path(pts, metal_width)
    laser_circuit_cell.shapes(ly.layer(ly.TECHNOLOGY['M2_router'])).insert(path)
    
    # Bond pads for the heater (moved to left edge)
    # Place first heater bond pad
    bondpads_y += pad_pitch
    t = pya.Trans(bondpads_x_offset, bondpads_y)
    inst_pad1 = laser_circuit_cell.insert(pya.CellInstArray(cell_pad.cell_index(), t))
    
    # Place second heater bond pad
    bondpads_y += pad_pitch
    t = pya.Trans(bondpads_x_offset, bondpads_y)
    inst_pad2 = laser_circuit_cell.insert(pya.CellInstArray(cell_pad.cell_index(), t))
    
    # Metal routing from pad1 to heater elec1
    pts = [
        inst_pad1.find_pin('m_pin_right').center,
        pya.Point(inst_heater.find_pin('elec1').center.x,
                  inst_pad1.find_pin('m_pin_right').center.y),
        inst_heater.find_pin('elec1').center
    ]
    path = pya.Path(pts, metal_width)
    laser_circuit_cell.shapes(ly.layer(ly.TECHNOLOGY['M2_router'])).insert(path)
    
    # Metal routing from pad2 to heater elec2
    pts = [
        inst_pad2.find_pin('m_pin_right').center,
        pya.Point(inst_heater.find_pin('elec2').center.x,
                  inst_pad2.find_pin('m_pin_right').center.y),
        inst_heater.find_pin('elec2').center
    ]
    path = pya.Path(pts, metal_width)
    laser_circuit_cell.shapes(ly.layer(ly.TECHNOLOGY['M2_router'])).insert(path)
        
    
    # splitter tree
    from SiEPIC.utils.layout import y_splitter_tree
    if tree_depth == 4:
        n_x_gc_arrays = 6
        n_y_gc_arrays = 1
        x_tree_offset = 0
        inst_tree_in, inst_tree_out, cell_tree = y_splitter_tree(laser_circuit_cell, tree_depth=tree_depth, y_splitter_cell=cell_y, library="EBeam-SiN", wg_type=waveguide_type, draw_waveguides=True)
        ytree_x = inst_heater.bbox().right + x_tree_offset
        ytree_y = inst_heater.pinPoint('opt2').y # - cell_tree.bbox().height()/2
        t = Trans(Trans.R0, ytree_x, ytree_y)
        laser_circuit_cell.insert(CellInstArray(cell_tree.cell_index(), t))
    else:
        # Handle other cases if needed
        raise Exception("Invalid tree_depth value")
    
    inst_tree_out_all += inst_tree_out
    
    # Waveguide, heater to tree:
    connect_pins_with_waveguide(inst_heater, 'opt2', inst_tree_in, 'opt_1', waveguide_type=waveguide_type, turtle_A=[radius_um,90]) #turtle_B=[10,-90, 100, 90])

    # instantiate the student cells, and waveguides
    # in batches for each y-tree
    # in a 2D layout array, limited in the height by laser_dy
    position_y0 = laser_y - laser_dy/2
    position_x0 = laser_x+laser_design_offset
    cells_rows_per_laser
    cells_columns_per_laser
    cell_row, cell_column = 0, 0
    for d in range(row*tree_depth**2, min(design_count,(row+1)*tree_depth**2)):
        # Instantiate the course student cell in the laser circuit cell
        position_y = cell_row * (cell_Height + cell_Gap_Height)
        position_x = cell_column * (radius + cell_Width + waveguide_pitch/dbu * cells_rows_per_laser)
        t = Trans(Trans.R0, position_x0 + position_x, position_y0 + position_y)
        inst_student = laser_circuit_cell.insert(CellInstArray(course_cells[d].cell_index(), t))    
        # Get the dynamic port position for this student design
        dynamic_port_y = student_port_positions[d] if d < len(student_port_positions) else student_laser_in_y
        
        connect_pins_with_waveguide(
            inst_tree_out_all[int(d/2)], 'opt%s'%(2+(d+1)%2), 
            inst_student, 'opt_laser', 
            waveguide_type=waveguide_type_routing, 
            turtle_B = [ # from the student
                (cells_rows_per_laser-cell_row-1)*waveguide_pitch+radius_um,-90, # left away from student design
                (500-dynamic_port_y*ly.dbu)+(cells_rows_per_laser-cell_row-1)*(cell_Height + cell_Gap_Height)*dbu + (cell_row + cell_column*cells_rows_per_laser)*waveguide_pitch,90, # up the column to the top
                100,90, # left towards the laser
            ],
            turtle_A = [ # from the laser
                radius_um+((cells_columns_per_laser-cell_column-1)*cells_rows_per_laser + (cells_rows_per_laser-cell_row-1))*waveguide_pitch, 90,
                radius_um,-90,
            ],
            verbose=False) 
        #, turtle_A=[10,90]) #turtle_B=[10,-90, 100, 90])
        cell_row += 1
        if cell_row > cells_rows_per_laser-1:
            cell_column += 1
            cell_row = 0
            # break

    from SiEPIC.scripts import connect_cell
    for d in range(min(design_count,(row+1)*tree_depth**2), (row+1)*tree_depth**2):
             
            inst = connect_cell(inst_tree_out_all[int(d/2)], 'opt%s'%(2+(d+1)%2), 
                                cell_terminator, 'opt1')

    laser_y += laser_dy

def ground_wire(topcell):
    '''
    Create separate ground wires between each pair of lasers, using the deep trench layer
    '''
    ly = topcell.layout()
    layer = ly.layer(ly.TECHNOLOGY['Deep Trench'])
    components = topcell.find_components(verbose=False)
    
    # Collect laser positions
    laser_positions = []
    for c in components:
        if c.component == "ebeam_dream_Laser_SiN_1310_Bond_BB":
            bbox = c.cell.bbox().transformed(c.trans)
            laser_positions.append((bbox.top, bbox.bottom))
    
    # Sort lasers by position (top to bottom)
    laser_positions.sort(key=lambda x: x[0], reverse=True)  # Sort by top position, highest first
    
    print(f"Found {len(laser_positions)} lasers at positions: {laser_positions}")
    
    # Create separate wires between each pair of lasers
    for i in range(len(laser_positions) - 1):
        # Wire from bottom of current laser to top of next laser
        current_laser_bottom = laser_positions[i][1]    # Bottom of current laser
        next_laser_top = laser_positions[i+1][0]        # Top of next laser
        
        wire = pya.Path([pya.Point(-die_edge + ground_wire_width/2, current_laser_bottom), 
                         pya.Point(-die_edge + ground_wire_width/2, next_laser_top)], ground_wire_width)
        topcell.shapes(layer).insert(wire)
        print(f"Created ground wire {i+1}: from laser {i+1} bottom ({current_laser_bottom}) to laser {i+2} top ({next_laser_top})")

# Insert all laser circuit cells into the top cell
for i, laser_circuit_cell in enumerate(laser_circuit_cells):
    t = Trans(Trans.R0, 0, 0)
    top_cell.insert(CellInstArray(laser_circuit_cell.cell_index(), t))

# Add ground wire between the lasers
ground_wire(top_cell)

  

# Export for fabrication
import os 
path = os.path.dirname(os.path.realpath(__file__))
filename = 'Shuksan' # top_cell_name
file_out = export_layout(top_cell, path, filename, relative_path = '.', format='oas', screenshot=True)

# Copy to Shuksan designs folder if running on specific computer
if is_running_on_lukasc_air():
    print("Running on Lukass-Air - copying files to SiEPIC_Shuksan_ANT_SiN_2025_08/designs")
    copy_to_shuksan_designs_folder(file_out)
else:
    print(f"Running on {socket.gethostname()} - will not copy to Shuksan designs folder")


from SiEPIC._globals import Python_Env
if Python_Env == "Script":
    from SiEPIC.utils import klive
    klive.show(file_out, technology=tech)

# Create an image of the layout
top_cell.image(os.path.join(path,filename+'.png'))

print('Completed %s designs' % design_count)


