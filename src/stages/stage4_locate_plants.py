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
from src.stages.exit_reason import ExitReason
from src.processing.item_processing import dont_overlap_with_items, all_segments_from_rows
from src.util.image_writer import ImageWriter
from src.util.image_utils import postfix_filename, draw_rect
from src.util.clustering import cluster_rectangle_items, rect_to_global, rect_to_image, corner_rect_center
from src.util.plant_localization import RecursiveSplitPlantFilter
from src.data.field_item import Plant

if __name__ == '__main__':
    '''Extract out possible plant parts to be clustered in next stage.'''

    parser = argparse.ArgumentParser(description='''Extract out possible plant parts to be clustered in next stage.''')
    parser.add_argument('input_filepath', help='pickled file from stage 3.')
    parser.add_argument('output_directory', help='where to write output files')
    parser.add_argument('max_plant_size', help='maximum size of a plant in centimeters')
    parser.add_argument('-mk', dest='marked_image', default='false', help='If true then will output marked up image.  Default false.')

    args = parser.parse_args()
    
    # convert command line arguments
    input_filepath = args.input_filepath
    out_directory = args.output_directory
    max_plant_size = float(args.max_plant_size)

    rows = unpickle_stage3_output(input_filepath)
    
    if len(rows) == 0:
        print "No rows or could be loaded from {}".format(input_filepath)
        sys.exit(ExitReason.no_rows)
    
    if not os.path.exists(out_directory):
        os.makedirs(out_directory)
        
    all_segments = all_segments_from_rows(rows)
    
    plant_spacing = 0.6096 # meters (24 inches)
    code_spacing = plant_spacing / 2
    plant_filter = RecursiveSplitPlantFilter(code_spacing, plant_spacing)
    
    item_colors = [(0, 0, 255), (255, 0, 0), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
    item_idx = 0
    
    for segment in all_segments:
        
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
                #plant_parts = plant_parts[:2]
                geo_image_possible_plants = cluster_rectangle_items(plant_parts, max_plant_size)
                geo_image.items['possible_plants'] = geo_image_possible_plants
                possible_plants += geo_image_possible_plants
                
        if len(possible_plants) == 0:
            #print "Warning: segment {} has no associated images.".format(segment.start_code.name)
            continue

        # Cluster together possible plants between multiple images.
        possible_plants = cluster_rectangle_items(possible_plants, max_plant_size)
    
        for plant in possible_plants:  
            px, py = corner_rect_center(plant['rect'])
            plant['position'] = (px, py, segment.start_code.position[2])
        
        actual_plants = plant_filter.locate_actual_plants_in_segment(possible_plants, segment)
      
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
        
        print "Segment {} has {} possible plants and {} actual plants".format(segment.start_code.name, len(possible_plants), len(actual_plants))
        
        # Write images out to subdirectory to keep separated from pickled results.
        image_out_directory = os.path.join(out_directory, 'images/')
        if not os.path.exists(image_out_directory):
            os.makedirs(image_out_directory)
            
        debug_images = []
        for geo_image in segment.geo_images:
            if hasattr(geo_image, 'debug_filepath'):
                path = geo_image.debug_filepath
            else:
                path = geo_image.file_path
            debug_images.append(cv2.imread(geo_image.file_path, cv2.CV_LOAD_IMAGE_COLOR))
        for item in possible_plants:
            item_color = item_colors[item_idx % len(item_colors)]
            for k, geo_image in enumerate(segment.geo_images):
                for ext_item in [item] + item.get('items',[]):
                    image_rect = rect_to_image(ext_item['rect'], geo_image)
                    draw_rect(debug_images[k], image_rect, item_color, thickness=2)
                
            item_idx += 1
            
        for plant in actual_plants:
            for ref in plant.all_refs:
                if not ref.parent_image_filename:
                    continue
                geo_image_filenames = [geo_image.file_name for geo_image in segment.geo_images]
                debug_img_index = geo_image_filenames.index(ref.parent_image_filename)
                debug_img = debug_images[debug_img_index]
                draw_rect(debug_img, ref.bounding_rect, (0, 255, 0), thickness=3)
                
        debug_filepaths = [os.path.join(image_out_directory, postfix_filename(geo_image.file_name, 'marked')) for geo_image in segment.geo_images]
        for k, (image, filepath) in enumerate(zip(debug_images, debug_filepaths)):
            cv2.imwrite(filepath, image)
            segment.geo_images[k].debug_filepath = filepath

    # go through each plant/code in segment
    # -> then convert bounding box to positions
    # -> then go through every image and see if position is on imame.. if it is then draw box.
    # -> change color of box for next item

    # Pickle
    dump_filename = "stage4_output.s4"
    print "\nSerializing {} rows to {}".format(len(rows), dump_filename)
    pickle_results(dump_filename, out_directory, rows)
    
    # Write arguments out to file for archiving purposes.
    write_args_to_file("stage4_args.csv", out_directory, vars(args))
    