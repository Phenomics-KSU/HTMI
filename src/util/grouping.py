#! /usr/bin/env python

import sys
import copy
from collections import defaultdict, namedtuple

# Project imports
from src.data.field_item import GroupCode
from src.data.field_grouping import Row, PlantGroup, PlantGroupSegment
from src.processing.item_processing import orient_items, lateral_and_projection_distance_2d, position_difference

def associate_ids_to_entry_rep(group_codes, grouping_info):
    # Update group codes with entry x rep
    num_matched_ids_to_info = 0
    for group_code in group_codes:
        matching_info = [info for info in grouping_info if info[0] == group_code.name]
        if len(matching_info) == 0:
            continue
        matching_info = matching_info[0]
        group_code.entry = matching_info[1]
        group_code.rep = matching_info[2]
        num_matched_ids_to_info += 1
        
    print "Updated {} group codes with entry x rep".format(num_matched_ids_to_info)

def group_row_codes(row_codes):
    # Group row codes in dictionary by row code number.
    grouped_row_codes = defaultdict(list)
    for code in row_codes:
        grouped_row_codes[code.row].append(code)
    return grouped_row_codes

def group_row_codes_by_pass_name(row_codes):
    # Group row codes in dictionary by row code name (not counting last character for L/R direction).
    paired_codes = [False] * len(row_codes)
    grouped_codes = []
    for i, code in enumerate(row_codes):
        if paired_codes[i]:
            continue # already paired this code
        dir = code.name[3:5].lower() # start or end (St or En)
        side = code.name[-1].lower() # right or left (R or L)
        
        for j, other_code in enumerate(row_codes):
            if paired_codes[j]:
                continue # already paired this code
            if i == j:
                continue # don't compare a code with itself
            other_dir = other_code.name[3:5].lower()
            other_side = other_code.name[-1].lower()
            
            if (code.row == other_code.row) and (side == other_side):
                if paired_codes[i]:
                    print "Error: Found multiple matches for code {}".format(code.name)
                    sys.exit(-1)
                if dir == other_dir:
                    print "Error: Found duplicates pass codes {} and {}".format(code.name, other_code.name)
                    sys.exit(-1)
                    
                # Make sure first element in group tuple is the start code
                if dir == 'st' and other_dir == 'en':
                    grouped_codes.append((code, other_code))
                elif other_dir == 'st' and dir == 'en':
                    grouped_codes.append((other_code, code))
                else:
                    print "Error: Bad pass code formats, should be one 'st' and one 'en'. Codes: {} and {}".format(code.name, other_code.name)
                    sys.exit(-1)
                    
                # Mark that we've already paired the codes so they don't get re-paired
                paired_codes[i] = True
                paired_codes[j] = True
                
        if not paired_codes[i]:
            print "Couldn't find a match for row code {} found in image {}".format(code.name, code.parent_image_filename)
        
    return grouped_codes

def group_row_codes_by_row_name(row_codes):
    # Group row codes in list of (start code, end code) base on st or end in code name
    
    # First collect codes with the same row number.
    grouped_row_codes = defaultdict(list)
    for code in row_codes:
        grouped_row_codes[code.row].append(code)
    
    grouped_row_codes_list = []
    for row_num, row_codes in grouped_row_codes.iteritems():
        
        if len(row_codes) != 2:
            print 'WARNING - skipping row {} because it has {} rows codes'.format(row_num, len(row_codes))
            continue 
    
        try:
            start_code = [code for code in row_codes if 'st' in code.name.lower()][0]
            end_code = [code for code in row_codes if 'en' in code.name.lower()][0]
        except IndexError:
            print 'WARNING - skipping row {} because it has either 2 start or 2 end codes {}'.format(row_num, row_codes)
            continue
    
        grouped_row_codes_list.append((start_code, end_code))

    return grouped_row_codes_list

def display_row_info(grouped_row_codes):
    # Show user information about which rows were found and which are missing.
    sorted_row_numbers = sorted([codes[0].row for codes in grouped_row_codes])
    smallest_row_number = sorted_row_numbers[0]
    biggest_row_number = sorted_row_numbers[-1]
    print "Found rows from {} to {}".format(smallest_row_number, biggest_row_number)
    missing_row_numbers = set(range(smallest_row_number, biggest_row_number+1)) - set(sorted_row_numbers)
    if len(missing_row_numbers) > 0:
        print "Missing row numbers {}".format(missing_row_numbers)
    else:
        print "No skipped row numbers."

