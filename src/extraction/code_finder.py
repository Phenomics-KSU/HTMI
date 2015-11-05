#! /usr/bin/env python

# OpenCV imports
import cv2
import numpy as np

# Zbar imports
import zbar
import Image # Python Imaging Library

# Project imports
from src.util.image_writer import ImageWriter
from src.util.image_utils import postfix_filename, draw_rect
from src.extraction.item_extraction import filter_by_size, extract_rotated_image
from src.data.field_item import GroupCode, SingleCode, RowCode

class CodeFinder:
    '''Locates and decodes QR codes.'''
    def __init__(self, qr_min_size, qr_max_size):
        '''Constructor.  QR size is an estimate for searching.'''
        self.qr_min_size = qr_min_size
        self.qr_max_size = qr_max_size
    
    def locate(self, geo_image, image, marked_image):
        '''Find QR codes in image and decode them.  Return list of FieldItems representing valid QR codes.''' 
        
        # Threshold grayscaled image to make white QR codes stands out.
        #gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        #_, thresh_image = cv2.threshold(gray_image, 160, 255, 0)
        
        # Convert Blue-Green-Red color space to HSV
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        lower_white = np.array([0, 0, 40], np.uint8)
        upper_white = np.array([179, 30, 255], np.uint8)
        mask = cv2.inRange(hsv_image, lower_white, upper_white)
        
        # Find outer contours (edges) and 'approximate' them to reduce the number of points along nearly straight segments.
        contours, hierarchy = cv2.findContours(mask.copy(), cv2.cv.CV_RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        #contours = [cv2.approxPolyDP(contour, .1, True) for contour in contours]
        
        # Create bounding box for each contour.
        bounding_rectangles = [cv2.minAreaRect(contour) for contour in contours]

        # Remove any rectangles that couldn't be a QR item based off specified side length.
        filtered_rectangles = filter_by_size(bounding_rectangles, geo_image.resolution, self.qr_min_size, self.qr_max_size)
        
        if ImageWriter.level <= ImageWriter.DEBUG:
            # Debug save intermediate images
            thresh_filename = postfix_filename(geo_image.file_name, 'thresh')
            ImageWriter.save_debug(thresh_filename, mask)
        
        # Scan each rectangle with QR reader to remove false positives and also extract data from code.
        qr_items = []
        for rectangle in filtered_rectangles:
            qr_data = self.scan_image_different_trims_and_threshs(image, rectangle, trims=[0, 3, 8, 12])
            scan_successful = len(qr_data) != 0

            if scan_successful:

                qr_code = self.create_qr_code(qr_data[0], rectangle) 
                
                if qr_code is None:
                    print 'WARNING: Invalid QR data found ' + qr_data[0]
                else:
                    qr_items.append(qr_code)
                
            if marked_image is not None:
                # Show success/failure using colored bounding box
                success_color = (0, 255, 0) # green
                if scan_successful and qr_code is not None and qr_code.type == 'RowCode': 
                    success_color = (0, 255, 255) # yellow for row codes
                failure_color = (0, 0, 255) # red
                item_color = success_color if scan_successful else failure_color
                draw_rect(marked_image, rectangle, item_color, thickness=2)
        
        return qr_items
    
    def scan_image_different_trims_and_threshs(self, full_image, rotated_rect, trims):
        '''Scan image using different trims if first try fails. Return list of data found in image.'''
        
        for i, trim in enumerate(trims):
            extracted_image = extract_rotated_image(full_image, rotated_rect, 30, trim=trim)
            qr_data = self.scan_image_different_threshs(extracted_image)
            if len(qr_data) != 0:
                if i > 0:
                    print "Success with trim value {} on try {}".format(trim, i+1)
                return qr_data # scan successful
            
        return [] # scans unsuccessful.
    
    def scan_image_different_threshs(self, cv_image):
        '''Scan image using multiple thresholds if first try fails. Return list of data found in image.'''
        scan_try = 0
        qr_data = []
        while True:
            if scan_try == 0:
                image_to_scan = cv_image # use original image
            elif scan_try == 1:
                cv_gray_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
                cv_thresh_image = cv2.adaptiveThreshold(cv_gray_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 101, 2)
                image_to_scan = cv2.cvtColor(cv_thresh_image, cv2.COLOR_GRAY2BGR)
            elif scan_try == 2:
                cv_gray_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
                cv_thresh_image = cv2.adaptiveThreshold(cv_gray_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 39, 2)
                image_to_scan = cv2.cvtColor(cv_thresh_image, cv2.COLOR_GRAY2BGR)
            elif scan_try == 3:
                cv_gray_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
                _, cv_thresh_image = cv2.threshold(cv_gray_image, 150, 255, 0)
                image_to_scan = cv2.cvtColor(cv_thresh_image, cv2.COLOR_GRAY2BGR)
            else:
                break # nothing else to try.
            
            qr_data = self.scan_image(image_to_scan)
            
            if len(qr_data) > 0:
                break # found code data in image so don't need to keep trying
            
            scan_try += 1
            
        # Notify if had to use a backup thresholding and had success.
        if scan_try > 0 and len(qr_data) > 0:
            print 'success on scan try {0}'.format(scan_try)
            
        return qr_data
    
    def scan_image(self, cv_image):
        '''Scan image with Zbar and return data found in visual code(s)'''
        # Create and configure reader.
        scanner = zbar.ImageScanner()
        scanner.parse_config('enable')
         
        # Convert colored OpenCV image to grayscale PIL image.
        cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        pil_image= Image.fromarray(cv_image)
        pil_image = pil_image.convert('L') # convert to grayscale

        # Wrap image data. Y800 is grayscale format.
        width, height = pil_image.size
        raw = pil_image.tostring()
        image = zbar.Image(width, height, 'Y800', raw)
        
        # Scan image and return results.
        scanner.scan(image)

        return [symbol.data for symbol in image]

    def create_qr_code(self, qr_data, bounding_rect):
        '''Return either SingleCode, GroupCode or RowCode depending on data.  Return None if not valid data.'''
        
        # change misprinted code
        # TODO remove this
        if qr_data == 'K000736': 
            qr_data = '736'
        
        if qr_data[0].lower() == 'k':
            qr_item = SingleCode(name = qr_data)
        elif qr_data[-3:-1].lower() in ['st', 'en']: 
            qr_item = RowCode(name = qr_data)
            qr_item.row = int(qr_data[:3])
        elif qr_data.isdigit():
            qr_item = GroupCode(name = qr_data) 
        else:
            qr_item = None
            
        # Fill in any common fields here.
        if qr_item is not None:
            qr_item.bounding_rect = bounding_rect
            
        return qr_item
