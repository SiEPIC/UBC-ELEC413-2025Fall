'''
ELEC413 PIClet Generator - Advanced Multi-Submission Layout Creation
====================================================================

OVERVIEW:
---------
This script generates 3x3 mm PIClet layouts from student submissions, creating
individual testable photonic integrated circuits with laser sources, heaters,
bond pads, and student designs. The system supports multiple submissions per
PIClet and uses GitHub commit history for intelligent naming.

FEATURES:
---------
1. **Two Submissions Per PIClet**: Reduces chip count by 2x by placing two
   student designs on each PIClet with 1000 µm vertical separation.

2. **GitHub Username Extraction**: Automatically extracts GitHub usernames using
   GitHub API, repository fork detection, and commit history analysis for
   accurate, clean PIClet naming instead of filenames.

3. **Y-Branch Tree Architecture**: Uses a depth-2 Y-branch tree (4 outputs)
   to distribute optical power from a single laser to multiple test paths.

4. **FaML Copy Generation**: Creates independent copies of student designs
   with grating couplers replaced by FaML cells for reference measurements.

5. **Dynamic Port Detection**: Automatically finds port_SiN cells within
   student designs and places optical pins for waveguide connections.

6. **Verification System**: Runs layout verification during submission loading
   to filter out problematic designs with disconnected pins or other critical errors.

7. **Robust Top Cell Selection**: Uses SiEPIC-Tools utility functions for
   reliable identification of the main design cell in hierarchical layouts.

8. **Regular Array Explosion**: Automatically detects and explodes regular arrays
   in submission copies to ensure proper processing of all instances.

INPUT:
------
- Student submission files in submissions/*.oas or submissions/*.gds
- Each file should contain a complete photonic design with port_SiN cells
- Files are processed in pairs to create combined PIClets

OUTPUT:
-------
- Individual PIClet layouts in aggregate/piclets/
            - Naming format: "PIClet-3x3-usernameA-usernameB.oas"
- Each PIClet contains: laser, heater, bond pads, Y-branch tree, student designs, FaML copies

ARCHITECTURE:
-------------
Each PIClet contains:

1. **Laser Circuit** (top):
   - DFB laser with bond pads
   - Waveguide heater with electrical connections
   - Y-branch tree (depth 2, 4 outputs)

2. **Student Design A** (upper):
   - Original student design with port_SiN detection
   - Connected to Y-branch output 1
   - FaML copy positioned 250 µm down, aligned to chip edge

3. **Student Design B** (lower):
   - Second student design positioned 1000 µm below Design A
   - Connected to Y-branch output 2
   - FaML copy positioned 250 µm down from Design B

4. **Reference Paths**:
   - FaML cells on right edge for optical power monitoring
   - Connected to remaining Y-branch outputs

TECHNICAL IMPLEMENTATION:
-------------------------

            **GitHub Username Extraction:**
            - Multi-layered approach for maximum accuracy:
              1. **GitHub noreply emails**: Direct extraction from format `ID+username@users.noreply.github.com`
              2. **Repository fork matching**: Queries GitHub API for repository forks and matches author names
              3. **GitHub API search**: Searches GitHub API by email address for public accounts
              4. **Email parsing fallback**: Extracts username from email with special mappings
            - Caches API responses to avoid rate limiting
            - Handles GitHub API rate limits with automatic retry
            - Handles duplicate usernames by adding numeric suffixes (1, 2, 3...)
            - Falls back to 'unknown' if all methods fail

**Dynamic Port Detection:**
- Recursively searches cell hierarchy for port_SiN instances
- Places optical pins directly in port cells for accurate connections
- Uses visited_cells set to prevent infinite recursion
- Calculates absolute positions including all transformations

**FaML Copy Generation:**
- Creates deep copy by reloading original GDS file
- Recursively replaces GC cells with FaML cells
- Calculates pin offsets to align FaML opt1 with GC origin
- Positions copies to align rightmost FaML with chip edge

**Y-Branch Tree Implementation:**
- Uses SiEPIC-Tools y_splitter_tree function with depth=2
- Creates 4 optical outputs from single laser input
- Connects outputs to student designs and reference paths
- Leaves unused outputs disconnected for future expansion

**Positioning Algorithm:**
- First submission: y_offset = 0 (relative to laser_start_y = 300 µm above center)
- Second submission: y_offset = -laser_circuit_spacing (1100 µm down from first)
- FaML copies: positioned submission_GC_dy (500 µm) down from respective designs
- Chip edge alignment: calculates offset to align rightmost FaML

**Regular Array Explosion:**
- Performed on submission copies during PIClet creation (not original files)
- Recursively traverses cell hierarchy to find regular arrays
- Uses instance.is_regular_array() to detect arrays
- Calls instance.explode() to expand arrays into individual instances
- Prevents infinite recursion with visited_cells tracking
- Reports count of exploded arrays for debugging

**Error Handling:**
- Graceful fallback for missing port_SiN cells
- Robust top cell selection with multiple methods
- Comprehensive exception handling for git operations
- Verification error reporting with detailed diagnostics

CONFIGURATION:
--------------
- process_num_submissions: Number of submissions to process (default: 4)
- die_width: Chip width in nanometers (default: 2753330)
- laser_start_y: Vertical position of the first laser (default: 300e3 = 300 µm above center)
- laser_circuit_spacing: Vertical spacing between submissions (default: 1100e3 = 1100 µm)
- submission_GC_dy: Vertical offset for submission grating couplers (default: 500e3 = 500 µm)
- die_height: Chip height in nanometers (default: 2753330)
- layout_name: Base name for generated layouts (default: "ELEC413-PIClet-3x3")

DEPENDENCIES:
-------------
- SiEPIC-Tools: Layout creation, waveguide routing, verification
- KLayout Python API: Layout manipulation and cell operations
- Git: Commit history analysis and repository information
- GitHub API: Username lookup and repository fork detection
- requests: HTTP client for GitHub API calls
- siepic_ebeam_pdk: Photonic component library

USAGE:
------
python piclet_generator.py

The script automatically:
1. Loads all GDS/OAS files from submissions directory
2. Runs verification checks and filters out problematic designs
3. Extracts GitHub usernames using multiple methods (API, forks, emails)
4. Processes submissions in pairs to reduce chip count
5. Creates copies and explodes regular arrays during PIClet generation
6. Generates PIClets with combined designs and exports layouts

EXAMPLE OUTPUT:
---------------
            For submissions from users "cameron647" and "aabousaleh":
            - Generated: PIClet-3x3-cameron647-aabousaleh.oas
- Contains: Laser + Y-branch tree + 2 student designs + 2 FaML copies
- Verification: Reports any layout errors or warnings

DEVELOPMENT HISTORY:
-------------------
- Initial implementation: Single submission per PIClet
- Added Y-branch tree: Multiple optical paths from single laser
- Implemented FaML copying: Reference measurements for each design
- Added GitHub username extraction: Clean, readable naming from commit history
- Implemented dual submissions: 2x reduction in chip count
- Enhanced port detection: Dynamic positioning for accurate connections
- Added verification system: Early filtering of problematic designs
- Integrated GitHub API: Accurate username extraction using repository forks
- Added regular array explosion: Automatic detection and expansion of arrays

This implementation represents a significant advancement in automated PIClet
generation, combining multiple student designs efficiently while maintaining
full functionality for optical testing and characterization.

Author: Lukas Chrostowski, with Cursor AI
Date: 2025
Based on: dream_piclet_3x3.py (simplified architecture)
'''

