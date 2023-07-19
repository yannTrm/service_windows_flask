# -*- coding: utf-8 -*-

import requests
import numpy as np
import json
import cv2
import time as t

PATH_IMAGE = "./test.jpg"

def load_image(chemin_image):
    image = cv2.imread(chemin_image, 0) # type numpy ndarray
    if image is None:
        return None
    return image



image_array = cv2.bitwise_not(load_image(PATH_IMAGE))
image_list = image_array.tolist()
image_json = json.dumps(image_list)



url = 'http://localhost:5000/tete_yann'
data = {'image': image_json}
t1 = t.time()
response = requests.post(url, json=data)
print(response.text)


