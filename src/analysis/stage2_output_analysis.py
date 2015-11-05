#! /usr/bin/env python

import sys
import os
import argparse
import pickle
import itertools
import copy
from collections import Counter
from collections import defaultdict

# Project imports
from src.util.image_utils import list_images, index_containing_substring, verify_geo_images, make_filename_unique
from src.util.image_writer import ImageWriter
from src.util.parsing import parse_grouping_file
from src.extraction.code_finder import CodeFinder
from src.processing.item_processing import process_geo_image, merge_items
from src.stages.exit_reason import ExitReason
    

def make_grouping_info_unique(grouping_info):
    # Warn if there are duplicate groups in info file.
    unique_grouping_info_dict = defaultdict(list)
    unique_grouping_info_list = []
    for info in grouping_info:
        unique_grouping_info_dict[info[0]].append(info)
    for id, infos in unique_grouping_info_dict.iteritems():
        if len(infos) > 2:
            print "More than 2 entries with id {}".format(id)
        elif len(infos) == 2:
            if infos[0][:-1] == infos[1][:-1]:
                print "Duplicate entries with id {}".format(id)
            else:
                print "Two different entries with id {}".format(id)
                print infos
            unique_grouping_info_list.append(infos[0])
        else: # just one unique info listing
            unique_grouping_info_list.append(infos[0])
    return unique_grouping_info_list
                

def add_in_none_codes(updated_none_items, grouping_info):

    # codes that were missing from expected grouping file
    for none_item in updated_none_items:
        # TODO make grouping info a class. This needs to stay in sync with actual parsing of grouping file.
        order_entered = -1 # don't know it wasn't in file
        qr_id = none_item[0] # same as name
        flag = none_item[3]
        entry = flag[:-1]
        rep = flag[-1].upper()
        try:
            # use actual number of plant since we don't know estimated.
            actual_num_plants = int(none_item[2])
            estimated_num_plants = actual_num_plants
        except ValueError:
            estimated_num_plants = -1
        grouping_info.append((qr_id, entry, rep, estimated_num_plants, order_entered))

def add_in_missing_codes(updated_missing_items, all_codes):

    # codes that weren't originally found
    for missing_item_info in updated_missing_items:
        missing_name = missing_item_info[4]
        missing_flag =  missing_item_info[5]
        missing_position = missing_item_info[6]

        # TODO once have position then add to list
        if 'R.' in missing_flag:
            all_codes.append(RowCode(missing_name, position=missing_position))
        else: # group code
            group_code = GroupCode(missing_name, position=missing_position)
            group_code.entry = missing_flag[:-1]
            group_code.rep = missing_flag[-1].upper()
            all_codes.append(group_code)
            
def check_code_precision(merged_codes):
    # Sanity check that multiple references of the same code are all close to each other.
    largest_separation = 0
    sum_separation = 0
    sum_separation_count = 0
    for code in merged_codes:
        avg_position = average_position(code)
        code_refs = [code] + code.other_items
        for code_ref in code_refs:
            diff = position_difference(avg_position, code_ref.position)
            sum_separation += diff
            sum_separation_count += 1
            if diff > largest_separation:
                largest_separation = diff
            
        #code_combos = itertools.combinations([code] + code.other_items, 2)
        #for (code1, code2) in code_combos:
        #    separation = position_difference(code1.position, code2.position)
        #    if separation > largest_separation:
        #        largest_separation = separation
                
    average_separation = 0
    if sum_separation_count > 0:
        average_separation = sum_separation / sum_separation_count
                
    print "From average position largest separation is {} and average is {}".format(largest_separation, average_separation)

def warn_about_missing_and_extra_codes(missing_code_ids, extra_code_ids):
    print "Missing {} ids.".format(len(missing_code_ids))
    if len(missing_code_ids) < 30:
        for id in missing_code_ids:
            print "missing id: {}".format(id)
            
    if len(extra_code_ids) > 0:
        print "WARNING: Found {} group codes that aren't listed in expected grouping file.".format(len(extra_code_ids))
        for id in extra_code_ids:
            print "Extra ID: {}".format(id)

