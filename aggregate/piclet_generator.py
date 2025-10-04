'''
Generate 3x3 mm PIClet layouts from submissions
One layout per mission

Input:
files in submissions/*.oas or submissions/*.gds

Output:
layouts in aggregate/piclets/

Based on dream_piclet_3x3.py but simplified:
- without the MZI and rings
- only GC (grating couplers)
- keep the laser, bond pads, heater
- but instead of drawing the circuit after the heater, just immediately connect the submission design to the location of the Port_SiN_800

'''

import os
import pya
from SiEPIC.utils.layout import new_layout, floorplan, make_pin
from SiEPIC.utils import klive
from SiEPIC.verification import layout_check
from SiEPIC.scripts import (
    zoom_out,
    export_layout,
    connect_pins_with_waveguide,
    connect_cell,
)
from SiEPIC.extend import to_itype
import siepic_ebeam_pdk as pdk
from SiEPIC.utils import create_cell2

# Configuration
layout_name = "ELEC413-PIClet-3x3"
die_width = 2753330
die_height = 2753340
keepout_width = 2000e3
keepout_height = 200e3
fiber_pitch = 127e3
ground_wire_width = 20e3  # on the edge of the chip
trench_bondpad_offset = 20e3

def create_laser_and_heater(cell, ly, wavelength=1310, laser_x=-500e3, center_y=0, laser_align='left', left_edge=0):
    """
    Create laser and heater components with waveguide connection.
    
    Args:
        cell: The cell to insert components into
        ly: The layout
        wavelength: The wavelength for the laser
        laser_x: absolute X position of the laser, OR
        laser_align: Alignment of the laser ('left': relative to the left_edge)
        center_y: Y position of the laser
        
    Returns:
        tuple: (inst_laser, inst_heater, wg_type, radius)
    """
    wg_type = f"SiN Strip TE {wavelength} nm, w=800 nm"
    # Get bend radius from waveguide specification
    try:
        radius = pdk.tech.waveguides[wg_type].radius
    except Exception:
        radius = 60  # fallback default in microns if not found
    
    # Load the laser cell
    laser = ly.create_cell(
        f"ebeam_dream_Laser_SiN_{wavelength}_Bond_BB",
        "EBeam-Dream",
    )
    if not laser:
        raise Exception(f"Cannot import cell ebeam_dream_Laser_SiN_{wavelength}_BB")

    # Place the laser
    if 'left' in laser_align:
        laser_x = left_edge - laser.bbox().left
    t = pya.Trans(pya.Trans.R0, laser_x, center_y)
    inst_laser = cell.insert(pya.CellInstArray(laser.cell_index(), t))

    # Add wg_heater after the laser
    cell_heater = ly.create_cell('wg_heater', 'EBeam-SiN', 
                                  {'length': 500,
                                   'waveguide_type': wg_type,
                                   })
    inst_heater = connect_cell(inst_laser, 'opt1', cell_heater, 'opt1')
    # Move heater 100µm to the right
    inst_heater.transform(pya.Trans(100e3, 0))
    
    # Connect laser to heater with waveguide
    connect_pins_with_waveguide(inst_laser, 'opt1',
                                 inst_heater, 'opt1',
                                 waveguide_type=wg_type)
    
    return inst_laser, inst_heater, wg_type, radius


