#! /usr/bin/env python

import sys
import os
import argparse
from collections import defaultdict

# Project imports
from src.util.stage_io import unpickle_stage2_output
from src.util.parsing import parse_code_listing_file
from src.processing.item_processing import position_difference, all_segments_from_rows, all_groups_from_segments
from src.stages.exit_reason import ExitReason
    
def make_code_listings_unique(code_listings):
    # Warn if there are duplicate groups in info file.
    unique_code_listings_dict = defaultdict(list)
    unique_code_listings_list = []
    for listing in code_listings:
        unique_code_listings_dict[listing.id].append(listing)
    for id, listings in unique_code_listings_dict.iteritems():
        if len(listings) > 2:
            print "More than 2 entries with id {}".format(id)
        elif len(listings) == 2:
            if (listings[0].max_plants == listings[1].max_plants):
                print "Duplicate entries with id {}".format(id)
            else:
                print "Two different entries with id {}".format(id)
                print listings
            unique_code_listings_list.append(listings[0])
        else: # just one unique info listing
            unique_code_listings_list.append(listings[0])
    return unique_code_listings_list
            
def check_code_precision(merged_codes):
    # Sanity check that multiple references of the same code are all close to each other.
    largest_separation = 0
    sum_separation = 0
    sum_separation_count = 0
    for code in merged_codes:
        for code_ref in code.all_refs:
            diff = position_difference(code.position, code_ref.position)
            sum_separation += diff
            sum_separation_count += 1
            if diff > largest_separation:
                largest_separation = diff
                
    average_separation = 0
    if sum_separation_count > 0:
        average_separation = sum_separation / sum_separation_count
                
    print "From average position largest separation is {} and average is {}".format(largest_separation, average_separation)

def warn_about_missing_and_extra_group_codes(missing_code_ids, extra_code_ids):
    print "Missing {} group ids.".format(len(missing_code_ids))
    if len(missing_code_ids) < 30:
        for id in missing_code_ids:
            print "missing id: {}".format(id)
            
    if len(extra_code_ids) > 0:
        print "WARNING: Found {} group codes that aren't listed in expected grouping file.".format(len(extra_code_ids))
        for id in extra_code_ids:
            print "Extra ID: {}".format(id)

def warn_about_bad_group_lengths(groups, spacing_between_plants):

    num_groups_without_expected_length = 0
    num_good_lengths = 0 # how many groups have a close to expected length
    num_too_long = 0 # how many groups have a longer than expected length
    num_too_short = 0 # how many groups have a longer than expected length
    for group in groups:
        
        if group.expected_num_plants < 0:
            num_groups_without_expected_length += 1
            continue

        spacing_for_codes = spacing_between_plants / 2.0
        expected_length = (group.expected_num_plants - 1) * spacing_between_plants
        expected_length += spacing_for_codes * 2 * len(group.segments) # for before and end codes for each segment

        actual_length = group.length
        
        length_difference = actual_length - expected_length
        
        # how long segment can be without being flagged
        max_length = expected_length * 1.3
        min_length = expected_length * 0.7
        
        if len(group.segments) > 1:
            # Give a little more wiggle room if there's multiple segments
            max_length += spacing_between_plants * 5
            continue # temporary, just want to look at single segments
        
        if actual_length > max_length:
            print "Group with start code {} is {} meters too long.".format(group.id, abs(length_difference))
            for k, segment in enumerate(group.segments):
                print "Segment {} starts with {} and ends with {}".format(k, segment.start_code.name, segment.end_code.name)
                print "{} to {}".format(segment.start_code.parent_image_filename, segment.end_code.parent_image_filename)
            num_too_long += 1
        elif actual_length < min_length:
            #print "Group with start code {} is {} meters too short.".format(group.id, abs(length_difference))
            num_too_short += 1
    
    print "\n------Group Length Report------"
    print "Found {} groups with close expected lengths".format(num_good_lengths)
    print "{} that were longer than expected".format(num_too_long)
    print "{} that were shorter than expected".format(num_too_short)
    print " and {} groups that didn't have expected lengths".format(num_groups_without_expected_length)
    print "\n"
 
def warn_about_missing_single_codes(found_code_ids):
    
    found_code_numbers = [int(id[1:]) for id in found_code_ids]

    max_number = max(found_code_numbers)
    expected_code_numbers = range(1, max_number+1)
    
    missing_code_numbers = [n for n in expected_code_numbers if n not in found_code_numbers]
 
    print "Missing {} single ids.".format(len(missing_code_numbers))
    for number in missing_code_numbers:
        print "missing single id with number {}".format(number)
 
