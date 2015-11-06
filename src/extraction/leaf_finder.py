#! /usr/bin/env python

# OpenCV imports
import cv2
import numpy as np

# Project imports
from src.util.image_writer import ImageWriter
from src.util.image_utils import postfix_filename, draw_rect, cluster_rectangles
from src.extraction.item_extraction import filter_by_size
from src.data.field_item import Plant

class LeafFinder:
    '''Locates plants within an image.'''
    def __init__(self, min_plant_size, max_plant_size):
        '''Constructor.  Plant size is an estimate for searching.'''
        self.min_plant_size = min_plant_size
        self.max_plant_size = max_plant_size
    
    def locate(self, geo_image, image, marked_image):
        '''Find plants in image and return list of Plant instances.''' 
        # Grayscale original image so we can find edges in it. Default for OpenCV is BGR not RGB.
        #blue_channel, green_channel, red_channel = cv2.split(image)
        
        # Convert Blue-Green-Red color space to HSV
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
        # Threshold the HSV image to get only green colors that correspond to healthy plants.
        green_hue = 60
        lower_green = np.array([green_hue - 30, 90, 50], np.uint8)
        upper_green = np.array([green_hue + 30, 255, 255], np.uint8)
        plant_mask = cv2.inRange(hsv_image, lower_green, upper_green)
        
        # Now do the same thing for greenish dead plants.
        lower_dead_green = np.array([10, 35, 60], np.uint8)
        upper_dead_green = np.array([90, 255, 255], np.uint8)
        dead_green_plant_mask = cv2.inRange(hsv_image, lower_dead_green, upper_dead_green)
    
        # Now do the same thing for yellowish dead plants.
        #lower_yellow = np.array([10, 50, 125], np.uint8)
        #upper_yellow = np.array([40, 255, 255], np.uint8)
        #dead_yellow_plant_mask = cv2.inRange(hsv_image, lower_yellow, upper_yellow)
        
        filtered_rectangles = []
        for i, mask in enumerate([plant_mask, dead_green_plant_mask]):
            # Open mask (to remove noise) and then dilate it to connect contours.
            #kernel = np.ones((5,5), np.uint8)
            #mask_open = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            #mask = cv2.dilate(mask_open, kernel, iterations = 1)
            
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
            filtered_rectangles.extend(filter_by_size(bounding_rectangles, geo_image.resolution, self.min_plant_size, self.max_plant_size, enforce_min_on_w_and_h=False))
            
            if ImageWriter.level <= ImageWriter.DEBUG:
                # Debug save intermediate images
                mask_filename = postfix_filename(geo_image.file_name, 'mask_{0}'.format(i))
                ImageWriter.save_debug(mask_filename, mask)
        
        if marked_image is not None:
            for rectangle in filtered_rectangles:
                # Show rectangles using colored bounding box.
                purple = (255, 0, 255)
                draw_rect(marked_image, rectangle, purple, thickness=2)
        
        # Now go through and cluster plants (leaves) that are close together.
        max_distance = 20 # centimeters
        rectangle_clusters = cluster_rectangles(filtered_rectangles, max_distance / geo_image.resolution)
            
        plants = []
        for i, rectangle in enumerate(rectangle_clusters):
            
            # Just give default name for saving image until we later go through and assign to plant group.
            plant = Plant(name = 'plant' + str(i), bounding_rect = rectangle)
            plants.append(plant)
                
            if marked_image is not None:
                # Show successful plants using colored bounding box.
                blue = (255, 0, 0)
                draw_rect(marked_image, rectangle, blue, thickness=2)
        
        return plants
    
    
