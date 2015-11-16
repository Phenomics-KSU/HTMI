#! /usr/bin/env python

def is_overlapping_segment(image_ewns, segment):
    
    e, w, n, s = image_ewns

    seg_e, seg_w, seg_n, seg_s = segment.ewns

    return n > seg_s and s < seg_n and e > seg_w and w < seg_e
    
def calculate_image_ewns(geo_image):

    east = max(geo_image.top_left_position[0], geo_image.top_right_position[0],
               geo_image.bottom_left_position[0], geo_image.bottom_right_position[0])
    west = min(geo_image.top_left_position[0], geo_image.top_right_position[0],
               geo_image.bottom_left_position[0], geo_image.bottom_right_position[0])
    north = max(geo_image.top_left_position[1], geo_image.top_right_position[1],
                geo_image.bottom_left_position[1], geo_image.bottom_right_position[1])
    south = min(geo_image.top_left_position[1], geo_image.top_right_position[1],
                geo_image.bottom_left_position[1], geo_image.bottom_right_position[1])
    return (east, west, north, south)

def calculate_segment_ewns(segment, pad):
    
    p1 = segment.start_code.position
    p2 = segment.end_code.position
    
    east = max(p1[0], p2[0]) + pad
    west = min(p1[0], p2[0]) - pad
    north = max(p1[1], p2[1]) + pad
    south = min(p1[1], p2[1]) - pad
        
    return (east, west, north, south)

def calculate_special_segment_ewns(segment, pad):
    
    p1 = segment.start_code.position

    # segment is centered on start code
    east = p1[0] + pad
    west = p1[0] - pad
    north = p1[1] + pad
    south = p1[1] - pad
        
    return (east, west, north, south)