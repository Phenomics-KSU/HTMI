#! /usr/bin/env python

# OpenCV imports
import cv2
import numpy as np

# Project imports
from src.util.image_writer import ImageWriter
from src.util.image_utils import postfix_filename, draw_rect
from src.extraction.item_extraction import filter_by_size
from src.data.field_item import FieldItem

class BlueStickFinder:
    '''Locates blue sticks that are inserted into center of plants.'''
    def __init__(self, stick_length, stick_diameter):
        '''Constructor.  Sizes should be in centimeters.'''
        self.stick_length = stick_length
        self.stick_diameter = stick_diameter
    
    def locate(self, geo_image, image, marked_image):
        '''Find sticks in image and return list of FieldItem instances.''' 
        # Extract out just blue channel from BGR image.
        #blue_channel, _, _ = cv2.split(image)
        #_, mask = cv2.threshold(blue_channel, 160, 255, 0)
        
        # Convert Blue-Green-Red color space to HSV
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        lower_blue = np.array([90, 90, 50], np.uint8)
        upper_blue = np.array([130, 255, 255], np.uint8)
        mask = cv2.inRange(hsv_image, lower_blue, upper_blue)
        
        # Night time testing
        lower_blue = np.array([90, 10, 5], np.uint8)
        upper_blue = np.array([142, 255, 255], np.uint8)
        mask = cv2.inRange(hsv_image, lower_blue, upper_blue)
        
        # Salina testing
        lower_blue = np.array([67, 15, 5], np.uint8)
        upper_blue = np.array([142, 255, 255], np.uint8)
        mask = cv2.inRange(hsv_image, lower_blue, upper_blue)
        
        # Find outer contours (edges) and 'approximate' them to reduce the number of points along nearly straight segments.
        contours, hierarchy = cv2.findContours(mask.copy(), cv2.cv.CV_RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        #contours = [cv2.approxPolyDP(contour, .1, True) for contour in contours]
        
        # Create bounding box for each contour.
        bounding_rectangles = [cv2.minAreaRect(contour) for contour in contours]
        
        if marked_image is not None:
            for rectangle in bounding_rectangles:
                # Show rectangles using bounding box.
                draw_rect(marked_image, rectangle, (0,0,0), thickness=2)
        
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
                purple = (255, 0, 255)
                draw_rect(marked_image, rectangle, purple, thickness=2)

        sticks = []
        for i, rectangle in enumerate(filtered_rectangles):
            # Just give default name for saving image until we later go through and assign to plant group.
            stick = FieldItem(name = 'stick' + str(i), bounding_rect = rectangle)
            sticks.append(stick)
                
        return sticks
