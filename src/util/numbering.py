#! /usr/bin/env python

import sys
import math

# OpenCV imports
import cv2
import numpy as np

# Project imports
from src.util.image_utils import rotated_to_regular_rect, rectangle_corners
from src.extraction.item_extraction import calculate_pixel_position, calculate_position_pixel

def number_serpentine(rows):
    '''Return list of all items in rows ordered (and numbered) in a serpentine pattern.'''
    
    rows = sorted(rows, key=lambda r: r.number)
    
    current_field_item_num = 1
    ordered_items = []
    for row in rows:
        row_items = []
        for i, segment in enumerate(row.segments):
            row_items.append(segment.start_code)
            row_items += segment.items
            if i == len(row.segments) - 1:
                row_items.append(segment.end_code) # since on last segment it won't show up in next segment
                
        # Get everything going in the 'up' direction
        if row.direction == 'back':
            row_items.reverse()
        
        # Reverse items in even row numbers for serpentine ordering    
        if row.number % 2 == 0:
            row_items.reverse()
            
        for item_num_in_row, item in enumerate(row_items):
            item.number_within_field = current_field_item_num
            item.number_within_row = item_num_in_row + 1 # index off 1 instead of 0
            ordered_items.append(item)
            current_field_item_num += 1
            
    return ordered_items
   
def assign_range_number(items, rows):
    
    # use field angle to calculate range for each item.
    field_angle = np.mean([row.angle for row in rows])
    
    # How much we need to rotate East-North so that 'y' runs along rows.
    correction_angle = 90 - field_angle 
    
    item_field_coords = []
    for item in items:
        east_x = item.position[0]
        north_y = item.position[1]
        field_x = east_x * math.cos(correction_angle) - north_y * math.sin(correction_angle)
        field_y = east_x * math.sin(correction_angle) + north_y * math.cos(correction_angle)
        item_field_coords.append((field_x, field_y))
    
    field_y_coords = [c[1] for c in item_field_coords]
    min_field_y = min(field_y_coords)
    max_field_y = max(field_y_coords)
    
    print "Min field y " + str(min_field_y)
    print "Max field y " + str(max_field_y)
    
    for item in items:
        field_y = item.position[0] * math.sin(correction_angle) + item.position[1] * math.cos(correction_angle)

        field_y_diff = field_y - min_field_y
        
        #print "field_y_diff is " + str(field_y_diff)
        
        # scale range so that there are around 5 plants in each unit.
        # TODO use actual plant spacing here instead of hardcoding scale.
        # Add one to reference off 1 like row number.
        range_units_per_meter = 0.25;
        item.range = int(field_y_diff * range_units_per_meter) + 1