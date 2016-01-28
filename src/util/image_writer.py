#! /usr/bin/env python

import os
import cv2

class ImageWriter(object):
    '''Facilitate writing output images to an output directory.'''
    DEBUG = 0
    NORMAL = 1
    
    level = DEBUG
    output_directory = './'

    @staticmethod
    def save_debug(filename, image):
        return ImageWriter.save(filename, image, ImageWriter.DEBUG)

    @staticmethod
    def save_normal(filename, image):
        return ImageWriter.save(filename, image, ImageWriter.NORMAL)

    @staticmethod
    def save(filename, image, level):
        '''Save image if the specified level is above current output level.'''
        if level < ImageWriter.level:
            return
        
        if not os.path.exists(ImageWriter.output_directory):
            os.makedirs(ImageWriter.output_directory)
        
        unique_filename = ImageWriter.make_filename_unique(ImageWriter.output_directory, filename)

        filepath = os.path.join(ImageWriter.output_directory, unique_filename)
            
        cv2.imwrite(filepath, image)
        
        return filepath
    
    @staticmethod
    def make_filename_unique(directory, fname):
        
        fname_no_ext, ext = os.path.splitext(fname)
        original_fname = fname_no_ext
        dir_contents = os.listdir(directory)
        dir_fnames = [os.path.splitext(c)[0] for c in dir_contents]
        
        while fname_no_ext in dir_fnames:
            
            try:
                v = fname_no_ext.split('_')
                i = int(v[-1])
                i += 1
                fname_no_ext = '_'.join(v[:-1] + [str(i)])
            except ValueError:
                fname_no_ext = '{}_{}'.format(original_fname, 1)
    
        return fname_no_ext + ext