#! /usr/bin/env python

import os
from math import sqrt

# OpenCV imports
import cv2

# Project imports
from src.extraction.item_extraction import *
from src.util.image_writer import ImageWriter
from src.util.image_utils import *
from src.extraction.code_finder import create_qr_code

def process_geo_image(geo_image, locators, image_directory, out_directory, use_marked_image):
    '''Return list of extracted items'''
    image_filepath = os.path.join(image_directory, geo_image.file_name)
    geo_image.file_path = image_filepath
    
    image = cv2.imread(image_filepath, cv2.CV_LOAD_IMAGE_COLOR)
    
    if image is None:
        print 'Cannot open image: {}'.format(image_filepath)
        return []
    
    # Update remaining geo image properties before doing image analysis.
    geo_image.height, geo_image.width, _ = image.shape
    
    if geo_image.resolution <= 0:
        print "Cannot calculate image resolution. Skipping image."
        return []
    
    # Specify 'image directory' so that if any images associated with current image are saved a directory is created.
    image_out_directory = os.path.join(out_directory, os.path.splitext(geo_image.file_name)[0])
    ImageWriter.output_directory = image_out_directory
    
    marked_image = None
    if use_marked_image:
        # Copy original image so we can mark on it for debugging.
        marked_image = image.copy()
    
    calculate_geo_image_corners(geo_image)
    
    image_items = locate_items(locators, geo_image, image, marked_image)
    image_items = extract_items(image_items, geo_image, image, marked_image)
    #image_items = order_items(image_items, camera_rotation)

    if marked_image is not None:
        marked_image_filename = postfix_filename(geo_image.file_name, '_marked')
        marked_image_path = os.path.join(out_directory, marked_image_filename)
        cv2.imwrite(marked_image_path, marked_image)
        
    return image_items

def process_geo_image_to_find_plant_parts(geo_image, leaf_finder, stick_finder, tag_finder, out_directory, use_marked_image):
    '''Return list of leaves and sticks found inside geo image.'''

    image = cv2.imread(geo_image.file_path, cv2.CV_LOAD_IMAGE_COLOR)
    
    if image is None:
        print 'Cannot open image: {}'.format(geo_image.file_path)
        return [], []
    
    if geo_image.resolution <= 0:
        print "Cannot calculate image resolution. Skipping image."
        return [], []
    
    # Specify 'image directory' so that if any images associated with current image are saved a directory is created.
    image_out_directory = os.path.join(out_directory, os.path.splitext(geo_image.file_name)[0])
    ImageWriter.output_directory = image_out_directory
    
    marked_image = None
    if use_marked_image:
        # Copy original image so we can mark on it for debugging.
        marked_image = image.copy()
    
    leaves = leaf_finder.locate(geo_image, image, marked_image)
    if stick_finder is not None:
        sticks = stick_finder.locate(geo_image, image, marked_image)
    else:
        sticks = []
        
    if tag_finder is not None:
        tags = tag_finder.locate(geo_image, image, marked_image)
    else:
        tags = []

    if marked_image is not None:
        marked_image_filename = postfix_filename(geo_image.file_name, '_marked')
        marked_image_path = os.path.join(out_directory, marked_image_filename)
        cv2.imwrite(marked_image_path, marked_image)
        
    return leaves, sticks, tags

def all_items(geo_images):
    '''Return single list of all items found within geo images.'''
    items = []
    for geo_image in geo_images:
        items.extend(geo_image.items)
    return items

def all_segments_from_rows(rows):
    segments_by_row = [row.segments for row in rows]
    all_segments = [seg for row_segments in segments_by_row for seg in row_segments]
    return all_segments

def all_groups_from_segments(segments):
    groups = []
    for segment in segments:
        if segment.group is not None and segment.group not in groups:
            groups.append(segment.group)
    return groups

def order_items(items, camera_rotation):
    '''Return new list but sorted from backward to forward taking into account camera rotation.'''
    if camera_rotation == 180:  # top to bottom
        return sorted(items, key=lambda item: rectangle_center(item.bounding_rect)[1])
    elif camera_rotation == 0: # bottom to top
        return sorted(items, key=lambda item: rectangle_center(item.bounding_rect)[1], reverse=True)
    elif camera_rotation == 90: # left to right
        return sorted(items, key=lambda item: rectangle_center(item.bounding_rect)[0])
    elif camera_rotation == 270: # right to left
        return sorted(items, key=lambda item: rectangle_center(item.bounding_rect)[0], reverse=True)
    else:
        return None
    
