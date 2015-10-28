#! /usr/bin/env python

import sys
import os
import argparse
import math
import datetime
import csv
import bisect

def find_less_than_or_equal(a, x):
    '''
    Return rightmost index in list a where the value at a[i] is less than or equal to x.
    If x is greater than all elements in a then len(a)-1 is returned.
    If x is smaller than all elements in a then -1 is returned.
    '''
    i = bisect.bisect_right(a, x)
    return i - 1

if __name__ == '__main__':
    '''Convert file(s) to correct format for database.'''

    parser = argparse.ArgumentParser(description='Convert file(s) to correct format for database.')
    parser.add_argument('-p', dest='position_filepath', default='none', help='File path for vehicle position file.')
    parser.add_argument('-o', dest='orientation_filepath', default='none', help='File path for vehicle orientation file.')
    parser.add_argument('-i', dest='image_log_filepath', default='none', help='File path for image log file.')
    args = parser.parse_args()
    
    # Convert command line arguments
    position_filepath = args.position_filepath
    orientation_filepath = args.orientation_filepath
    image_log_filepath = args.image_log_filepath
    
    if os.path.exists(image_log_filepath):
        log_file_name, log_file_ext = os.path.splitext(image_log_filepath)
        new_log_filepath = '{}_db{}'.format(log_file_name, log_file_ext)
        new_log_file = open(new_log_filepath, 'wb')
        new_log_writer = csv.writer(new_log_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        with open(image_log_filepath, 'r') as log_file:
            for i, line in enumerate(log_file):
                if line.startswith('#'):
                    new_log_file.writeline(line)
                else:
                    fields = line.replace(',',' ').split()
                    if len(fields) != 8:
                        print 'Incorrect number of fields on line ' + str(i+1)
                    
                    utc_timestamp = float(fields[0])
                    image_name = fields[1]
                    position_fields = fields[2:4]
                    orientation_fields = fields[5:]
                    
                    utc_datetime = datetime.datetime.utcfromtimestamp(utc_timestamp)
                    
                    utc_date = "{:04d}/{:02d}/{:02d}".format(utc_datetime.year, utc_datetime.month, utc_datetime.day)
                    utc_time = "{:02d}:{:02d}:{:02d}".format(utc_datetime.hour, utc_datetime.minute, utc_datetime.second)
                    utc_milliseconds = int(utc_datetime.microsecond / 1000)
                    
                    orientation_info = []
                    for field in orientation_fields:
                        orientation_info.append(math.degrees(float(field)))
                    
                    new_log_writer.writerow([image_name, utc_date, utc_time, utc_milliseconds] + fields[2:])
                    
        print "\nFinished writing updated file {}".format(new_log_filepath)
        new_log_file.close()
        
    elif image_log_filepath.lower() != 'none':
        print "Image log doesn't exist: {}".format(image_log_filepath)
        
    # Try to combine orientation and position
    if os.path.exists(position_filepath) and os.path.exists(orientation_filepath):
        position_filepath_directory = os.path.split(position_filepath)[0]
        output_filepath = os.path.join(position_filepath_directory, 'combined_db.csv')
        new_file = open(output_filepath, 'wb')
        new_file_writer = csv.writer(new_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        position_file = open(position_filepath, 'r')
        orientation_file = open(orientation_filepath, 'r')
        
        orientations = []
        for i, line in enumerate(orientation_file.readlines()):
            fields = line.replace(',',' ').split()
            if len(fields) != 4:
                print 'Incorrect number of fields on line ' + str(i+1)
                
            timestamp = float(fields[0])
            orientation_info = [float(f) for f in fields[1:]]
        
            orientations.append({'timestamp': timestamp, 'info': orientation_info })
        
        orientation_line_num = 0
        last_position_timestamp = 0
        for i, line in enumerate(position_file):
            
            fields = line.replace(',',' ').split()
            if len(fields) != 5:
                print 'Incorrect number of fields on line ' + str(i+1)
                
            timestamp = float(fields[0])
            position_info = fields[1:]
            
            while True:
                if orientation_line_num > len(orientations):
                    orientation_info = [float('nan')] * 3
                    break
                else:
                    orientation = orientations[orientation_line_num]
                    if orientation['timestamp'] > timestamp:
                        orientation_info = [float('nan')] * 3
                        break
                    elif orientation['timestamp'] == timestamp:
                        orientation_info = orientation['info']
                        break
                    
                    orientation_line_num += 1
                        
            # Limit how much data is saved
            if abs(timestamp - last_position_timestamp) < 0.175:
                continue
            
            # Convert orientation data to degrees
            for i in range(len(orientation_info)):
                orientation_info[i] = math.degrees(orientation_info[i])
            
            last_position_timestamp = timestamp
            
            utc_datetime = datetime.datetime.utcfromtimestamp(timestamp)
            utc_date = "{:04d}/{:02d}/{:02d}".format(utc_datetime.year, utc_datetime.month, utc_datetime.day)
            utc_time = "{:02d}:{:02d}:{:02d}".format(utc_datetime.hour, utc_datetime.minute, utc_datetime.second)
            utc_milliseconds = int(utc_datetime.microsecond / 1000)
            
            new_file_writer.writerow([utc_date, utc_time, utc_milliseconds] + position_info + orientation_info)
            
        print "\nFinished writing updated file {}".format(output_filepath)
            
        position_file.close()
        orientation_file.close()
        new_file.close()
        