def warn_about_missing_single_code_lengths(single_segments, spacing_between_plants):

    num_good_lengths = 0 # how many groups have a close to expected length
    num_too_long = 0 # how many groups have a longer than expected length
    for k, segment in enumerate(single_segments[:-1]):

        next_segment = single_segments[k+1]

        expected_length = spacing_between_plants

        if len(segment.items) > 0 and len(next_segment.items) > 0:
            # Plants have been found.
            plant1 = segment.items[0]
            plant2 = next_segment.items[0]
            actual_length = position_difference(plant1.position, plant2.position)
        else:
            # Plants not found yet so just compare codes.
            actual_length = segment.length
        
        length_difference = actual_length - expected_length
        
        # how long segment can be without being flagged
        max_length = spacing_between_plants * 1.75
        
        if actual_length > max_length:
            print "\nSingle segment {} to {} is {} feet too long.".format(segment.start_code.name, segment.end_code.name, length_difference * 100 / 30)
            print "{} to {}.".format(segment.start_code.parent_image_filename, segment.end_code.parent_image_filename)
            num_too_long += 1
            
        if actual_length < 0.06:
            print "WARNING - segment {} to {} is way too short".format(segment.start_code.name, segment.end_code.name)
    
    print "\n------Single Segment Length Report------"
    print "Found {} single codes with close expected lengths".format(num_good_lengths)
    print "and {} that were too long".format(num_too_long)
    print "\n"
 
if __name__ == '__main__':
    '''Analyze stage 2 output.'''

    parser = argparse.ArgumentParser(description='''Analyze stage 2 output.''')
    parser.add_argument('input_filepath', help='pickled file from stage 2.')
    parser.add_argument('output_directory', help='where to write output files')
    parser.add_argument('code_list_filepath', help='Filepath to code list CSV file. If 3 columns then must be code, max plants, alternate_ids. If 2 columns then must exclude alternate ids.')
    parser.add_argument('plant_spacing', help='Expected distance between plants in meters.')
    
    args = parser.parse_args()
    
    # convert command line arguments
    input_filepath = args.input_filepath
    out_directory = args.output_directory
    code_list_filepath = args.code_list_filepath
    plant_spacing = float(args.plant_spacing)

    rows, geo_images = unpickle_stage2_output(input_filepath)
    
    if len(rows) == 0 or len(geo_images) == 0:
        print "No rows or no geo images could be loaded from {}".format(input_filepath)
        sys.exit(ExitReason.no_rows)
        
    if not os.path.exists(code_list_filepath):
        print "Code list file doesn't exist {}".format(code_list_filepath)
        sys.exit(ExitReason.bad_arguments)
    
    code_listings, _ = parse_code_listing_file(code_list_filepath)
    
    code_listings = make_code_listings_unique(code_listings)
    
    all_segments = all_segments_from_rows(rows)
    groups = all_groups_from_segments(all_segments)
    
    single_segments = []
    group_segments = []
    for segment in all_segments:
        if segment.start_code.type == 'SingleCode':
            single_segments.append(segment)
        elif segment.start_code.type == 'GroupCode':
            group_segments.append(segment)
    
    single_codes = [seg.start_code for seg in single_segments]
    group_codes = [seg.start_code for seg in group_segments]
    
    single_code_ids = [code.name for code in single_codes]
    group_code_ids = [code.name for code in group_codes]
    listed_code_ids = [listing.id for listing in code_listings]
    
    extra_group_codes_ids = [code.name for code in group_codes if code.name not in listed_code_ids]
    missing_group_code_ids = [id for id in listed_code_ids if id not in group_code_ids]
    
    warn_about_missing_and_extra_group_codes(missing_group_code_ids, extra_group_codes_ids)
    
    warn_about_bad_group_lengths(groups, plant_spacing) 
    
    # KLM - not reliable since not all numbers were actually planted
    #warn_about_missing_single_codes(single_code_ids)
    
    warn_about_missing_single_code_lengths(single_segments, plant_spacing)
    
    if not os.path.exists(out_directory):
        os.makedirs(out_directory)
    
    # Write averaged results out to file.
    import time
    from src.processing.export_results import export_results
    from src.util.numbering import number_serpentine
    avg_results_filename = time.strftime("_results_averaged-%Y%m%d-%H%M%S.csv")
    avg_results_filepath = os.path.join(out_directory, avg_results_filename)
    sorted_rows = sorted(rows, key=lambda r: r.number)
    items = number_serpentine(sorted_rows)
    export_results(items, [], avg_results_filepath)
    print 'Output codes to {}'.format(avg_results_filepath)
    
#     extra_ids = ['123', '302', '488', '645', '647']
#     extra_groups = [group for group in groups if group.id in extra_ids]
#     for group in extra_groups:
#         length = group.length
#         
#         expected_plants = length / plant_spacing
#         print "Group ID {} has {} expected plants".format(group.id, expected_plants)
    
    