def merge_items(items, max_distance):
    '''Return new list of items with all duplicates removed and instead can be referenced through surviving items.'''
    unique_items = []
    for item in items:
        matching_item = None
        for comparision_item in unique_items:
            if is_same_item(item, comparision_item, max_distance):
                matching_item = comparision_item
                break
        if matching_item is None:
            #print 'No matching item for {} adding to list'.format(item.name)
            unique_items.append(item)
        else:
            # We've already stored this same item so just have the one we stored reference this one.
            matching_item.other_items.append(item)
            
    return unique_items

def get_subset_of_geo_images(geo_images, debug_start, debug_stop):
    '''Return start and stop indices in geo_images corresponding to the substrings in debug start/stop'''
    geo_image_filenames = [g.file_name for g in geo_images]
    start_geo_index = index_containing_substring(geo_image_filenames, debug_start)
    if start_geo_index < 0:
        start_geo_index = 0
    stop_geo_index = index_containing_substring(geo_image_filenames, debug_stop)
    if stop_geo_index < 0:
        stop_geo_index = len(geo_images) - 1
        
    return start_geo_index, stop_geo_index

def dont_overlap_with_items(items, rectangles):
    '''Return updated rectangles list such that no rectangles are fully enclosed in any items.'''
    unenclosed_rectangles = []
    for rect in rectangles:
        enclosed = False
        rx1, ry1, rx2, ry2 = rectangle_corners(rotated_to_regular_rect(rect), False)
        for item in items:
            if item.bounding_rect is None:
                continue # item wasn't imaged
            ix1, iy1, ix2, iy2 = rectangle_corners(rotated_to_regular_rect(item.bounding_rect), False) # item corners
            if ry1 > iy1 and ry2 < iy2 and rx1 > ix1 and rx2 < ix2:
                enclosed = True
                break
        if not enclosed:
            unenclosed_rectangles.append(rect)

    return unenclosed_rectangles

def calculate_geo_image_corners(geo_image):
    '''Update corner positions of geo_image.'''
    geo_image.top_left_position = calculate_pixel_position(0, 0, geo_image)
    geo_image.top_right_position = calculate_pixel_position(geo_image.width, 0, geo_image)
    geo_image.bottom_right_position = calculate_pixel_position(geo_image.width, geo_image.height, geo_image)
    geo_image.bottom_left_position = calculate_pixel_position(0, geo_image.height, geo_image)
        
def position_difference(position1, position2):
    '''Return difference in XY positions between both items.'''
    delta_x = position1[0] - position2[0]
    delta_y = position1[1] - position2[1]
    return sqrt(delta_x*delta_x + delta_y*delta_y)
        
def is_same_item(item1, item2, max_position_difference):
    '''Return true if both items are similar enough to be considered the same.'''
    if item1.type != item2.type:
        return False
    
    if (item1.type.lower() != 'rowcode') and (item1.parent_image_filename == item2.parent_image_filename):
        return False # Come from same image so can't be different... except there were duplicate row codes right next to each other.
    
    if 'code' in item1.type.lower(): 
        if item1.name == item2.name:
            # Same QR code so give ourselves more room to work with.
            # TODO - normally want to take into account specified max position difference.  But
            # if same code is planted in adjacent rows then definitely don't want those to be able to
            # be the same code (and rows are 1 meter apart so don't want those to get confused).
            max_position_difference = 50 # centimeters
        else:
            # Two codes with different names so can't be same item.
            return False

    # convert max difference from cm to meters
    max_position_difference /= 100.0
    
    if position_difference(item1.position, item2.position) > max_position_difference:
        return False # Too far apart
    
    return True # Similar enough

def is_same_position_item(item1, item2, max_position_difference):
    if item1.name != item2.name:
        return False
    
    # convert from cm to meters
    max_position_difference /= 100.0
    
    return position_difference(item1.position, item2.position) < max_position_difference

def cap_angle_plus_minus_180_deg(angle):
    '''Return angle in range of (-180, 180]'''
    while angle <= -180.0:
        angle += 360.0
    while angle > 180.0:
        angle -= 360.0
    return angle
        
def compare_angles(angle1, angle2, thresh):
    '''Return true if angle1 is within thresh degrees of angle2.  Everything in degrees.'''
    diff = angle1 - angle2
    diff = cap_angle_plus_minus_180_deg(diff)
    return abs(diff) < thresh

