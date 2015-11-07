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
from src.processing.item_processing import process_geo_image_to_find_plant_parts, get_subset_of_geo_images
from src.processing.item_processing import dont_overlap_with_items
from src.util.image_writer import ImageWriter

def is_overlapping_segment(image_ewns, segment):
    
    e, w, n, s = image_ewns

    seg_e, seg_w, seg_n, seg_s = segment.ewns

    return n > seg_s and s < seg_n and e > seg_w and w < seg_e
    
def calculate_image_ewns(geo_image):

    east = max(geo_image.top_left_position[0], geo_image.top_right_position[0],
               geo_image.bottom_left_position[0], geo_image.bottom_right_position[0])
    west = min(geo_image.top_left_position[0], geo_image.top_right_position[0],
               geo_image.bottom_left_position[0], geo_image.bottom_right_position[0])
    north = max(geo_image.top_left_position[1], geo_image.top_right_position[1],
                geo_image.bottom_left_position[1], geo_image.bottom_right_position[1])
    south = min(geo_image.top_left_position[1], geo_image.top_right_position[1],
                geo_image.bottom_left_position[1], geo_image.bottom_right_position[1])
    return (east, west, north, south)

def calculate_segment_ewns(segment, pad):
    
    p1 = segment.start_code.position
    p2 = segment.end_code.position
    
    if segment.is_special:
        # segment is centered on start code
        east = p1[0] + pad
        west = p1[0] - pad
        north = p1[1] + pad
        south = p1[1] - pad
    else:
        east = max(p1[0], p2[0]) + pad
        west = min(p1[0], p2[0]) - pad
        north = max(p1[1], p2[1]) + pad
        south = min(p1[1], p2[1]) - pad
        
    return (east, west, north, south)

if __name__ == '__main__':
    '''Extract out possible plant parts to be clustered in next stage.'''

    parser = argparse.ArgumentParser(description='''Extract out possible plant parts to be clustered in next stage.''')
    parser.add_argument('input_filepath', help='pickled file from stage 2.')
    parser.add_argument('output_directory', help='where to write output files')
    parser.add_argument('pad', help='how far (in meters) to pad around each segment border to determine if image overlaps.')
    parser.add_argument('-mk', dest='marked_image', default='false', help='If true then will output marked up image.  Default false.')
    parser.add_argument('-debug_start', dest='debug_start', default='__none__', help='Substring in image name to start processing at.')
    parser.add_argument('-debug_stop', dest='debug_stop', default='__none__', help='Substring in image name to stop processing at.')

    args = parser.parse_args()
    
    # convert command line arguments
    input_filepath = args.input_filepath
    out_directory = args.output_directory
    pad = float(args.pad)
    use_marked_image = args.marked_image.lower() == 'true'
    debug_start = args.debug_start
    debug_stop = args.debug_stop

    rows, geo_images = unpickle_stage2_output(input_filepath)
    
    if len(rows) == 0 or len(geo_images) == 0:
        print "No rows or no geo images could be loaded from {}".format(input_filepath)
        sys.exit(ExitReason.no_rows)
    
    
    ImageWriter.level = ImageWriter.DEBUG
    
    # Write images out to subdirectory to keep separated from pickled results.
    image_out_directory = os.path.join(out_directory, 'images/')
    if not os.path.exists(image_out_directory):
        os.makedirs(image_out_directory)
    
    rows = sorted(rows, key=lambda r: r.number)
    
    # Look for start/stop filenames so user doesn't have to process all images.
    # Look for start/stop filenames so user doesn't have to process all images.
    start_geo_index, stop_geo_index = get_subset_of_geo_images(geo_images, debug_start, debug_stop)
        
    print "Processing geo images {} through {}".format(start_geo_index, stop_geo_index)
    geo_images = geo_images[start_geo_index : stop_geo_index+1]

    num_images_not_in_segment = 0
    num_images_without_path = 0

    leaf_finder = LeafFinder(0.4, 40)
    stick_finder = BlueStickFinder(14, 0.35)
    
    segments_by_row = [row.segments for row in rows]
    all_segments = [seg for row_segments in segments_by_row for seg in row_segments]
    
    for segment in all_segments:
        segment.ewns = calculate_segment_ewns(segment, pad)
    
    num_matched = [] # keep track of how many segments each image maps to.
    num_leaves = [] # how many leaves are in each processed image
    num_sticks = [] # how many sticks are in each processed images
    
    for k, geo_image in enumerate(geo_images):
        
        if not geo_image.file_path:
            num_images_without_path += 1
            continue
        
        # Check if image east/west/north/south (ewns) overlaps with any segments.
        image_ewns = calculate_image_ewns(geo_image)
        overlapping_segments = [seg for seg in all_segments if is_overlapping_segment(image_ewns, seg)]
        
        if len(overlapping_segments) == 0:
            num_images_not_in_segment += 1
            continue
        
        print "[{} / {}]".format(k, len(geo_images))
            
        leaves, sticks = process_geo_image_to_find_plant_parts(geo_image, leaf_finder, stick_finder, image_out_directory, use_marked_image)
        
        # Remove any false positive leaves or sticks that came from codes. 
        leaves = dont_overlap_with_items(geo_image.items['codes'], leaves)
        sticks = dont_overlap_with_items(geo_image.items['codes'], sticks)
        
        geo_image.items['leaves'] = leaves
        geo_image.items['stick_parts'] = sticks
        
        print "Found {} leaves and {} stick parts".format(len(leaves), len(sticks))

        for segment in overlapping_segments:
            segment.geo_images.append(geo_image)
         
        num_matched.append(len(overlapping_segments))
        num_leaves.append(len(leaves))
        num_sticks.append(len(sticks))

    print "\nProcessed {}".format(len(num_matched))
    print "Not in segment {}".format(num_images_not_in_segment)
    print "Invalid path {}".format(num_images_without_path)

    print "Matched images were in average of {} segments".format(np.mean(num_matched))
    print "Average of {} leaves and {} stick parts per image".format(np.mean(num_leaves), np.mean(num_sticks))

    if not os.path.exists(out_directory):
        os.makedirs(out_directory)

    # Pickle
    dump_filename = "stage3_output.s3"
    print "\nSerializing {} rows to {}".format(len(rows), dump_filename)
    pickle_results(dump_filename, out_directory, rows)
    
    # Write arguments out to file for archiving purposes.
    write_args_to_file("stage3_args.csv", out_directory, vars(args))
    