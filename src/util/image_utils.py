#! /usr/bin/env python

import os
import math

# OpenCV imports
import cv2
import numpy as np

def list_images(image_directory, extensions):
    '''Return list of images with specified extensions inside of directory.'''
    image_filenames = []
    for fname in os.listdir(image_directory):
        extension = os.path.splitext(fname)[1][1:]
        if extension.lower() in extensions:
            image_filenames.append(fname)
        else:
            print 'Skipping file {0} due to unsupported extension'.format(fname)
    return image_filenames

def postfix_filename(filename, postfix):
    '''Return post-fixed file name with original extension.'''
    filename, extension = os.path.splitext(filename)
    postfixed_name = "{0}{1}{2}".format(filename, postfix, extension)
    return postfixed_name

def make_filename_unique(directory, fname_no_ext):
    
    original_fname = fname_no_ext
    dir_contents = os.listdir(directory)
    dir_fnames = [os.path.splitext(c)[0] for c in dir_contents]
    
    while fname_no_ext in dir_fnames:
        
        try:
            v = fname_no_ext.split('_')
            i = int(v[-1])
            i += 1
            fname_no_ext = '_'.join(v[:-1] + [str(i)])
        except ValueError:
            fname_no_ext = '{}_{}'.format(original_fname, 1)

    return fname_no_ext

def verify_geo_images(geo_images, image_filenames):
    '''Verify each geo image exists in specified image file names. Return # missing images.'''
    missing_image_count = 0
    matching_geo_images = []
    image_filenames_no_ext = [os.path.splitext(fname)[0] for fname in image_filenames]
    for geo_image in geo_images:
        try:
            # Make sure actual image exists and use it's file extension.
            index = image_filenames_no_ext.index(geo_image.file_name)
            extension = os.path.splitext(image_filenames[index])[1][1:]
            geo_image.file_name = "{0}.{1}".format(geo_image.file_name, extension)
            matching_geo_images.append(geo_image)
        except ValueError:
            # Geo image doesn't have corresponding actual image
            missing_image_count += 1
            
    return matching_geo_images, missing_image_count

def index_containing_substring(the_list, substring):
    for i, s in enumerate(the_list):
        if substring in s:
            return i
    return -1

def draw_rect(img, rect, color=(0,0,0), thickness=1, rotated=True):
    '''Draws the rotated rectangle on the specified image.'''
    if rotated:
        box = cv2.cv.BoxPoints(rect)
        box = np.int0(box)
        cv2.drawContours(img, [box], 0, color, thickness)
    else:
        corners = rectangle_corners(rect, rotate=False)
        cv2.rectangle(img, corners[0], corners[1], color, thickness) 

def rectangle_center(rectangle, rotated=True):
    '''Returns (x,y) tuple of center of rectangle.'''
    if rotated:
        center, dim, theta = rectangle
        return center
    else: 
        x, y, w, h = rectangle
        return (x + w/2, y + h/2)

def rectangle_corners(rectangle, rotated=True):
    '''If non-rotated then returns top left (x1, y1) and bottom right (x2, y2) corners as flat tuple.
       If rotated then uses BoxPoints to get tuple of 4 corners.'''
    if rotated:
        return cv2.cv.BoxPoints(rectangle)
    else:
        x, y, w, h = rectangle
        return (x, y, x+w, y+h)

def rotated_to_regular_rect(rotated_rect):
    '''Return regular non-rotated rectangle that bounds rotated rectangle.'''
    corners = rectangle_corners(rotated_rect, rotated=True)
    x_values = [c[0] for c in corners]
    y_values = [c[1] for c in corners]
    min_x = min(x_values)
    min_y = min(y_values)
    max_x = max(x_values)
    max_y = max(y_values)
    width = max_x - min_x
    height = max_y - min_y
    return (min_x, min_y, width, height)

def distance_between_rects(rect1, rect2, rotated=True):
    '''Return distance between center of rectangles.'''
    x1, y1 = rectangle_center(rect1, rotated)
    x2, y2 = rectangle_center(rect2, rotated)
    dx = x1 - x2
    dy = y1 - y2
    return math.sqrt(dx*dx + dy*dy)

def merge_rectangles(rectangles):
    '''Return rectangle that contains all rectangles.'''
    
    raise NotImplementedError

    corners = [rectangle_corners(rectangle) for rectangle in rectangles]
    x1 = min([c[0] for c in corners])
    y1 = min([c[1] for c in corners])
    x2 = max([c[2] for c in corners])
    y2 = max([c[3] for c in corners])
    return (x1, y1, x2-x1, y2-y1)
                
def cluster_rectangles(rectangles, eps):
    '''Combine rectangles within eps (pixels) of each other.'''
    
    raise NotImplementedError

    groupings = [-1] * len(rectangles)
    for i, rectangle in enumerate(rectangles):
        if groupings[i] == -1:
            groupings[i] = i # haven't been claim yet.
        for j, other_rectangle in enumerate(rectangles):
            if i == j:
                continue # same rectangle
            if distance_between_rects(rectangle, other_rectangle) < eps:
                if groupings[j] == -1:
                    groupings[j] = groupings[i] # claim this rectangle
                else:
                    # claim all rectangle with group we're running into
                    groupings = [groupings[i] if x==groupings[j] else x for x in groupings]
     
    used_groupings = list(set(groupings))
    
    clustered_rectangles = []
    for group in used_groupings:
        # Get all rectangles associated with this group
        rectangles_in_group = []
        for i, g in enumerate(groupings):
            if g == group:
                rectangles_in_group.append(rectangles[i])
                
        clustered_rectangles.append(merge_rectangles(rectangles_in_group))
   
    return clustered_rectangles
