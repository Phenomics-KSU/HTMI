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
from src.processing.item_processing import calculate_field_positions, all_segments_from_rows
from src.processing.export_results import export_group_segments, export_results
from src.util.image_writer import ImageWriter
from src.util.image_utils import postfix_filename, draw_rect
from src.util.numbering import number_serpentine, assign_range_number

if __name__ == '__main__':
    '''Output results.'''

    parser = argparse.ArgumentParser(description='''Output results.''')
    parser.add_argument('input_filepath', help='pickled file from stage 4.')
    parser.add_argument('output_directory', help='where to write output files')
    
    args = parser.parse_args()
    
    # convert command line arguments
    input_filepath = args.input_filepath
    out_directory = args.output_directory

    # Unpickle rows.
    rows = unpickle_stage4_output(input_filepath)
    
    print 'Loaded {} rows'.format(len(rows))
    
    if len(rows) == 0:
        sys.exit(ExitReason.no_rows)
    
    rows = sorted(rows, key=lambda r: r.number)
    
    items = number_serpentine(rows)
    
    print 'Found {} items in rows.'.format(len(items))
    
    assign_range_number(items, rows)
    
    calculate_field_positions(items)
    
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
    just_codes = [item for item in items if 'code' in item.type.lower()]
    export_results(just_codes, rows, just_codes_results_filepath)
    print "Exported just code results to " + just_codes_results_filepath

    # Output group segments to a file.
    segment_results_filename = time.strftime("results_segments-%Y%m%d-%H%M%S.csv")
    segment_results_filepath = os.path.join(out_directory, segment_results_filename)
    all_segments = all_segments_from_rows(rows)
    export_group_segments(all_segments, segment_results_filepath)
    print "Exported segment results to " + segment_results_filepath