def create_bond_pads_and_routing(cell, ly, inst_laser, inst_heater, laser_x=-500e3, x_laser_top_contact=-380e3):
    """
    Create bond pads and metal routing for laser heater control.
    
    Args:
        cell: The cell to insert components into
        ly: The layout
        inst_laser: Laser instance
        inst_heater: Heater instance
        laser_x: X position of the laser
        x_laser_top_contact: X position of the laser top contact, relative to the laser cell right edge
        
    Returns:
        tuple: (inst_pad1, inst_pad2)
    """
    # Metal and pad parameters
    pad_pitch = 150e3
    laser_pad_distance = 200e3
    metal_width = 20e3
    
    # Add bond pads above the laser
    cell_pad = create_cell2(ly, 'ebeam_BondPad', 'EBeam-SiN')

    bondpads_x_offset = inst_laser.bbox().left + cell_pad.bbox().width()/2 + ground_wire_width + trench_bondpad_offset
    bondpads_y = inst_laser.bbox().top + laser_pad_distance + cell_pad.bbox().height()/2

    # Bond pad for the laser top contact, and route to the left edge
    t = pya.Trans(inst_laser.trans.disp.x + x_laser_top_contact, 
                  bondpads_y)
    inst_padL1 = cell.insert(pya.CellInstArray(cell_pad.cell_index(), t))
    t = pya.Trans(bondpads_x_offset, 
                  bondpads_y)
    inst_padL2 = cell.insert(pya.CellInstArray(cell_pad.cell_index(), t))
    # Metal routing to connect the two bond pads
    pts = [
        inst_padL1.find_pin('m_pin_left').center,
        inst_padL2.find_pin('m_pin_right').center,
    ]
    path = pya.Path(pts, metal_width)
    cell.shapes(ly.layer(ly.TECHNOLOGY['M2_router'])).insert(path)
    
    # Bond pads for the heater    
    # Place first bond pad
    bondpads_y += pad_pitch
    t = pya.Trans(bondpads_x_offset, 
                  bondpads_y)
    inst_pad1 = cell.insert(pya.CellInstArray(cell_pad.cell_index(), t))
    
    # Place second bond pad
    bondpads_y += pad_pitch
    t = pya.Trans(bondpads_x_offset, 
                  bondpads_y)
    inst_pad2 = cell.insert(pya.CellInstArray(cell_pad.cell_index(), t))
    
    # Metal routing from pad1 to heater elec1
    pts = [
        inst_pad1.find_pin('m_pin_right').center,
        pya.Point(inst_heater.find_pin('elec1').center.x,
                  inst_pad1.find_pin('m_pin_right').center.y),
        inst_heater.find_pin('elec1').center
    ]
    path = pya.Path(pts, metal_width)
    cell.shapes(ly.layer(ly.TECHNOLOGY['M2_router'])).insert(path)
    
    # Metal routing from pad2 to heater elec2
    pts = [
        inst_pad2.find_pin('m_pin_right').center,
        pya.Point(inst_heater.find_pin('elec2').center.x,
                  inst_pad2.find_pin('m_pin_right').center.y),
        inst_heater.find_pin('elec2').center
    ]
    path = pya.Path(pts, metal_width)
    cell.shapes(ly.layer(ly.TECHNOLOGY['M2_router'])).insert(path)
    
    return inst_pad1, inst_pad2


def create_grating_couplers(cell, ly, wavelength=1310, gc_x=None, gc_y_start=-200e3):
    """
    Create grating couplers for fiber I/O.
    
    Args:
        cell: The cell to insert components into
        ly: The layout
        wavelength: The wavelength
        gc_x: X position for grating couplers (default: right side of die)
        gc_y_start: Y start position for grating couplers
        
    Returns:
        list: List of grating coupler instances with tapers
    """
    if gc_x is None:
        gc_x = die_width/2 - 150e3
    
    # Create grating coupler cell
    cell_gc = create_cell2(ly, f'GC_SiN_TE_{wavelength}_8degOxide_BB', 'EBeam-SiN')
    
    # Create taper cell
    cell_taper = create_cell2(ly, 'taper_SiN_750_800', 'EBeam-SiN')
    
    # Instantiate GC + taper combinations
    gc_instances = []
    for i in range(4):
        t = pya.Trans(pya.Trans.R180, gc_x, gc_y_start + fiber_pitch * i)
        inst_gc = cell.insert(pya.CellInstArray(cell_gc.cell_index(), t))
        inst_gct = connect_cell(inst_gc, 'opt1', cell_taper, 'opt2')
        gc_instances.append(inst_gct)
    
    return gc_instances


