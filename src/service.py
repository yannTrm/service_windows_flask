# -*- coding: utf-8 -*-
# Import
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
from cv2 import (findContours, 
                 RETR_EXTERNAL, CHAIN_APPROX_SIMPLE, INTER_LANCZOS4, 
                 boundingRect, resize)
from tensorflow.keras.models import load_model as tf_load_model
from numpy import (stack, count_nonzero, pad, delete, argmax, max as maxi, array, uint8)
from flask import Flask, request, jsonify

import win32serviceutil, win32service , win32event, servicemanager, socket 
import sys, os, json, signal, requests
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
# Function
def get_executable_directory():
    if getattr(sys, 'frozen', False):return os.path.dirname(sys.executable)
    else:return os.path.dirname(os.path.abspath(__file__))
    
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
# Constant   
MAIN_PATH = get_executable_directory()

CONFIG_FILE_PATH = os.path.join(MAIN_PATH, 'config.json')
CONFIG_FILE_PATH = CONFIG_FILE_PATH.replace('\\', '/')  # Convert backslashes to forward slashes
with open(CONFIG_FILE_PATH, 'r') as json_file:
    data = json.load(json_file)

PATH_MODEL = data['PATH']['model']
SVC_NAME = data['SERVICE_INFO']['name']
SVC_DISPLAY_NAME = data['SERVICE_INFO']['display_name']
ALLOWED_IP = data.get('ALLOWED_IP', [])
PORT = data["PORT"]
HOST = data["HOST"]

FORMAT_54 = [0, 4, 28, 31, 38, 43, 50, 53]
FORMAT_53 = [0, 4, 28, 31, 38, 43, 50, 52]

#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
# Class
class AppServerSvc(win32serviceutil.ServiceFramework):
    _svc_name_ = SVC_NAME
    _svc_display_name_ = SVC_DISPLAY_NAME

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_running = True

    def SvcStop(self):
        requests.post('http://localhost:5000/shutdown')
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False
        
    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        self.main()

    def main(self):
        serveur = Serveur()
                    
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
class Serveur:
    app = Flask(__name__)
    model = None
    allowed_ips = []
    port = None
    host = None
    
    def __init__(self):
        self.load_params()
        self.setup_routes()
        self.app.run(host= self.host, port = self.port)
      
    def load_params(self):
        self.load_allowed_ips()
        self.load_host()
        self.load_model()
        self.load_port()
    def load_allowed_ips(self):
        Serveur.allowed_ips = ALLOWED_IP
    def load_port(self):
        Serveur.port = PORT
    def load_host(self):
        Serveur.host = HOST
    
    
    def setup_routes(self):
        def is_allowed_request():
            return request.remote_addr in Serveur.allowed_ips
        
        @Serveur.app.before_request
        def restrict_requests():
            if not is_allowed_request():
                return "Access denied. Only requests from specific IP addresses are allowed.", 403
            
        @Serveur.app.route('/test')
        def test():
            return f"Le serveur est actif"

        @Serveur.app.route('/tete_yann', methods=['POST'])
        def tete_yann():
            if 'image' not in request.json:
                return 'Aucune image trouvée'

            image = array(json.loads(request.json['image']), dtype=uint8)
            numbers = process_image(image)

            pred = predict(Serveur.model, numbers)
            data_serializable = [arr.tolist() for arr in pred]

            return jsonify(data_serializable)

        @Serveur.app.route('/shutdown', methods=['POST'])
        def shutdown():
            os.kill(os.getpid(), signal.SIGINT)
            return 'Server shutting down...'

    def load_model(self):
        Serveur.model = tf_load_model(PATH_MODEL)
    
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------
# process images
def segment_image(image):
    contours, _ = findContours(image, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE)
    sorted_contours = sorted(contours, key=lambda ctr: boundingRect(ctr)[0])  
    segmented_objects = []
    for contour in sorted_contours:
        x, y, w, h = boundingRect(contour)
        segmented_object = image[y:y+h, x:x+w]
        if is_digit_segment(segmented_object):
            border_width = 3
            segmented_object = pad(segmented_object, border_width, mode='constant')
            segmented_object = resize(segmented_object, (28, 28), interpolation=INTER_LANCZOS4)
            segmented_objects.append(segmented_object)
    return segmented_objects
    
def is_digit_segment(segment):
    pixel_ratio = count_nonzero(segment) / segment.size
    if pixel_ratio < 0.9:  
        if (segment.shape[0] < 7 and segment.shape[1] < 7):
            return False
        return True
    else:
        return False
    
# main process
def process_image(image):
    images_segmented = segment(image)
    if images_segmented.shape[0] == 54:
        number_to_predict = delete(images_segmented, FORMAT_54, axis = 0)
    else :
        number_to_predict = delete(images_segmented, FORMAT_53, axis = 0)
    return number_to_predict

def predict(model, data):
    prediction = model.predict(data, verbose = 0)
    return [argmax(prediction, axis=1), maxi(prediction, axis=1)]

def segment(image):
    segmentation = segment_image(image)
    if segmentation:
        numbers = stack(segmentation, axis=0).astype("float32") / 255.0
        return numbers
    return None
     
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------ 
if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AppServerSvc)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(AppServerSvc)
             
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------