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
