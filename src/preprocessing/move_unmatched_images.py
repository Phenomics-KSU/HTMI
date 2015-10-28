#! /usr/bin/env python

import sys
import os
import argparse
import time
import itertools

if __name__ == '__main__':
    '''Match move any images that don't have a log entry to a an 'unmatched directory.'''

    default_recursive = 'true'
    parser = argparse.ArgumentParser(description='Match move any images that dont have a log entry to a an unmatched directory')
    parser.add_argument('image_directory', help='Directory containing image files.')
    parser.add_argument('image_logs', help='Space separated list of log filepaths containing file names to match to actual images.')
    parser.add_argument('extensions', help='List of file extensions to rename separated by commas. Example "jpg, CR2". Case sensitive.')
    parser.add_argument('-r', dest='recursive', default=default_recursive, help='If true then will recursively search through input directory for images. Default {}'.format(default_recursive))
    args = parser.parse_args()
    
    # Convert command line arguments
    image_directory = args.image_directory
    image_logs = [log_path.strip() for log_path in args.image_logs.split(',')]
    extensions = args.extensions.split(',')
    recursive = args.recursive.lower() == 'true'
    
    if not os.path.exists(image_directory):
        print "Directory does not exist: {}".format(image_directory)
        sys.exit(1)
        
    filesystem_image_names = []
    for (dirpath, dirnames, filenames) in os.walk(image_directory):
        for filename in filenames:
            # Make sure file has correct extension before adding it.
            just_filename, extension = os.path.splitext(filename)
            if extension[1:] in extensions:
                filesystem_image_names.append((dirpath, filename))
        if not recursive:
            break # only walk top level directory
        
    if len(filesystem_image_names) == 0:
        print "No images with extensions {} from directory {} could be read in.".format(extensions, image_directory)
        sys.exit(1)
        
    print "Read in {} images from image directory.".format(len(filesystem_image_names))

    # Read in input file.
    log_contents = []
    for image_log in image_logs:
        with open(image_log, 'r') as input_file:
            for line in input_file.readlines():
                if line.strip().startswith('#'):
                    continue # comment line
                items = [i.strip() for i in line.split(',')]
                utc_time = float(items[0])
                image_filename = items[1]
                log_contents.append((utc_time, image_filename))
            
    print "Read in {} time stamped image names from image log.".format(len(log_contents))

    output_directory = os.path.join(image_directory, 'unmatched')
    
    if not os.path.exists(output_directory):
        os.mkdir(output_directory)

    number_moved = 0
    for filesystem_dir, filesystem_image_name in filesystem_image_names:

            filesystem_image_just_filename, filesystem_image_extension = os.path.splitext(filesystem_image_name)

            found_match = False
            for log_line in log_contents:

                utc_time = log_line[0]
                original_filename = log_line[1]
                just_filename, extension = os.path.splitext(original_filename)
                
                if just_filename == filesystem_image_just_filename:
                    found_match = True
                    break
                
            if not found_match:
                # Move file to new directory since it's unmatched
                new_filepath = os.path.join(output_directory, filesystem_image_name)
                try:
                    filepath = os.path.join(filesystem_dir, filesystem_image_name)
                    os.rename(filepath, new_filepath)
                    number_moved += 1
                except WindowsError as e:
                    print "Failed to rename\n{} to\n{}\n{}".format(filepath, new_filepath, e)
          
    print "Moved {} images to new directory.".format(number_moved)
