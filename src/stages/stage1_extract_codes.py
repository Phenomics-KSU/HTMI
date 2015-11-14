#! /usr/bin/env python

import sys
import os
import argparse
import pickle
import csv
import datetime

# Project imports
from src.util.image_utils import list_images, verify_geo_images
from src.util.stage_io import pickle_results, write_args_to_file
from src.util.image_writer import ImageWriter
from src.util.parsing import parse_geo_file
from src.extraction.code_finder import CodeFinder
from src.processing.item_processing import process_geo_image, merge_items, get_subset_of_geo_images
from exit_reason import ExitReason
    
def stage1_extract_codes(**args):
    ''' 
    Extract codes from set of images and write out results to file.
    args should match the names and descriptions of command line parameters,
    but unlike command line, all arguments must be present.
    '''
    # Copy args so we can archive them to a file when function is finished.
    args_copy = args.copy()
    
    # Convert arguments to local variables of the correct type.
    image_directory = args.pop('image_directory')
    image_geo_file = args.pop('image_geo_file')
    out_directory = args.pop('output_directory')
    postfix_id = args.pop('postfix_id')
    code_min_size = float(args.pop('code_min_size'))
    code_max_size = float(args.pop('code_max_size'))
    provided_resolution = float(args.pop('resolution'))
    use_marked_image = args.pop('marked_image').lower() == 'true'
    camera_rotation = int(args.pop('camera_rotation'))
    debug_start = args.pop('debug_start')
    debug_stop = args.pop('debug_stop')

    if len(args) > 0:
        print "Unexpected arguments provided: {}".format(args)
        return ExitReason.bad_arguments
    
    if code_max_size <= 0 or code_min_size <= 0:
        print "\nError: code sizes must be greater than zero.\n"
        return ExitReason.bad_arguments
        
    if code_max_size <= code_min_size:
        print "\nError: Max code size must be greater than min.\n"
        return ExitReason.bad_arguments
    
    if provided_resolution <= 0:
        print "\nError: Resolution must be greater than zero."
        return ExitReason.bad_arguments
        
    possible_camera_rotations = [0, 90, 180, 270]
    if camera_rotation not in possible_camera_rotations:
        print "Error: Camera rotation {} invalid.  Possible choices are {}".format(camera_rotation, possible_camera_rotations)
        return ExitReason.bad_arguments
        
    image_filenames = list_images(image_directory, ['tiff', 'tif', 'jpg', 'jpeg', 'png'])
                        
    if len(image_filenames) == 0:
        print "No images found in directory: {}".format(image_directory)
        return ExitReason.no_images
    
    print "\nFound {} images to process".format(len(image_filenames))
    
    geo_images = parse_geo_file(image_geo_file, provided_resolution, camera_rotation)
            
    print "Parsed {} geo images".format(len(geo_images))
    
    if len(geo_images) == 0:
        print "No geo images. Exiting."
        return ExitReason.no_geo_images
    
    # Look for start/stop filenames so user doesn't have to process all images.
    start_geo_index, stop_geo_index = get_subset_of_geo_images(geo_images, debug_start, debug_stop)
        
    print "Processing geo images {} through {}".format(start_geo_index, stop_geo_index)
    geo_images = geo_images[start_geo_index : stop_geo_index+1]
        
    print "Sorting images by timestamp."
    geo_images = sorted(geo_images, key=lambda image: image.image_time)
    
    geo_images, missing_image_count = verify_geo_images(geo_images, image_filenames)
           
    if missing_image_count > 0:
        print "Warning {} geo images do not exist and will be skipped.".format(missing_image_count)

    if len(geo_images) == 0:
        print "No images match up with any geo images. Exiting."
        return ExitReason.no_geo_images

    code_finder = CodeFinder(code_min_size, code_max_size)
    
    ImageWriter.level = ImageWriter.NORMAL
    
    # Write images out to subdirectory to keep separated from pickled results.
    image_out_directory = os.path.join(out_directory, 'images/')
    if not os.path.exists(image_out_directory):
        os.makedirs(image_out_directory)

    # Find and extract all codes from images.
    codes = []
    try:
        for i, geo_image in enumerate(geo_images):
            print "Analyzing image {} [{}/{}]".format(geo_image.file_name, i+1, len(geo_images))
            newly_found_codes = process_geo_image(geo_image, [code_finder], image_directory, image_out_directory, use_marked_image)
            geo_image.items["codes"] = newly_found_codes
            for code in newly_found_codes:
                print "Found {}: {}".format(code.type, code.name)
            codes += newly_found_codes
    except KeyboardInterrupt:
        print "\nKeyboard interrupt detected."
        answer = raw_input("\nType y to save results or anything else to quit: ").strip()
        if answer.lower() != 'y':
            return ExitReason.user_interrupt
  
    dump_filename = "stage1_output_{}_{}_{}.s1".format(postfix_id, int(geo_images[0].image_time), int(geo_image.image_time))
    print "Serializing {} geo images and {} codes to {}.".format(len(geo_images), len(codes), dump_filename)
    pickle_results(dump_filename, out_directory, geo_images, codes)
    
    # Display code stats for user.
    merged_codes = merge_items(codes, max_distance=500)
    if len(merged_codes) == 0:
        print "No codes found."
    else:
        print "There were {} codes found and {} were unique.  Average code is in {} images.".format(len(codes), len(merged_codes), float(len(codes)) / len(merged_codes))
        print "Merged codes not being saved.  Just for user information."

    # Write arguments out to file for archiving purposes.
    args_filename = "stage1_args_{}_{}_{}.csv".format(postfix_id, int(geo_images[0].image_time), int(geo_image.image_time))
    write_args_to_file(args_filename, out_directory, args_copy)
        
    return ExitReason.success

if __name__ == '__main__':
    '''Extract codes from geotagged images.'''

    parser = argparse.ArgumentParser(description='''Extract codes from geotagged images''')
    parser.add_argument('image_directory', help='where to search for images to process')
    parser.add_argument('image_geo_file', help='file with position/heading data for each image.')
    parser.add_argument('output_directory', help='where to write output files')
    parser.add_argument('postfix_id', help='unique string to be appended to output files. For example could be camera name.')
    parser.add_argument('code_min_size', help='Minimum side length of code item in centimeters. Must be > 0')
    parser.add_argument('code_max_size', help='Maximum side length of code item in centimeters. Must be > 0')
    parser.add_argument('-rs', dest='resolution', default=0, help='Image resolution in centimeter/pixel.')
    parser.add_argument('-mk', dest='marked_image', default='false', help='If true then will output marked up image.  Default false.')
    parser.add_argument('-cr', dest='camera_rotation', default=0, help='Camera rotation (0, 90, 180, 270).  0 is camera top forward and increases counter-clockwise.' )
    parser.add_argument('-debug_start', dest='debug_start', default='__none__', help='Substring in image name to start processing at.')
    parser.add_argument('-debug_stop', dest='debug_stop', default='__none__', help='Substring in image name to stop processing at.')
    
    args = vars(parser.parse_args())
    
    exit_code = stage1_extract_codes(**args)
    
    if exit_code == ExitReason.bad_arguments:
        print "\nSee --help for argument descriptions."
    
    sys.exit(exit_code)