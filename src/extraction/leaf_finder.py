#! /usr/bin/env python

# OpenCV imports
import cv2
import numpy as np

# Project imports
from src.util.image_writer import ImageWriter
from src.util.image_utils import postfix_filename, draw_rect
from src.extraction.item_extraction import filter_by_size

class LeafFinder:
    '''Locates plant leaves within an image.'''
    
    def __init__(self, min_leaf_size, max_leaf_size):
        '''Constructor.  Leaf sizes (in centimeters) is an estimate for searching.'''
        self.min_leaf_size = min_leaf_size
        self.max_leaf_size = max_leaf_size
    
    def locate(self, geo_image, image, marked_image):
        '''Find possible plant leaves in image and return list of rotated rectangle instances.''' 

        # Convert Blue-Green-Red color space to HSV
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
        # Threshold the HSV image to get only green colors that correspond to healthy plants.
        lower_green = np.array([35, 80, 20], np.uint8)
        upper_green = np.array([90, 255, 255], np.uint8)
        plant_mask = cv2.inRange(hsv_image, lower_green, upper_green)
        
        # Now do the same thing for greenish dead plants.
        #lower_dead_green = np.array([10, 35, 60], np.uint8)
        #upper_dead_green = np.array([90, 255, 255], np.uint8)
        #dead_green_plant_mask = cv2.inRange(hsv_image, lower_dead_green, upper_dead_green)
    
        # Now do the same thing for yellowish dead plants.
        #lower_yellow = np.array([10, 50, 125], np.uint8)
        #upper_yellow = np.array([40, 255, 255], np.uint8)
        #dead_yellow_plant_mask = cv2.inRange(hsv_image, lower_yellow, upper_yellow)
        
        filtered_rectangles = []
        for i, mask in enumerate([plant_mask]):
            # Open mask (to remove noise) and then dilate it to connect contours.
            kernel = np.ones((3,3), np.uint8)
            mask_open = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.dilate(mask_open, kernel, iterations = 1)
            
            # Find outer contours (edges) and 'approximate' them to reduce the number of points along nearly straight segments.
            contours, hierarchy = cv2.findContours(mask.copy(), cv2.cv.CV_RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Create bounding box for each contour.
            bounding_rectangles = [cv2.minAreaRect(contour) for contour in contours]
            
            if marked_image is not None and ImageWriter.level <= ImageWriter.DEBUG:
                for rectangle in bounding_rectangles:
                    # Show rectangles using bounding box.
                    draw_rect(marked_image, rectangle, (0,0,0), thickness=2)
            
            # Remove any rectangles that couldn't be a plant based off specified size.
            filtered_rectangles.extend(filter_by_size(bounding_rectangles, geo_image.resolution, self.min_leaf_size, self.max_leaf_size, enforce_min_on_w_and_h=False))
            
            if ImageWriter.level <= ImageWriter.DEBUG:
                # Debug save intermediate images
                mask_filename = postfix_filename(geo_image.file_name, 'mask_{}'.format(i))
                ImageWriter.save_debug(mask_filename, mask)
        
        if marked_image is not None:
            for rectangle in filtered_rectangles:
                # Show rectangles using colored bounding box.
                purple = (255, 0, 255)
                draw_rect(marked_image, rectangle, purple, thickness=2)
        
        return filtered_rectangles
