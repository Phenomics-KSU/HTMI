#! /usr/bin/env python

import sys
import os
import argparse

# non-default import
#import numpy as np

# Project imports
from src.util.stage_io import unpickle_stage2_output, pickle_results
from src.stages.exit_reason import ExitReason
from src.extraction.leaf_finder import LeafFinder
from src.extraction.blue_stick_finder import BlueStickFinder

def is_overlapping_segment(image_ewns, segment):
    
    e, w, n, s = image_ewns

    seg_e, seg_w, seg_n, seg_s = calculate_segment_ewns(segment)

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

def calculate_segment_ewns(seg, pad):
    
    p1 = seg.start_code.position
    p2 = seg.end_code.position
    
    if segment.is_special():
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

    args = parser.parse_args()
    
    # convert command line arguments
    input_filepath = args.input_filepath
    out_directory = args.output_directory

    rows, geo_images = unpickle_stage2_output(input_filepath)
    
    if len(rows) == 0 or len(geo_images) == 0:
        print "No rows or no geo images could be loaded from {}".format(input_filepath)
        sys.exit(ExitReason.no_rows)
    
    rows = sorted(rows, key=lambda r: r.number)

    num_images_not_in_segment = 0
    num_images_without_path = 0
    num_images_processed = 0
    
    leaf_finder = LeafFinder()
    blue_stick_finder = BlueStickFinder()
    
    segments_by_row = [row.segments for row in rows]
    segments = [seg for row_segments in segments_by_row for seg in row_segments]
    
    for geo_image in geo_images:
        
        if not geo_image.file_path:
            num_images_without_path += 1
            continue
        
        # Check if image east/west/north/south (ewns) overlaps with any segments.
        image_ewns = calculate_image_ewns(geo_image)
        overlapping_segment = [seg for seg in segments if is_overlapping_segment(image_ewns, seg)]
        
        if len(segments) == 0:
            num_images_not_in_segment += 1
            continue
            
        #process_geo_image(geo_image)
        num_images_processed += 1
            
        for segment in segments:
            segment.geo_images.append(geo_image)
         
    print "\nProcessed {}".format(num_images_processed)
    print "Not in segment {}".format(num_images_not_in_segment)
    print "Invalid path {}".format(num_images_without_path)

    # Pickle
    dump_filename = "stage3_output.s3"
    print "Serializing {} rows to {}.".format(len(rows), dump_filename)
    pickle_results(dump_filename, out_directory, rows)
    