#! /usr/bin/env python

import sys
import os
import argparse

# non-default import
import numpy as np

# Project imports
from src.util.stage_io import unpickle_stage2_output, pickle_results, write_args_to_file
from src.stages.exit_reason import ExitReason
from src.extraction.leaf_finder import LeafFinder
from src.extraction.blue_stick_finder import BlueStickFinder
from src.extraction.tag_finder import TagFinder
from src.processing.item_processing import process_geo_image_to_find_plant_parts, get_subset_of_geo_images
from src.processing.item_processing import dont_overlap_with_items, all_segments_from_rows
from src.util.image_writer import ImageWriter
from src.util.overlap import *

def stage3_extract_plant_parts(**args):
    ''' 
    Extract out possible plant parts to be clustered in next stage.
    args should match the names and descriptions of command line parameters,
    but unlike command line, all arguments must be present.
    '''
    # Copy args so we can archive them to a file when function is finished.
    args_copy = args.copy()
    
    # Convert arguments to local variables of the correct type.
    input_filepath = args.pop('input_filepath')
    out_directory = args.pop('output_directory')
    pad = float(args.pop('pad'))
    special_pad = float(args.pop('special_pad'))
    min_leaf_size = float(args.pop('min_leaf_size'))
    max_leaf_size = float(args.pop('max_leaf_size'))
    min_stick_part_size = float(args.pop('min_stick_part_size'))
    max_stick_part_size = float(args.pop('max_stick_part_size'))
    min_tag_size = float(args.pop('min_tag_size'))
    max_tag_size = float(args.pop('max_tag_size'))
    disable_sticks = args.pop('disable_sticks').lower() == 'true'
    disable_tags = args.pop('disable_tags').lower() == 'true'
    use_marked_image = args.pop('marked_image').lower() == 'true'
    debug_start = args.pop('debug_start')
    debug_stop = args.pop('debug_stop')
    
    if len(args) > 0:
        print "Unexpected arguments provided: {}".format(args)
        return ExitReason.bad_arguments

    rows, geo_images = unpickle_stage2_output(input_filepath)
    
    if len(rows) == 0 or len(geo_images) == 0:
        print "No rows or no geo images could be loaded from {}".format(input_filepath)
        return ExitReason.no_rows
    
    ImageWriter.level = ImageWriter.NORMAL
    
    # Write images out to subdirectory to keep separated from pickled results.
    image_out_directory = os.path.join(out_directory, 'images/')
    if not os.path.exists(image_out_directory):
        os.makedirs(image_out_directory)
    
    rows = sorted(rows, key=lambda r: r.number)
    
    # Sort geo images so they're processed by time.
    geo_images = sorted(geo_images, key=lambda img: img.image_time)
    
    # Look for start/stop filenames so user doesn't have to process all images.
    start_geo_index, stop_geo_index = get_subset_of_geo_images(geo_images, debug_start, debug_stop)
        
    print "Processing geo images {} through {}".format(start_geo_index, stop_geo_index)
    geo_images = geo_images[start_geo_index : stop_geo_index+1]

    num_images_not_in_segment = 0
    num_images_without_path = 0

    leaf_finder = LeafFinder(min_leaf_size, max_leaf_size)
    
    if disable_sticks:
        stick_finder = None
    else:
        stick_finder = BlueStickFinder(min_stick_part_size, max_stick_part_size)
        
    if disable_tags:
        tag_finder = None
    else:
        tag_finder = TagFinder(min_tag_size, max_tag_size)

    all_segments = all_segments_from_rows(rows)
    
    for segment in all_segments:
        if segment.is_special:
            segment.lrud = calculate_special_segment_lrud(segment, special_pad)
        else:
            segment.lrud = calculate_segment_lrud(segment, pad)
    
    num_matched = [] # keep track of how many segments each image maps to.
    num_leaves = [] # how many leaves are in each processed image
    num_sticks = [] # how many sticks are in each processed images
    num_tags = [] # how many tags are in each processed images
    
    for k, geo_image in enumerate(geo_images):
        
        if not geo_image.file_path:
            num_images_without_path += 1
            continue
        
        # Check if image east/west/north/south (lrud) overlaps with any segments.
        image_lrud = calculate_image_lrud(geo_image)
        overlapping_segments = [seg for seg in all_segments if is_overlapping_segment(image_lrud, seg)]
        
        if len(overlapping_segments) == 0:
            num_images_not_in_segment += 1
            continue
        
        print "{} [{} / {}]".format(geo_image.file_name, k, len(geo_images))
            
        leaves, sticks, tags = process_geo_image_to_find_plant_parts(geo_image, leaf_finder, stick_finder, tag_finder, image_out_directory, use_marked_image)
        
        # Remove any false positive items that came from codes.
        geo_codes = geo_image.items['codes'] 
        leaves = dont_overlap_with_items(geo_codes, leaves)
        sticks = dont_overlap_with_items(geo_codes, sticks)
        tags = dont_overlap_with_items(geo_codes, tags)
        
        geo_image.items['leaves'] = leaves
        geo_image.items['stick_parts'] = sticks
        geo_image.items['tags'] = tags
        
        print "Found {} leaves, {} stick parts and {} tags".format(len(leaves), len(sticks), len(tags))

        for segment in overlapping_segments:
            segment.geo_images.append(geo_image)
         
        num_matched.append(len(overlapping_segments))
        num_leaves.append(len(leaves))
        num_sticks.append(len(sticks))
        num_tags.append(len(tags))

    print "\nProcessed {}".format(len(num_matched))
    print "Not in segment {}".format(num_images_not_in_segment)
    print "Invalid path {}".format(num_images_without_path)

    print "Matched images were in average of {} segments".format(np.mean(num_matched))
    print "Average of {} leaves, {} stick parts and {} tags per image".format(np.mean(num_leaves), np.mean(num_sticks), np.mean(num_tags))

    if not os.path.exists(out_directory):
        os.makedirs(out_directory)

    # Pickle
    dump_filename = "stage3_output.s3"
    print "\nSerializing {} rows to {}".format(len(rows), dump_filename)
    pickle_results(dump_filename, out_directory, rows)
    
    # Write arguments out to file for archiving purposes.
    write_args_to_file("stage3_args.csv", out_directory, args_copy)
    