def add_measurement_labels(cell, ly, coupler_x, coupler_y_start, coupler_pitch, label_suffix="MZI0"):
    """
    Add opt_in and DFT measurement labels.
    
    Args:
        cell: The cell to insert labels into
        ly: The layout
        coupler_x: X position for opt_in label
        coupler_y_start: Y start position for couplers
        coupler_pitch: Pitch between couplers
        label_suffix: Suffix for the measurement label
    """
    # Add opt_in label on the top-most coupler
    t = pya.Trans(pya.Trans.R0, coupler_x, coupler_y_start + coupler_pitch * 3)
    text = pya.Text(f"opt_in_TE_1310_device_lukasc_{label_suffix}", t)
    text.halign = pya.Text.HAlignRight
    s = cell.shapes(ly.layer(ly.TECHNOLOGY['Text'])).insert(text)
    s.text_size = 10/ly.dbu
    
    # Add DFT label
    t_dft = pya.Trans(pya.Trans.R0, 0, 500e3)
    text_dft = pya.Text("DFT=DFT_AIM_SiEPIC_Laser_PIC_Project1", t_dft)
    text_dft.valign = pya.Text.VAlignTop
    s_dft = cell.shapes(ly.layer(ly.TECHNOLOGY['Text'])).insert(text_dft)
    s_dft.text_size = 10/ly.dbu


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

