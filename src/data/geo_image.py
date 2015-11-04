#!/usr/bin/env python

class GeoImage(object):
    '''Image properties with X,Y,Z position and heading. All distances in centimeters.'''
    def __init__(self, file_name, image_time=0, position=(0,0,0), zone='N/A', heading_degrees=0, 
                 resolution=0, camera_rotation_degrees=0, size=(0,0)):
        '''Constructor.'''
        self.file_name = file_name # name of image file with extension (not full path).
        self.image_time = image_time # UTC time when image was taken.
        self.position = position # 3D position of camera in either local ENU frame or UTM when the image was taken.
        self.zone = zone # UTM zone (e.g. 14S). Should be '--' if not being used.
        self.heading_degrees = heading_degrees # heading of image with 0 degrees being East and increasing CCW.
        self.resolution = resolution # resolution (cm/pix) that user specified.
        self.camera_rotation_degrees = camera_rotation_degrees # 0 degrees camera top forward. Increase CCW.
        self.width = size[0] # image width in pixels.
        self.height = size[1] # image height in pixels.
        
        # 3D positions of image corners.
        self.top_left_position = (0,0,0) 
        self.top_right_position = (0,0,0) 
        self.bottom_right_position = (0,0,0)
        self.bottom_left_position = (0,0,0)
        
    @property
    def size(self):
        '''Return image size in pixels.'''
        return (self.width, self.height)
        