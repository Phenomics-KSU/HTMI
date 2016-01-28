#! /usr/bin/env python

import sys
import math

# OpenCV imports
import cv2
import numpy as np

# Project imports
from src.util.image_utils import rotated_to_regular_rect, rectangle_corners
from src.extraction.item_extraction import calculate_pixel_position, calculate_position_pixel

def number_serpentine(rows, field_num_start=1):
    '''Return list of all items in rows ordered (and numbered) in a serpentine pattern.'''
    
    rows = sorted(rows, key=lambda r: r.number)
    
    current_field_item_num = field_num_start
    current_field_plant_num = field_num_start
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
            
        item_num_in_row = 1
        plant_num_in_row = 1
        for item in row_items:
            
            item.number_within_field = current_field_item_num
            item.number_within_row = item_num_in_row
            current_field_item_num += 1
            item_num_in_row += 1
            
            if 'plant' in item.type.lower():
                item.plant_num_in_field = current_field_plant_num
                item.plant_num_in_row = plant_num_in_row
                current_field_plant_num += 1
                plant_num_in_row += 1

            ordered_items.append(item)
            
    return ordered_items
