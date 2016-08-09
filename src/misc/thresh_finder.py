import cv2
import numpy as np

def nothing(x):
    # get info from track bar and apply to result
    thresh = cv2.getTrackbarPos('thresh','result')
    
    _, thresh_image = cv2.threshold(gray_image, thresh, 255, 0)
    
    # Open mask (to remove noise) and then dilate it to connect contours.
    #kernel = np.ones((2,2), np.uint8)
    #mask_open = cv2.morphologyEx(thresh_image, cv2.MORPH_OPEN, kernel)
    #thresh_image = cv2.dilate(mask_open, kernel, iterations = 1)
    
    #if thresh > 5 and thresh % 2 == 1:
        #thresh_image = cv2.adaptiveThreshold(gray_image,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,thresh,2)
        #thresh_image = cv2.adaptiveThreshold(gray_image,255,cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY,thresh,2)
        #thresh_image = cv2.adaptiveThreshold(gray_image,255,cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV,thresh,2)
    
    cv2.imshow("result", thresh_image)

# Creating a window for later use
cv2.namedWindow('result', cv2.CV_WINDOW_AUTOSIZE)

# Creating track bar
cv2.createTrackbar('thresh', 'result', 0,255,nothing)

image = cv2.imread(r"L:\sunflower\PCRT_20160001_20160614_020826\data_files\cam-left_CAM_1\CAM_1_20160614_080159_IMG_1657.JPG")

gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
gray_image = cv2.resize(gray_image, (0,0), fx=0.2, fy=0.2) 

cv2.imshow("result", gray_image)

while True:

    if cv2.waitKey(1) & 0xFF == 27:
        break
    
cv2.destroyAllWindows()