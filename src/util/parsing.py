#! /usr/bin/env python

import os
import math
import utm
from collections import namedtuple

# Project imports
from src.data.geo_image import GeoImage
    
def parse_geo_file(image_geo_file, provided_resolution, camera_height):
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
                lat = float(fields[1])
                lon = float(fields[2])
                alt = float(fields[3])
                roll = float(fields[4])
                pitch = float(fields[5])
                yaw = float(fields[6])
                image_name = fields[7]
                # Make sure filename doesn't have extension, we'll add it from image that we're processing.
                image_name = os.path.splitext(image_name)[0]
                
                # Make sure position is valid.
                if math.isnan(lat) or math.isnan(lon):
                    print 'Image {} doesnt have valid position so it wont be used.'.format(image_name)
                    continue
                
                # Roll and pitch are optional, but every image we use should have a yaw. If not then skip it.
                if math.isnan(yaw):
                    print 'Image {} doesnt have yaw (heading) so it wont be used.'.format(image_name)
                    continue
                
                # Convert WGS84 to UTM.
                easting, northing, zone_num, zone_letter = utm.from_latlon(lat, lon)
                
            except (IndexError, ValueError) as e:
                print 'Bad line: {}'.format(line) 
                raise
                 
            geo_image = GeoImage(file_name=image_name, image_time=image_time, position=(easting, northing, alt), zone=str(zone_num)+zone_letter,
                                 roll_degrees=roll, pitch_degrees=pitch, heading_degrees=yaw, resolution=provided_resolution, cam_height=camera_height)
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
    
    AddImagedCode = namedtuple('AddImagedCode', 'id parent_filename x_pixels y_pixels')
    AddSurveyedCode = namedtuple('AddSurveyedCode', 'id x y z zone')
    DeleteCode = namedtuple('DeleteCode', 'code_id')
    ChangeCodeName = namedtuple('ChangeCodeName', 'original_code_id new_code_id')
    AddGapCode = namedtuple('AddGapCode', 'code_id')
    
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
                elif modification_type == 'add_surveyed_code':
                    id = fields[1]
                    x = float(fields[2])
                    y = float(fields[3])
                    z = float(fields[4])
                    zone = fields[5]
                    code_modifications.append(AddSurveyedCode(id, x, y, z, zone))
                elif modification_type == 'delete_code':
                    code_id = fields[1]
                    code_modifications.append(DeleteCode(code_id))
                elif modification_type == 'change_code_name':
                    original_id = fields[1]
                    new_id = fields[2]
                    code_modifications.append(ChangeCodeName(original_id, new_id))
                elif modification_type == 'add_gap_code':
                    code_id = fields[1]
                    code_modifications.append(AddGapCode(code_id))
                else:
                    print "Unsupported modification {}".format(modification_type)
            except (IndexError, ValueError) as e:
                print 'Bad line: {}. Exception {}'.format(line, e) 
                continue
            
    return code_modifications

def parse_survey_file(survey_filepath):
    '''Parse file and return named tuple for each surveyed code.'''
    SurveyItem = namedtuple('SurveyItem', 'name position')
    survey_items = []
    with open(survey_filepath, 'r') as survey_file:
        lines = survey_file.readlines()
        for line_index, line in enumerate(lines):
            if line.isspace():
                continue
            fields = [field.strip() for field in line.split(',')]
            if len(fields) == 0:
                continue
            try:
                easting = float(fields[3])
                northing = float(fields[4])
                name = fields[5]
                survey_items.append(SurveyItem(name, (easting, northing)))
            except (IndexError, ValueError) as e:
                print 'Bad line: {}. Exception {}'.format(line, e) 
                continue
            
    return survey_items