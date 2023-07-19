


# <p align="center">Utilisation service windows IA</p>
  
# Coucou BH-techno👋

Ce readme a pour but d'expliquer l'utilisation du service windows créé par Yann Terrom en python.

Il y a deux cas d'utilisation :

- Le premier, si python est installé sur la machine :

Un fichier config.json dois être présent dans le même repertoire que le fichier source python (.py)

## 🛠️ Install service (cmd en mode Admin)
```bash
python nom_fichier.py install 
```
Une fois le service installé, on peut le démarrer directement depuis l'outil Services de windows, ou bien depuis l'invite de commande.


##  Run service
```bash
python nom_fichier.py start
```
##  Stop service
```bash
python nom_fichier.py stop
```
##  Remove service
```bash
python nom_fichier.py remove
```
##  Update service
```bash
python nomfichier.py stop
python nom_fichier.py install
```
        
- Le deuxieme, si python n'est pas installé :

Comme pour le cas ou python est installé, le fichier config.json doit être présent dans le même répertoire que le fichier .exe.

## 🛠️ Install service (cmd en mode Admin)
Le service en executable ne peut pas être installé manuellement (double click), il doit obligatoirement être installé depuis l'invite de commande. Une fois installé, il peut être démarré depuis l'outil Services de windows ou depuis le cmd
```bash
nom_fichier.exe install 
```

##  Run service
```bash
nom_fichier.exe start
```
##  Stop service
```bash
nom_fichier.exe stop
```
##  Remove service
```bash
nom_fichier.exe remove
```
##  Update service
```bash
nomfichier.exe stop
nom_fichier.exe install
```
    