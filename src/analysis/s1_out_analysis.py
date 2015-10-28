#! /usr/bin/env python

import sys
import os
import argparse
import pickle
import itertools
import copy
from collections import Counter
from collections import defaultdict

# Project imports
from data import *
from item_extraction import *
from image_utils import *
from item_processing import *

if __name__ == '__main__':
    '''Group codes into rows/groups/segments.'''

    parser = argparse.ArgumentParser(description='''Group codes into rows/groups/segments.''')
    parser.add_argument('input_directory', help='directory containing pickled files from previous stage.')
    parser.add_argument('output_directory', help='where to write output files')
    
    args = parser.parse_args()
    
    # convert command line arguments
    input_directory = args.input_directory
    out_directory = args.output_directory

    # Unpickle geo images.
    stage1_filenames = [f for f in os.listdir(input_directory) if os.path.isfile(os.path.join(input_directory, f))]
    geo_images = []
    for stage1_filename in stage1_filenames:
        stage1_filepath = os.path.join(input_directory, stage1_filename)
        with open(stage1_filepath) as stage1_file:
            file_geo_images = pickle.load(stage1_file)
            print 'Loaded {} geo images from {}'.format(len(file_geo_images), stage1_filename)
            geo_images += file_geo_images
            
    if len(geo_images) == 0:
        print "Couldn't load any geo images from input directory {}".format(input_directory)
        sys.exit(1)
    
    all_codes = []
    for geo_image in geo_images:
        all_codes += [item for item in geo_image.items if 'code' in item.type.lower()]
    
    print 'Found {} codes in {} geo images.'.format(len(all_codes), len(geo_images))
    
    if len(all_codes) == 0:
        sys.exit(1)

    merged_codes = merge_items(all_codes, max_distance=2000)
    
    for code in merged_codes:
        dx = code.position[0] - merged_codes[0].position[0]
        dy = code.position[1] - merged_codes[0].position[1]
        dz = code.position[2] - merged_codes[0].position[2]
        print '{} {} {} {}'.format(code.parent_image_filename, dx, dy, dz)

    # Sanity check that multiple references of the same code are all close to each other.
    largest_separation = 0
    sum_separation = 0
    sum_separation_count = 0
    for code in merged_codes:
        avg_position = average_position(code)
        code_refs = [code] + code.other_items
        for code_ref in code_refs:
            diff = position_difference(avg_position, code_ref.position)
            sum_separation += diff
            sum_separation_count += 1
            if diff > largest_separation:
                largest_separation = diff
                
    average_separation = 0
    if sum_separation_count > 0:
        average_separation = sum_separation / sum_separation_count
                
    print "From average position largest separation is {} and average is {}".format(largest_separation, average_separation)

    # Write everything out to CSV file to be imported into database.
    all_results_filename = time.strftime("_results_all-%Y%m%d-%H%M%S.csv")
    all_results_filepath = os.path.join(out_directory, all_results_filename)
    all_output_items = []
    for item in all_codes:
        all_output_items.extend([item] + item.other_items)
    export_results(all_output_items, [], all_results_filepath)
    print "Exported all results to " + all_results_filepath
    
    # Write averaged results out to file.
    avg_results_filename = time.strftime("_results_averaged-%Y%m%d-%H%M%S.csv")
    avg_results_filepath = os.path.join(out_directory, avg_results_filename)
    avg_output_items = []
    for item in all_codes:
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
    print 'Output averaged {} items'.format(len(avg_output_items))
    export_results(avg_output_items, [], avg_results_filepath)
    print "Exported averaged results to " + avg_results_filepath