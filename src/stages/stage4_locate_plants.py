#! /usr/bin/env python

import sys
import os
import argparse
import copy

# Project imports
from src.util.stage_io import unpickle_stage3_output, pickle_results, write_args_to_file
from src.util.stage_io import debug_draw_plants_in_images
from src.stages.exit_reason import ExitReason
from src.processing.item_processing import all_segments_from_rows
from src.util.clustering import cluster_rectangle_items, cluster_geo_image_items
from src.util.clustering import corner_rect_center, filter_out_noise
from src.util.plant_localization import RecursiveSplitPlantFilter, ClosestSinglePlantFilter
from src.extraction.item_extraction import extract_global_plants_from_images

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
    max_plant_part_distance = float(args.pop('max_plant_part_distance')) / 100.0 # convert to meters
    plant_spacing = float(args.pop('plant_spacing')) / 100.0 # convert to meters
    code_spacing = float(args.pop('code_spacing')) / 100.0 # convert to meters
    single_max_dist = float(args.pop('single_max_dist')) / 100.0 # convert to meters
    stick_multiplier = float(args.pop('stick_multiplier'))
    leaf_multiplier = float(args.pop('leaf_multiplier'))
    lateral_penalty = float(args.pop('lateral_penalty'))
    projection_penalty = float(args.pop('projection_penalty'))
    closeness_penalty = float(args.pop('closeness_penalty'))
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

    # Use different filters for normal vs. single segments
    normal_plant_filter = RecursiveSplitPlantFilter(code_spacing, plant_spacing, lateral_penalty, projection_penalty, 
                                                    closeness_penalty, stick_multiplier, leaf_multiplier)
    closest_plant_filter = ClosestSinglePlantFilter(single_max_dist)
    
    for seg_num, segment in enumerate(all_segments):
        
        print "Processing segment {} [{}/{}] with {} images".format(segment.start_code.name, seg_num+1, len(all_segments), len(segment.geo_images))

        #if seg_num != 16:
        #    continue # debug break
    
        # Cluster together leaves and stick parts into possible plants
        possible_plants = []
        for geo_image in segment.geo_images:
            if 'possible_plants' in geo_image.items:
                # Already clustered this image.
                possible_plants += geo_image.items['possible_plants']
            else:
                possible_plants += cluster_geo_image_items(geo_image, segment, max_plant_size, max_plant_part_distance)
                
            # write out period to show that images are being clustered
            sys.stdout.write('.')
                
        if len(possible_plants) == 0:
            print "Warning: segment {} has no associated images.".format(segment.start_code.name)
            continue

        print "{} possible plants found between all images".format(len(possible_plants))

        # Cluster together possible plants between multiple images.
        global_max_plant_part_distance = min(2 * max_plant_part_distance, max_plant_size * 0.7)
        possible_plants = cluster_rectangle_items(possible_plants, global_max_plant_part_distance, max_plant_size)
    
        print "clustered down to {} possible plants".format(len(possible_plants))
    
        # Remove small parts that didn't get clustered.
        possible_plants = filter_out_noise(possible_plants)
    
        for plant in possible_plants:  
            px, py = corner_rect_center(plant['rect'])
            plant['position'] = (px, py, segment.start_code.position[2])
        
        if segment.is_special:
            selected_plant = closest_plant_filter.find_actual_plant(possible_plants, segment)
            actual_plants = [selected_plant] 
        else:
            actual_plants = normal_plant_filter.locate_actual_plants_in_segment(possible_plants, segment)
            print "{} actual plants found".format(len(actual_plants))
        
        extract_global_plants_from_images(actual_plants, segment.geo_images)
                
        for plant in actual_plants:
            plant.row = segment.row_number
            segment.add_item(plant)
        
        if debug_marked_image:
            if len(actual_plants) > 0:
                debug_draw_plants_in_images(segment.geo_images, possible_plants, actual_plants, out_directory)

    print "\n---------Normal Groups----------"
    print 'Successfully found {} total plants'.format(normal_plant_filter.num_successfully_found_plants)
    print 'Created {} plants due to no possible plants'.format(normal_plant_filter.num_created_because_no_plants)
    print 'Created {} plants due to no valid plants'.format(normal_plant_filter.num_created_because_no_valid_plants)

    print "\n---------Single Groups----------"
    print 'Successfully found {} total plants'.format(closest_plant_filter.num_successfully_found_plants)
    print 'Created {} plants due to no valid plants'.format(closest_plant_filter.num_created_because_no_plants)

    # Pickle
    dump_filename = "stage4_output.s4"
    print "\nSerializing {} rows to {}".format(len(rows), dump_filename)
    pickle_results(dump_filename, out_directory, rows)
    
    # Write arguments out to file for archiving purposes.
    write_args_to_file("stage4_args.csv", out_directory, args_copy)
    
if __name__ == '__main__':
    '''Group codes into rows/groups/segments.'''

    parser = argparse.ArgumentParser(description='''Group codes into rows/groups/segments.''')
    parser.add_argument('input_filepath', help='pickled file from stage 3.')
    parser.add_argument('output_directory', help='where to write output files')
    parser.add_argument('max_plant_size', help='maximum size of a plant in centimeters')
    parser.add_argument('max_plant_part_distance', help='maximum distance (in centimeters) between parts of a plant.')
    parser.add_argument('plant_spacing', help='expected distance (in centimeters) between consecutive plant')
    parser.add_argument('code_spacing', help='expected distance (in centimeters) before or after group or row codes')
    parser.add_argument('single_max_dist', help='maximum distance (in centimeters) that a plant can be separate from a single code')
    parser.add_argument('-sm', dest='stick_multiplier', default=2, help='Higher value places more emphasis on having a blue stick.')
    parser.add_argument('-lm', dest='leaf_multiplier', default=1.5, help='Higher value places more emphasis on having one or more leaves.')
    parser.add_argument('-lp', dest='lateral_penalty', default=1, help='Higher value penalizes larger values from projected line in orthogonal direction.')
    parser.add_argument('-pp', dest='projection_penalty', default=1, help='Higher value penalizes larger values along projected line.')
    parser.add_argument('-cp', dest='closeness_penalty', default=1, help='Higher value penalizes distances from current item.')
    parser.add_argument('-mk', dest='marked_image', default='false', help='If true then will output marked up image.  Default false.')
    
    args = vars(parser.parse_args())
    
    exit_code = stage4_locate_plants(**args)
    
    if exit_code == ExitReason.bad_arguments:
        print "\nSee --help for argument descriptions."
    
    sys.exit(exit_code)
    