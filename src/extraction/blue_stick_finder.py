#! /usr/bin/env python

# OpenCV imports
import cv2
import numpy as np

# Project imports
from src.util.image_writer import ImageWriter
from src.util.image_utils import postfix_filename, draw_rect
from src.extraction.item_extraction import filter_by_size

class BlueStickFinder:
    '''Locates blue sticks that are inserted into center of plants.'''
    
    def __init__(self, stick_length, stick_diameter):
        '''Constructor.  Sizes should be in centimeters.'''
        self.stick_length = stick_length
        self.stick_diameter = stick_diameter
    
    def locate(self, geo_image, image, marked_image):
        '''Find possible blue sticks in image and return list of rotated bounding box instances.''' 

        # Convert Blue-Green-Red color space to HSV
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Create binary mask image where potential sticks are white.
        lower_blue = np.array([67, 15, 5], np.uint8)
        upper_blue = np.array([142, 255, 255], np.uint8)
        mask = cv2.inRange(hsv_image, lower_blue, upper_blue)
        
        # Open mask (to remove noise) and then dilate it to connect contours.
        kernel = np.ones((3,3), np.uint8)
        mask_open = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.dilate(mask_open, kernel, iterations = 1)
        
        # Find outer contours (edges)
        contours, hierarchy = cv2.findContours(mask.copy(), cv2.cv.CV_RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Create bounding box for each contour.
        bounding_rectangles = [cv2.minAreaRect(contour) for contour in contours]
        
        if marked_image is not None and ImageWriter.level <= ImageWriter.DEBUG:
            for rectangle in bounding_rectangles:
                # Show rectangles using bounding box.
                draw_rect(marked_image, rectangle, (255,255,255), thickness=1)
        
        # Remove any rectangles that couldn't be a plant based off specified size.
        min_stick_size = self.stick_diameter * 0.75 # looking straight down on it
        max_stick_size = self.stick_length * 1.25 # laying flat on the ground
        filtered_rectangles = filter_by_size(bounding_rectangles, geo_image.resolution, min_stick_size, max_stick_size, enforce_min_on_w_and_h=True)
        
        if ImageWriter.level <= ImageWriter.DEBUG:
            # Debug save intermediate images
            mask_filename = postfix_filename(geo_image.file_name, 'blue_thresh')
            ImageWriter.save_debug(mask_filename, mask)
        
        if marked_image is not None:
            for rectangle in filtered_rectangles:
                # Show rectangles using colored bounding box.
                purple = (50, 255, 255)
                draw_rect(marked_image, rectangle, purple, thickness=2)
                
        return filtered_rectangles
