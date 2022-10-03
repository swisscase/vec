#!/usr/bin/python

import RPi.GPIO as GPIO
import time, threading
from datetime import datetime
from socket import *
from time import sleep
 
SCHRANKE_A = 22
SCHRANKE_B = 17
ZEITMESSUNG_GESTARTET = 0
ENDZEIT_RISING = []
ENDZEIT_LAST_RISING = 0
ENDZEIT_FALLING = []
ENDZEIT_LAST_FALLING = 0
STARTZEIT = []
SENSORABSTAND = 0.37            #in m
ERSTE_MESSUNG = 0
WARTEN_ZWISCHEN_MESSUNGEN = 5

SOCKET_S = socket(AF_INET, SOCK_STREAM)

host = '192.168.178.39'
port = 8051  

def sendMsg(s,xmlType,xmlMsg):
    temptext = xmlMsg
    temptext = '<xmlh><xml size="{0}" name="{1}"/></xmlh>{2}'.format(len(xmlMsg),xmlType,temptext)
    temptext = temptext.encode('utf-8')
    print(temptext)
    s.sendall(temptext)

def resetVar():
    global ZEITMESSUNG_GESTARTET,ENDZEIT_LAST_RISING,ENDZEIT_RISING,ENDZEIT_LAST_FALLING,ENDZEIT_FALLING,STARTZEIT,ERSTE_MESSUNG
    #print("RESET Variablen\n")
    ZEITMESSUNG_GESTARTET = 0
    ENDZEIT_LAST_RISING = 0
    ENDZEIT_RISING = []
    ENDZEIT_LAST_FALLING = 0
    ENDZEIT_FALLING = []
    STARTZEIT = []
    ERSTE_MESSUNG = 0

def auswertung():
    global ERSTE_MESSUNG,ENDZEIT_RISING,WARTEN_ZWISCHEN_MESSUNGEN
    #print("Auswertung ErsteMessung: {0}".format(ERSTE_MESSUNG))
    if ERSTE_MESSUNG == 0: 
        threading.Timer(WARTEN_ZWISCHEN_MESSUNGEN, auswertung).start()
        ERSTE_MESSUNG = 1
    elif len(ENDZEIT_RISING) > 0 and len(ENDZEIT_FALLING) > 0 and ERSTE_MESSUNG==1:
        zeitmessung("stop")
        ERSTE_MESSUNG = 0
    else:
        print("Auswertung FAIL")
        resetVar()

def zeitmessung(aktion):
    global ZEITMESSUNG_GESTARTET,ENDZEIT_RISING,ENDZEIT_FALLING,STARTZEIT
    now = datetime.now()
    aktuelleZeit = now.strftime("%H:%M:%S")
    if aktion == "stop":
        print(aktuelleZeit+": Stoppuhr stop")
        berechnung()
        resetVar()
        
    elif aktion == "start":
        ZEITMESSUNG_GESTARTET = 1
        STARTZEIT.append(time.time())
        print(aktuelleZeit+": Stoppuhr start")

def schrankeA_callback(channel):
    global ERSTE_MESSUNG
    if ZEITMESSUNG_GESTARTET==0 and ERSTE_MESSUNG == 0:
        zeitmessung("start")
        auswertung()
    else:
        now = datetime.now()
        aktuelleZeit = now.strftime("%H:%M:%S")
        print(aktuelleZeit+": Fehler Sensor A: SCHON GESTARTET -> resetVar")
        resetVar()

