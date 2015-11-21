#! /usr/bin/env python

import os
import csv
from collections import namedtuple

# OpenCV imports
import cv2
import numpy as np

# Project imports
from src.util.image_utils import rectangle_center, postfix_filename
from src.extraction.item_extraction import calculate_pixel_position, extract_square_image
from src.processing.item_processing import position_difference

class MissedCodeFinder:
    ''''''
    
    def __init__(self):
        '''Constructor'''
        self.possibly_missed_codes = []
        self.MissedCode = namedtuple("MissedCode", 'rect position parent_filename, parent_filepath')

    def add_possibly_missed_code(self, bouding_rect, geo_image):

        x, y = rectangle_center(bouding_rect)
        position = calculate_pixel_position(x, y, geo_image)
        self.possibly_missed_codes.append(self.MissedCode(bouding_rect, position, geo_image.file_name, geo_image.file_path))

    def write_out_missed_codes(self, found_codes, missed_code_filename, out_directory):
        
        missing_codes = []
        for possibly_missed_code in self.possibly_missed_codes:
            was_actually_found = False
            for found_code in found_codes:
                pos_diff = position_difference(possibly_missed_code.position, found_code.position)
                if pos_diff < 0.12:
                    was_actually_found = True
                    break
            if not was_actually_found:
                missing_codes.append(possibly_missed_code)
        
        missed_code_filepath = os.path.join(out_directory, missed_code_filename)
        missed_code_file = open(missed_code_filepath, 'wb')
        missed_code_csv_writer = csv.writer(missed_code_file)
        
        # Create subdirectory to store extracted images in.
        extracted_img_out_directory = os.path.join(out_directory, 'extracted_images/')
        if not os.path.exists(extracted_img_out_directory):
            os.makedirs(extracted_img_out_directory)
        
        for k, missed_code in enumerate(missing_codes):
            
            parent_img = cv2.imread(missed_code.parent_filepath, cv2.CV_LOAD_IMAGE_COLOR)
    
            if parent_img is None:
                print 'Cannot open image: {}'.format(missed_code.parent_filepath)
                continue
            
            extracted_img = extract_square_image(parent_img, missed_code.rect, 60, rotated=True)
            
            extracted_img_filename = '{}_{}'.format(k, postfix_filename(missed_code.parent_filename, '_missed'))
            extracted_img_filepath = os.path.join(extracted_img_out_directory, extracted_img_filename)
            
            cv2.imwrite(extracted_img_filepath, extracted_img)
            
            x, y = rectangle_center(missed_code.rect)
            missed_code_csv_writer.writerow(['add_imaged_code', k, missed_code.parent_filename, int(x), int(y)])
            
        