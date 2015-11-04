#! /usr/bin/env python

import os
from math import sqrt

# OpenCV imports
import cv2

# Project imports
from src.extraction.item_extraction import *
from src.util.image_writer import ImageWriter
from src.util.image_utils import *

def process_geo_image(geo_image, locators, camera_rotation, image_directory, out_directory, use_marked_image):
    '''Return list of extracted items sorted in direction of movement.'''
    full_filename = os.path.join(image_directory, geo_image.file_name)
    
    image = cv2.imread(full_filename, cv2.CV_LOAD_IMAGE_COLOR)
    
    if image is None:
        print 'Cannot open image: {}'.format(full_filename)
        return []
    
    # Update remaining geo image properties before doing image analysis.  This makes it so we only open image once.
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
    image_items = order_items(image_items, camera_rotation)

    if marked_image is not None:
        marked_image_filename = postfix_filename(geo_image.file_name, '_marked')
        marked_image_path = os.path.join(out_directory, marked_image_filename)
        cv2.imwrite(marked_image_path, marked_image)
        
    return image_items

def all_items(geo_images):
    '''Return single list of all items found within geo images.'''
    items = []
    for geo_image in geo_images:
        items.extend(geo_image.items)
    return items

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

def calculate_geo_image_corners(geo_image):
    '''Update corner positions of geo_image.'''
    geo_image.top_left_position = calculate_pixel_position(0, 0, geo_image)
    geo_image.top_right_position = calculate_pixel_position(geo_image.width, 0, geo_image)
    geo_image.bottom_right_position = calculate_pixel_position(geo_image.width, geo_image.height, geo_image)
    geo_image.bottom_left_position = calculate_pixel_position(0, geo_image.height, geo_image)

def cluster_merged_items(items, parent_images, cluster_size):
    
    clustered_merged_items = []
    for item in items:
        clusters = []
        item_refs = [item] + item.other_items
        for item_ref in item_refs:
            added_to_an_existing_cluster = False
            for cluster in clusters:
                for clustered_item in cluster:
                    if position_difference(item_ref.position, clustered_item.position) < cluster_size:
                        cluster.append(item_ref)
                        added_to_an_existing_cluster = True
                        break
            if not added_to_an_existing_cluster:
                # make a new cluster
                clusters.append([item_ref])
        
        clusters = sorted(clusters, key=lambda c: len(c), reverse=True)
        
        if len(clusters) == 0:
            continue 
        
        # TODO Remove hardcoded removal checks
        south_end_row_set = 0
        north_end_row_set = 0
        #effective_cluster_lengths = []
        valid_clusters = []
        for i, cluster in enumerate(clusters):
            #effective_cluster_length = 0
            non_bad_items = []
            for item_ref in cluster:
                geo_images = [geo_image for geo_image in parent_images if geo_image.file_name == item_ref.parent_image_filename]
                if len(geo_images) == 0:
                    continue # no parent image so no time stamp
                geo_image = geo_images[0]
                image_time = geo_image.image_time
                if image_time > 1436381595.84399 and image_time < 1436382495.42099:
                    south_end_row_set += 1
                elif image_time > 1436384915.009 and image_time < 1436385609.175:
                    north_end_row_set += 1
                else:
                    #effective_cluster_length += 1
                    non_bad_items.append(item_ref)
                    
            if len(non_bad_items) > 0:
                valid_clusters.append(non_bad_items)
            
            #if len(non_bad_items) != len(cluster):
            #    print "For {} reducing cluster from {} to {}".format(item.name, len(cluster), len(non_bad_items))
                    
        if len(valid_clusters) > 0:
            clusters = valid_clusters
        else:
            pass
            #print "No valid clusters for {}".format(item.name)
            
        '''
        if item.name == "R.51":
            print "For R.51"
            for c, cluster in enumerate(clusters):
                #print "Cluster {}".format(c)
                for ref in cluster:
                    #print "{} in {}".format(ref.position, ref.parent_image_filename)
        '''
            
        kept_cluster = []
        if len(clusters) == 1:
            kept_cluster = clusters[0]
        elif len(clusters) > 1:
            largest_cluster = clusters[0]
            second_largest_cluster = clusters[1]
            
            if len(largest_cluster) > len(second_largest_cluster):
                kept_cluster = largest_cluster
            else:
                #kept_cluster = largest_cluster
                for cluster in clusters:
                    kept_cluster += cluster # keep all clusters

        main_item = kept_cluster[0]
        main_item.other_items = []
        for item in kept_cluster[1:]:
            item.other_items = []
            main_item.other_items.append(item)

        clustered_merged_items.append(main_item)

    return clustered_merged_items
        
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
            # Can't just say they're the same because row/start end could have same name.
            max_position_difference = max(max_position_difference, 30)
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
 