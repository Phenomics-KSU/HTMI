#! /usr/bin/env python

import sys
import os
import argparse
import copy

# non-default import
import cv2
import numpy as np

# Project imports
from src.util.stage_io import unpickle_stage3_output, pickle_results, write_args_to_file
from src.util.stage_io import debug_draw_plants_in_images
from src.stages.exit_reason import ExitReason
from src.processing.item_processing import all_segments_from_rows
from src.util.clustering import cluster_rectangle_items, rect_to_global, rect_to_image
from src.util.clustering import corner_rect_center, filter_out_noise
from src.util.plant_localization import RecursiveSplitPlantFilter
from src.data.field_item import Plant

def stage4_locate_plants(**args):
    ''' 
    Cluster and filter plant parts into actual plants.
    args should match the names and descriptions of command line parameters,
    but unlike command line, all arguments must be present.
    '''
    # Copy args so we can archive them to a file when function is finished.
    args_copy = args.copy()

    # convert command line arguments
    input_filepath = args.pop('input_filepath')
    out_directory = args.pop('output_directory')
    max_plant_size = float(args.pop('max_plant_size')) / 100.0 # convert to meters
    plant_spacing = float(args.pop('plant_spacing')) / 100.0 # convert to meters
    code_spacing = float(args.pop('code_spacing')) / 100.0 # convert to meters
    debug_marked_image = args.pop('marked_image').lower() == 'true'
    
    if len(args) > 0:
        print "Unexpected arguments provided: {}".format(args)
        return ExitReason.bad_arguments
    
    rows = unpickle_stage3_output(input_filepath)
    
    if len(rows) == 0:
        print "No rows or could be loaded from {}".format(input_filepath)
        sys.exit(ExitReason.no_rows)
    
    if not os.path.exists(out_directory):
        os.makedirs(out_directory)
        
    all_segments = all_segments_from_rows(rows)

    plant_filter = RecursiveSplitPlantFilter(code_spacing, plant_spacing)
    
    for seg_num, segment in enumerate(all_segments):
        
        print "Processing segment {} [{}/{}] with {} images".format(segment.start_code.name, seg_num+1, len(all_segments), len(segment.geo_images))
    
        # Cluster together leaves and stick parts into possible plants
        possible_plants = []
        for geo_image in segment.geo_images:
            if 'possible_plants' in geo_image.items:
                # Already clustered this image.
                possible_plants += geo_image.items['possible_plants']
            else:
                # Merge items into possible plants, while referencing rectangle off global coordinates so we can
                # compare rectangles between multiple images.
                leaves = [{'item_type':'leaf', 'rect':rect_to_global(rect, geo_image)} for rect in geo_image.items['leaves']]
                stick_parts = [{'item_type':'stick_part', 'rect':rect_to_global(rect, geo_image)} for rect in geo_image.items['stick_parts']]
                plant_parts = leaves + stick_parts
                geo_image_possible_plants = cluster_rectangle_items(plant_parts, max_plant_size*0.5, max_plant_size)
                geo_image.items['possible_plants'] = geo_image_possible_plants
                possible_plants += geo_image_possible_plants
                
            # write out period to show that images are being clustered
            sys.stdout.write('.')
                
        if len(possible_plants) == 0:
            print "Warning: segment {} has no associated images.".format(segment.start_code.name)
            continue

        print "{} possible plants found".format(len(possible_plants))

        # Cluster together possible plants between multiple images.
        possible_plants = cluster_rectangle_items(possible_plants, max_plant_size*0.7, max_plant_size)
    
        possible_plants = filter_out_noise(possible_plants)
    
        for plant in possible_plants:  
            px, py = corner_rect_center(plant['rect'])
            plant['position'] = (px, py, segment.start_code.position[2])
        
        actual_plants = plant_filter.locate_actual_plants_in_segment(possible_plants, segment)
      
        print "{} actual plants found".format(len(actual_plants))
      
        for plant in actual_plants:
            global_bounding_rect = plant.bounding_rect
            if global_bounding_rect is None:
                continue
            for k, geo_image in enumerate(segment.geo_images):
                image_rect = rect_to_image(global_bounding_rect, geo_image)
                x, y = image_rect[0]
                if x > 0 and x < geo_image.width and y > 0 and y < geo_image.height:
                    if not plant.parent_image_filename.strip():
                        plant.bounding_rect = image_rect
                        plant.parent_image_filename = geo_image.file_name
                    else:
                        plant_copy = Plant('plant', position=plant.position, zone=plant.zone)
                        plant_copy.bounding_rect = image_rect
                        plant_copy.parent_image_filename = geo_image.file_name
                        plant.add_other_item(plant_copy)
                    
                    # TODO extract picture of plant
                
        for plant in actual_plants:
            plant.row = segment.row_number
            segment.add_item(plant)
        
        if debug_marked_image:
            debug_draw_plants_in_images(segment.geo_images, possible_plants, actual_plants, out_directory)

    print 'Successfully found {} total plants'.format(plant_filter.num_successfully_found_plants)
    print 'Created {} plants due to no possible plants'.format(plant_filter.num_created_because_no_plants)
    print 'Created {} plants due to no valid plants'.format(plant_filter.num_created_because_no_valid_plants)

    # go through each plant/code in segment
    # -> then convert bounding box to positions
    # -> then go through every image and see if position is on imame.. if it is then draw box.
    # -> change color of box for next item

    # Pickle
    dump_filename = "stage4_output.s4"
    print "\nSerializing {} rows to {}".format(len(rows), dump_filename)
    pickle_results(dump_filename, out_directory, rows)
    
    # Write arguments out to file for archiving purposes.
    write_args_to_file("stage4_args.csv", out_directory, args_copy)
    
if __name__ == '__main__':
    '''Group codes into rows/groups/segments.'''

    parser = argparse.ArgumentParser(description='''Extract out possible plant parts to be clustered in next stage.''')
    parser.add_argument('input_filepath', help='pickled file from stage 3.')
    parser.add_argument('output_directory', help='where to write output files')
    parser.add_argument('max_plant_size', help='maximum size of a plant in centimeters')
    parser.add_argument('plant_spacing', help='expected distance (in centimeters) between consecutive plant')
    parser.add_argument('code_spacing', help='expected distance (in centimeters) before or after group or row codes')
    parser.add_argument('-mk', dest='marked_image', default='false', help='If true then will output marked up image.  Default false.')
    
    args = vars(parser.parse_args())
    
    exit_code = stage4_locate_plants(**args)
    
    if exit_code == ExitReason.bad_arguments:
        print "\nSee --help for argument descriptions."
    
    sys.exit(exit_code)
    