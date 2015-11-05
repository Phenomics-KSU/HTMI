#! /usr/bin/env python

import os
import time
import argparse

# Project imports
from src.util.grouping import *
from src.util.stage_io import unpickle_stage1_output, pickle_results, write_args_to_file
from src.processing.item_processing import merge_items
from src.stages.exit_reason import ExitReason
from src.processing.item_processing import position_difference
from src.processing.export_results import export_results

if __name__ == '__main__':
    '''Group codes into rows/groups/segments.'''

    parser = argparse.ArgumentParser(description='''Group codes into rows/groups/segments.''')
    parser.add_argument('input_directory', help='directory containing pickled files from previous stage.')
    parser.add_argument('output_directory', help='where to write output files')
    
    args = parser.parse_args()
    input_directory = args.input_directory
    out_directory = args.output_directory

    geo_images, all_codes = unpickle_stage1_output(input_directory)

    print 'Found {} codes in {} geo images.'.format(len(all_codes), len(geo_images))

    if len(geo_images) == 0 or len(all_codes) == 0:
        print "Couldn't load any geo images or codes from input directory {}".format(input_directory)
        sys.exit(ExitReason.no_geo_images)

    # Merge items so they're unique.  One code references other instances of that same code.
    merged_codes = merge_items(all_codes, max_distance=500)

    print '{} unique codes.'.format(len(merged_codes))

    # Sanity check that multiple references of the same code are all close to each other.
    largest_separation = 0
    sum_separation = 0
    sum_separation_count = 0
    for code in merged_codes:
        for code_ref in code.all_refs:
            diff = position_difference(code.position, code_ref.position)
            sum_separation += diff
            sum_separation_count += 1
            if diff > largest_separation:
                largest_separation = diff
                
    average_separation = 0
    if sum_separation_count > 0:
        average_separation = sum_separation / sum_separation_count
                
    print "From average position largest separation is {} and average is {}".format(largest_separation, average_separation)

    if not os.path.exists(out_directory):
        os.makedirs(out_directory)

    # Write everything out to CSV file.
    all_results_filename = time.strftime("_results_all-%Y%m%d-%H%M%S.csv")
    all_results_filepath = os.path.join(out_directory, all_results_filename)
    export_results(all_codes, [], all_results_filepath)
    print 'Output all codes to {}'.format(all_results_filepath)
    
    # Write averaged results out to file.
    avg_results_filename = time.strftime("_results_averaged-%Y%m%d-%H%M%S.csv")
    avg_results_filepath = os.path.join(out_directory, avg_results_filename)
    export_results(merged_codes, [], avg_results_filepath)
    print 'Output merged codes to {}'.format(avg_results_filepath)