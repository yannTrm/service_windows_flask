# <p align="center">Service windows python</p>
  
## Coucou👋

Ce code a été rédigé en juillet 2022 par Yann Terrom. La technique utilisée est une reconnaissance image par IA (reséau convolutif LeNet-4). Le modèle est entrainé, la partie entrainement est expliqué dans le projet "reconnaissance_ia". Ce readme a pour but d'expliquer le code source python qui gère le service windows. Bonne lecture ;)

----------

### Récuperation des données de configurations 

Dans le même répertoire que le code source doit se trouver un fichier config.json qui contient des informations essentielles au bon fonctionnement du code : 

config.json

```json
{
  "PATH": {
    "model": "path_to_model/name_file_model.h5"
  }, 
  "SERVICE_INFO" : {
      "name" : "service name",
      "display_name" : "service name (display)"
  },
  "ALLOWED_IP" :  ["127.0.0.1", "::1", "192.168.1.100", "192.168.1.101"],
    "HOST" : "0.0.0.0", 
    "PORT" : 5000
}
```

- "PATH" correspond au chemin d'accès du modèle d'IA entrainé. 
- "SERVICE_INFO" avec "name" et "display_name" correspond au nom du service windows qui sera notamment affiché dans l'outil Services de windows.
- "ALLOWED_IP" permet d'autoriser uniquement les IPs présentent dans cette liste (inutile puisque le serveur flask est local mais l'idée est cool).
- "HOST" et "PORT" permet de donner l'adresse ou l'on fera la requête http. (0.0.0.0 = toutes les adresses du localhost).


La première fonction du code python permet de recuperer le chemin d'accès du répertoire courant (répertoire qui contient le fichier sur lequel on execute le service, et fichier config.json)

```python
def get_executable_directory():
    if getattr(sys, 'frozen', False):
        # Si le script est exécuté en tant qu'exécutable (fichier .exe)
        # Utiliser la fonction 'sys._MEIPASS' fournie par PyInstaller pour obtenir le répertoire
        return os.path.dirname(sys.executable)
    else:
        # Si le script est exécuté directement avec Python
        # Utiliser le répertoire du fichier source
        return os.path.dirname(os.path.abspath(__file__))
```
 Les commentaires parlent d'eux mêmes, mais une petite précision s'impose. Il y a deux méthodes différentes pour installer et demarrer le service windows. Ces deux méthodes sont expliqués de manière détaillé dans le readme du projet correspondant. Cependant pour être bref, on installer soit depuis un exe, soit depuis python (cela dépend si python est installé sur la machine windows ou non). Cette fonction gère donc les deux cas, à savoir récupérer le chemin si on démarre depuis python ou depuis un exe.

----------

```python
# Load config.json file using the relative path
CONFIG_FILE_PATH = os.path.join(MAIN_PATH, 'config.json')
CONFIG_FILE_PATH = CONFIG_FILE_PATH.replace('\\', '/')  # Convert backslashes to forward slashes
with open(CONFIG_FILE_PATH, 'r') as json_file:
    data = json.load(json_file)
  
# Constant
PATH_MODEL = data['PATH']['model']
SVC_NAME = data['SERVICE_INFO']['name']
SVC_DISPLAY_NAME = data['SERVICE_INFO']['display_name']
ALLOWED_IP = data.get('ALLOWED_IP', [])
PORT = data["PORT"]
HOST = data["HOST"]

FORMAT_54 = [0, 4, 28, 31, 38, 43, 50, 53]
FORMAT_53 = [0, 4, 28, 31, 38, 43, 50, 52]
```

C'est avec ce code que non allons charger le fichier config.json est récupérer les informations nécessaire. L'explication de FORMAT_54_53 arrivera un peu plus tard lors de son utilisation

----------

### Le service windows

Passons à l'implémentation des classes. Dans un premier temps voyons la classes qui s'occupe du service windows en lui même (l'installation, le démarrage et l'arrêt).

```python
class AppServerSvc(win32serviceutil.ServiceFramework):
    _svc_name_ = SVC_NAME
    _svc_display_name_ = SVC_DISPLAY_NAME

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_running = True
```

Le nom du service s'instancie dans les variables `_svc_name_` et `_svc_display_name_`.
Le timeout du service est mis par défaut à 60 secondes.

Les methodes qui gèrent le démarrage et l'arrêt du service sont les suivantes :

```python
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
```

La méthode `SvcStop` arrête dans un premier temps le serveur web flask, puis stop le service windows.

La méthode `SvcDoRun` démarre le service, puis appelle la fonction main. Cette fonction main va instancier un classe "Serveur", qui va donc démarrer le serveur Flask.

```python
    def main(self):
        serveur = Serveur()
```
----------

### Le serveur Flask (web service)

Passons maintenant au serveur Flask. 

```python
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
```

L'initialisation du serveur web se déroule de la manière suivante :

- Déclaration des variables : on va déclarer les variables nécessaire au bon déroulement du service proposé par le serveur web.
- Chargement des données

Les données vont être chargées une fois au lancement du serveur web et n'auront plus à être chargées par la suite.

chargement des données relatives au serveur :
```python
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
```

chargement du modele d'IA:

```python
    def load_model(self):
        Serveur.model = tf_load_model(PATH_MODEL)
```

#### Setup des routes

Il faut maintenant définir l'adresse des requêtes

```python
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
```

La route `/test` permet uniquement de tester si le serveur est actif.

Pour ce qui est de la tete de lecture, on appelle la route `/tete_yann` (EHEHEH je lui donne mon nom comme je suis le créateur ;) !!)

Pour expliquer un peu plus en détail l'utilisation de cette route, elle récupère une image opencv en format json, va la transformer en image opencv exploitable, effectuer les opérations de transformation nécessaire pour présenter l'image à l'IA, faire la prédiction, et enfin retourner une liste.

- la fonction process_image :

```python
def process_image(image):
    images_segmented = segment(image)
    if images_segmented.shape[0] == 54:
        number_to_predict = delete(images_segmented, FORMAT_54, axis = 0)
    else :
        number_to_predict = delete(images_segmented, FORMAT_53, axis = 0)
    return number_to_predict
```

Je deconseille de modifier les fonctions liées au pré-processing de l'image, puisque le modèle d'IA traite des images dans un format spécial (binaire, 28x28 pixels...). C'est pourquoi je n'expliquerai pas ici le fonctionnement de ces fonctions, cependant si vous voulez en savoir plus vous pouvez vous rendre sur le readme du projet de creation de cette IA, ici tout vous sera expliqué ;)

Une petite précision tout de même sur cette fonction. Rappelez vous des constant `FORMAT_53` et `FORMAT_54`. C'est ici qu'elles interviennt. Pour cela il faut comprendre que le code OCR est composé de 44 chiffres suivi du rlmc. Voici un exemple d'OCR

`(253)36103214568811234567890(17)01012000(3902)001000 *11*`

L'idée est ici de supprimer les parenthèse et les "*" pour avoir à traiter uniquement les chiffres. (54 dans le cas ou le rlmc est composé de 2 chiffres, 53 si 1).

----------

### Execution du code

```python
if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AppServerSvc)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(AppServerSvc)
```

Jusque la nous avons déclaré tout le code nécessaire, c'est ici que nous l'appelons. Cette partie du code ne devrait pas être à modifer, c'est un code très générique.

----------

Pour créer le fichier exe utiliser la commande :

`pyinstaller --hiddenimport win32timezone -F service.py`
        
