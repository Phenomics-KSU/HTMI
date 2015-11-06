#! /usr/bin/env python

import sys
import os
import argparse

# non-default import
#import numpy as np

# Project imports
from src.util.stage_io import unpickle_stage3_output, pickle_results
from src.data.field_item import Plant
from src.stages.exit_reason import ExitReason

if __name__ == '__main__':
    '''.'''

    parser = argparse.ArgumentParser(description='''.''')
    parser.add_argument('input_filepath', help='pickled file from stage 3.')
    parser.add_argument('output_directory', help='where to write output files')

    args = parser.parse_args()
    
    # convert command line arguments
    input_filepath = args.input_filepath
    out_directory = args.output_directory
    method = args.method.lower()

    rows = unpickle_stage3_output(input_filepath)
    
    if len(rows) == 0:
        print "No rows could be loaded from {}".format(input_filepath)
        sys.exit(ExitReason.no_rows)
    
    rows = sorted(rows, key=lambda r: r.number)

    for row in rows:

        for segment in row.segments:
            
            pass
                    
                
                
    # Pickle
    dump_filename = "stage4_output.s4"
    print "Serializing {} rows to {}.".format(len(rows), dump_filename)
    pickle_results(dump_filename, out_directory, rows)
    