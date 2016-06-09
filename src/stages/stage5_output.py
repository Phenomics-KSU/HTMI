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
from src.util.stage_io import unpickle_stage4_output, write_args_to_file
from src.stages.exit_reason import ExitReason
from src.util.parsing import parse_survey_file
from src.analysis.stage2_output_analysis import warn_about_missing_single_code_lengths
from src.processing.item_processing import calculate_field_positions_and_range, all_segments_from_rows
from src.processing.item_processing import position_difference
from src.processing.export_results import export_group_segments, export_results
from src.util.numbering import number_serpentine
from src.util.survey import *

if __name__ == '__main__':
    '''Output results.'''

    parser = argparse.ArgumentParser(description='''Output results.''')
    parser.add_argument('input_filepath', help='pickled file from stage 4.')
    parser.add_argument('output_directory', help='where to write output files')
    parser.add_argument('-s', dest='survey_filepath', default='none', help='File containing hand-surveyed items.')
    parser.add_argument('-c', dest='convert_coords', default='true', help='If true then will convert all coordinates to match survey file. Default true.')
    parser.add_argument('-ps', dest='plant_spacing', default=0, help='Expect plant spacing in meters.  If provided then will run spacing checks on single code plants.')
    parser.add_argument('-ns', dest='field_num_start', default=1, help='First number of first item used for numbering within field.  Default 1.')
    
    args = parser.parse_args()
    
    # convert command line arguments
    input_filepath = args.input_filepath
    out_directory = args.output_directory
    survey_filepath = args.survey_filepath
    convert_coords = args.convert_coords.lower() == 'true'
    plant_spacing = float(args.plant_spacing)
    field_num_start = int(args.field_num_start)

    rows = unpickle_stage4_output(input_filepath)
    
    print 'Loaded {} rows'.format(len(rows))
    
    if len(rows) == 0:
        sys.exit(ExitReason.no_rows)
    
    rows = sorted(rows, key=lambda r: r.number)
    
    items = number_serpentine(rows, field_num_start)
    
    print 'Found {} items in rows.'.format(len(items))
    
    codes = [item for item in items if 'code' in item.type.lower()]
    plants = [item for item in items if 'plant' in item.type.lower()]
    
    print '{} are codes and {} are plants.'.format(len(codes), len(plants))
    
    # Now that plants are found calculate their field coordinates based on codes.
    calculate_field_positions_and_range(rows, codes, plants)
    
    # Shouldn't be necessary, but do it anyway.
    print 'Sorting items by number within field.'
    items = sorted(items, key=lambda item: item.number_within_field)
    
    plant_spacings = []
    if plant_spacing > 0:
        # Run spacing verification on single plants to double check no codes were missed.
        all_segments = all_segments_from_rows(rows)
        single_segments = [segment for segment in all_segments if segment.start_code.type == 'SingleCode']
        warn_about_missing_single_code_lengths(single_segments, plant_spacing)
    
        # Run spacing verification on regular plants.
        last_plant = None
        for item in items:
            if item.type not in ['Plant', 'CreatedPlant']:
                continue
            if last_plant and last_plant.row == item.row:
                spacing = position_difference(last_plant.position, item.position)
                if spacing > plant_spacing * 1.5:
                    print "{} between {} and {}".format(spacing, last_plant.number_within_field, item.number_within_field)
                plant_spacings.append(spacing)
            last_plant = item
    
    # generate a sub-directory in specified output directory to house all output files.
    out_directory = os.path.join(out_directory, time.strftime('results-%Y%m%d-%H%M%S/'))
    
    if not os.path.exists(out_directory):
        os.makedirs(out_directory)
        
    if survey_filepath != 'none':
        if not os.path.exists(survey_filepath):
            print "Survey file doesn't exist {}".format(survey_filepath)
            sys.exit(ExitReason.bad_arguments)
        else:
            survey_items = parse_survey_file(survey_filepath)
            if convert_coords:
                print "Converting coordinates"
                east_offset, north_offset = calculate_east_north_offsets(items, survey_items)
                convert_coordinates(items, east_offset, north_offset)
                
            # Now that items are in same coordinates run accuracy checks
            run_survey_verification(items, survey_items)
            
    # Write everything out to CSV file to be imported into database.
    all_results_filename = time.strftime('results_all-%Y%m%d-%H%M%S.csv')
    all_results_filepath = os.path.join(out_directory, all_results_filename)
    all_output_items = [ref for item in items for ref in item.all_refs]
    export_results(all_output_items, rows, all_results_filepath)
    print "Exported all results to " + all_results_filepath
    
    # Output all averaged results to one file.
    avg_results_filename = time.strftime("results_averaged-%Y%m%d-%H%M%S.csv")
    avg_results_filepath = os.path.join(out_directory, avg_results_filename)
    print 'Output averaged {} items'.format(len(items))
    export_results(items, rows, avg_results_filepath)
    print "Exported averaged results to " + avg_results_filepath
    
    # And output just codes to another file.
    just_codes_results_filename = time.strftime("results_just_codes-%Y%m%d-%H%M%S.csv")
    just_codes_results_filepath = os.path.join(out_directory, just_codes_results_filename)
    export_results(codes, rows, just_codes_results_filepath)
    print "Exported just code results to " + just_codes_results_filepath

    # Output group segments to a file.
    segment_results_filename = time.strftime("results_segments-%Y%m%d-%H%M%S.csv")
    segment_results_filepath = os.path.join(out_directory, segment_results_filename)
    all_segments = all_segments_from_rows(rows)
    export_group_segments(all_segments, segment_results_filepath)
    print "Exported segment results to " + segment_results_filepath

    if len(plant_spacings) > 0:
        avg_results_filename = time.strftime("plant_spacings-%Y%m%d-%H%M%S.csv")
        avg_results_filepath = os.path.join(out_directory, avg_results_filename)
        with open(avg_results_filepath, 'wb') as spacingfile:
            csv_writer = csv.writer(spacingfile)
            for spacing in plant_spacings:
                csv_writer.writerow([spacing])
            
