#! /usr/bin/env python

# OpenCV imports
import cv2
import numpy as np

# Project imports
from src.util.image_writer import ImageWriter
from src.util.image_utils import postfix_filename, draw_rect
from src.extraction.item_extraction import filter_by_size

class TagFinder:
    '''Locates colored tags that are inserted into plant sticks.'''
    
    def __init__(self, min_tag_size, max_tag_size):
        '''Constructor.  Sizes should be in centimeters.'''
        self.min_tag_size = min_tag_size
        self.max_tag_size = max_tag_size
    
    def locate(self, geo_image, image, marked_image):
        '''Find possible tags in image and return list of rotated bounding box instances.''' 

        # Convert Blue-Green-Red color space to HSV
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Create binary mask image where potential tags are white.
        lower_hsv = np.array([15, 130, 100], np.uint8)
        upper_hsv = np.array([45, 255, 255], np.uint8)
        mask = cv2.inRange(hsv_image, lower_hsv, upper_hsv)
        
        # Open mask (to remove noise) and then dilate it to connect contours.
        #kernel = np.ones((3,3), np.uint8)
        #mask_open = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        #mask = cv2.dilate(mask_open, kernel, iterations = 1)
        
        # Find outer contours (edges)
        contours, hierarchy = cv2.findContours(mask.copy(), cv2.cv.CV_RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Create bounding box for each contour.
        bounding_rectangles = [cv2.minAreaRect(contour) for contour in contours]
        
        if marked_image is not None and ImageWriter.level <= ImageWriter.DEBUG:
            for rectangle in bounding_rectangles:
                # Show rectangles using bounding box.
                draw_rect(marked_image, rectangle, (255,255,255), thickness=1)
        
        # Remove any rectangles that couldn't be a tag part based off specified size.
        filtered_rectangles = filter_by_size(bounding_rectangles, geo_image.resolution, self.min_tag_size, self.max_tag_size, enforce_min_on_w_and_h=True)
        
        if ImageWriter.level <= ImageWriter.DEBUG:
            # Debug save intermediate images
            mask_filename = postfix_filename(geo_image.file_name, 'blue_thresh')
            ImageWriter.save_debug(mask_filename, mask)
        
        if marked_image is not None:
            for rectangle in filtered_rectangles:
                # Show rectangles using colored bounding box.
                purple = (50, 255, 100)
                draw_rect(marked_image, rectangle, purple, thickness=2)
                
        return filtered_rectangles