def create_rows(grouped_row_codes, field_direction):
    rows = []
    for row_number, codes in grouped_row_codes.iteritems():
        if len(codes) == 1:
            print "Only found 1 code for row {}".format(row_number)
        elif len(codes) > 2:
            print "Found {} codes for row {} with positions: ".format(len(codes), row_number)
            for code in codes:
                print "\t{}".format(code.position)
        else:
            # Create row objects with start/end codes.
            code1, code2 = codes
            start_code, end_code = orient_items(code1, code2, field_direction)
            if start_code and end_code:
                rows.append(Row(start_code, end_code)) 
    return rows

def associate_row_numbers_with_up_back_rows():
    
    # Take into account how the row runs (up or back)
    # Have to change this for each field or all to pass in with args.
    first_start = 1 # first section start row
    first_end = 22 # last row number from first section
    second_start = first_end + 1 # first row number from second section (since started in wrong direction)
    second_end = 58 # last row number in field
    row_step = 4 # Goes with double planter.
    # First section
    up_row_nums = range(first_start, second_start, row_step)
    up_row_nums += range(first_start+1, second_start, row_step)
    back_row_nums = range(first_start+2, second_start, row_step)
    back_row_nums += range(first_start+3, second_start, row_step)
    # Second section
    up_row_nums += range(second_start, second_end+1, row_step)
    up_row_nums += range(second_start+1, second_end+1, row_step)
    back_row_nums += range(second_start+2, second_end+1, row_step)
    back_row_nums += range(second_start+3, second_end+1, row_step)
    
    up_row_nums = sorted(up_row_nums, key=lambda n: n)
    back_row_nums = sorted(back_row_nums, key=lambda n: n)
    
    return up_row_nums, back_row_nums

def associate_row_numbers_with_up_back_rows_using_code_names():
    
    # Take into account how the row runs (up or back)
    # Have to change this for each field or all to pass in with args.
    first_start = 1 # first section start row
    first_end = 22 # last row number from first section
    second_start = first_end + 1 # first row number from second section (since started in wrong direction)
    second_end = 58 # last row number in field
    row_step = 4 # Goes with double planter.
    # First section
    up_row_nums = range(first_start, second_start, row_step)
    up_row_nums += range(first_start+1, second_start, row_step)
    back_row_nums = range(first_start+2, second_start, row_step)
    back_row_nums += range(first_start+3, second_start, row_step)
    # Second section
    up_row_nums += range(second_start, second_end+1, row_step)
    up_row_nums += range(second_start+1, second_end+1, row_step)
    back_row_nums += range(second_start+2, second_end+1, row_step)
    back_row_nums += range(second_start+3, second_end+1, row_step)
    
    up_row_nums = sorted(up_row_nums, key=lambda n: n)
    back_row_nums = sorted(back_row_nums, key=lambda n: n)
    
    return up_row_nums, back_row_nums

def assign_rows_a_direction(rows, up_row_nums, back_row_nums):
    for row in rows:
        if row.number in up_row_nums:
            row.direction = 'up'
        elif row.number in back_row_nums:
            row.direction = 'back'
        else:
            print "Row number {} doesn't have a defined up/back direction".format(row.number)
            sys.exit(1)

def create_rows_and_field_passes_by_pass_codes(grouped_row_codes, field_direction):
    
    rows = []
    field_passes = defaultdict(list)
    for pass_start_code, pass_end_code in grouped_row_codes:
        
        field_start_code, field_end_code = orient_items(pass_start_code, pass_end_code, field_direction)
    
        if pass_start_code is field_start_code:
            row_direction = 'up'
        else:
            row_direction = 'back'
            
        new_row = Row(field_start_code, field_end_code, direction=row_direction)
        rows.append(new_row)
        
        # At this point row numbers should be pass numbers so can use them to group rows into passes.
        field_passes[new_row.number].append(new_row)
        
        # Convert pass number on codes to row numbers
        pass_side = pass_start_code.name[-1].lower()
        pass_start_code.assigned_row = pass_start_code.row * 2 - 1
        pass_end_code.assigned_row = pass_end_code.row * 2 - 1
        if (pass_side == 'r' and row_direction == 'up') or (pass_side == 'l' and row_direction == 'back'):
            pass_start_code.assigned_row += 1
            pass_end_code.assigned_row += 1
            
    sorted_field_passes = []
    for sorted_pass_num in sorted(field_passes.keys()):
        rows_in_pass = field_passes[sorted_pass_num]
        if len(rows_in_pass) == 1:
            print "Only 1 row found in pass {}".format(sorted_pass_num)
        elif len(rows_in_pass) > 2:
            print "Error: more than 2 rows in pass {}".format(sorted_pass_num)
            sys.exit(-1)
        
        sorted_field_passes.append(rows_in_pass)
            
    field_passes = sorted_field_passes
    
    return rows, field_passes

