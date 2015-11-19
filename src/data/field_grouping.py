#!/usr/bin/env python

from math import sqrt, atan2

class Row(object):
    '''Collection of items in field row.'''
    def __init__(self, start_code=None, end_code=None, direction=None, segments=None):
        # Start and end codes are defined to be in the direction of the entire field... not the individual row.
        self.start_code = start_code # code on the side of the field where range = 0
        self.end_code = end_code # code on the other side of the field.
        self.direction = direction # Either 'up' if the in same direction as field or 'back' if row runs opposite direction.
        self.segments = segments # Segments in row in order of direction (up or back)
        if self.segments is None:
            self.segments = []
    
    @property
    def number(self):
        '''Return row number using start code.'''
        return self.start_code.row
    
    @property
    def angle(self):
        '''Return angle of row (from start to end code) in radians where 0 deg is east and 90 deg is north.'''
        dx = self.end_code.position[0] - self.start_code.position[0]
        dy = self.end_code.position[1] - self.start_code.position[1]
        return atan2(dy, dx)
    
    @property
    def group_segments(self):
        '''Return list of segments in row that have plants between codes.'''
        return [s for s in self.segments if not s.is_special]

    @property
    def special_segments(self):
        '''Return list of segments in row that just have a single plant right next to start code.'''
        return [s for s in self.segments if s.is_special]
    
    @property
    def center_field_position(self):
        avg_x = (self.start_code.field_position[0] + self.end_code.field_position[0]) / 2.0
        avg_y = (self.start_code.field_position[1] + self.end_code.field_position[1]) / 2.0
        avg_z = (self.start_code.field_position[2] + self.end_code.field_position[2]) / 2.0
        return (avg_x, avg_y, avg_z)
    
class PlantGroupSegment(object):
    '''Part of a plant grouping. Hit end of row before entire grouping could be planted.'''
    def __init__(self, start_code, end_code, items=None):
        '''Constructor.'''
        self._items = items # items found in segment not counting start or end QR code.
        if self._items is None:
            self._items = []
        self.geo_images = [] # list of geo images that are in (or close enough to) segment.
        self._group = None # group that segment belongs to.
        self.start_code = start_code # QR code to start segment. Could either be Row, Group or Single Code depending on if segment is starting or ending.
        self.end_code = end_code # QR code that ends segment. Could either be Row, Group or Single Code depending on if segment is starting or ending.
        self.expected_num_plants = -1 # how many plants should be in segment. negative if not sure.
        self.num_plants_was_measured = False # set to true if expected num plants was directly measured in field.

    def update_group(self, new_group):
        '''Update the grouping that this segment belongs to and update the reference of all the items stored in the segment.'''
        self._group = new_group
        self.start_code.group = new_group
        for item in self._items:
            item.group = new_group
    
    def add_item(self, item):
        '''Add item to list of items and updates item reference. Raise ValueError if item is None.'''
        if item is None:
            raise ValueError('Cannot add None item to item group.')
        self._items.append(item)
        item.group = self._group
        
    @property
    def items(self):
        return self._items
    
    @property
    def group(self):
        return self._group
            
    @property
    def next_segment(self):
        '''If segment has a next segment then return it.'''
        if self.group:
            i = self.group.segments.index(self)
            if i >= 0 and i < (len(self.group.segments) - 1):
                return self.group.segments[i + 1]
        return None
    
    @property
    def row_number(self):
        return self.start_code.row
    
    @property
    def length(self):
        '''Return distance between start and end code in centimeters.'''
        if self.start_code is None or self.end_code is None:
            return 0
        delta_x = self.start_code.position[0] - self.end_code.position[0]
        delta_y = self.start_code.position[1] - self.end_code.position[1]
        return sqrt(delta_x*delta_x + delta_y*delta_y)
    
    @property
    def is_special(self):
        '''Return true if start of segment corresponds to SingleCode.'''
        return self.start_code.type.lower() == 'singlecode'
        
class PlantGroup(object):
    '''Complete plant grouping made of 1 or more segments that span multiple rows.'''
    def __init__(self):
        '''Constructor.'''
        self.segments = []
        self.expected_num_plants = -1 # how many plants should be in group. negative if not sure.

    def add_segment(self, segment):
        segment.update_group(self)
        self.segments.append(segment)

    @property
    def start_code(self):
        return self.segments[0].start_code
    @property
    def id(self):
        return self.start_code.id
    @property
    def alternate_id(self):
        return self.start_code.alternate_id
    @property
    def length(self):
        '''Return distance of all segments in centimeters.'''
        length = 0
        for segment in self.segments:
            length += segment.length
        return length
