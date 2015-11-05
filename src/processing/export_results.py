#! /usr/bin/env python

import os
import csv
 
def export_results(items, rows, out_filepath):
    '''Write all items to results file.'''
    with open(out_filepath, 'wb') as out_file:
        writer = csv.writer(out_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Write out header
        writer.writerow([
                        'item_type',
                        'unique_id',
                        'alternate_id',
                        'code_data',
                        'planting_direction',
                        'row',
                        'range',
                        'num_in_field',
                        'num_in_row',
                        'easting',
                        'northing',
                        'altitude',
                        'zone',
                        'cropped_image_file_name',
                        'parent_image_file_name',
                        'bound_x_pix',
                        'bound_y_pix',
                        'bound_width_pix',
                        'bound_height_pix',
                        'bound_rotation,'
                        ])

        for item in items:
            
            has_group = hasattr(item, 'group') and item.group is not None
            
            unique_id = ''
            alternate_id = ''
            if has_group:
                unique_id = item.group.id
                alternate_id = item.group.alternate_id
                
            code_data = ''
            if 'code' in item.type.lower():
                code_data = item.name 

            # TODO cleanup
            #if hasattr(item, 'row_number'):
            #    item.row = item.row_number

            # Row properties
            row_direction = 'N/A'
            row = [row for row in rows if row.number == item.row]
            if len(row) > 0:
                row_direction = row[0].direction
                
            bound_x_pix = -1
            bound_y_pix = -1
            bound_width_pix = -1
            bound_height_pix = -1
            bound_rotation = -1
            if item.bounding_rect:
                center, dim, theta = item.bounding_rect
                bound_x_pix, bound_y_pix = center
                bound_width_pix, bound_height_pix = dim
                bound_rotation = theta
                
            writer.writerow([
                           item.type,
                           unique_id,
                           alternate_id,
                           code_data,
                           row_direction,
                           item.row,
                           item.range,
                           item.number_within_field,
                           item.number_within_row,
                           item.position[0],
                           item.position[1],
                           item.position[2],
                           item.zone,
                           os.path.splitext(os.path.split(item.image_path)[1])[0],
                           os.path.splitext(item.parent_image_filename)[0],
                           bound_x_pix,
                           bound_y_pix,
                           bound_width_pix,
                           bound_height_pix,
                           bound_rotation
                           ])

    return out_filepath

def export_group_segments(segments, out_filepath):
    '''Write all groups to results file.'''
    with open(out_filepath, 'wb') as out_file:
        writer = csv.writer(out_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Write out header
        writer.writerow([
                        'group_id',
                        'start_code_data',
                        'end_code_data',
                        'expected_num_items',
                        'actual_num_items',
                        'segment_length',
                        'next_segment_start_code_data'
                        ])

        for seg in segments:
            
            group_id = seg.group.id if seg.group else -1
            
            next_segment_code_data = ''
            if seg.next_segment:
                next_segment_code_data = seg.next_segment.start_code.name
            
            writer.writerow([
                             group_id,
                             seg.start_code.name,
                             seg.end_code.name,
                             seg.expected_num_plants,
                             len(seg.items),
                             seg.length,
                             next_segment_code_data
                            ])

    return out_filepath