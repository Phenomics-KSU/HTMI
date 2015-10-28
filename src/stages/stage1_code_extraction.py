#! /usr/bin/env python

import sys
import os
import argparse
import pickle

# Project imports
from src.util.image_utils import list_images, index_containing_substring, verify_geo_images
from src.util.image_writer import ImageWriter
from src.util.parsing import parse_geo_file
from src.extraction.item_extraction import ItemExtractor
from src.extraction.code_finder import CodeFinder
from src.processing.item_processing import process_geo_image, merge_items

if __name__ == '__main__':
    '''Extract codes from images.'''

    parser = argparse.ArgumentParser(description='''Extract codes from images''')
    parser.add_argument('image_directory', help='where to search for images to process')
    parser.add_argument('image_geo_file', help='file with position/heading data for each image.')
    parser.add_argument('output_directory', help='where to write output files')
    parser.add_argument('code_min_size', help='Minimum side length of code item in centimeters. Must be > 0')
    parser.add_argument('code_max_size', help='Maximum side length of code item in centimeters. Must be > 0')
    parser.add_argument('-rs', dest='resolution', default=0, help='Image resolution in centimeter/pixel.')
    parser.add_argument('-mk', dest='marked_image', default='false', help='If true then will output marked up image.  Default false.')
    parser.add_argument('-cr', dest='camera_rotation', default=0, help='Camera rotation (0, 90, 180, 270).  0 is camera top forward and increases counter-clockwise.' )
    parser.add_argument('-debug_start', dest='debug_start', default='__none__', help='Substring in image name to start processing at.')
    parser.add_argument('-debug_stop', dest='debug_stop', default='__none__', help='Substring in image name to stop processing at.')
    
    args = parser.parse_args()
    
    # Convert command line arguments
    image_directory = args.image_directory
    image_geo_file = args.image_geo_file
    out_directory = args.output_directory
    code_min_size = float(args.code_min_size)
    code_max_size = float(args.code_max_size)
    provided_resolution = float(args.resolution)
    use_marked_image = args.marked_image.lower() == 'true'
    camera_rotation = int(args.camera_rotation)
    debug_start = args.debug_start
    debug_stop = args.debug_stop
    
    if code_max_size <= 0 or code_min_size <= 0:
        print "\nError: code sizes must be greater than zero.\n"
        parser.print_help()
        sys.exit(1)
        
    if code_max_size <= code_min_size:
        print "\nError: Max code size must be greater than min.\n"
        parser.print_help()
        sys.exit(1)
    
    if provided_resolution <= 0:
        print "\nError: Resolution must be greater than zero."
        parser.print_help()
        sys.exit(1)
        
    possible_camera_rotations = [0, 90, 180, 270]
    if camera_rotation not in possible_camera_rotations:
        print "Error: Camera rotation {} invalid.  Possible choices are {}".format(camera_rotation, possible_camera_rotations)
        sys.exit(1)
        
    image_filenames = list_images(image_directory, ['tiff', 'tif', 'jpg', 'jpeg', 'png'])
                        
    if len(image_filenames) == 0:
        print "No images found in directory: {}".format(image_directory)
        sys.exit(1)
    
    print "\nFound {} images to process".format(len(image_filenames))
    
    geo_images = parse_geo_file(image_geo_file, provided_resolution, camera_rotation)
            
    print "Parsed {} geo images".format(len(geo_images))
    
    if len(geo_images) == 0:
        print "No geo images. Exiting."
        sys.exit(1)
    
    geo_image_filenames = [g.file_name for g in geo_images]
    start_geo_index = index_containing_substring(geo_image_filenames, debug_start)
    if start_geo_index < 0:
        start_geo_index = 0
    stop_geo_index = index_containing_substring(geo_image_filenames, debug_stop)
    if stop_geo_index < 0:
        stop_geo_index = len(geo_images) - 1
        
    print "Processing geo images {} through {}".format(start_geo_index, stop_geo_index)
    geo_images = geo_images[start_geo_index : stop_geo_index+1]
        
    print "Sorting images by timestamp."
    geo_images = sorted(geo_images, key=lambda image: image.image_time)
    
    geo_images, missing_image_count = verify_geo_images(geo_images, image_filenames)
           
    if missing_image_count > 0:
        print "Warning {} geo images do not exist and will be skipped.".format(missing_image_count)

    code_finder = CodeFinder(code_min_size, code_max_size)
    item_extractor = ItemExtractor()
    
    ImageWriter.level = ImageWriter.NORMAL
    
    # Write images out to subdirectory to keep separated from pickled results.
    image_out_directory = os.path.join(out_directory, 'images/')

    # Extract all code items from images.
    codes = []
    for i, geo_image in enumerate(geo_images):
        print "Analyzing image {} [{}/{}]".format(geo_image.file_name, i+1, len(geo_images))
        newly_found_codes = process_geo_image(geo_image, item_extractor, camera_rotation, image_directory, image_out_directory, use_marked_image)
        for code in newly_found_codes:
            print "Found code: {}".format(code.name)
        codes += newly_found_codes
  
    dump_filename = "stage1_geoimages_{}_{}.txt".format(int(geo_images[0].image_time), int(geo_image[-1].image_time))
    dump_filepath = os.path.join(out_directory, dump_filename)
    print "Serializing {} geo images and {} codes to {}.".format(len(geo_images), len(codes), dump_filepath)
    with open(dump_filepath, 'wb') as dump_file:
        pickle.dump(geo_images, codes, dump_file)

    # Display code stats for user.
    merged_codes = merge_items(codes, max_distance=500)
    if len(merged_codes) == 0:
        print "No codes found."
    else:
        print "There were {} codes found and {} were unique.  Average code is in {} images.".format(len(codes), len(merged_codes), float(len(codes)) / len(merged_codes))
        print "Merged codes not being saved.  Just for user information."
