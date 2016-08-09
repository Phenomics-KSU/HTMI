#! /usr/bin/env python

import sys
import math
import copy
import itertools

# OpenCV imports
import cv2
import numpy as np

# Project imports
from src.util.image_utils import rectangle_corners
from src.extraction.item_extraction import calculate_pixel_position, calculate_position_pixel
from src.processing.item_processing import position_difference

def rect_to_global(rect, geo_image, rotated=True):
    '''Convert rect in pixels to tuple of 4 corners in global coordinates (in meters).'''
    if rotated:
        corners = rectangle_corners(rect)
    else:
        x, y, w, h = rect
        corners = [(x,y), (x,y+h), (x+w,y), (x+w,y+h)]
    
    g_corners = []
    for corner in corners:
        x_meters, y_meters, _ = calculate_pixel_position(corner[0], corner[1], geo_image)
        g_corners.append((x_meters, y_meters))
    
    return g_corners

def rect_to_image(rect, geo_image):
    '''Return rotated rectangle but in image coordinates instead of global coordinates.'''
    
    pixel_points = []
    for corner in rect:
        x_pixel, y_pixel = calculate_position_pixel(corner[0], corner[1], geo_image)
        pixel_points.append((int(x_pixel), int(y_pixel)))

    rotated_rect = cv2.minAreaRect(np.array(pixel_points))
        
    return rotated_rect

def merge_corner_rectangles(rectangles):
    '''Return global rectangle that contains all rectangles.'''

    #all_corners = [(int(c[0]), int(c[1])) for rect in rectangles for c in rect]
    #min_bounding = cv2.minAreaRect(np.array(all_corners))
    #return rectangle_corners(min_bounding)
    x_coords = [corner[0] for rect in rectangles for corner in rect]
    y_coords = [corner[1] for rect in rectangles for corner in rect]
    
    xmin = min(x_coords)
    xmax = max(x_coords)
    ymin = min(y_coords)
    ymax = max(y_coords)

    return ((xmin, ymin), (xmin, ymax), (xmax, ymin), (xmax, ymax))

def distance_between_clusters(c1, c2):
    '''Return smallest distance between rectangle corners in cluster rectangles.'''

    smallest_dist = sys.float_info.max
    for item in c1['items']:
        for other_item in c2['items']:
            dist = distance_between_corner_rects(item['rect'], other_item['rect'])
            if dist < smallest_dist:
                smallest_dist = dist
            
    return smallest_dist

def distance_between_corner_rects(r1, r2):
    '''Return smallest distance between rectangle corners.'''

    dists = [] * 4
    for k in range(4):
        dx = r1[k][0] - r2[k][0]
        dy = r1[k][1] - r2[k][1]
        dists.append(math.sqrt(dx*dx + dy*dy))

    return min(dists)

def corner_rect_center(rect):
    '''Return center of rectangle.'''

    rx = np.mean([corner[0] for corner in rect])
    ry = np.mean([corner[1] for corner in rect])
    
    return rx, ry

def corner_rectangle_size(rect):
    '''Return distance between rectangle centers.'''
    
    x_coords = [corner[0] for corner in rect]
    y_coords = [corner[1] for corner in rect]
    
    xmin = min(x_coords)
    xmax = max(x_coords)
    ymin = min(y_coords)
    ymax = max(y_coords)
    
    return (xmax - xmin), (ymax - ymin)
                
def merge_clusters(c1, c2):
    
    merged_rect = merge_corner_rectangles([c1['rect'], c2['rect']])
    merged_items = c1['items'] + c2['items']
    merged_item_center = corner_rect_center(merged_rect)
    return {'rect':merged_rect, 'items':merged_items, 'rect_center':merged_item_center}
 
def cluster_geo_image_items(geo_image, segment, max_plant_size, max_plant_part_distance):
    # Merge items into possible plants, while referencing rectangle off global coordinates so we can
    # compare rectangles between multiple images.
    leaves = [{'item_type':'leaf', 'rect':rect_to_global(rect, geo_image)} for rect in geo_image.items['leaves']]
    stick_parts = [{'item_type':'stick_part', 'rect':rect_to_global(rect, geo_image)} for rect in geo_image.items['stick_parts']]
    tags = [{'item_type':'tag', 'rect':rect_to_global(rect, geo_image)} for rect in geo_image.items['tags']]
    
    if segment.is_special:
        plant_parts = leaves # no blue sticks in single plants
        plant_parts = remove_plant_parts_close_to_code(plant_parts, segment.start_code, 0.04)
    else:
        plant_parts = leaves + stick_parts + tags
    geo_image_possible_plants = cluster_rectangle_items(plant_parts, max_plant_part_distance, max_plant_size)
    
    for plant in geo_image_possible_plants:
        plant['image_altitude'] = geo_image.position[2]
    
    geo_image.items['possible_plants'] = geo_image_possible_plants
    return geo_image_possible_plants

def cluster_rectangle_items(items, max_spacing, max_size):
    ''''''
    clusters = copy.copy(items)
    
    for cluster in clusters:
        cluster['items'] = [cluster]
    
    while True:

        closest_clusters, closest_spacing = find_closest_pair(clusters)
    
        if closest_clusters is None:
            break # clustered everything together

        if closest_spacing > max_spacing:
            break # everything too far apart to cluster any more.

        new_cluster = merge_clusters(*closest_clusters)
    
        new_width, new_height = corner_rectangle_size(new_cluster['rect'])
        if new_width > max_size or new_height > max_size:
            break # resulting cluster would be too big so don't do it.
        
        clusters.remove(closest_clusters[0])
        clusters.remove(closest_clusters[1])
        clusters.append(new_cluster)
        
    return clusters

def find_closest_pair(clusters):

    closest_clusters = None
    closest_spacing = sys.float_info.max
    for k, cluster in enumerate(clusters):
        for other_cluster in itertools.islice(clusters, k+1, None):
            cluster_spacing = distance_between_clusters(cluster, other_cluster)
            if cluster_spacing < closest_spacing:
                closest_clusters = (cluster, other_cluster)
                closest_spacing = cluster_spacing
            
    return closest_clusters, closest_spacing

def filter_out_noise(possible_plants):
    # Filter out anything that's most likely noise.  Worse case there's only one image of a blue stick
    # taken from the top that will get filtered out, but in that case it will be projected which should be close.
    filtered_possible_plants = []
    for possible_plant in possible_plants:
        if len(possible_plant.get('items',[])) > 1:
            xsize, ysize = corner_rectangle_size(possible_plant['rect'])
            if xsize > 0.015 or ysize > 0.015: # TODO remove hard coded numbers
                filtered_possible_plants.append(possible_plant)
    return filtered_possible_plants

def remove_plant_parts_close_to_code(plant_parts, code, closest_dist):
    '''Return updated plant part list such that none are within 'closest_dist' of code.'''
    filtered_plant_parts = []
    for part in plant_parts:
        x, y = corner_rect_center(part['rect'])
        dist_to_item = position_difference((x, y), code.position)
        if dist_to_item > closest_dist:
            filtered_plant_parts.append(part)

    return filtered_plant_parts
    
