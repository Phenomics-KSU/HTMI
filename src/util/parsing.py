#! /usr/bin/env python

import os
import math

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

def parse_grouping_file(group_filename):
    '''Parse file and return list of tuples (group_name, number_plants) for each row.'''
    groups = []
    with open(group_filename, 'r') as group_file:
        lines = group_file.readlines()
        for line in lines:
            if line.isspace():
                continue
            fields = [field.strip() for field in line.split(',')]
            if len(fields) == 0:
                continue
            try:
                order_entered = int(fields[0])
                qr_id = fields[1]
                flag = fields[2] # just entry x rep combined
                entry = fields[3]
                rep = fields[4].upper()
                estimated_num_plants = int(fields[5])
                groups.append((qr_id, entry, rep, estimated_num_plants, order_entered))
            except (IndexError, ValueError):
                print 'Bad line: {0}'.format(line) 
                continue
            
    return groups

def parse_updated_fix_file(updated_items_filepath):
    '''Parse file and return list of tuples (group_name, number_plants) for each row.'''
    none_items = []
    missing_items = []
    all_items = []
    with open(updated_items_filepath, 'r') as group_file:
        lines = group_file.readlines()
        for line_index, line in enumerate(lines):
            if line_index == 0:
                continue # skip column headers
            if line.isspace():
                continue
            fields = [field.strip() for field in line.split(',')]
            #fields = filter(None, fields) # remove empty entries
            if len(fields) == 0:
                continue
            try:
                name = fields[5]
                expected_plants = fields[8]
                actual_plants = fields[9]
                none_group = fields[10]
                missing_group = fields[11]
                notes = fields[12]
                
                position = (0, 0, 0)
          
                easting = float(fields[17])
                northing = float(fields[18])
                altitude = float(fields[19])
                position = (easting, northing, altitude)
                
                item = (name, expected_plants, actual_plants, none_group, missing_group, notes, position)
                
                if len(none_group) != 0:
                    none_items.append(item)
                if len(missing_group) != 0:
                    missing_items.append(item)
                
                all_items.append(item)

            except (IndexError, ValueError) as e:
                print 'Bad line: {}. Exception {}'.format(line, e) 
                continue
            
    return all_items, missing_items, none_items
