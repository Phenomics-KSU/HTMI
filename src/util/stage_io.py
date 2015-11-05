#! /usr/bin/env python

import os
import sys
import pickle
import csv
import datetime

# Project imports
from src.util.image_utils import make_filename_unique

def pickle_results(filename, out_directory, *args):
    
    filename = make_filename_unique(out_directory, filename)
    filepath = os.path.join(out_directory, filename)
    sys.setrecursionlimit(10000)
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