import os
import pya
import subprocess
import requests
import time
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
process_num_submissions = -1  # -1 for all
layout_name = "ELEC413-PIClet-3x3"
die_width = 2753330
die_height = 2753340
keepout_width = 2000e3
keepout_height = 200e3
fiber_pitch = 127e3
ground_wire_width = 20e3  # on the edge of the chip
trench_bondpad_offset = 40e3

# Laser circuit vertical spacing control
laser_start_y = 300e3  # Vertical position of the first laser (y=0 is center)
laser_circuit_spacing = 1100e3  # 1500 µm spacing between submissions
submission_GC_dy = 500e3  # Vertical offset for submission grating couplers

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
                                   'mh_width': 5,
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


# Cache for GitHub username lookups to avoid repeated API calls
_github_username_cache = {}
_github_forks_cache = None

def move_instance_up_hierarchy(instance, num_levels=1):
    """
    Move an instance up one or more levels in the hierarchy while accounting for parent transformations.
    
    This function is crucial for maintaining proper absolute positioning when moving instances
    up in the cell hierarchy. It accumulates all transformations from parent instances and
    applies the inverse transformation to maintain the same absolute position after the move.
    
    The function uses KLayout's each_parent_inst() method to traverse up the hierarchy
    and accumulates transformations using matrix multiplication. This ensures that when
    an instance is moved to a higher level in the hierarchy, its absolute position
    remains unchanged relative to the top cell.
    
    Args:
        instance (pya.Instance): The KLayout instance to move up in the hierarchy.
            Must be a valid instance with a parent cell.
        num_levels (int, optional): The number of levels to move up in the hierarchy.
            Defaults to 1. Must be a positive integer.
            
    Returns:
        pya.Instance: The same instance object with updated parent_cell and trans
            properties. The instance is modified in-place and also returned for
            convenience.
            
    Raises:
        ValueError: If num_levels would move the instance beyond the top of the
            hierarchy, or if a cell has multiple parent instances (ambiguous path).
            
    Example:
        >>> # Move an instance up one level in the hierarchy
        >>> moved_instance = move_instance_up_hierarchy(my_instance, num_levels=1)
        >>> 
        >>> # Move an instance up two levels
        >>> moved_instance = move_instance_up_hierarchy(my_instance, num_levels=2)
        
    Note:
        This function modifies the instance in-place. The original instance object
        is returned with updated properties. If the hierarchy path is ambiguous
        (multiple parent instances), an error is raised to prevent incorrect positioning.
        
    Technical Details:
        The transformation accumulation follows the formula:
        accumulated_transform = parent_n.trans * parent_(n-1).trans * ... * parent_1.trans
        
        After moving the instance, the transformation is applied as:
        instance.trans = accumulated_transform.inverted() * original_transform
        
        This ensures that the absolute position remains unchanged after the hierarchy move.
    """

    from SiEPIC.utils import top_cell_with_most_subcells_or_shapes
        
    cell = instance.cell
    layout = cell.layout()
    top_cell = top_cell_with_most_subcells_or_shapes(layout)
    
    print(f"Moving instance name {instance.cell.name}")
    
    # Calculate accumulated transformation from parent instances
    # Store the current transformation before moving up hierarchy
    accumulated_transform = pya.Trans.R0 

    # Walk up the hierarchy using each_parent_inst()
    current_inst = instance
    for level in range(num_levels+1):
        accumulated_transform *= current_inst.trans
        print(f"Next transform: {current_inst.trans}, Accumulated transform: {accumulated_transform}")

        parent_insts = list(current_inst.cell.each_parent_inst())
        
        if not parent_insts:
            raise ValueError(f"Cannot move up {num_levels} levels. Reached top of hierarchy at level {level}")
        
        if len(parent_insts) > 1:
            raise ValueError(f"Cell '{instance.name}' has multiple parent instances. Cannot determine unique path.")
                
        # Get the parent cell:
        parent_cell = current_inst.parent_cell
        print(f"Parent cell: {parent_cell.name}")

        # Find the parent cell's Instance

        # Iterate through all instances in the hierarchy
        
        iter = top_cell.begin_instances_rec()
        iter.targets = parent_cell.name
        while not iter.at_end():
            print(f"Instance of {iter.inst_cell().name} in {top_cell.name}: {iter.dtrans() * iter.inst_dtrans()}")
            print(f"Instance: {iter.current_inst_element().inst()}")
            instance1 = iter.current_inst_element().inst()
            iter.next()
        '''
        for inst_ptr in iter.each_instance():
            # Check if the current instance refers to the target cell
            if inst_ptr.cell().name == parent_cell.name:
                print(f"Found instance of '{parent_cell.name}' in cell '{inst_ptr.parent_cell().name}'")
        '''
        current_inst = instance1

    
    # Move the instance to the target cell (the parent cell of the final parent instance)
    instance.parent_cell = cell.layout().cell(current_inst.cell_index)

    # Apply the accumulated transformation to maintain absolute position
    instance.trans = accumulated_transform
    
    print(f"Moved instance {instance.cell.name} to new parent cell {instance.parent_cell.name} {cell.layout().cell(current_inst.cell_index).name}")
    
    return instance


