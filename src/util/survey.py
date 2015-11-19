#! /usr/bin/env python

# non-default import
import numpy as np

def calculate_east_north_offsets(items, survey_items):
    
    east_offsets = []
    north_offsets = []
    for survey_item in survey_items:
        
        try:
            matching_item = [item for item in items if item.name.lower() == survey_item.name][0]
        except IndexError:
            continue
        
        east_offsets.append(survey_item.position[0] - matching_item.position[0])
        north_offsets.append(survey_item.position[1] - matching_item.position[1])
        
    return np.mean(east_offsets), np.mean(north_offsets)

def run_survey_verification(items, survey_items):
    
    east_errors = []
    north_errors = []
    for survey_item in survey_items:
        
        try:
            matching_item = [item for item in items if item.name.lower() == survey_item.name][0]
        except IndexError:
            print "No match for {}".format(survey_item)
            continue
        
        east_error = survey_item.position[0] - matching_item.position[0]
        north_error = survey_item.position[1] - matching_item.position[1]
        
        print "{} off by ({}, {})".format(matching_item.name, east_error, north_error)
        
        east_errors.append(east_error)
        north_errors.append(north_error)
        
    avg_easting = np.mean(east_errors)
    avg_northing = np.mean(north_errors)
    
    abs_easting = [abs(error) for error in east_errors]
    abs_northing = [abs(error) for error in north_errors]
        
    print "\n\n-----Survey Verification Results-----"
    print "Average error East: {:3f}  North: {:3f}".format(avg_easting, avg_northing)
    print "|Average| error East: {:3f}  North: {:3f}".format(np.mean(abs_easting), np.mean(abs_northing))
    print "Min error East: {:3f}  North: {:3f}".format(min(abs_easting), min(abs_northing))
    print "Max error East: {:3f}  North: {:3f}".format(max(abs_easting), max(abs_northing))
    
def convert_coordinates(items, east_offset, north_offset):
    
    for item in items:
        new_position = (item.position[0] + east_offset, item.position[1] + north_offset, item.position[2])
        item.position = new_position
