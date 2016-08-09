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
from src.util.clustering import corner_rect_center, filter_out_noise, merge_corner_rectangles
from src.util.plant_localization import RecursiveSplitPlantFilter, ClosestSinglePlantFilter, PlantSpacingFilter
from src.extraction.item_extraction import extract_global_plants_from_images
from src.util.image_writer import ImageWriter

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
    start_code_spacing = float(args.pop('start_code_spacing')) / 100.0 # convert to meters
    end_code_spacing = float(args.pop('end_code_spacing')) / 100.0 # convert to meters
    single_max_dist = float(args.pop('single_max_dist')) / 100.0 # convert to meters
    stick_multiplier = float(args.pop('stick_multiplier'))
    leaf_multiplier = float(args.pop('leaf_multiplier'))
    tag_multiplier = float(args.pop('tag_multiplier'))
    lateral_penalty = float(args.pop('lateral_penalty'))
    projection_penalty = float(args.pop('projection_penalty'))
    closeness_penalty = float(args.pop('closeness_penalty'))
    spacing_filter_thresh = float(args.pop('spacing_filter_thresh'))
    extract_images = args.pop('extract_images').lower() == 'true'
    debug_marked_image = args.pop('marked_image').lower() == 'true'
    
    if len(args) > 0:
        print "Unexpected arguments provided: {}".format(args)
        return ExitReason.bad_arguments
    
    rows = unpickle_stage3_output(input_filepath)
    
    if len(rows) == 0:
        print "No rows could be loaded from {}".format(input_filepath)
        sys.exit(ExitReason.no_rows)
    
    if not os.path.exists(out_directory):
        os.makedirs(out_directory)
        
    all_segments = all_segments_from_rows(rows)

    # Use different filters for normal vs. single segments
    normal_plant_filter = RecursiveSplitPlantFilter(start_code_spacing, end_code_spacing, plant_spacing, lateral_penalty, projection_penalty, 
                                                    closeness_penalty, stick_multiplier, leaf_multiplier, tag_multiplier)
    closest_plant_filter = ClosestSinglePlantFilter(single_max_dist)
    
    # Use a spacing filter for detecting and fixing any mis-chosen plants.
    plant_spacing_filter = PlantSpacingFilter(spacing_filter_thresh)
    
    if extract_images:
        ImageWriter.level = ImageWriter.NORMAL
        image_out_directory = os.path.join(out_directory, 'images/')
    else:
        image_out_directory = None
    
    for seg_num, segment in enumerate(all_segments):
    
        #if segment.start_code.name != 'TBJ':
        #    continue
        
        print "Processing segment {} [{}/{}] with {} images".format(segment.start_code.name, seg_num+1, len(all_segments), len(segment.geo_images))

        if segment.row_number > 6:
            for geo_image in segment.geo_images:
                try:
                    del geo_image.items['stick_parts']
                    del geo_image.items['leaves']
                except KeyError:
                    pass
    
        try:
            if segment.start_code.is_gap_item:
                print "Skipping segment since its start code is listed as a gap."
                continue
        except AttributeError:
            pass # This used to not be supported so it's not a big deal if segment is missing property 
            
        # Cluster together leaves, stick parts and tags into possible plants
        possible_plants = []
        for geo_image in segment.geo_images:
            if 'possible_plants' in geo_image.items:
                # Already clustered this image.
                possible_plants += geo_image.items['possible_plants']
            else:
                possible_plants += cluster_geo_image_items(geo_image, segment, max_plant_size, max_plant_part_distance)
                
        if len(possible_plants) == 0:
            print "Warning: segment {} has no possible plants.".format(segment.start_code.name)
            continue
        
        # Remove small parts that didn't get clustered.
        possible_plants = filter_out_noise(possible_plants)

        print "{} possible plants found between all images".format(len(possible_plants))
    
        print "clustered down to {} possible plants".format(len(possible_plants))
    
        # Find UTM positions of possible plants so that they can be easily compared between different images.
        last_plant = None
        for plant in possible_plants:  
            stick_parts = [part for part in plant['items'] if part['item_type'] == 'stick_part']
            plant_tags = [tag for tag in plant['items'] if part['item_type'] == 'tag']
            if len(plant_tags) > 0:
                # Use position of tag for plant position.
                positioning_rect = merge_corner_rectangles([tag['rect'] for tag in plant_tags])
            elif len(stick_parts) > 0:
                # Use blue stick parts for position
                positioning_rect = merge_corner_rectangles([part['rect'] for part in stick_parts])
            else:
                # No tags or blue sticks so just use entire plant
                positioning_rect = plant['rect']
            if 'image_altitude' in plant:
                altitude = plant['image_altitude']
            elif last_plant is not None:
                altitude = last_plant['position'][2]
            else:
                altitude = segment.start_code.position[2]
            px, py = corner_rect_center(positioning_rect)
            plant['position'] = (px, py, altitude)
            
            last_plant = plant
            
        if segment.start_code.type == 'RowCode' and segment.end_code.type == 'SingleCode':
            # Special case... don't want to process this segment since there shouldn't be a plant associated with it.
            continue
        
        if segment.is_special:
            selected_plant = closest_plant_filter.find_actual_plant(possible_plants, segment)
            actual_plants = [selected_plant] 
        else:
            actual_plants = normal_plant_filter.locate_actual_plants_in_segment(possible_plants, segment)
            plant_spacing_filter.filter(actual_plants)
            print "{} actual plants found".format(len(actual_plants))
            
        # Now that plant filter has run make sure all created plants have a bounding rectangle so they show up in output images.
        for plant in actual_plants:
            if plant.type == 'CreatedPlant':
                px, py, pz = plant.position
                po = .12 # plant offset in meters
                plant.bounding_rect = [(px-po,py-po), (px-po,py+po), (px+po,py-po), (px+po,py+po)] 
        
        extract_global_plants_from_images(actual_plants, segment.geo_images, image_out_directory)
                
        for plant in actual_plants:
            plant.row = segment.row_number
            segment.add_item(plant)
        
        if debug_marked_image:
            if len(actual_plants) > 0:
                debug_draw_plants_in_images(segment.geo_images, possible_plants, actual_plants, out_directory)

    print "\n---------Normal Groups----------"
    print 'Successfully found {} total plants'.format(normal_plant_filter.num_successfully_found_plants)
    print 'Created {} plants'.format(normal_plant_filter.num_created_plants)
    
    print "\n---------Single Groups----------"
    print 'Successfully found {} total plants'.format(closest_plant_filter.num_successfully_found_plants)
    print 'Created {} plants due to no valid plants'.format(closest_plant_filter.num_created_because_no_plants)
    
    print "\n-----Spacing Filter Results-----"
    print 'Relocated {} plants due to bad spacing.'.format(plant_spacing_filter.num_plants_moved)

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
    parser.add_argument('start_code_spacing', help='expected distance (in centimeters) between segment start code and first plant')
    parser.add_argument('end_code_spacing', help='expected distance (in centimeters) between last plant in segment and the next code')
    parser.add_argument('single_max_dist', help='maximum distance (in centimeters) that a plant can be separate from a single code')
    parser.add_argument('-sm', dest='stick_multiplier', default=2, help='Higher value places more emphasis on having a blue stick.')
    parser.add_argument('-lm', dest='leaf_multiplier', default=1.5, help='Higher value places more emphasis on having one or more leaves.')
    parser.add_argument('-tm', dest='tag_multiplier', default=4, help='Higher value places more emphasis on having a tag.')
    parser.add_argument('-lp', dest='lateral_penalty', default=1, help='Higher value penalizes larger values from projected line in orthogonal direction.')
    parser.add_argument('-pp', dest='projection_penalty', default=1, help='Higher value penalizes larger values along projected line.')
    parser.add_argument('-cp', dest='closeness_penalty', default=1, help='Higher value penalizes distances from current item.')
    parser.add_argument('-st', dest='spacing_filter_thresh', default=1.5, help='If you take the ratio of distances between 3 consecutive plants and its greater than this value then the center plant will be centered between the outside 2 plants.')
    parser.add_argument('-ei', dest='extract_images', default='false', help='If true then will extract image of each plant. This can take a while.  Default false.')
    parser.add_argument('-mk', dest='marked_image', default='false', help='If true then will output marked up image.  Default false.')
    
    args = vars(parser.parse_args())
    
    exit_code = stage4_locate_plants(**args)
    
    if exit_code == ExitReason.bad_arguments:
        print "\nSee --help for argument descriptions."
    
    sys.exit(exit_code)
    