def display_row_info(grouped_row_codes):
    # Show user information about which rows were found and which are missing.
    sorted_row_numbers = sorted(grouped_row_codes.keys())
    smallest_row_number = sorted_row_numbers[0]
    biggest_row_number = sorted_row_numbers[-1]
    print "Found rows from {} to {}".format(smallest_row_number, biggest_row_number)
    missing_row_numbers = set(range(smallest_row_number, biggest_row_number+1)) - set(sorted_row_numbers)
    if len(missing_row_numbers) > 0:
        print "Missing row numbers {}".format(missing_row_numbers)
    else:
        print "No skipped row numbers."

def verify_up_back_row_numbers(up_row_nums, back_row_nums):

    overlap = list(set(up_row_nums) & set(back_row_nums))
    if len(overlap) > 0:
        print "Bad row generation.  Overlapping between up and back: "
        print overlap
        sys.exit(1)
    
    if back_row_nums[-1] != 58:
        print "Bad row generation.  Last row should be back and number 58"
        sys.exit(1) 
        
    if 22 not in up_row_nums or 23 not in up_row_nums:
        print "Bad row generation.  Back rows should have number 22"
        sys.exit(1) 

def order_and_number_items_by_row(rows):
    '''JUST HERE FOR FINDING MISSING CODES'''
    rows = sorted(rows, key=lambda r: r.number)
    #missing_code_ids = sorted(missing_code_ids, key=lambda r: int(r))
    
    current_field_item_num = 1
    ordered_items = []
    for row in rows:
        row_items = []
        for i, segment in enumerate(row.group_segments):
            row_items.append(segment.start_code)
            row_items += segment.items
            if i == len(row.segments) - 1:
                row_items.append(segment.end_code) # since on last segment it won't show up in next segment
                
        # Get everything going in the 'up' direction
        if row.direction == 'back':
            row_items.reverse()
        
        # Reverse items in even row numbers for serpentine ordering    
        #if row.number % 2 == 0:
        #    row_items.reverse()
            
        for item_num_in_row, item in enumerate(row_items):
            item.number_within_field = current_field_item_num
            item.number_within_row = item_num_in_row + 1 # index off 1 instead of 0
            ordered_items.append(item)
            current_field_item_num += 1
            
    return ordered_items

def warn_about_bad_group_lengths(groups):

    num_good_lengths = 0 # how many groups have a close expected length
    num_bad_lengths = 0 # how many groups don't have a close expected length
    num_no_info = 0 # how many groups don'have any expected lengths
    num_too_much_info = 0 # how many groups have more than 1 expected lengths
    for group in groups:
        info = [i for i in grouping_info if i[0] == group.id]
        if len(info) == 0:
            #print "no expected info for group found in field {}".format(group.id)
            num_no_info += 1
            group.expected_num_plants = -1
            continue
        if len(info) > 1:
            #print "too many matches for row {} found in plant info file.".format(group.id)
            num_too_much_info += 1
            group.expected_num_plants = -1
            continue
        info = info[0]
        expected_num_plants = info[3]
        group.expected_num_plants = expected_num_plants
        if len(group.segments) == 1:
            # TODO clean this ups
            group.segments[0].expected_num_plants = group.expected_num_plants
        spacing_between_plants = 0.9144 # meters
        spacing_for_codes = spacing_between_plants / 2.0
        expected_length = (expected_num_plants - 1) * spacing_between_plants
        expected_length += spacing_for_codes * 2 * len(group.segments) # for before and end codes for each segment
        actual_length = group.length

        max_length_difference = 5.0

        length_difference = actual_length - expected_length

        if abs(length_difference) > max_length_difference:
            #print "For group {} the actual length of {} is {} meters off from expected length {}.".format(group.id, actual_length, length_difference, expected_length)
            if length_difference > max_length_difference:
                print "Group with start code {} ({}{}) that is {} from the {} side of row {} is {} meters too long.".format(group.id,
                                                                                                                     group.entry,
                                                                                                                     group.rep,
                                                                                                                     group.start_code.number_within_row,
                                                                                                                     'south',
                                                                                                                     group.start_code.row, 
                                                                                                                     length_difference)
            num_bad_lengths += 1
        else:
            num_good_lengths += 1
    
    print "Found {} groups with close expected lengths and {} groups that aren't close.".format(num_good_lengths, num_bad_lengths)
    print "{} groups with no expected number of plants and {} with too many expected number number of plants.".format(num_no_info, num_too_much_info)