def explode_regular_arrays(cell, log_func=None, visited_cells=None):
    """
    Recursively inspect a cell and explode all regular arrays.
    
    Args:
        cell: The cell to inspect
        log_func: Optional logging function
        visited_cells: Set of already visited cells to prevent infinite recursion
        
    Returns:
        int: Number of regular arrays exploded
    """
    if visited_cells is None:
        visited_cells = set()
    
    # Prevent infinite recursion
    cell_id = id(cell)
    if cell_id in visited_cells:
        return 0
    visited_cells.add(cell_id)
    
    exploded_count = 0
    
    try:
        # Check all instances in this cell
        for instance in cell.each_inst():
            if instance.is_regular_array():
                if log_func:
                    log_func(f"Exploding regular array: {instance.cell.name}")
                instance.explode()
                exploded_count += 1
        
        # Recursively check sub-cells
        for instance in cell.each_inst():
            if not instance.is_regular_array():  # Only check non-array instances
                subcell = instance.cell
                exploded_count += explode_regular_arrays(subcell, log_func, visited_cells)
                
    except Exception as e:
        if log_func:
            log_func(f"Error exploding regular arrays in cell {cell.name}: {e}")
    
    return exploded_count


def get_repository_forks():
    """
    Get list of forks for the repository to map contributors to GitHub usernames.
    
    Returns:
        dict: Dictionary mapping email -> username, or None if failed
    """
    global _github_forks_cache
    
    if _github_forks_cache is not None:
        return _github_forks_cache
    
    try:
        # Get repository information from git remote
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run([
            'git', '-C', repo_dir, 'remote', 'get-url', 'origin'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            print("  Warning: Could not get git remote URL")
            _github_forks_cache = {}
            return {}
        
        remote_url = result.stdout.strip()
        # Extract owner/repo from URL
        if 'github.com' in remote_url:
            if remote_url.endswith('.git'):
                remote_url = remote_url[:-4]
            parts = remote_url.split('github.com/')[-1]
            if parts:
                owner, repo = parts.split('/', 1)
                
                # Get forks from GitHub API
                url = f"https://api.github.com/repos/{owner}/{repo}/forks"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    forks = response.json()
                    print(f"  Found {len(forks)} forks for {owner}/{repo}")
                    
                    # Create mapping of fork owner usernames
                    fork_usernames = set()
                    for fork in forks:
                        if 'owner' in fork and 'login' in fork['owner']:
                            fork_usernames.add(fork['owner']['login'])
                    
                    _github_forks_cache = {
                        'forks': fork_usernames,
                        'owner': owner,
                        'repo': repo
                    }
                    return _github_forks_cache
                else:
                    print(f"  Warning: GitHub API returned status {response.status_code}")
        
        _github_forks_cache = {}
        return {}
        
    except Exception as e:
        print(f"  Warning: Could not get repository forks: {e}")
        _github_forks_cache = {}
        return {}


def get_github_username_from_api(email):
    """
    Query GitHub API to get username from email address.
    
    Args:
        email: Email address to look up
        
    Returns:
        str: GitHub username or None if not found
    """
    # Check cache first
    if email in _github_username_cache:
        return _github_username_cache[email]
    
    try:
        # GitHub API endpoint for searching users by email
        url = f"https://api.github.com/search/users?q={email}"
        
        # Make request with rate limiting
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('total_count', 0) > 0:
                # Get the first user's login (username)
                user = data['items'][0]
                username = user.get('login')
                # Cache the result
                _github_username_cache[email] = username
                return username
        elif response.status_code == 403:
            # Rate limited - wait and try again
            print(f"  GitHub API rate limited, waiting...")
            time.sleep(60)
            return get_github_username_from_api(email)
        
        # Cache negative result
        _github_username_cache[email] = None
        return None
    except Exception as e:
        print(f"  Warning: GitHub API lookup failed for {email}: {e}")
        return None


def get_github_username(file_path):
    """
    Extract GitHub username from the commit history of a file using GitHub API and fork information.
    
    Args:
        file_path: Path to the file
        
    Returns:
        str: GitHub username or 'unknown' if not found
    """
    try:
        # Get the directory containing the file (should be the git repo root)
        repo_dir = os.path.dirname(os.path.dirname(file_path))  # Go up from submissions/ to repo root
        
        # Get the author email of the most recent commit for this file
        result = subprocess.run([
            'git', '-C', repo_dir, 'log', '-1', '--pretty=format:%ae', '--', file_path
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            email = result.stdout.strip()
            
            # For GitHub noreply emails, extract username directly (most reliable)
            if '@' in email:
                userid = email.split('@')[0]
                if '+' in userid and '@users.noreply.github.com' in email:
                    # This is a GitHub noreply email - extract username after +
                    username = userid.split('+')[1]
                    print(f"  Extracted GitHub username: {username}")
                    return username
            
            # Try to match with repository forks first
            fork_info = get_repository_forks()
            if fork_info and 'forks' in fork_info:
                # Get author name to potentially match with fork usernames
                author_result = subprocess.run([
                    'git', '-C', repo_dir, 'log', '-1', '--pretty=format:%an', '--', file_path
                ], capture_output=True, text=True, timeout=10)
                
                if author_result.returncode == 0 and author_result.stdout.strip():
                    author_name = author_result.stdout.strip().lower()
                    # Try to find a fork owner whose username matches the author name
                    for fork_username in fork_info['forks']:
                        if author_name in fork_username.lower() or fork_username.lower() in author_name:
                            print(f"  Matched author '{author_name}' to fork owner: {fork_username}")
                            return fork_username
            
            # Try GitHub API lookup for other emails
            print(f"  Looking up GitHub username for {email}...")
            username = get_github_username_from_api(email)
            
            if username:
                return username
            
            # Fallback to email parsing if API lookup fails
            if '@' in email:
                userid = email.split('@')[0]
                # Clean up the userid (remove dots, etc.)
                userid = userid.replace('.', '').replace('-', '')
                
                # Special mapping for known GitHub usernames
                if userid == 'lukasc':
                    userid = 'lukasc-ubc'
                
                return userid
            else:
                return 'unknown'
        else:
            return 'unknown'
    except Exception as e:
        print(f"Warning: Could not get GitHub user ID for {file_path}: {e}")
        return 'unknown'


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

def create_simplified_piclet(topcell, submission_cell, submission_name, filename, wavelength=1310, y_offset=0):
    """
    Create a simplified PIClet with laser, heater, bond pads, and connect to submission design.
    
    Args:
        topcell: The top-level cell to insert the circuit into
        submission_cell: The submission design cell to connect
        submission_name: Name of the submission for labeling
        filename: Original filename of the submission
        wavelength: The wavelength (default: 1310)
        y_offset: Y-axis offset for positioning multiple submissions (default: 0)
        
    Returns:
        pya.Instance: The instance of the created PIClet layout
    """
    # Create a new layout for the chip floor plan
    ly = topcell.layout()
    cell = ly.create_cell(f"piclet_{submission_name}_{wavelength}")
    inst = topcell.insert(pya.CellInstArray(cell.cell_index(), pya.Vector(0, 0)))

    # Position variables
    center_y = laser_start_y + y_offset
    gc_x = die_width/2 - 150e3
    gc_y_start = -200e3 + y_offset  # Adjust for y_offset

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
        
        # Create Y-branch tree with depth 2
        from SiEPIC.utils import create_cell2
        cell_y_branch = create_cell2(ly, 'ebeam_YBranch_te1310', 'EBeam-SiN')
        if not cell_y_branch:
            raise Exception('Cannot load Y-branch cell')
        
        # Create Y-branch tree with depth 2
        from SiEPIC.utils.layout import y_splitter_tree
        tree_depth = 1
        inst_tree_in, inst_tree_out, cell_tree = y_splitter_tree(cell, tree_depth=tree_depth, y_splitter_cell=cell_y_branch, library="EBeam-SiN", wg_type=wg_type, draw_waveguides=True)
        
        # Position the tree after the heater
        tree_x = inst_heater.bbox().right
        tree_y = inst_heater.pinPoint('opt2').y
        t = pya.Trans(pya.Trans.R0, tree_x, tree_y)
        tree_inst = cell.insert(pya.CellInstArray(cell_tree.cell_index(), t))
        
        # Connect heater to tree input
        connect_pins_with_waveguide(inst_heater, 'opt2', inst_tree_in, 'opt_1', waveguide_type=wg_type)
        
        print(f'Placing student design {submission_cell_new.name}')
        # Connect student design to tree output using connect_cell
        submission_inst = connect_cell(inst_tree_out[0], 'opt2', submission_cell_new, 'opt_laser')
        
        # Move the instance up hierarchy with proper transformation handling
        submission_inst = move_instance_up_hierarchy(submission_inst, num_levels=1)
        # Apply positioning transform after hierarchy move
        submission_inst.transform(pya.Trans(2 * radius * 1e3, submission_GC_dy))

        wg = connect_pins_with_waveguide(inst_tree_out[0], 'opt2', submission_inst, 'opt_laser', waveguide_type=wg_type)
        print(f'waveguide: {wg}')
        
        
        # Create a copy of the student design
        print(f"Creating copy of student design")
        submission_copy = ly.create_cell(submission_cell_new.name + "_copy")
        
        # Load the layout again to make a fresh copy
        print(f"Loading fresh copy from {filename}")
        # Construct full path to submission file
        import os
        script_path = os.path.dirname(os.path.realpath(__file__))
        submissions_path = os.path.join(os.path.dirname(script_path), "submissions")
        full_filename = os.path.join(submissions_path, filename)
        layout_copy = pya.Layout()
        layout_copy.read(full_filename)
        from SiEPIC.utils import top_cell_with_most_subcells_or_shapes
        fresh_top_cell = top_cell_with_most_subcells_or_shapes(layout_copy)
        
        # Explode regular arrays in the copy
        print(f"    Exploding regular arrays in copy...")
        exploded_count = explode_regular_arrays(fresh_top_cell, log_func=lambda msg: print(f"      {msg}"))
        if exploded_count > 0:
            print(f"    Exploded {exploded_count} regular arrays in copy")
        else:
            print(f"    No regular arrays found in copy")

        # Create sub-cell under subcell cell, using user's cell name
        subcell_copy = ly.create_cell(fresh_top_cell.name+'_copy')
        #t = pya.Trans(pya.Trans.R0, 0,0)
        #subcell_inst = cell.insert(pya.CellInstArray(subcell_copy.cell_index(), t)) 
        subcell_copy.copy_tree(fresh_top_cell)
        
        # Create FaML cell for GC replacement
        cell_faml = create_cell2(ly, 'ebeam_dream_FaML_Shuksan_SiN_1310_BB', 'EBeam-Dream')
        if not cell_faml:
            print("Warning: Could not load FaML cell")
        
        # Function to recursively find and replace GC cells with FaML in the copy
        def replace_gc_with_faml(cell, visited_cells=None):
            if visited_cells is None:
                visited_cells = set()
            
            if cell.cell_index() in visited_cells:
                return []
            
            visited_cells.add(cell.cell_index())
            gc_positions = []
            
            # Check all instances in this cell
            instances_to_replace = []
            for inst in cell.each_inst():
                inst_cell = ly.cell(inst.cell_index)
                if "GC" in inst_cell.name:
                    instances_to_replace.append(inst)
                    # Store GC position for reference (no accumulated transformation needed)
                    gc_bbox = inst_cell.bbox().transformed(inst.trans)
                    gc_positions.append((gc_bbox.center().x, gc_bbox.center().y))
            
            # Replace GC instances with FaML
            for inst in instances_to_replace:
                inst_cell = ly.cell(inst.cell_index)
                print(f"Replacing GC cell '{inst_cell.name}' with FaML in copy")
                
                if cell_faml:
                    # Calculate offset between FaML origin and opt1 pin
                    faml_pin = cell_faml.find_pin('opt1')
                    if faml_pin:
                        # Get the offset from FaML origin to opt1 pin
                        pin_offset_x = faml_pin.center.x
                        pin_offset_y = faml_pin.center.y
                        
                        # Apply the offset to position FaML so its opt1 pin aligns with GC position
                        # Since GC origin is at opt1, we need to offset FaML by the pin position
                        offset_trans = pya.Trans(pin_offset_x, pin_offset_y)
                        faml_trans = offset_trans * inst.trans
                        
                        faml_inst = cell.insert(pya.CellInstArray(cell_faml.cell_index(), faml_trans))
                        print(f"Replaced GC at position ({inst.trans.disp.x}, {inst.trans.disp.y}) with FaML (offset by {pin_offset_x}, {pin_offset_y})")
                    else:
                        # Fallback: use original transformation if pin not found
                        faml_inst = cell.insert(pya.CellInstArray(cell_faml.cell_index(), inst.trans))
                        print(f"Replaced GC at position ({inst.trans.disp.x}, {inst.trans.disp.y}) with FaML (no pin offset)")
                    
                    # Remove the original GC instance
                    cell.erase(inst)
                else:
                    print("Warning: FaML cell not available for replacement")
            
            # Recursively check sub-cells (no need to pass transformations)
            for inst in cell.each_inst():
                inst_cell = ly.cell(inst.cell_index)
                sub_gc_positions = replace_gc_with_faml(inst_cell, visited_cells)
                gc_positions.extend(sub_gc_positions)
            
            return gc_positions
        
        # Replace GC cells with FaML in the copy
        gc_positions = replace_gc_with_faml(subcell_copy)
        
        print(f'Adding port for design {subcell_copy.name}')
        # Add a pin to the copy cell for Y-branch connection
        # Find the port_SiN cell in the copy and add a pin
        port_cell_copy, port_y_copy = find_port_sin_cell_and_position(subcell_copy)
        if port_cell_copy:
            port_bbox_copy = port_cell_copy.bbox()
            pin_x_copy = int(port_bbox_copy.left - port_bbox_copy.left)  # 0, left edge
            pin_y_copy = int(0)  # middle vertically
            make_pin(port_cell_copy, 'opt_laser', [pin_x_copy, pin_y_copy], 800, 'PinRec', 180, debug=False)
            print(f"Added opt_laser pin to copy port cell")
        else:
            print("Warning: Could not find port_SiN in copy for pin creation")

        # Connect student design to tree output using connect_cell
        subcell_inst = connect_cell(inst_tree_out[0], 'opt3', subcell_copy, 'opt_laser')
        
        # Move the instance up hierarchy with proper transformation handling
        subcell_inst = move_instance_up_hierarchy(subcell_inst, num_levels=1)
        # Apply positioning transform after hierarchy move
        subcell_inst.transform(pya.Trans(2 * radius * 1e3, submission_GC_dy-fresh_top_cell.bbox().height()))

                
        # Find the absolute position of the FaML cell and align it with chip edge
        if cell_faml:
            # Function to find FaML positions in the layout by traversing the hierarchy
            def find_faml_positions(cell, parent_transform=pya.Trans()):
                faml_positions = []
                for inst in cell.each_inst():
                    inst_cell = ly.cell(inst.cell_index)
                    # Check if this instance is a FaML cell
                    if inst_cell.name == cell_faml.name:
                        # Calculate absolute position including all transformations
                        absolute_trans = parent_transform * inst.trans
                        faml_positions.append(absolute_trans.disp.x)
                        print(f"Found FaML instance at absolute x={absolute_trans.disp.x}")
                    else:
                        # Recursively check sub-cells
                        sub_transform = parent_transform * inst.trans
                        sub_faml_positions = find_faml_positions(inst_cell, sub_transform)
                        faml_positions.extend(sub_faml_positions)
                return faml_positions
            
            # Find all FaML positions in the copy
            faml_positions = find_faml_positions(subcell_copy, pya.Trans())
            
            if faml_positions:
                # Get the rightmost FaML position
                rightmost_faml_x = max(faml_positions)
                
                # Calculate how much to move the copy to align rightmost FaML with chip edge
                chip_right_edge = die_width/2
                faml_to_edge_offset = chip_right_edge - rightmost_faml_x
                
                # Move the entire copy by this offset
                new_copy_x = faml_to_edge_offset
                subcell_inst.parent_cell = cell
                subcell_inst.trans = pya.Trans(pya.Trans.R0, new_copy_x, subcell_inst.trans.disp.y)
                
                print(f"Found rightmost FaML at absolute x={rightmost_faml_x}")
                print(f"Chip right edge at x={chip_right_edge}")
                print(f"Moving copy by {faml_to_edge_offset} to align FaML with chip edge")
                print(f"Copy repositioned to x={new_copy_x}")
            else:
                print("No FaML cells found in copy")
        
        # Connect second tree output (opt3) to student design copy
        connect_pins_with_waveguide(inst_tree_out[0], 'opt3', subcell_inst, 'opt_laser',
                                    waveguide_type=wg_type)
        
        print(f"Positioned student design copy at x={subcell_inst.trans.disp.x}")
        print(f"Copy positioned down 250 µm from tree")
        print(f"Connected tree output 2 to student copy")
        
    else:
        print(f"No port_SiN found in submission {submission_name}, using fallback connection")
        # Fallback: create pin at submission cell center and connect manually
        from SiEPIC.utils.layout import make_pin
        make_pin(submission_cell_new, 'opt_laser', [submission_bbox.width()//2, 0], 800, 'PinRec', 0)
        
        # Create Y-branch tree with depth 2
        from SiEPIC.utils import create_cell2
        cell_y_branch = create_cell2(ly, 'ebeam_YBranch_te1310', 'EBeam-SiN')
        if not cell_y_branch:
            raise Exception('Cannot load Y-branch cell')
        
        # Create Y-branch tree with depth 2
        from SiEPIC.utils.layout import y_splitter_tree
        tree_depth = 2
        inst_tree_in, inst_tree_out, cell_tree = y_splitter_tree(cell, tree_depth=tree_depth, y_splitter_cell=cell_y_branch, library="EBeam-SiN", wg_type=wg_type, draw_waveguides=True)
        
        # Position the tree after the heater
        tree_x = inst_heater.bbox().right
        tree_y = inst_heater.pinPoint('opt2').y
        t = pya.Trans(pya.Trans.R0, tree_x, tree_y)
        tree_inst = cell.insert(pya.CellInstArray(cell_tree.cell_index(), t))
        
        # Connect heater to tree input
        connect_pins_with_waveguide(inst_heater, 'opt2', inst_tree_in, 'opt_1', waveguide_type=wg_type)
        
        # Connect student design to tree output using connect_cell
        #submission_inst = connect_cell(inst_tree_out[0], 'opt2', submission_cell_new, 'opt_laser')
        
        # Move the instance up hierarchy with proper transformation handling
        #submission_inst = move_instance_up_hierarchy(submission_inst, num_levels=1)
        # Apply positioning transform after hierarchy move
        # submission_inst.transform(pya.Trans(2 * radius * 1e3, 250e3))
        
        # Connection already established via connect_cell above
        
        # Create FaML cell on the right edge of the chip as reference path
        cell_faml = create_cell2(ly, 'ebeam_dream_FaML_Shuksan_SiN_1310_BB', 'EBeam-Dream')
        if cell_faml:
            # Position FaML exactly at the right edge of the chip, rotated 180°
            faml_x = die_width/2  # Exactly at right edge
            faml_y = center_y  # Center vertically (includes y_offset)
            faml_inst = cell.insert(pya.CellInstArray(cell_faml.cell_index(), 
                                                     pya.Trans(pya.Trans.R180, faml_x, faml_y)))
            
            # Connect the second tree output (opt3) to FaML
            connect_pins_with_waveguide(inst_tree_out[0], 'opt3', faml_inst, 'opt1',
                                   waveguide_type=wg_type)
            print(f"Created FaML cell on right edge at x={faml_x}")
        else:
            print("Warning: Could not load FaML cell")
    
    return inst


def parse_verification_errors(verification_output):
    """
    Parse verification output to categorize different types of errors.
    
    Args:
        verification_output: String output from layout_check with verbose=True
        
    Returns:
        dict: Dictionary with error types as keys and counts as values
    """
    error_counts = {
        'disconnected_pins': 0,
        'floating_shapes': 0,
        'invalid_components': 0,
        'missing_pins': 0,
        'pin_errors': 0,
        'other_errors': 0
    }
    
    lines = verification_output.split('\n')
    for line in lines:
        line_lower = line.lower()
        if 'disconnected pin' in line_lower:
            error_counts['disconnected_pins'] += 1
        elif 'floating shape' in line_lower:
            error_counts['floating_shapes'] += 1
        elif 'invalid component' in line_lower:
            error_counts['invalid_components'] += 1
        elif 'missing pin' in line_lower:
            error_counts['missing_pins'] += 1
        elif 'pin' in line_lower and ('error' in line_lower or 'warning' in line_lower):
            error_counts['pin_errors'] += 1
        elif any(keyword in line_lower for keyword in ['error', 'warning', 'fail']):
            if not any(known_error in line_lower for known_error in ['disconnected', 'floating', 'invalid', 'missing']):
                error_counts['other_errors'] += 1
    
    return error_counts


def load_submission_designs(submissions_path):
    """
    Load all submission designs from the submissions directory with verification.
    Skips files with disconnected pins or other critical errors.
    
    Args:
        submissions_path: Path to the submissions directory
        
    Returns:
        tuple: (submissions_list, error_summary_dict)
            submissions_list: List of tuples (filename, cell, layout, username)
            error_summary_dict: Dictionary with error summary statistics
    """
    submissions = []
    username_counts = {}  # Track how many files per username
    error_summary = {}  # Track errors by filename
    
    # Get all GDS/OAS files
    files_in = []
    for f in os.listdir(submissions_path):
        if f.lower().endswith(('.gds', '.oas')):
            files_in.append(os.path.join(submissions_path, f))

    if process_num_submissions > 0:
        files_in = files_in[0:process_num_submissions]

    
    for f in sorted(files_in):
        filename = os.path.basename(f)
        print(f"Loading submission: {filename}")
        
        # Load layout
        layout = pya.Layout()
        layout.read(f)
        
        # Find the top cell using robust method
        from SiEPIC.utils import top_cell_with_most_subcells_or_shapes
        cell = top_cell_with_most_subcells_or_shapes(layout)
        
        import siepic_ebeam_pdk
        layout.technology_name = 'EBeam'
        
        # Note: Regular array explosion will be done on the copy during PIClet creation
        
        # Run verification on the submission
        print(f"  Running verification...")
        try:
            num_errors = layout_check(cell=cell, verbose=False, GUI=False)
            
            # Get detailed error information by capturing verbose output
            error_details = {}
            if num_errors > 0:
                import io
                import sys
                
                # Capture verification output
                old_stdout = sys.stdout
                sys.stdout = captured_output = io.StringIO()
                try:
                    layout_check(cell=cell, verbose=True, GUI=False)
                except:
                    pass
                finally:
                    sys.stdout = old_stdout
                
                verification_output = captured_output.getvalue()
                
                # Parse error types
                error_details = parse_verification_errors(verification_output)
                
                # Check for critical errors (disconnected pins)
                if error_details.get('disconnected_pins', 0) > 0:
                    print(f"  SKIPPING: Found {error_details['disconnected_pins']} disconnected pins in {filename}")
                    error_summary[filename] = error_details
                    continue
                
                if num_errors > 0:
                    print(f"  Warning: {num_errors} verification errors found, but continuing")
                    for error_type, count in error_details.items():
                        if count > 0:
                            print(f"    {error_type}: {count}")
                else:
                    print(f"  ✓ Verification passed")
                
        except Exception as e:
            print(f"  Warning: Verification failed for {filename}: {e}")
            # Fallback to simple validation
            bbox = cell.bbox()
            if bbox.width() < 1000 or bbox.height() < 1000:  # Less than 1 µm
                print(f"  SKIPPING: Cell too small (likely empty) in {filename}")
                error_summary[filename] = {'error': 'Cell too small'}
                continue
            print(f"  ✓ Basic validation passed")
            error_details = {'verification_failed': 1}
        
        # Get GitHub username
        username = get_github_username(f)
        
        # Handle duplicate usernames by adding numbers
        if username in username_counts:
            username_counts[username] += 1
            username_with_number = f"{username}{username_counts[username]}"
        else:
            username_counts[username] = 1
            username_with_number = username
        
        print(f"  GitHub username: {username_with_number}")
        print(f"  ✓ Loaded successfully")
        submissions.append((filename, cell, layout, username_with_number))
        
        # Store error details for this file
        error_summary[filename] = error_details
         
    return submissions, error_summary

def ground_wire(topcell):
    '''
    Create a ground wire between the lasers, using the deep trench layer
    '''
    ly = topcell.layout()
    layer = ly.layer(ly.TECHNOLOGY['Deep Trench'])
    components = topcell.find_components(verbose=False)
    ymin, ymax = [], []
    for c in components:
        if c.component == "ebeam_dream_Laser_SiN_1310_Bond_BB":
            ymin.append(c.cell.bbox().transformed(c.trans).bottom)
            ymax.append(c.cell.bbox().transformed(c.trans).top)
    print(ymin, ymax)
    # Wire from the smallest ymax to the highest ymin
    wire = pya.Path([pya.Point(-die_width/2 + ground_wire_width/2, min(ymax)), 
                     pya.Point(-die_width/2 + ground_wire_width/2, max(ymin))], ground_wire_width)
    topcell.shapes(layer).insert(wire)


def print_error_summary_table(error_summary):
    """
    Print a formatted table showing error counts by file and error type.
    
    Args:
        error_summary: Dictionary with filename as keys and error details as values
    """
    print("\n" + "="*100)
    print("VERIFICATION ERROR SUMMARY")
    print("="*100)
    
    if not error_summary:
        print("No errors found in any files.")
        return
    
    # Get all unique error types across all files
    all_error_types = set()
    for filename, errors in error_summary.items():
        if isinstance(errors, dict):
            all_error_types.update(errors.keys())
    
    # Sort error types for consistent display
    error_types = sorted(list(all_error_types))
    
    # Print header
    header = f"{'Filename':<40}"
    for error_type in error_types:
        header += f"{error_type.replace('_', ' ').title():<15}"
    header += "Status"
    print(header)
    print("-" * len(header))
    
    # Print data rows
    for filename in sorted(error_summary.keys()):
        row = f"{filename:<40}"
        errors = error_summary[filename]
        
        if isinstance(errors, dict):
            status = "SKIPPED" if any(count > 0 for count in errors.values()) else "PASSED"
            for error_type in error_types:
                count = errors.get(error_type, 0)
                row += f"{count:<15}"
        else:
            status = "SKIPPED"
            for error_type in error_types:
                row += f"{'N/A':<15}"
        
        row += status
        print(row)
    
    # Print totals
    print("-" * len(header))
    total_row = f"{'TOTAL ERRORS':<40}"
    total_errors = 0
    for error_type in error_types:
        total = sum(errors.get(error_type, 0) for errors in error_summary.values() 
                   if isinstance(errors, dict))
        total_row += f"{total:<15}"
        total_errors += total
    
    total_row += f"{len(error_summary)} files"
    print(total_row)
    
    # Summary statistics
    skipped_files = sum(1 for errors in error_summary.values() 
                       if isinstance(errors, dict) and any(count > 0 for count in errors.values()))
    passed_files = len(error_summary) - skipped_files
    
    print(f"\nSUMMARY:")
    print(f"  Total files processed: {len(error_summary)}")
    print(f"  Files passed verification: {passed_files}")
    print(f"  Files with errors (skipped): {skipped_files}")
    print(f"  Total error count: {total_errors}")


def create_piclet_layout(ly, filename, submission_name, submission_cell, filename2=None, submission_name2=None, submission_cell2=None):
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

    # Load and insert the Dream logo
    try:
        # Try to find the logo file in the current project first
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(os.path.dirname(script_dir), "designs", "KLayout Python", "dreamlogo_outline.oas")
        
        # If not found, try the SiEPIC_Shuksan_ANT_SiN_2025_08 project
        if not os.path.exists(logo_path):
            logo_path = "/Users/lukasc/Documents/GitHub/SiEPIC_Shuksan_ANT_SiN_2025_08/designs/KLayout Python/dreamlogo_outline.oas"
        
        if os.path.exists(logo_path):
            logo_layout = pya.Layout()
            logo_layout.read(logo_path)
            logo_cell = logo_layout.top_cell()
            # Position logo at bottom-left corner of the chip
            logo_cell.transform(pya.Trans(-die_width/2, -die_height/2))
            topcell.copy_shapes(logo_cell)
            print(f"  Added Dream logo from {logo_path}")
        else:
            print("  Warning: Dream logo file not found")
    except Exception as e:
        print(f"  Warning: Could not load Dream logo: {e}")

    # Create simplified PIClet with submission design(s)
    if filename2 and submission_name2 and submission_cell2:
        # Two submissions per PIClet
        inst_piclet1 = create_simplified_piclet(topcell, submission_cell, submission_name, filename, wavelength=1310, y_offset=0)
        inst_piclet2 = create_simplified_piclet(topcell, submission_cell2, submission_name2, filename2, wavelength=1310, y_offset=-laser_circuit_spacing)  # Use configurable spacing
    else:
        # Single submission
        inst_piclet = create_simplified_piclet(topcell, submission_cell, submission_name, filename)

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
    submissions, error_summary = load_submission_designs(submissions_path)
    print(f"Found {len(submissions)} submissions")
        
    # Process submissions in pairs
    for i in range(0, len(submissions), 2):
        if i + 1 < len(submissions):
            # Two submissions per PIClet
            filename1, submission_cell1, submission_layout1, username1 = submissions[i]
            filename2, submission_cell2, submission_layout2, username2 = submissions[i + 1]
            print(f"Generating PIClet for pair: {username1} and {username2}")
            
            try:
                # Create new layout for this PIClet
                dbu = 0.001
                piclet_name = f"PIClet-3x3-{username1}-{username2}"
                topcell, ly = new_layout(pdk.tech.name, piclet_name, overwrite=True)
                ly.dbu = dbu
                ly.technology_name = pdk.tech.name
                from SiEPIC.utils.layout import add_time_stamp
                add_time_stamp(topcell, layerinfo=pya.LayerInfo(10,0))    
                
                # Create the PIClet layout with both submissions
                topcell = create_piclet_layout(ly, filename1, username1, submission_cell1,
                                            filename2, username2, submission_cell2)

                ground_wire(topcell)

                from SiEPIC.utils import layout_pgtext
                layout_pgtext(topcell, pya.LayerInfo(4, 0), -200, -1170, piclet_name, 20)
                                
                # Export layout
                tapeout_path = "/Users/lukasc/Documents/GitHub/SiEPIC_Shuksan_ANT_SiN_2025_08/submissions/3x3"
                if os.path.exists(tapeout_path):
                    file_out = export_layout(
                        topcell, tapeout_path, filename=topcell.name
                    )
                else:  
                    raise Exception(f"Tapeout path {tapeout_path} does not exist")
                
                file_out = export_layout(
                    topcell, piclets_path, filename=topcell.name
                )
                topcell.show()
                
                print(f"  Generated: {file_out}")
                    
            except Exception as e:
                print(f"  Error generating PIClet for {username1}/{username2}: {str(e)}")
                continue
                            
        else:
            # Single submission (odd number)
            filename, submission_cell, submission_layout, username = submissions[i]
            print(f"Generating PIClet for single submission: {username}")
            
            try:
                # Create new layout for this PIClet
                dbu = 0.001
                piclet_name = f"PIClet-3x3-{username}"
                topcell, ly = new_layout(pdk.tech.name, piclet_name, overwrite=True)
                ly.dbu = dbu
                ly.technology_name = pdk.tech.name
                from SiEPIC.utils.layout import add_time_stamp
                add_time_stamp(topcell, layerinfo=pya.LayerInfo(10,0))    
                
                # Create the PIClet layout with single submission
                topcell = create_piclet_layout(ly, filename, username, submission_cell)
                
                from SiEPIC.utils import layout_pgtext
                layout_pgtext(topcell, pya.LayerInfo(4, 0), -200, -1170, piclet_name, 20)
                
                # Export layout
                file_out = export_layout(
                    topcell, piclets_path, filename=topcell.name
                )
                topcell.show()
                tapeout_path = "/Users/lukasc/Documents/GitHub/SiEPIC_Shuksan_ANT_SiN_2025_08/submissions/3x3"
                if os.path.exists(tapeout_path):
                    file_out = export_layout(
                        topcell, tapeout_path, filename=topcell.name
                    )
                else:  
                    raise Exception(f"Tapeout path {tapeout_path} does not exist")
                    
                                
                
                print(f"  Generated: {file_out}")
                
            except Exception as e:
                print(f"  Error generating PIClet for {username}: {str(e)}")
                continue
    
    # Display error summary table
    print_error_summary_table(error_summary)
    
    print("PIClet generation complete!")


if __name__ == "__main__":
    """
    Main execution block for generating PIClets from submissions.
    """
    generate_piclets()
    
    
    
    
    