if __name__ == '__main__':
    '''Extract out possible plant parts to be clustered in next stage.'''

    parser = argparse.ArgumentParser(description='''Extract out possible plant parts to be clustered in next stage.''')
    parser.add_argument('input_filepath', help='pickled file from stage 2.')
    parser.add_argument('output_directory', help='where to write output files')
    parser.add_argument('pad', help='how far (in meters) to pad around each segment border to determine if image overlaps.')
    parser.add_argument('special_pad', help='how far (in meters) to pad around each special single code to determine if image overlaps.')
    parser.add_argument('min_leaf_size', help='in centimeters')
    parser.add_argument('max_leaf_size', help='in centimeters')
    parser.add_argument('min_stick_part_size', help='in centimeters')
    parser.add_argument('max_stick_part_size', help='in centimeters')
    parser.add_argument('min_tag_size', help='in centimeters')
    parser.add_argument('max_tag_size', help='in centimeters')
    parser.add_argument('-ds', dest='disable_sticks', default='false', help='If true then will not look for sticks next to plants.  Default false.')
    parser.add_argument('-dt', dest='disable_tags', default='false', help='If true then will not look for tags next to plants.  Default false.')
    parser.add_argument('-mk', dest='marked_image', default='false', help='If true then will output marked up image.  Default false.')
    parser.add_argument('-debug_start', dest='debug_start', default='__none__', help='Substring in image name to start processing at.')
    parser.add_argument('-debug_stop', dest='debug_stop', default='__none__', help='Substring in image name to stop processing at.')

    args = vars(parser.parse_args())
    
    exit_code = stage3_extract_plant_parts(**args)
    
    if exit_code == ExitReason.bad_arguments:
        print "\nSee --help for argument descriptions."
    
    sys.exit(exit_code)
    