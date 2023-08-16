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
import sys, os, json, signal, requests, logging, time


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

# Configuration des paramètres de journalisation
LOG_FILE = os.path.join(MAIN_PATH, "app.log")
logging.basicConfig(level=logging.DEBUG, filename=LOG_FILE, filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s')


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
        time.sleep(1)
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False
        
    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                      servicemanager.PYS_SERVICE_STARTED,
                      (self._svc_name_, ''))
        try:
            self.main()  # Tentative de démarrage du service
        except Exception as e:
            logging.error(f"Service failed to start: {str(e)}")  # Log en cas d'échec
        
             

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
        logging.info("Initializing the server...")  # Log d'initialisation du serveur
        try:
            self.load_params()
            self.setup_routes()
            self.app.run(host=self.host, port=self.port)
        except Exception as e:
            logging.error(f"Server initialization failed: {str(e)}")  # Log d'erreur en cas d'échec
      
    def load_params(self):
        logging.debug("Loading parameters...")
        try:
            self.load_allowed_ips()
            self.load_host()
            self.load_model()
            self.load_port()
            logging.debug("Parameters loaded.")
        except Exception as e:
            logging.error(f"Loading parameters failed: {str(e)}")  # Log d'erreur en cas d'échec
        
    def load_allowed_ips(self):
        try:
            Serveur.allowed_ips = ALLOWED_IP
            logging.info(f"Allowed IPs: {Serveur.allowed_ips}")
        except Exception as e:
            logging.error(f"Loading allowed IPs failed: {str(e)}")  # Log d'erreur en cas d'échec

    def load_port(self):
        try:
            Serveur.port = PORT
            logging.info(f"Port: {Serveur.port}")
        except Exception as e:
            logging.error(f"Loading port failed: {str(e)}")  # Log d'erreur en cas d'échec

    def load_host(self):
        try:
            Serveur.host = HOST
            logging.info(f"Host: {Serveur.host}")
        except Exception as e:
            logging.error(f"Loading host failed: {str(e)}")  # Log d'erreur en cas d'échec

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
            if Serveur.model is None:
                logging.error("Le modèle n'est pas chargé.")  # Log d'erreur pour le modèle non chargé
                return 'Le modèle n\'est pas chargé.', 500  # Réponse indiquant que le modèle n'est pas chargé

            if 'image' not in request.json:
                logging.error("Aucune image trouvée")
                return 'Aucune image trouvée', 400

            image = array(json.loads(request.json['image']), dtype=uint8)
            if image.size == 0:
                logging.error("L'image est vide")
                return 'L\'image est vide', 400
            
            try:
                numbers = process_image(image)
                if numbers is None:
                    logging.debug("Erreur lors de la segmentation de l'image. Vérifier la qualité de l'image envoyée (bruit, code barre, qualité...)")
                    return "La prédiction n\'a pas aboutie", 400
                try:
                    pred = predict(Serveur.model, numbers)
                    try:
                        data_serializable = [arr.tolist() for arr in pred]
                        logging.info("Succès, prédiction effectuée et envoyée")
                        return jsonify(data_serializable)
                    
                    except Exception as e:
                        logging.error("Erreur lors de la sérialisation des données prédites : %s", str(e))
                        return 'Erreur lors de la sérialisation des données prédites', 500
                except Exception as e:
                    logging.error("Erreur lors de la prédiction : %s", str(e))
                    return 'Erreur lors de la prédiction', 500
            except Exception as e:
                logging.error("Erreur lors du traitement de l'image : %s", str(e))
                return 'Erreur lors du traitement de l\'image', 500

        @Serveur.app.route('/shutdown', methods=['POST'])
        def shutdown():
            os.kill(os.getpid(), signal.SIGINT)
            return 'Server shutting down...'

    def load_model(self):
        try:
            Serveur.model = tf_load_model(PATH_MODEL)
            logging.info("Model loaded.")
        except Exception as e:
            Serveur.model = None
            logging.error(f"Model loading failed: {str(e)}")  # Log d'erreur en cas d'échec


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
    elif images_segmented.shape[0] == 53:
        number_to_predict = delete(images_segmented, FORMAT_53, axis = 0)
    else :
        return None
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
    logging.info("Starting the application...")  # Log de démarrage de l'application

    if len(sys.argv) == 1:
        logging.info("Running as a Windows service.")
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AppServerSvc)
        
        try:
            servicemanager.StartServiceCtrlDispatcher()
        except Exception as e:
            logging.error(f"Error starting service dispatcher: {str(e)}")
    else:
        logging.info("Running as a console application.")
        win32serviceutil.HandleCommandLine(AppServerSvc)
    
    logging.info("Application finished.")
             
#------------------------------------------------------------------------------
#------------------------------------------------------------------------------