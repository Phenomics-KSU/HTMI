#! /usr/bin/env python

import sys
import os
import argparse
import time
import itertools

if __name__ == '__main__':
    '''Rename contents of directories with their owning directory name as a prefix'''

    default_recursive = 'true'
    parser = argparse.ArgumentParser(description='Rename contents of directories with their owning directory name as a prefix')
    parser.add_argument('directory', help='Parent directory to iterate through.')
    parser.add_argument('-r', dest='recursive', default=default_recursive, help='If true then will recursively search through input directory. Default {}'.format(default_recursive))
    args = parser.parse_args()
    
    # Convert command line arguments
    input_directory = args.directory
    recursive = args.recursive.lower() == 'true'

    if not os.path.exists(input_directory):
        print "Directory does not exist: {}".format(input_directory)
        sys.exit(1)
        
    for (dirpath, dirnames, filenames) in os.walk(input_directory):
        for filename in filenames:
            file_dir_name =  os.path.basename(dirpath)
            new_filename = file_dir_name + "_" + filename
            new_filepath = os.path.join(dirpath, new_filename)
            original_filepath = os.path.join(dirpath, filename)
            os.rename(original_filepath, new_filepath)
        if not recursive:
            break # only walk top level directory
 