import cv2
import numpy as np
import sys

hsv = None

def nothing(x):
    
    if hsv is None:
        print 'no hsv image'
        return
    
    # get info from track bar and apply to result
    hlow = cv2.getTrackbarPos('hlow','result')
    slow = cv2.getTrackbarPos('slow','result')
    vlow = cv2.getTrackbarPos('vlow','result')
    hhigh = cv2.getTrackbarPos('hhigh','result')
    shigh = cv2.getTrackbarPos('shigh','result')
    vhigh = cv2.getTrackbarPos('vhigh','result')

    # Normal masking algorithm
    lower = np.array([hlow,slow,vlow])
    upper = np.array([hhigh,shigh,vhigh])

    mask = cv2.inRange(hsv,lower, upper)
    
    #kernel = np.ones((2,2), np.uint8)
    #mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    
    cv2.imshow("result", mask)

# "L:\sunflower\PCRT_20160001_20160614_020826\data_files\cam-left_CAM_1\CAM_1_20160614_074718_IMG_617.JPG"
image = cv2.imread(r"L:\sunflower\stage3_output\images\CAM_1_20160617_055716_IMG_112_marked.JPG", cv2.CV_LOAD_IMAGE_COLOR)

if image is None:
    print "Image is none"
    sys.exit(1)

#image.convertTo(image, cv2.CV_32F);

# Creating a window for later use
cv2.namedWindow('result', cv2.CV_WINDOW_AUTOSIZE)

# Starting with 100's to prevent error while masking
#hlow,slow,vlow = 67,15,5
#hhigh,shigh,vhigh = 142,255,255
hlow,slow,vlow = 0,00,160
hhigh,shigh,vhigh = 179,65,255

# Creating track bar
cv2.createTrackbar('hlow', 'result', 0,179,nothing)
cv2.createTrackbar('slow', 'result', 0,255,nothing)
cv2.createTrackbar('vlow', 'result', 0,255,nothing)
cv2.createTrackbar('hhigh', 'result', 0,179,nothing)
cv2.createTrackbar('shigh', 'result', 0,255,nothing)
cv2.createTrackbar('vhigh', 'result', 0,255,nothing)
cv2.setTrackbarPos('hlow', 'result', hlow)
cv2.setTrackbarPos('slow', 'result', slow)
cv2.setTrackbarPos('vlow', 'result', vlow)
cv2.setTrackbarPos('hhigh', 'result', hhigh)
cv2.setTrackbarPos('shigh', 'result', shigh)
cv2.setTrackbarPos('vhigh', 'result', vhigh)

#converting to HSV
hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
hsv = cv2.resize(hsv, (0,0), fx=0.1, fy=0.1) 

cv2.imshow("result", hsv)

while True:

    if cv2.waitKey(1) & 0xFF == 27:
        break