def schrankeB_callback(channel):
    global ENDZEIT_RISING,ENDZEIT_FALLING,ENDZEIT_LAST_RISING,ENDZEIT_LAST_FALLING,SCHRANKE_B
    now = time.time()    
    if GPIO.input(SCHRANKE_B) and ZEITMESSUNG_GESTARTET == 1:        #ist ein RiSING Edge impuls
        if  now > ENDZEIT_LAST_RISING:
            ENDZEIT_LAST_RISING = now
            ENDZEIT_RISING.append(now)
    elif ZEITMESSUNG_GESTARTET == 1:                                      #ist ein FALLING Edge impuls
        if  now > ENDZEIT_LAST_FALLING:
            ENDZEIT_LAST_FALLING = now
            ENDZEIT_FALLING.append(now)
    #print("BR: {0}".format(ENDZEIT_RISING))
    #print("BF: {0}".format(ENDZEIT_FALLING))

def berechnung():
    global SENSORABSTAND,ENDZEIT_RISING,ENDZEIT_FALLING,STARTZEIT,SOCKET_S,host,port
    if len(ENDZEIT_RISING) > 0 and len(ENDZEIT_FALLING) > 0 and len(STARTZEIT) > 0:
        #print("BR: {0}".format(ENDZEIT_RISING))
        #print("BF: {0}".format(ENDZEIT_FALLING))
        #print("Startzeit: {0}".format(STARTZEIT))
        zeitSpitzeEnde = ENDZEIT_RISING[len(ENDZEIT_RISING)-1]-ENDZEIT_FALLING[0]
        zeitSpitzeSpitze = ENDZEIT_FALLING[0]-STARTZEIT[0]
        if zeitSpitzeEnde > 0 and zeitSpitzeSpitze > 0:
            now = datetime.now()
            aktuelleZeit = now.strftime("%H:%M:%S")
            geschwindigkeit = SENSORABSTAND/zeitSpitzeSpitze
            zuglaenge = round(zeitSpitzeEnde*geschwindigkeit*100,2)
            #print("Erste FALLING:\t{0}\nLetzte RISING:\t{1}".format(ENDZEIT_FALLING[0],ENDZEIT_RISING[len(ENDZEIT_RISING)-1]))
            print("T_Spitze-Spitze:\t{0}s\nT_Spitze-Ende:\t\t{1}s\nGeschwindigkeit:\t{2}m/s\nZuglänge gemessen:\t{3}cm\n".format(round(zeitSpitzeSpitze,2),round(zeitSpitzeEnde,2),round(geschwindigkeit,2),zuglaenge))
            try:
                print(aktuelleZeit+": Versuche mit Rocrail zu verbinden...")
                SOCKET_S = socket(AF_INET, SOCK_STREAM)
                SOCKET_S.connect( ( host, port ) )
            except socket.error:
                SOCKET_S.close()
            sendeParameterAnRocrail("Zugmessung_Bl1_Geschwindigkeit",round(geschwindigkeit,2),"true")
            sendeParameterAnRocrail("Zugmessung_Bl1_Laenge",zuglaenge,"true")
            time.sleep(2)
            sendeParameterAnRocrail("Zugmessung_Bl1_Geschwindigkeit",round(geschwindigkeit,2),"false")
            sendeParameterAnRocrail("Zugmessung_Bl1_Laenge",zuglaenge,"false")
            time.sleep(2)
            SOCKET_S.close()

def sendeParameterAnRocrail(varID,inhalt,status):
    global HOST,SOCKET_S
    rrMsg = '<fb id="{0}" state="{1}" identifier="{2}"/>'.format(varID,status,inhalt)
    sendMsg(SOCKET_S,"fb",rrMsg)

GPIO.setmode(GPIO.BCM)
GPIO.setup(SCHRANKE_A, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(SCHRANKE_A, GPIO.FALLING, callback=schrankeA_callback, bouncetime=WARTEN_ZWISCHEN_MESSUNGEN*1000)

GPIO.setup(SCHRANKE_B, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(SCHRANKE_B, GPIO.BOTH, callback=schrankeB_callback)

while True:
    now = datetime.now()
    aktuelleZeit = now.strftime("%H:%M:%S")
    print(aktuelleZeit+": Warte auf Zugdurchfahrt")
    time.sleep(5)

GPIO.cleanup()
SOCKET_S.close()