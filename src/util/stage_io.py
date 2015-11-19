#! /usr/bin/env python

import os
import sys
import pickle
import csv
import datetime
import copy
from collections import namedtuple

# OpenCV imports
import cv2

# Project imports
from src.util.image_utils import make_filename_unique
from src.util.image_utils import postfix_filename, draw_rect
from src.util.clustering import rect_to_image

def pickle_results(filename, out_directory, *args):
    
    filename = make_filename_unique(out_directory, filename)
    filepath = os.path.join(out_directory, filename)
    sys.setrecursionlimit(100000)
    with open(filepath, 'wb') as dump_file:
        for arg in args:
            pickle.dump(arg, dump_file, protocol=2)
            
def write_args_to_file(filename, out_directory, args):
    # Write arguments out to file for archiving purposes.
    args_filepath = os.path.join(out_directory, filename)
    with open(args_filepath, 'wb') as args_file:
        csv_writer = csv.writer(args_file)
        csv_writer.writerow(['Date', str(datetime.datetime.now())])
        csv_writer.writerows([[k, v] for k, v in args.items()])

def unpickle_stage1_output(input_directory):
    stage1_filenames = [f for f in os.listdir(input_directory) if os.path.isfile(os.path.join(input_directory, f)) 
                                                                  and os.path.splitext(f)[1] == '.s1']
    geo_images = []
    codes = []
    for stage1_filename in stage1_filenames:
        stage1_filepath = os.path.join(input_directory, stage1_filename)
        with open(stage1_filepath, 'rb') as stage1_file:
            file_geo_images = pickle.load(stage1_file)
            file_codes = pickle.load(stage1_file)
            print 'Loaded {} geo images and {} codes from {}'.format(len(file_geo_images), len(file_codes), stage1_filename)
            geo_images += file_geo_images
            codes += file_codes
    return geo_images, codes

def unpickle_stage2_output(input_filepath):
    with open(input_filepath, 'rb') as stage2_file:
        rows = pickle.load(stage2_file)
        geo_images = pickle.load(stage2_file)
    return rows, geo_images

def unpickle_stage3_output(input_filepath):
    with open(input_filepath, 'rb') as stage3_file:
        rows = pickle.load(stage3_file)
    return rows

def unpickle_stage4_output(input_filepath):
    with open(input_filepath, 'rb') as stage4_file:
        rows = pickle.load(stage4_file)
    return rows

def debug_draw_plants_in_images(geo_images, possible_plants, actual_plants, out_directory):
    
    # Write images out to subdirectory to keep separated from pickled results.
    image_out_directory = os.path.join(out_directory, 'images/')
    if not os.path.exists(image_out_directory):
        os.makedirs(image_out_directory)
        
    print "Writing out debug images"
        
    # Limit the max number of images to keep from overfilling memory.
    set_num = 0
    set_increment = 20
    while set_num < len(geo_images):
        debug_geo_images = copy.copy(geo_images[set_num : set_num + set_increment])
        debug_draw_plants_in_images_subset(debug_geo_images, possible_plants, actual_plants, image_out_directory)
        set_num += set_increment
        sys.stdout.write('.')

def debug_draw_plants_in_images_subset(debug_geo_images, possible_plants, actual_plants, image_out_directory):
    
    debug_images = []
    DebugImage = namedtuple('DebugImage', 'image existed')
    for geo_image in debug_geo_images:
        if hasattr(geo_image, 'debug_filepath'):
            path = geo_image.debug_filepath
            already_existed = True
        else:
            path = geo_image.file_path
            already_existed = False
        debug_images.append(DebugImage(cv2.imread(path, cv2.CV_LOAD_IMAGE_COLOR, already_existed)))
    for item in possible_plants:
        from random import randint
        item_color = (randint(0, 255), randint(0, 100), randint(0, 255))
        for k, geo_image in enumerate(debug_geo_images):
            for ext_item in [item] + item.get('items',[]):
                image_rect = rect_to_image(ext_item['rect'], geo_image)
                draw_rect(debug_images[k].image, image_rect, item_color, thickness=2)
            
    for plant in actual_plants:
        for ref in plant.all_refs:
            if not ref.parent_image_filename:
                continue
            geo_image_filenames = [geo_image.file_name for geo_image in debug_geo_images]
            try:
                debug_img_index = geo_image_filenames.index(ref.parent_image_filename)
            except ValueError:
                continue
            debug_img = debug_images[debug_img_index].image
            draw_rect(debug_img, ref.bounding_rect, (0, 255, 0), thickness=4)
            
    debug_filepaths = [os.path.join(image_out_directory, postfix_filename(geo_image.file_name, 'marked')) for geo_image in debug_geo_images]
    for k, (debug_image, filepath) in enumerate(zip(debug_images, debug_filepaths)):
        if not debug_image.existed:
            debug_image.image = cv2.resize(debug_image.image, (0,0), fx=0.25, fy=0.25) 
        cv2.imwrite(filepath, debug_image.image)
        debug_geo_images[k].debug_filepath = filepath