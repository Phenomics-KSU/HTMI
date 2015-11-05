#! /usr/bin/env python

import argparse
import os

# Project imports
from src.util.grouping import *
from src.util.stage_io import unpickle_stage1_output, pickle_results, write_args_to_file
from src.processing.item_processing import merge_items
from src.stages.exit_reason import ExitReason

def stage2_grouping(**args):
    ''' 
    Group codes into rows.
    args should match the names and descriptions of command line parameters,
    but unlike command line, all arguments must be present.
    '''
    # Copy args so we can archive them to a file when function is finished.
    args_copy = args.copy()
    
    # Convert arguments to local variables of the correct type.
    input_directory = args.pop('input_directory')
    field_direction = float(args.pop('field_direction'))
    output_directory = args.pop('output_directory')
    row_labeling_scheme = int(args.pop('row_labeling_scheme'))
    
    if len(args) > 0:
        print "Unexpected arguments provided: {}".format(args)
        return ExitReason.bad_arguments
    
    geo_images, all_codes = unpickle_stage1_output(input_directory)
    
    # TODO REMOVE
    for c in all_codes:
        c.assigned_row = -1

    print 'Found {} codes in {} geo images.'.format(len(all_codes), len(geo_images))

    if len(geo_images) == 0 or len(all_codes) == 0:
        print "Couldn't load any geo images or codes from input directory {}".format(input_directory)
        return ExitReason.no_geo_images

    # Merge items so they're unique.  One code references other instances of that same code.
    merged_codes = merge_items(all_codes, max_distance=500)

    print '{} unique codes.'.format(len(merged_codes))
                
    row_codes = [code for code in merged_codes if code.type.lower() == 'rowcode']
    group_codes = [code for code in merged_codes if code.type.lower() == 'groupcode']
    single_codes = [code for code in merged_codes if code.type.lower() == 'singlecode']

    #associate_ids_to_entry_rep(group_codes)
        
    if row_labeling_scheme == 0:
        
        grouped_row_codes = group_row_codes(row_codes)
    
        if len(grouped_row_codes) == 0:
            print "No row codes found. Exiting"
            return ExitReason.no_rows
    
        display_row_info(grouped_row_codes)
            
        rows = create_rows(grouped_row_codes, field_direction)
        
        up_row_nums, back_row_nums = associate_row_numbers_with_up_back_rows()
        
        assign_rows_a_direction(rows, up_row_nums, back_row_nums)
        
        field_passes = [rows[x:x+2] for x in xrange(0, len(rows), 2)]
        
    elif row_labeling_scheme == 1:
        
        grouped_row_codes = group_row_codes_by_pass_name(row_codes)
        
        rows, field_passes = create_rows_and_field_passes_by_pass_codes(grouped_row_codes, field_direction)
        
    else:
        print "Invalid row lobeling scheme."
        return ExitReason.bad_arguments
    
    if len(rows) == 0:
        print "No complete rows found.  Exiting."
        return ExitReason.no_rows
    
    print [r.number for r in rows]
    
    codes_with_projections = calculate_projection_to_nearest_row(group_codes + single_codes, rows)
            
    group_segments, special_segments = create_segments(codes_with_projections, rows)
        
    # Go through and organize segments.
    start_segments, middle_segments, end_segments, single_segments = organize_group_segments(group_segments)
    
    if len(middle_segments) > 0:
        print "Middle segments that span entire row aren't supported right now. Exiting"
        return ExitReason.operation_not_supported
    
    groups = complete_groups(end_segments, single_segments, field_passes)
        
    handle_single_segments(single_segments, groups)
        
    display_segment_info(group_segments, special_segments, groups)
    
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
 
    dump_filename = "stage2_rows_{}_{}.s2".format(int(geo_images[0].image_time), int(geo_images[-1].image_time))
    print "Serializing {} rows to {}.".format(len(rows), dump_filename)
    pickle_results(dump_filename, output_directory, rows)
    
    # Write arguments out to file for archiving purposes.
    args_filename = "stage2_args_{}_{}.csv".format(int(geo_images[0].image_time), int(geo_images[-1].image_time))
    write_args_to_file(args_filename, output_directory, args_copy)
    
if __name__ == '__main__':
    '''Group codes into rows/groups/segments.'''

    parser = argparse.ArgumentParser(description='''Group codes into rows/groups/segments.''')
    parser.add_argument('input_directory', help='directory containing pickled files from previous stage.')
    parser.add_argument('field_direction', help='Planting angle of entire field.  0 degrees East and increases CCW.')
    parser.add_argument('output_directory', help='where to write output files')
    parser.add_argument('row_labeling_scheme', help='if 0 then uses simple row number, if 1 then uses pass numbering with St/En and L/R in row codes')
    
    args = vars(parser.parse_args())
    
    exit_code = stage2_grouping(**args)
    
    if exit_code == ExitReason.bad_arguments:
        print "\nSee --help for argument descriptions."
    
    sys.exit(exit_code)