def display_missing_codes_neighbors(missing_code_ids):

    for missing_id in missing_code_ids:
        missing_id_info = [info for info in grouping_info if info[0] == missing_id][0]
        
        order_entered = missing_id_info[4]
        
        print "\nMissing id {} ({}{}) is entered {} in document".format(missing_id, missing_id_info[1], missing_id_info[2], order_entered)
  
        neighbor_info = [] 
        neighbors_order_entered = range(order_entered - 3, order_entered + 4, 1)
        for neighbor_order_entered in neighbors_order_entered:
            close_neighbor_info = [info for info in grouping_info if info[4] == neighbor_order_entered]
            neighbor_info.append(close_neighbor_info)
            '''
            if missing_id == '1525':
                print str(neighbor_order_entered)
                grouping_info = sorted(grouping_info, key=lambda k: k[4])
                for i in grouping_info:
                    print i
                sys.exit(1)
            '''

        for neighbor in neighbor_info:
            if len(neighbor) == 0:
                print "\tNo neighbor in document."
            else:
                neighbor = neighbor[0]
                neighbor_code = [code for code in group_codes if code.name == neighbor[0]]
                if len(neighbor_code) == 0:
                    print "\tNeighbor code with id {} not found in field.".format(neighbor[0])
                else:
                    neighbor_code = neighbor_code[0]
                    print "\tHas neighbor code {} ({}{}) that is {} code from {} side of row {}".format(neighbor_code.name,
                                                                                                                      neighbor_code.entry,
                                                                                                                      neighbor_code.rep,
                                                                                                                      neighbor_code.number_within_row,
                                                                                                                      'south',
                                                                                                                      neighbor_code.row)

def update_number_of_plants_in_groups(updated_all_items, group_segments):

    plant_spacings = [] # list of plant spacing for each group that was measured.
    
    num_fixed_segments_expected_plants = 0
    for updated_item_info in updated_all_items:
        item_name = updated_item_info[0]
        expected_plants = updated_item_info[1]
        actual_plants = updated_item_info[2]
        position = updated_item_info[6]
        
        try:
            actual_plants = int(actual_plants)
        except ValueError:
            continue
        
        segment = None
        matching_segments = [seg for seg in group_segments if seg.start_code.name == item_name]
        if len(matching_segments) >= 1:
            segment = matching_segments[0]
                    
        if (segment is not None) and ('R' not in item_name) and (actual_plants >= 0):
            segment.expected_num_plants = actual_plants 
            segment.num_plants_was_measured = True
            segment_length = segment.length
            if segment_length > 0:
                plant_spacings.append(segment_length / actual_plants)
            num_fixed_segments_expected_plants += 1

    print "{} segments updated with actual number of plants.".format(num_fixed_segments_expected_plants)
    
    # how many meters between plants.
    average_plant_spacing = 0
    if len(plant_spacings) > 0:
        print "Max plant spacing is {}".format(max(plant_spacings))
        plant_spacings = sorted(plant_spacings, key=lambda spacing: spacing)
        plant_spacings = plant_spacings[10:-10] 
        average_plant_spacing = np.sum(plant_spacings) / len(plant_spacings)
    
    print "\nAverage plant spacing is {}\n".format(average_plant_spacing)
    
    return average_plant_spacing