def create_simplified_piclet(topcell, submission_cell, submission_name, wavelength=1310):
    """
    Create a simplified PIClet with laser, heater, bond pads, and connect to submission design.
    
    Args:
        topcell: The top-level cell to insert the circuit into
        submission_cell: The submission design cell to connect
        submission_name: Name of the submission for labeling
        wavelength: The wavelength (default: 1310)
        
    Returns:
        pya.Instance: The instance of the created PIClet layout
    """
    # Create a new layout for the chip floor plan
    ly = topcell.layout()
    cell = ly.create_cell(f"piclet_{submission_name}_{wavelength}")
    inst = topcell.insert(pya.CellInstArray(cell.cell_index(), pya.Vector(0, 0)))

    # Position variables
    center_y = 0
    gc_x = die_width/2 - 150e3
    gc_y_start = -200e3

    # Create laser and heater using shared function
    inst_laser, inst_heater, wg_type, radius = create_laser_and_heater(
        cell, ly, wavelength, center_y=center_y, left_edge=-die_width/2)
    
    # Create bond pads and routing using shared function
    inst_pad1, inst_pad2 = create_bond_pads_and_routing(cell, ly, inst_laser, inst_heater)

        
    # Create a new cell for the submission design in the current layout
    submission_bbox = submission_cell.bbox()
    submission_cell_new = ly.create_cell(f"submission_{submission_name}")
    
    # Copy the submission cell content to the new cell
    submission_cell_new.copy_tree(submission_cell)
    
    # Find port_SiN cell in the submission design
    port_cell, port_y = find_port_sin_cell_and_position(submission_cell_new, log_func=print)
    
    if port_cell is not None:
        # Add pin directly to the port cell
        from SiEPIC.utils.layout import make_pin
        # Calculate pin position relative to the port cell's origin
        port_bbox = port_cell.bbox()
        pin_x = int(port_bbox.left - port_bbox.left)  # Left edge of the cell (x=0)
        pin_y = int(0)  # Middle vertically (y=0)
        make_pin(port_cell, 'opt_laser', [pin_x, pin_y], 800, 'PinRec', 180, debug=False)
        print(f"Added pin to port cell '{port_cell.name}' at left edge, middle vertically [{pin_x}, {pin_y}]")
        
        # Create Y-branch between heater and student design
        from SiEPIC.utils import create_cell2
        cell_y_branch = create_cell2(ly, 'ebeam_YBranch_te1310', 'EBeam-SiN')
        if not cell_y_branch:
            raise Exception('Cannot load Y-branch cell')
        
        # Connect heater to Y-branch input
        from SiEPIC.scripts import connect_cell
        y_branch_inst = connect_cell(inst_heater, 'opt2', cell_y_branch, 'opt1')
        
        # Position student design: right 2*radius*1e3, up 250 µm from Y-branch
        student_x = y_branch_inst.bbox().right + 2 * radius * 1e3
        student_y = y_branch_inst.bbox().center().y + 250e3  # 250 µm up
        submission_inst = cell.insert(pya.CellInstArray(submission_cell_new.cell_index(), 
                                                       pya.Trans(pya.Trans.R0, student_x, student_y)))
        
        # Connect Y-branch output to student design
        connect_pins_with_waveguide(y_branch_inst, 'opt2', submission_inst, 'opt_laser',
                                   waveguide_type=wg_type)
        
        # Create FaML cell on the right edge of the chip as reference path
        cell_faml = create_cell2(ly, 'ebeam_dream_FaML_SiN_1310_BB', 'EBeam-Dream')
        if cell_faml:
            # Position FaML exactly at the right edge of the chip, rotated 180°
            faml_x = die_width/2  # Exactly at right edge
            faml_y = center_y  # Center vertically
            faml_inst = cell.insert(pya.CellInstArray(cell_faml.cell_index(), 
                                                     pya.Trans(pya.Trans.R180, faml_x, faml_y)))
            
            # Connect the other Y-branch output (opt3) to FaML
            connect_pins_with_waveguide(y_branch_inst, 'opt3', faml_inst, 'opt1',
                                       waveguide_type=wg_type)
            print(f"Created FaML cell on right edge at x={faml_x}")
        else:
            print("Warning: Could not load FaML cell")
        
    else:
        print(f"No port_SiN found in submission {submission_name}, using fallback connection")
        # Fallback: create pin at submission cell center and connect manually
        from SiEPIC.utils.layout import make_pin
        make_pin(submission_cell_new, 'opt_laser', [submission_bbox.width()//2, 0], 800, 'PinRec', 0)
        
        # Create Y-branch between heater and student design
        from SiEPIC.utils import create_cell2
        cell_y_branch = create_cell2(ly, 'ebeam_YBranch_te1310', 'EBeam-SiN')
        if not cell_y_branch:
            raise Exception('Cannot load Y-branch cell')
        
        # Connect heater to Y-branch input
        from SiEPIC.scripts import connect_cell
        y_branch_inst = connect_cell(inst_heater, 'opt2', cell_y_branch, 'opt1')
        
        # Position student design: right 2*radius*1e3, up 250 µm from Y-branch
        student_x = y_branch_inst.bbox().right + 2 * radius * 1e3
        student_y = y_branch_inst.bbox().center().y + 250e3  # 250 µm up
        submission_inst = cell.insert(pya.CellInstArray(submission_cell_new.cell_index(), 
                                                       pya.Trans(pya.Trans.R0, student_x, student_y)))
        
        # Connect Y-branch output to the submission design
        connect_pins_with_waveguide(y_branch_inst, 'opt2',
                                    submission_inst, 'opt_laser',
                                    waveguide_type=wg_type)
        
        # Create FaML cell on the right edge of the chip as reference path
        cell_faml = create_cell2(ly, 'ebeam_dream_FaML_SiN_1310_BB', 'EBeam-Dream')
        if cell_faml:
            # Position FaML exactly at the right edge of the chip, rotated 180°
            faml_x = die_width/2  # Exactly at right edge
            faml_y = center_y  # Center vertically
            faml_inst = cell.insert(pya.CellInstArray(cell_faml.cell_index(), 
                                                     pya.Trans(pya.Trans.R180, faml_x, faml_y)))
            
            # Connect the other Y-branch output (opt3) to FaML
            connect_pins_with_waveguide(y_branch_inst, 'opt3', faml_inst, 'opt1',
                                       waveguide_type=wg_type)
            print(f"Created FaML cell on right edge at x={faml_x}")
        else:
            print("Warning: Could not load FaML cell")
    
    return inst


def load_submission_designs(submissions_path):
    """
    Load all submission designs from the submissions directory.
    
    Args:
        submissions_path: Path to the submissions directory
        
    Returns:
        list: List of tuples (filename, cell, layout)
    """
    submissions = []
    
    # Get all GDS/OAS files
    files_in = []
    for f in os.listdir(submissions_path):
        if f.lower().endswith(('.gds', '.oas')):
            files_in.append(os.path.join(submissions_path, f))
    
    for f in sorted(files_in):
        filename = os.path.basename(f)
        print(f"Loading submission: {filename}")
        
        # Load layout
        layout = pya.Layout()
        layout.read(f)
        
        # Find the top cell
        top_cells = layout.top_cells()
        if len(top_cells) == 1:
            cell = top_cells[0]
            submissions.append((filename, cell, layout))
        else:
            print(f"  Warning: {filename} has {len(top_cells)} top cells, skipping")
    
    return submissions


def create_piclet_layout(ly, submission_name, submission_cell):
    """
    Create and return a PIClet layout for a single submission.
    
    Args:
        ly: The layout to create the PIClet in
        submission_name: Name of the submission
        submission_cell: The submission design cell
        
    Returns:
        pya.Cell: The top cell of the created PIClet layout
    """
    topcell = ly.top_cell()
    ly.technology_name = pdk.tech.name

    # Draw a floorplan
    floorplan(topcell, die_width, die_height, centered=True)

    # Insert keepout regions
    ko_box1 = pya.Box(-die_width/2, -die_height/2, keepout_width-die_width/2, keepout_height-die_height/2)
    ko_box2 = pya.Box(-die_width/2, die_height/2, keepout_width-die_width/2, die_height/2 - keepout_height)
    topcell.shapes(ly.layer(ly.TECHNOLOGY["Keep out"])).insert(ko_box1)
    topcell.shapes(ly.layer(ly.TECHNOLOGY["Keep out"])).insert(ko_box2)

    # Create simplified PIClet with submission design
    inst_piclet = create_simplified_piclet(topcell, submission_cell, submission_name)

    zoom_out(topcell)
    return topcell


def generate_piclets():
    """
    Main function to generate PIClets for all submissions.
    """
    print("ELEC413 PIClet Generator - 3x3mm")
    
    # Get paths
    script_path = os.path.dirname(os.path.realpath(__file__))
    submissions_path = os.path.join(os.path.dirname(script_path), "submissions")
    piclets_path = os.path.join(script_path, "piclets")
    
    # Create piclets directory if it doesn't exist
    os.makedirs(piclets_path, exist_ok=True)
    
    # Load submission designs
    submissions = load_submission_designs(submissions_path)
    print(f"Found {len(submissions)} submissions")
    
    # Generate PIClet for each submission
    for filename, submission_cell, submission_layout in submissions[0:1]:
        submission_name = os.path.splitext(filename)[0]
        print(f"Generating PIClet for: {submission_name}")
        
        try:
            # Create new layout for this PIClet
            dbu = 0.001
            piclet_name = f"{layout_name}-{submission_name}"
            topcell, ly = new_layout(pdk.tech.name, piclet_name, overwrite=True)
            ly.dbu = dbu
            ly.technology_name = pdk.tech.name
            
            # Create the PIClet layout
            topcell = create_piclet_layout(ly, submission_name, submission_cell)
            
            # Run verification
            num_errors = layout_check(
                cell=topcell, verbose=False, GUI=False, 
                file_rdb=os.path.join(piclets_path, f"{piclet_name}.lyrdb")
            )
            
            # Export layout
            file_out = export_layout(
                topcell, piclets_path, filename=topcell.name
            )
            topcell.show()
            
            print(f"  Generated: {file_out}")
            if num_errors > 0:
                print(f"  Warning: {num_errors} verification errors found")
                
        except Exception as e:
            print(f"  Error generating PIClet for {submission_name}: {str(e)}")
            continue
    
    print("PIClet generation complete!")


if __name__ == "__main__":
    """
    Main execution block for generating PIClets from submissions.
    """
    generate_piclets()