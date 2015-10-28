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

        filepath = os.path.join(ImageWriter.output_directory, filename)
        if not os.path.exists(os.path.dirname(filepath)):
            os.makedirs(os.path.dirname(filepath))
            
        cv2.imwrite(filepath, image)
        
        return filepath
