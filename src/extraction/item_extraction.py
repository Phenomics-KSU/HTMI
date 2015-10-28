#! /usr/bin/env python

import os
import math

# OpenCV imports
import cv2
import numpy as np

# Project imports
from src.util.image_writer import ImageWriter
from src.util.image_utils import *
from src.processing.item_processing import touches_image_border

class ItemExtractor:
    '''Extracts field items from image.'''    
    def __init__(self, locators):
        '''Constructor'''
    
    def extract_items(self, field_items, geo_image, image, marked_image, out_directory):
        '''Extract items into separate images. Return updated list of field items..'''
        
        '''
        if marked_image is not None:
            # Show what 1" is on the top-left of the image.
            pixels = int(2.54 / geo_image.resolution)
            cv2.rectangle(marked_image, (1,1), (pixels, pixels), (255,255,255), 2) 
        
        
        field_items = []
        for locator in self.locators:
            located_items = locator.locate(geo_image, image, marked_image)
            field_items.extend(located_items)
        '''
        # Filter out any items that touch the image border since it likely doesn't represent entire item.
        items_without_border_elements = []
        for item in field_items:
            if touches_image_border(item, geo_image):
                # Mark as special color to show user why it wasn't included.
                if marked_image is not None:
                    dark_orange = (0, 140, 255) # dark orange
                    draw_rect(marked_image, item.bounding_rect, dark_orange, thickness=2)
            else:
                items_without_border_elements.append(item)
        field_items = items_without_border_elements

        # Extract field items into separate image
        for item in field_items:
            
            extracted_image = extract_square_image(image, item.bounding_rect, 20)
            
            extracted_image_fname = "{}_{}_{}.jpg".format(geo_image.file_name, item.type, item.name)
            extracted_image_path = ImageWriter.save_normal(extracted_image_fname, extracted_image)
            
            item.image_path = extracted_image_path
            
            item.parent_image_filename = geo_image.file_name
            
            item.position = calculate_position(item, geo_image)
        
        return field_items

def filter_by_size(bounding_rects, resolution, min_size, max_size, enforce_min_on_w_and_h=True):
    '''Return list of rectangles that are within min/max size (specified in centimeters)'''
    filtered_rects = []
    
    for rectangle in bounding_rects:    
        center, dim, theta = rectangle
        w_pixels, h_pixels = dim
        
        w = w_pixels * resolution
        h = h_pixels * resolution
        
        if enforce_min_on_w_and_h:
            # Need both side lengths to pass check.
            min_check_passed = h >= min_size and w >= min_size
        else:
            # Just need one side length to be long enough.
            min_check_passed = h >= min_size or w >= min_size
            
        if min_check_passed and h <= max_size and w <= max_size:
            filtered_rects.append(rectangle)
            
    return filtered_rects

def extract_square_image(image, rectangle, pad, rotated=True):
    '''Return image that corresponds to bounding rectangle with pad added in.
       If rectangle is rotated then it is converted to a normal non-rotated rectangle.'''
    # reference properties of bounding rectangle
    if rotated:
        rectangle = rotated_to_regular_rect(rectangle)

    x, y, w, h = rectangle
    
    # image width, height and depth
    image_h, image_w, image_d = image.shape
    
    # add in pad to rectangle and respect image boundaries
    top = int(max(1, y - pad))
    bottom = int(min(image_h - 1, y + h + pad))
    left = int(max(1, x - pad))
    right = int(min(image_w - 1, x + w + pad))

    return image[top:bottom, left:right]
    
def extract_rotated_image(image, rotated_rect, pad, trim=0):
    '''Return image that corresponds to bounding rectangle with a white pad background added in.'''
    center, dim, theta = rotated_rect
    width, height = dim
    trimmed_rect = (center, (width-trim, height-trim), theta)
    center, dim, theta = trimmed_rect
    width, height = dim

    rect_corners = rectangle_corners(trimmed_rect, rotated=True)
    poly = np.array([rect_corners], dtype=np.int32)
    mask = np.zeros((image.shape[0],image.shape[1],1), np.uint8)
    cv2.fillPoly(mask, poly, 255)
    masked_image = cv2.bitwise_and(image, image, mask=mask)
    
    inverted_mask = cv2.bitwise_not(mask, mask)
    masked_image = cv2.bitwise_not(masked_image, masked_image, mask=inverted_mask)
    
    return extract_square_image(masked_image, trimmed_rect, pad, rotated=True)
    
def calculate_position(item, geo_image):
    '''Return (x,y,z) position of item within geo image.'''
    resolution = geo_image.resolution
    x, y = rectangle_center(item.bounding_rect)
    # Reference x y from center of image instead of top left corner.
    x = x - geo_image.size[0]/2
    y = -y + geo_image.size[1]/2
    # Rotate x y from image frame to easting-northing frame.
    # A camera rotation of 0 corresponds to top of image being forward so need to subtract 90 to get positive x being top of image.
    heading = math.radians(geo_image.heading_degrees + geo_image.camera_rotation_degrees - 90)
    east_offset = math.cos(heading) * x - math.sin(heading) * y
    north_offset = math.sin(heading) * x + math.cos(heading) * y
    # Convert offsets from pixels to meters.
    east_offset *= resolution / 100
    north_offset *= resolution / 100
    # Take into account camera height.  Negative since item is below camera.
    z_meters = -geo_image.camera_height / 100
    
    return (geo_image.position[0] + east_offset, geo_image.position[1] + north_offset, geo_image.position[2] + z_meters)
    
