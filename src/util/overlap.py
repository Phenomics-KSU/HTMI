#! /usr/bin/env python

def is_overlapping_segment(image_lrud, segment):
    
    left, right, up, down = image_lrud

    seg_left, seg_right, seg_up, seg_down = segment.lrud

    return up > seg_down and down < seg_up and right > seg_left and left < seg_right
    
def calculate_image_lrud(geo_image):

    left = min(geo_image.top_left_field_position[0], geo_image.top_right_field_position[0],
               geo_image.bottom_left_field_position[0], geo_image.bottom_right_field_position[0])
    right = max(geo_image.top_left_field_position[0], geo_image.top_right_field_position[0],
               geo_image.bottom_left_field_position[0], geo_image.bottom_right_field_position[0])
    up = max(geo_image.top_left_field_position[1], geo_image.top_right_field_position[1],
                geo_image.bottom_left_field_position[1], geo_image.bottom_right_field_position[1])
    down = min(geo_image.top_left_field_position[1], geo_image.top_right_field_position[1],
                geo_image.bottom_left_field_position[1], geo_image.bottom_right_field_position[1])
    return (left, right, up, down)

def calculate_segment_lrud(segment, pad):
    
    p1 = segment.start_code.field_position
    p2 = segment.end_code.field_position
    
    left = min(p1[0], p2[0]) - pad
    right = max(p1[0], p2[0]) + pad
    up = max(p1[1], p2[1]) + pad
    down = min(p1[1], p2[1]) - pad
        
    return (left, right, up, down)

def calculate_special_segment_lrud(segment, pad):
    
    p1 = segment.start_code.field_position

    # segment is centered on start code
    left = p1[0] - pad
    right = p1[0] + pad
    up = p1[1] + pad
    down = p1[1] - pad
        
    return (left, right, up, down)