def fix_group_lengths_or_plant_count(group_segments, average_plant_spacing):
    
    if average_plant_spacing <= 0:
        return # don't have an estimate plant spacing to fix lengths with
    
    num_too_short_segments = 0
    num_too_long_segments = 0
    
    for segment in group_segments:
        
        if segment.length <= 0:
            print "Bad segment length!"
            continue
        
        if segment.num_plants_was_measured:
            continue # don't need to adjust it since we know exactly what it should be

        expected_segment_length = segment.expected_num_plants / average_plant_spacing
        
        length_difference = expected_segment_length - segment.length
        percent_difference = expected_segment_length / segment.length

        if percent_difference > 1.2:
            # Actual length is too short so scale down expected plants so that it matches plant spacing.
            scaled_down_number_of_plants = int(segment.length / average_plant_spacing)
            segment.expected_num_plants = scaled_down_number_of_plants
            num_too_short_segments += 1

        elif length_difference < -10:
            # TODO: Actual length is way longer so add in a temporary QR code to make spacing OK.
            scaled_up_number_of_plants = int(segment.length / average_plant_spacing)
            segment.expected_num_plants = scaled_up_number_of_plants
            num_too_long_segments += 1
            
    print "Corrected {} short segments and {} long segments.".format(num_too_short_segments, num_too_long_segments)

def update_number_of_plants_in_end_groups(updated_all_items, groups):
    
    measured_end_segment_row_codes = []        
    for updated_item in updated_all_items:
        
        item_name = updated_item[0]
        item_position = updated_item[6]
        actual_plants = updated_item[2]
        
        try:
            actual_plants = int(actual_plants)
        except ValueError:
            continue # didn't measure actual number of plants
        
        if 'R.' in item_name:
            measured_row_code = RowCode(item_name, position=item_position)
            measured_row_code.measured_plants = actual_plants
            measured_end_segment_row_codes.append(measured_row_code)
        
    # Calculate expected plants in each group that wraps to the next row.
    measured_row_seg_count = 0
    for group in groups:
        if len(group.segments) < 2:
            continue # don't care about single segments
        
        total_group_length = group.length
        remaining_group_plants = group.expected_num_plants
        for segment in group.segments:
            percent_of_group = segment.length / total_group_length
            num_segment_plants = int(round(group.expected_num_plants * percent_of_group))
            num_segment_plants =  min(remaining_group_plants, num_segment_plants)
            segment.expected_num_plants = num_segment_plants
            remaining_group_plants -= num_segment_plants
            
            # Check to see if actual amount was counted in the field.
            for measured_row_code in measured_end_segment_row_codes:
                if is_same_position_item(segment.start_code, measured_row_code, 4000) or \
                   is_same_position_item(segment.end_code, measured_row_code, 4000):
                    segment.expected_num_plants = measured_row_code.measured_plants
                    segment.num_plants_was_measured = True
                    measured_row_seg_count += 1
                    
    print "Updated {} row segs wtih measured values".format(measured_row_seg_count)