def orient_items(item1, item2, direction, thresh=45):
    '''Return item 1 and 2 as start_item , end_item specified by direction given in degrees.'''
    p1 = item1.position
    p2 = item2.position
    # Calculate angle from item1 to item2
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    angle =  math.degrees(math.atan2(dy, dx))
    if compare_angles(angle, direction, thresh):
        # item1 is the start item
        return item1, item2
    elif compare_angles(angle, -direction, thresh):
        # item2 is the start item
        return item2, item1
    else:
        print "Can't orient items with names {} and {}.  Angle {} is not within {} degrees of specified direction {}".format(item1.name, item2.name, angle, thresh, direction)
        return None, None
    
def lateral_and_projection_distance_2d(p, a, b):
    '''Return lateral error from position (p) to vector from points (a) to (b).'''
    a_to_b = (b[0] - a[0], b[1] - a[1])
    a_to_b_mag = sqrt(a_to_b[0]*a_to_b[0] + a_to_b[1]*a_to_b[1])
    
    if a_to_b_mag == 0.0:
        print "Warning: Vector from point a to b has zero magnitude. Returning NaN."
        return float('NaN')
    
    # Calculate position vector from a to p.
    a_to_p = (p[0] - a[0], p[1] - a[1])

    # Project a_to_p position vector onto a_to_b vector.
    a_to_b_traveled_mag = (a_to_p[0]*a_to_b[0] + a_to_p[1]*a_to_b[1]) / a_to_b_mag
    a_to_b_traveled = [0, 0]
    a_to_b_traveled[0] = a_to_b[0] * a_to_b_traveled_mag / a_to_b_mag
    a_to_b_traveled[1] = a_to_b[1] * a_to_b_traveled_mag / a_to_b_mag
    
    dx = a_to_p[0] - a_to_b_traveled[0]
    dy = a_to_p[1] - a_to_b_traveled[1]
    lateral_error_magnitude = sqrt(dx * dx + dy * dy)
    
    # Use cross product between path and position vector to find correct sign of lateral error.
    path_cross_position_z = a_to_b[0]*a_to_p[1] - a_to_b[1]*a_to_p[0]
    lateral_error_sign =  -1.0 if path_cross_position_z < 0.0 else 1.0
    
    lateral_error = lateral_error_sign * lateral_error_magnitude
    
    return lateral_error, a_to_b_traveled_mag

def projection_to_position_2d(projection, a, b):
    '''Return position associated with projecting along vector from points (a) to (b).'''
    a_to_b = (b[0] - a[0], b[1] - a[1])
    a_to_b_mag = sqrt(a_to_b[0]*a_to_b[0] + a_to_b[1]*a_to_b[1])
    
    if a_to_b_mag == 0.0:
        print "Warning: Vector from point a to b has zero magnitude. Returning NaN."
        return float('NaN')

    a_to_b_unit = [0, 0]
    a_to_b_unit[0] = a_to_b[0] / a_to_b_mag
    a_to_b_unit[1] = a_to_b[1] / a_to_b_mag
    
    x_offset = projection * a_to_b_unit[0]
    y_offset = projection * a_to_b_unit[1]
    
    return (a[0] + x_offset, a[1] + y_offset)
        
