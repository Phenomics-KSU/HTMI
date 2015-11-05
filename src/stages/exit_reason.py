#! /usr/bin/env python

class ExitReason:
    '''Map reason for a script exiting to an exit code'''
    success = 0
    bad_arguments = 1
    no_images = 2
    no_geo_images = 3
    user_interrupt = 4
    no_rows = 5
    operation_not_supported = 6
    