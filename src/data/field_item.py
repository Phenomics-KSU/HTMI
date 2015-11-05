#!/usr/bin/env python

import numpy as np


class FieldItem(object):
    '''Item found within image'''
    def __init__(self, name, position=(0,0,0), field_position=(0,0,0), zone='N/A', size=(0,0), area=0, row=0, range_grid=0,
                  image_path='', parent_image_filename='', bounding_rect=None, number_within_field=0, number_within_row=0):
        '''Constructor.'''
        self.name = name # identifier 
        self._position = position # 3D position of item in either local ENU frame or UTM
        self._field_position = field_position # 3D position relative to first field item. axes are in direction of row, range, altitude.
        self.zone = zone # UTM zone (e.g. 14S). Should be '--' if not being used.
        self._row = row # The row the item is found in. First row is #1.  If zero or negative then doesn't belong to a row.
        self._range = range_grid # The range the item is found in.  If row is the 'x' value then the range is the 'y' value and the units are dimensionless.
        self._number_within_field = number_within_field # Number of item within entire field.  
        self._number_within_row = number_within_row # Number of item within current row.  Measured from range = 0 side of field.
        self._other_items = [] # same field item from different images.
        
        # Image properties.  May be empty/None if item wasn't found in image.
        self.image_path = image_path # Full path where cropped out image of field item is found.
        self.parent_image_filename = parent_image_filename  # Filename of image where field item was found. Don't store ref since we'll run out of memory.
        self.bounding_rect = bounding_rect # OpenCV minimum rotated bounding rectangle containing item. Units in pixels. No pad added in.
        
    @property
    def other_items(self):
        return self._other_items
    
    @property
    def all_refs(self):
        return [self] + self._other_items
        
    @other_items.setter
    def add_other_item(self, other_item):
        if other_item is self:
            raise ValueError("Can't add self as reference.")
        if other_item.type != self.type:
            raise ValueError("Can't add reference to different type.")
        self.other_items.append(other_item)
        
    @property
    def position(self):
        return np.mean([self._position] + [ref.position for ref in self.other_items], axis=0)
        
    @position.setter
    def position(self, new_value):
        self._position = new_value
        
    @property
    def field_position(self):
        return np.mean([self._field_position] + [ref.field_position for ref in self.other_items], axis=0)
        
    @field_position.setter
    def field_position(self, new_value):
        self._field_position = new_value
        
    @property
    def row(self):
        return self._row
    
    @row.setter
    def row(self, new_value):
        self._row = new_value
        for item in self.other_items:
            item.row = new_value
            
    @property
    def range(self):
        return self._range
    
    @range.setter
    def range(self, new_value):
        self._range = new_value
        for item in self.other_items:
            item.range = new_value
            
    @property
    def number_within_field(self):
        return self._number_within_field
    
    @number_within_field.setter
    def number_within_field(self, new_value):
        self._number_within_field = new_value
        for item in self.other_items:
            item.number_within_field = new_value
            
    @property
    def number_within_row(self):
        return self._number_within_row
    
    @number_within_row.setter
    def number_within_row(self, new_value):
        self._number_within_row = new_value
        for item in self.other_items:
            item.number_within_row = new_value

    @property
    def type(self):
        '''Return type of item (ie plant, code, gap, etc). No need for subclass to override this, it will return name of child class already.'''
        return self.__class__.__name__
        
class GroupItem(FieldItem):
    '''Field item that belongs to grouping.'''
    def __init__(self, *args, **kwargs):
        '''Constructor.'''
        super(GroupItem, self).__init__(*args, **kwargs)
        self._group = None
        
    @property
    def group(self):
        return self._group
    
    @group.setter
    def group(self, new_value):
        self._group = new_value
        for item in self.other_items:
            item.group = new_value
        
    @property
    def number_within_segment(self):
        '''Return index number within grouping or -1 if not in a group.'''
        try:
            return self.group.items.index(self)
        except (AttributeError, ValueError):
            return -1
    
class Plant(GroupItem):
    '''Unique plant in field'''
    def __init__(self, *args, **kwargs):
        '''Constructor.'''
        super(Plant, self).__init__(*args, **kwargs)
        
class Gap(GroupItem):
    '''Gap detected within grouping.'''
    def __init__(self, *args, **kwargs):
        '''Constructor.'''
        super(Gap, self).__init__(*args, **kwargs)
        
class GroupCode(GroupItem):
    '''Code found within image corresponding to plant grouping.'''
    def __init__(self, *args, **kwargs):
        '''Constructor.'''
        super(GroupCode, self).__init__(*args, **kwargs)
        
        # Optional different ID that main ID maps to.  
        # Allows for multiple IDs to map to the same alternate ID.
        self.alternate_id = self.name
    
    @property
    def id(self):
        return self.name
        
    @property
    def alternate_id(self):
        return self._alternate_id
    
    @alternate_id.setter
    def alternate_id(self, new_value):
        self._alternate_id = new_value
        for item in self.other_items:
            item.alternate_id = new_value
    
class SingleCode(FieldItem):
    '''Code found within image corresponding to a single plant.'''
    def __init__(self, *args, **kwargs):
        '''Constructor.'''
        super(SingleCode, self).__init__(*args, **kwargs)
    
    @property
    def id(self):
        return self.name

class RowCode(FieldItem):
    '''Code found within image corresponding to a row start/end.'''
    def __init__(self, *args, **kwargs):
        '''Constructor.'''
        super(RowCode, self).__init__(*args, **kwargs)
        
        self.assigned_row = -1 # overrides row number assign from code name

    @FieldItem.row.getter
    def row(self):
        return self.assigned_row if self.assigned_row >= 0 else self._row