def apply_code_modifications(modifications, geo_images, all_codes, output_directory):
 
    for modification in modifications:
        if type(modification).__name__ == 'AddImagedCode':
            try:
                geo_image = [img for img in geo_images if modification.parent_filename == img.file_name][0]
            except IndexError:
                print "Can't find a matching geo image for modification {}".format(modification)
                continue
            x = modification.x_pixels
            y = modification.y_pixels
            resolution = geo_image.resolution
            side_length = 10 / resolution
            bounding_rect = ((x, y), (side_length, side_length), -1)
            code = create_qr_code(modification.id)
            code.bounding_rect = bounding_rect
            if code is None:
                print "Can't create code with ID {}".format(modification.id)
                continue
            image = cv2.imread(geo_image.file_path, cv2.CV_LOAD_IMAGE_COLOR)
            if image is None:
                print 'For modification {} cannot open image {}'.format(modification, geo_image.file_path)
                continue
            ImageWriter.output_directory = output_directory
            try:
                code = extract_items([code], geo_image, image, None, filter_edge_items=False)[0]
            except IndexError:
                print "Failure during extraction for modification {}".format(modification)
                continue
            all_codes.append(code)
            geo_image.items['codes'].append(code)
            print "Successfully added code with ID {}".format(code.name)
            
        if type(modification).__name__ == 'AddSurveyedCode':

            code = create_qr_code(modification.id)
            code.position = (modification.x, modification.y, modification.z)
            code.zone = modification.zone
            all_codes.append(code)
            #geo_image.items['codes'].append(code)
            
            print "Successfully added code with ID {}".format(code.name)
            
        elif type(modification).__name__ == 'DeleteCode':
 
            id_to_delete = modification.code_id
            all_codes = [code for code in all_codes if code.name != id_to_delete]
            
            num_refs_removed = 0
            for geo_image in geo_images:
                matching_codes = [code for code in geo_image.items.get('codes',[]) if code.name == id_to_delete]
                for code in matching_codes:
                    geo_image.items['codes'].remove(code)
                    num_refs_removed += 1
                
            print "Removed {} references to code id {} from geo images".format(num_refs_removed, id_to_delete)
                    
        elif type(modification).__name__ == 'ChangeCodeName':
            
            # Change code name, but won't change code type (row vs group code)
            # This will also update reference in images since not creating a new object.
            num_refs_changed = 0
            matching_codes = [code for code in all_codes if code.name == modification.original_code_id]
            for code in matching_codes:
                code.name = modification.new_code_id
                num_refs_changed += 1
                # TODO to this correctly, this is kind of hacky
                if code.type.lower() == 'rowcode':
                    code.row = int(modification.new_code_id[:-2])
                    
            print "Changed {} codes from {} to {}".format(num_refs_changed, modification.original_code_id, modification.new_code_id)
                    
        elif type(modification).__name__ == 'AddGapCode':
            
            # Set special flag that means any group starting with this code shouldn't have any plants
            matching_codes = [code for code in all_codes if code.name == modification.code_id]
            for code in matching_codes:
                code.is_gap_item = True
                
            num_refs_changed = 0
            for geo_image in geo_images:
                matching_codes = [code for code in geo_image.items.get('codes',[]) if code.name == modification.code_id]
                for code in matching_codes:
                    code.is_gap_item = True
                    num_refs_changed += 1
                
            print "Changed {} codes with ID {} to be gap codes with no plants.".format(num_refs_changed, modification.code_id)
                    
    return geo_images, all_codes

def calculate_field_positions_and_range(rows, base_items, items_to_calculate, geo_images=None):
    
    # use field angle to calculate range for each item.
    field_angle = np.mean([row.angle for row in rows])
    
    # How much we need to rotate East-North so that 'y' runs along rows.
    correction_angle = math.radians(90) - field_angle 
    
    # Find min/max of rotated coordinate so that after rotating the shift will be correct.
    rotated_x = []
    rotated_y = []
    base_z = []
    for item in base_items:
        x, y, z = rotate2d(item.position, correction_angle)
        rotated_x.append(x)
        rotated_y.append(y)
        base_z.append(z)
    min_x = min(rotated_x)
    min_y = min(rotated_y)
    min_z = min(base_z)
    
    # How much to shift regular positions after they've been rotated.
    field_shift = (min_x, min_y, min_z)

    # Now go through and assign field positions to each item.
    for item in items_to_calculate:
        item.field_position = rotate_and_shift(item.position, field_shift, correction_angle)
        
        # scale range so that there are around 5 plants in each unit.
        # TODO use actual plant spacing here instead of hardcoding scale.
        # Add one to reference off 1 like row number.
        range_units_per_meter = 0.25;
        item.range = int(item.field_position[1] * range_units_per_meter) + 1
        
    if geo_images is not None:
        for geo_image in geo_images:
            geo_image.field_position = rotate_and_shift(geo_image.position, field_shift, correction_angle)
            geo_image.top_left_field_position = rotate_and_shift(geo_image.top_left_position, field_shift, correction_angle)
            geo_image.top_right_field_position = rotate_and_shift(geo_image.top_right_position, field_shift, correction_angle)
            geo_image.bottom_right_field_position = rotate_and_shift(geo_image.bottom_right_position, field_shift, correction_angle)
            geo_image.bottom_left_field_position = rotate_and_shift(geo_image.bottom_left_position, field_shift, correction_angle)
            
def rotate2d(position, angle_rad):
    
    rotated_x = position[0] * math.cos(angle_rad) - position[1] * math.sin(angle_rad)
    rotated_y = position[0] * math.sin(angle_rad) + position[1] * math.cos(angle_rad)
    return rotated_x, rotated_y, position[2]
            
def rotate_and_shift(position, shift, angle_rad):
    
    x, y, z = rotate2d(position, angle_rad)
    x -= shift[0]
    y -= shift[1]
    z -= shift[2]
    return (x, y, z)
            
        