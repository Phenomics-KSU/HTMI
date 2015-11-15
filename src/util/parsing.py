#! /usr/bin/env python

import os
import math
from collections import namedtuple

# Project imports
from src.data.geo_image import GeoImage
    
def parse_geo_file(image_geo_file, provided_resolution, camera_rotation):
    '''Parse geo file and return list of GeoImage instances.'''
    images = []
    with open(image_geo_file, 'r') as geofile:
        lines = geofile.readlines()
        for line in lines:
            if line.isspace():
                continue
            fields = [field.strip() for field in line.split(',')]
            if len(fields) == 0:
                continue
            try:
                image_time = float(fields[0])
                image_name = fields[1]
                x = float(fields[2])
                y = float(fields[3])
                z = float(fields[4])
                zone = fields[5]
                roll = float(fields[6])
                pitch = float(fields[7])
                heading = math.degrees(float(fields[8]))
                # Make sure filename doesn't have extension, we'll add it from image that we're processing.
                image_name = os.path.splitext(image_name)[0]
            except (IndexError, ValueError) as e:
                print 'Bad line: {}'.format(line) 
                raise

            geo_image = GeoImage(image_name, image_time, (x, y, z), zone, heading, provided_resolution, camera_rotation)
            images.append(geo_image)
            
    return images

def parse_code_listing_file(group_filename):
    '''
    Parse file and return list of named tuples and flag indicating if alternate id is included
        true: list of tuples is (code_id, max_number_plants, alternate_id)
        false: list of tuples is (code_id, max_number_plants)
    '''
    code_listings = []
    alternate_ids_included = False
    CodeListing = namedtuple('CodeListing', 'id max_plants')
    CodeListingAlternate = namedtuple('CodeListingAlternate', 'id max_plants alternate_id')
    with open(group_filename, 'r') as group_file:
        lines = group_file.readlines()
        for line in lines:
            if line.isspace():
                continue
            fields = [field.strip() for field in line.split(',')]
            if len(fields) == 0:
                continue
            try:
                code_id = fields[0]
                max_plants = int(fields[1])
                if len(fields) > 2 and fields[2] != '':
                    alternate_id = fields[2]
                    alternate_ids_included = True
                    new_listing = CodeListingAlternate(code_id, max_plants, alternate_id)
                else:
                    new_listing = CodeListing(code_id, max_plants)
                code_listings.append(new_listing)
            except (IndexError, ValueError):
                print 'Bad line: {0}'.format(line) 
                continue
            
    return code_listings, alternate_ids_included

def parse_code_modifications_file(code_modifications_filepath):
    '''Parse file and return list of named tuples for difference modification types.'''
    AddImagedCode = namedtuple('AddImagedCode', 'id parent_filename, x_pixels, y_pixels')
    DeleteCode = namedtuple('DeleteCode', 'code_id')
    code_modifications = []
    with open(code_modifications_filepath, 'r') as code_modifications_file:
        lines = code_modifications_file.readlines()
        for line_index, line in enumerate(lines):
            if line.isspace():
                continue
            fields = [field.strip() for field in line.split(',')]
            if len(fields) == 0:
                continue
            try:
                modification_type = fields[0]
                if modification_type == 'add_imaged_code':
                    id = fields[1]
                    parent_filename = fields[2]
                    x_pixels = int(fields[3])
                    y_pixels = int(fields[4])
                    code_modifications.append(AddImagedCode(id, parent_filename, x_pixels, y_pixels))
                elif modification_type == 'delete_code':
                    id = fields[1]
                    code_modifications.append(DeleteCode(id))
                else:
                    print "Unsupported modification {}".format(modification_type)
            except (IndexError, ValueError) as e:
                print 'Bad line: {}. Exception {}'.format(line, e) 
                continue
            
    return code_modifications

def parse_updated_items(updated_items_filepath):
    
    updated_all_items = []
    updated_missing_items = []
    updated_none_items = []
    
    if updated_items_filepath != 'none':
        if os.path.exists(updated_items_filepath):
            updated_all_items, updated_missing_items, updated_none_items = parse_updated_fix_file(updated_items_filepath)
            print "From updated fix file parsed: "
            print "All {} missing {} none {}".format(len(updated_all_items), len(updated_missing_items), len(updated_none_items))
        else:
            print "Updated file file {} does not exist.".format(updated_items_filepath)
        
    return updated_all_items, updated_missing_items, updated_none_items