def create_rows_and_field_passes_by_row_codes(grouped_row_codes, field_direction, rows_per_pass):
    
    rows = []
    
    for pass_start_code, pass_end_code in grouped_row_codes:
        
        field_start_code, field_end_code = orient_items(pass_start_code, pass_end_code, field_direction)
    
        if pass_start_code is field_start_code:
            row_direction = 'up'
        else:
            row_direction = 'back'
            
        new_row = Row(field_start_code, field_end_code, direction=row_direction)
        rows.append(new_row)
        
    # Sort row number so can group them into passes.
    sorted_rows = sorted(rows, key=lambda row: row.number)
            
    # Current pass number to assign rows to.  Passes are indexed off 1.
    current_pass_num = 1
            
    field_passes = defaultdict(list)
    for row_idx, row in enumerate(sorted_rows):

        if row_idx == 0:
            current_direction = row.direction
            
        num_rows_in_current_pass = len(field_passes[current_pass_num])
            
        end_of_pass = (row.direction != current_direction) or (num_rows_in_current_pass >= rows_per_pass)
            
        if end_of_pass:
            
            if num_rows_in_current_pass < rows_per_pass:
                print 'WARNING - pass {} only has {} rows'.format(current_pass_num, num_rows_in_current_pass)
            
            current_pass_num += 1

        field_passes[current_pass_num].append(row)
        current_direction = row.direction
        
    # Convert field passes to a list and make sure it's sorted.
    sorted_field_passes = []
    for sorted_pass_num in sorted(field_passes.keys()):
        sorted_field_passes.append(field_passes[sorted_pass_num])

    field_passes = sorted_field_passes
    
    return rows, field_passes

def calculate_projection_to_nearest_row(codes, rows):
    
    # Copy rows so we can add temporary fields without modifying original
    rows = copy.copy(rows)
    
    CodeWithProjection = namedtuple('CodeWithProjection', 'code projection')
    codes_with_projections = []
    
    # Order codes and rows from left to right
    codes = sorted(codes, key=lambda c: c.field_position[0])
    rows = sorted(rows, key=lambda r: r.center_field_position[0])
    
    for row in rows:
        row.ordered_items = [row.start_code, row.end_code]
    
    for code in codes:
        
        rows_with_distance_to_code = [(row, abs(row.center_field_position[0] - code.field_position[0])) for row in rows]
        sorted_rows_with_distance_to_code = sorted(rows_with_distance_to_code, key=lambda r: r[1])
        closest_rows_to_code = [row[0] for row in sorted_rows_with_distance_to_code[:4]]
        
        min_distance = sys.float_info.max
        closest_row = None
        closest_after_in_closest_row = None
        for row in closest_rows_to_code:
            
            closest_beneath = None
            closest_after = None
            for item in row.ordered_items:
                if code.field_position[1] > item.field_position[1]:
                    closest_beneath = item
                else:
                    closest_after = item
                    break

            if closest_beneath is None or closest_after is None:
                continue # not in this row for sure

            distance_to_code, _ = lateral_and_projection_distance_2d(code.field_position, closest_beneath.field_position, closest_after.field_position)
            distance_to_code = abs(distance_to_code)
            
            if distance_to_code < min_distance:
                min_distance = distance_to_code
                closest_after_in_closest_row = closest_after
                closest_row = row
                
        if closest_row is not None and min_distance < 3: # TODO remove hard-coded value
            
            _, row_projection = lateral_and_projection_distance_2d(code.field_position, row.start_code.field_position, row.end_code.field_position)
            
            closest_item_idx = closest_row.ordered_items.index(closest_after_in_closest_row)
            closest_row.ordered_items.insert(closest_item_idx, code)
            
            code.row = closest_row.number
            codes_with_projections.append(CodeWithProjection(code, row_projection))
        else:
            code.row = -1
            print "Couldn't find a row for code {}. Closest row is {} meters away.".format(code.name, min_distance)
        
    return codes_with_projections

def create_segments(codes_with_projections, rows):
    
    group_segments = [] 
    special_segments = [] # segments that start with a SingleCode
    for row in rows:
        codes_in_row = [code for code in codes_with_projections if code.code.row == row.number]
        if len(codes_in_row) == 0:
            print "No codes in row {}. Creating pseudo group code at start.".format(row.number)
            pseudo_code1 = GroupCode(name='PS{}'.format(row.number), position=row.start_code.position, 
                                     field_position=row.start_code.field_position, zone=row.start_code.zone, row=row.number)
            pseudo_code2 = GroupCode(name='PE{}'.format(row.number), position=row.end_code.position,
                                     field_position=row.end_code.field_position, zone=row.end_code.zone, row=row.number)
            codes_in_row = [(pseudo_code1, 0), (pseudo_code2, 1)]
            
        # Sort codes by projection distance.
        sorted_row_codes = [row.start_code]
        sorted_group_codes_in_row = sorted(codes_in_row, key=lambda c: c[1])
        sorted_row_codes += [code[0] for code in sorted_group_codes_in_row]
        sorted_row_codes.append(row.end_code)
        if row.direction == 'back':
            sorted_row_codes = list(reversed(sorted_row_codes))
        
        for i, code in enumerate(sorted_row_codes[:-1]):
            new_segment = PlantGroupSegment(start_code=code, end_code=sorted_row_codes[i+1])
            row.segments.append(new_segment)
            if new_segment.is_special:
                special_segments.append(new_segment)
            else:
                group_segments.append(new_segment)
            
    return group_segments, special_segments

