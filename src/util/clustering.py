#! /usr/bin/env python

import sys
import math

# OpenCV imports
import cv2
import numpy as np

# Project imports
from src.util.image_utils import rotated_to_regular_rect, rectangle_corners
from src.extraction.item_extraction import calculate_pixel_position, calculate_position_pixel

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

def distance_between_corner_rects(r1, r2):
    '''Return distance between rectangle centers.'''

    r1x = np.mean([corner[0] for corner in r1])
    r1y = np.mean([corner[1] for corner in r1])
    r2x = np.mean([corner[0] for corner in r2])
    r2y = np.mean([corner[1] for corner in r2])
    
    dx = r1x - r2x
    dy = r1y - r2y
    return math.sqrt(dx*dx + dy*dy)

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
    merged_items = c1.get('items', [c1]) + c2.get('items', [c2])
    return {'rect':merged_rect, 'items':merged_items}

def cluster_rectangle_items(items, max_size):
    ''''''
    # convert max size to meters
    max_size /= 100.0
    
    import copy
    items = copy.copy(items)
    
    clusters = items
    while True:
        closest_clusters = None
        closest_spacing = sys.float_info.max
        for cluster in clusters:
            for other_cluster in clusters:
                if cluster is other_cluster:
                    continue # don't compare a cluster to itself
                cluster_spacing = distance_between_corner_rects(cluster['rect'], other_cluster['rect'])
                if cluster_spacing < closest_spacing:
                    closest_clusters = (cluster, other_cluster)
                    closest_spacing = cluster_spacing
    
        if closest_clusters is None:
            break # clustered everything together
    
        new_cluster = merge_clusters(*closest_clusters)
    
        new_width, new_height = corner_rectangle_size(new_cluster['rect'])
        if new_width > max_size or new_height > max_size:
            break
        
        clusters.remove(closest_clusters[0])
        clusters.remove(closest_clusters[1])
        clusters.append(new_cluster)
        
    return clusters
