#! /usr/bin/env python

import sys
import os
import argparse
import pickle
import time
import csv
import math

# non-default import
import numpy as np

# Project imports
from data import *
from item_processing import export_results, export_group_segments, position_difference

if __name__ == '__main__':
    '''Output results.'''

    parser = argparse.ArgumentParser(description='''Output results.''')
    parser.add_argument('input_filepath', help='pickled file from either stage 2 or stage 3.')
    parser.add_argument('output_directory', help='where to write output files')
    
    args = parser.parse_args()
    
    # convert command line arguments
    input_filepath = args.input_filepath
    out_directory = args.output_directory

    # Unpickle rows.
    with open(input_filepath) as input_file:
        rows = pickle.load(input_file)
        print 'Loaded {} rows from {}'.format(len(rows), input_filepath)
    
    if len(rows) == 0:
        sys.exit(1)
    
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
            
                    
    items = ordered_items
    
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
        range_units_per_meter = 0.25;
        item.range = int(field_y_diff * range_units_per_meter)
    
    first_group_code = None
    for item in items:
        if item.type.lower() == 'groupcode':
            first_group_code = item
            break
        
    if first_group_code is None:
        print "No group codes. Exiting"
        sys.exit(1)
        
    expected_first_group_code = '930'
    if first_group_code.name != expected_first_group_code:
        expected_first_group_code_actual_index = [item.name for item in items].index(expected_first_group_code)
        print "First group code is {0} and should be {1}. {1} actually has an index of {2}. Exiting".format(first_group_code.name, expected_first_group_code, expected_first_group_code_actual_index)
        sys.exit(1)
                
    first_position = first_group_code.position
    
    for item in items:
        rel_x = item.position[0] - first_position[0]
        rel_y = item.position[1] - first_position[1]
        rel_z = item.position[2] - first_position[2]
        item.field_position = (rel_x, rel_y, rel_z)
                
    print 'Found {} items in rows.'.format(len(items))
    
    # Shouldn't be necessary, but do it anyway.
    print 'Sorting items by number within field.'
    items = sorted(items, key=lambda item: item.number_within_field)
    
    # generate a sub-directory in specified output directory to house all output files.
    out_directory = os.path.join(out_directory, time.strftime('results-%Y%m%d-%H%M%S/'))
    
    if not os.path.exists(out_directory):
        os.makedirs(out_directory)
    
    # Write everything out to CSV file to be imported into database.
    all_results_filename = time.strftime('results_all-%Y%m%d-%H%M%S.csv')
    all_results_filepath = os.path.join(out_directory, all_results_filename)
    all_output_items = []
    for item in items:
        all_output_items.extend([item] + item.other_items)
    export_results(all_output_items, rows, all_results_filepath)
    print "Exported all results to " + all_results_filepath
    
    # Compute averaged results.
    avg_output_items = []
    for item in items:
        avg_item = item # copy.copy(item)
        item_references = [avg_item] + avg_item.other_items
        avg_x = np.mean([it.position[0] for it in item_references])
        avg_y = np.mean([it.position[1] for it in item_references])
        avg_z = np.mean([it.position[2] for it in item_references])
        avg_item.position = (avg_x, avg_y, avg_z)
        avg_item.area = np.mean([it.area for it in item_references])
        avg_width = np.mean([it.size[0] for it in item_references])
        avg_height = np.mean([it.size[1] for it in item_references])
        avg_item.size = (avg_width, avg_height)
        avg_output_items.append(avg_item)
        
    # Output all averaged results to one file.
    avg_results_filename = time.strftime("results_averaged-%Y%m%d-%H%M%S.csv")
    avg_results_filepath = os.path.join(out_directory, avg_results_filename)
    print 'Output averaged {} items'.format(len(avg_output_items))
    export_results(avg_output_items, rows, avg_results_filepath)
    print "Exported averaged results to " + avg_results_filepath
    
    # And output just codes to another file.
    just_codes_results_filename = time.strftime("results_just_codes-%Y%m%d-%H%M%S.csv")
    just_codes_results_filepath = os.path.join(out_directory, just_codes_results_filename)
    just_codes = [item for item in avg_output_items if 'code' in item.type.lower()]
    export_results(just_codes, rows, just_codes_results_filepath)
    print "Exported just code results to " + just_codes_results_filepath

    # Output group segments to a file.
    segment_results_filename = time.strftime("results_segments-%Y%m%d-%H%M%S.csv")
    segment_results_filepath = os.path.join(out_directory, segment_results_filename)
    all_segments = []
    for row in rows:
        all_segments.extend(row.group_segments)
    export_group_segments(all_segments, segment_results_filepath)
    print "Exported segment results to " + segment_results_filepath