if __name__ == '__main__':
    '''Group codes into rows/groups/segments.'''

    parser = argparse.ArgumentParser(description='''Group codes into rows/groups/segments.''')
    #parser.add_argument('group_info_file', help='file with group numbers and corresponding number of plants.')
    #parser.add_argument('path_file', help='file with path position information used for segmenting rows.')
    parser.add_argument('input_directory', help='directory containing pickled files from previous stage.')
    parser.add_argument('field_direction', help='Planting angle of entire field.  0 degrees East and increases CCW.')
    parser.add_argument('output_directory', help='where to write output files')
    parser.add_argument('-u', dest='updated_items_filepath', default='none', help='')
    
    args = parser.parse_args()
    
    # convert command line arguments
    #group_info_file = args.group_info_file
    #path_file = args.path_file
    input_directory = args.input_directory
    field_direction = float(args.field_direction)
    output_directory = args.output_directory
    updated_items_filepath = args.updated_items_filepath
    
    # Parse in group info
    #grouping_info = parse_grouping_file(group_info_file)
    #print "Parsed {} groups. ".format(len(grouping_info))
    
    #grouping_info = make_grouping_info_unique(grouping_info)

    geo_images = unpickle_geo_images(input_directory)

    if len(geo_images) == 0:
        print "Couldn't load any geo images from input directory {}".format(input_directory)
        sys.exit(1)
    
    all_codes = all_codes_from_geo_images(geo_images)
    
    print 'Found {} codes in {} geo images.'.format(len(all_codes), len(geo_images))
    if len(all_codes) == 0:
        sys.exit(1)
        
    # correction step
    do_row_replacements(all_codes)
                
    updated_all_items, updated_missing_items, updated_none_items = parse_updated_items(updated_items_filepath)

    add_in_none_codes(updated_none_items, grouping_info)
        
    add_in_missing_codes(updated_missing_items, all_codes)
        
    #for code in all_codes:
    #    from pprint import pprint
    #    pprint(vars(code))
    #    print "\n\n\n"
    
    # Merge items down so they're unique.  One code with reference other instances of that same code.
    merged_codes = merge_items(all_codes, max_distance=5000)
    
    merged_codes = cluster_merged_items(merged_codes, geo_images, cluster_size=0.3)
    
    print '{} unique codes.'.format(len(merged_codes))
    
    check_code_precision(merged_codes)
                
    row_codes = [code for code in merged_codes if code.type.lower() == 'rowcode']
    group_codes = [code for code in merged_codes if code.type.lower() == 'groupcode']
    
    # Tell user how many codes are missing or if there are any extra codes.
    found_code_ids = [code.name for code in group_codes] 
    all_code_ids = [g[0] for g in grouping_info] 
    missing_code_ids = [id for id in all_code_ids if id not in found_code_ids]
    extra_code_ids = [id for id in found_code_ids if id not in all_code_ids]
    
    warn_about_missing_and_extra_codes(missing_code_ids, extra_code_ids)

    associate_ids_to_entry_rep(group_codes)

    grouped_row_codes = group_row_codes(row_codes)
    
    if len(grouped_row_codes) == 0:
        print "No rows detected."
        sys.exit(1)

    display_row_info(grouped_row_codes)
        
    rows = create_rows(grouped_row_codes)
                
    if len(rows) == 0:
        print "No complete rows found.  Exiting."
        sys.exit(1)
        

    up_row_nums, back_row_nums = associate_row_numbers_with_up_back_rows()

    verify_up_back_row_numbers(up_row_nums, back_row_nums)

    assign_rows_a_direction(rows, up_row_nums, back_row_nums)

    field_passes = [rows[x:x+2] for x in xrange(0, len(rows), 2)]
    
    codes_with_projections = calculate_projection_to_nearest_row(group_codes, rows)
            
    group_segments = create_group_segments(codes_with_projections)
        
    # Go through and organize segments.
    start_segments, middle_segments, end_segments, single_segments = organize_group_segments(group_segments)
    
    if len(middle_segments) > 0:
        print "Middle segments that span entire row aren't supported right now. Exiting"
        sys.exit(1)
    
    groups = complete_groups(end_segments, single_segments, field_passes)
        
    handle_single_segments(single_segments, groups)
        
    display_group_info(group_segments, groups)

    # JUST HERE FOR FINDING MISSING CODES
    order_and_number_items_by_row(rows)
    
    warn_about_bad_group_lengths(groups)

    display_missing_codes_neighbors(missing_code_ids)
    
    # update # of plants in each measured groups and ones at end of rows
    update_number_of_plants_in_groups(updated_all_items, group_segments)

    update_number_of_plants_in_end_groups(updated_all_items, groups)
                    
    # This is calculate by running script and viewing output.  If you don't know yet then change this to 0.
    average_plant_spacing = 0.9688 # meters
    fix_group_lengths_or_plant_count(group_segments, average_plant_spacing)
                    
    output_results(geo_images, output_directory)