def organize_group_segments(group_segments):

    start_segments = []
    middle_segments = []
    end_segments = []
    single_segments = []
    for segment in group_segments:
        starts_with_row_code = segment.start_code.type.lower() == 'rowcode'
        ends_with_row_code = segment.end_code.type.lower() == 'rowcode'
        if starts_with_row_code and ends_with_row_code:
            middle_segments.append(segment)
        elif starts_with_row_code:
            start_segments.append(segment)
        elif ends_with_row_code:
            end_segments.append(segment)
        else:
            single_segments.append(segment)
    
    return start_segments, middle_segments, end_segments, single_segments

def complete_groups(end_segments, single_segments, field_passes, num_rows_per_pass):
    
    groups = []
    for end_segment in end_segments[:]: 
        
        matching_field_passes = [fpass for fpass in field_passes if end_segment.row_number in [row.number for row in fpass]]
        
        if len(matching_field_passes) == 0:
            print "End segment {} with row {} isn't in field pass list.".format(end_segment.start_code.name, end_segment.row_number)
            continue
        
        field_pass = matching_field_passes[0]
        pass_index = [row.number for row in field_pass].index(end_segment.row_number)
        
        field_pass_index = field_passes.index(field_pass)
        if field_pass_index >= len(field_passes) - 1:
            print "End segment {} can't be matched since it's in the last pass. Treating as single segment.".format(end_segment.start_code.name)
            single_segments.append(end_segment)
            end_segments.remove(end_segment)
            continue
        
        next_pass = field_passes[field_pass_index+1]
        
        # Find row index in next pass matching this one.
        # If 3 rows then a pass_index of 0 should have a corresponding index of 2 in the next row.
        corresponding_row_index = num_rows_per_pass - pass_index - 1
            
        try:
            this_planting_row = field_pass[pass_index]
            next_planting_row = next_pass[corresponding_row_index]
        except IndexError:
            single_segments.append(end_segment)
            end_segments.remove(end_segment)
            print "Segment at end of row {} in pass {} doesn't have corresponding row in next pass to match with.  Treating as single segment.".format(end_segment.row_number, field_pass_index+1)
            continue
        
        if this_planting_row.direction == next_planting_row.direction:
            single_segments.append(end_segment)
            end_segments.remove(end_segment)
            print "End segment {} in row {} can't match to row {} since both rows are in the same direction ({}).  Treating as single segment.".format(end_segment.start_code.name, this_planting_row.number, next_planting_row.number, this_planting_row.direction)
            continue
        
        if len(next_planting_row.group_segments) == 0:
            single_segments.append(end_segment)
            end_segments.remove(end_segment)
            print "End segment {} in row {} can't match to row {} since next row doesn't have any segments.  Treating as single segment.".format(end_segment.start_code.name, this_planting_row.number, next_planting_row.number)
            continue

        matching_start_segment = next_planting_row.group_segments[0]
        new_group = PlantGroup()
        new_group.add_segment(end_segment)
        new_group.add_segment(matching_start_segment)
        groups.append(new_group)
        
    return groups

def handle_single_segments(single_segments, groups):
    for segment in single_segments:
        new_group = PlantGroup()
        new_group.add_segment(segment)
        groups.append(new_group)

def apply_code_listings(code_listings, groups, alternate_ids_included):
    
    for group in groups:
        
        matched_listings = [listing for listing in code_listings if group.start_code.name == listing.id]
        
        if len(matched_listings) == 0:
            continue # no match
        
        matched_listing = matched_listings[0]
        group.expected_num_plants = matched_listing.max_plants
        if alternate_ids_included:
            group.start_code.alternate_id = matched_listing.alternate_id

def display_segment_info(group_segments, special_segments, groups):
    print "{} special segments.".format(len(special_segments))
    print "Combined {} segments into {} groups.".format(len(group_segments), len(groups))
    
    group_seg_count = defaultdict(list)
    for group in groups:
        group_seg_count[len(group.segments)].append(group)
        
    for num_segs, groups_with_that_many_segs in group_seg_count.iteritems():
        print "{} groups with {} segments".format(len(groups_with_that_many_segs), num_segs) 