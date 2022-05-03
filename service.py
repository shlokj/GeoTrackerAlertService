import os
import logging
import requests
import json
import time
from datetime import datetime
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon

EMAILTO = "engineering+challenge@sprinterhealth.com"
MONITORING_INTERVAL = 4 # query every n seconds
NUM_CLINICIANS = 6
EMAIL_SEND_TIMEOUT = 60 # time in seconds before which we can send another email about the same clinician

class GeoTrackerAlertService:

    def __init__(self):
        logging.basicConfig(filename="logfile.txt",
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)
        self.log = logging.getLogger()
        self.log.info("INIT")

    # use bash on server to send email
    def sendEmail(self, subject, body):
        try:
            cur_dt = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            body += "\n\nTime of this alert: " + cur_dt
            cmd = """
            echo "{b}" | mail -s "{subj}" "{e}"
            """.format(b = body, e = EMAILTO, subj = subject).strip()
            os.system(cmd)
        except Exception as e:
            self.log.critical("FAILED TO SEND EMAIL ALERT!")
            self.log.error(str(e))

    # email content

    def emailSubjectLocationLost(self, phlebotomistNumber):
        return "ALERT: Location of Phlebotomist " + str(phlebotomistNumber) + " Lost"

    def emailSubjectLeftZone(self, phlebotomistNumber):
        return "ALERT: Phlebotomist " + str(phlebotomistNumber) + " Out of Safety Zone"

    def emailBodyLocationLost(self, phlebotomistNumber):
        return "This is to alert you that we are unable to retrieve location information on phlebotomist number " + str(phlebotomistNumber) + "."

    def emailBodyLeftZone(self, phlebotomistNumber, numOfTimes):
        content = "This is to alert you that phlebotomist number " + str(phlebotomistNumber) + " has exited their designated safe area."
        if numOfTimes > 1:
            content += "\n\nNumber of times this phlebotomist has left their safe zone: " + str(numOfTimes)
        return content

    # make a get request to the clinician status API and return the result in a dictionary
    def getGeoJSONDict(self, phlebotomistNumber):
        try:
            geoJsonReq = requests.get("https://3qbqr98twd.execute-api.us-west-2.amazonaws.com/test/clinicianstatus/" + str(phlebotomistNumber))
            gjDict = geoJsonReq.json() # in a dictionary so we can work with it
            self.log.debug("getGeoJSONDict: make GET request and store in dictionary")
            return gjDict
        except Exception as e:
            self.log.error("getGeoJSONDict: Failed to get location")
            self.log.error(str(e))
            self.sendEmail(self, self.emailSubjectLocationLost(p), self.emailBodyLocationLost(p))
    
    # convert the coords in our dictionary to a shapely point so we can easily checkw whether it lies in a polygon
    def getPhlebotomistCoords(self, cDict):
        self.log.debug("getPhlebotomistCoords: Extract clinician location from geo dictionary")
        return Point(cDict['features'][0]['geometry']['coordinates'])

    # get a list of areas within which the phlebotomist remains
    def getBoundingArea(self, cDict):
        polygons = []
        featureNum = 0
        # features is a list of dictionaries
        for feature in cDict['features']: # it's possible that the safe zone consists of multiple polygons. here, we add all of them to a list
            if feature['geometry']['type'] == 'Polygon':
                polygons.append(Polygon(feature['geometry']['coordinates'][0])) # create a new polygon
            featureNum += 1
        self.log.debug("getBoundingArea: create list of bounding polygons")
        return polygons

    def isInSafeZone(self, phlebotomistLocation, boundingPolygons):
        for polygon in boundingPolygons:
            if polygon.contains(phlebotomistLocation) or polygon.touches(phlebotomistLocation): # our person is in or on the edge of one of our polygons - good to go
                return True
        # if we completed the for loop and found no polygon which contains the person, we know they are out
        else: 
            return False

    def reduceAllBy1Until0(self, waitTimes): # helper function for email send timeouts
        length = len(waitTimes)
        for i in range(length):
            if waitTimes[i] > 0:
                waitTimes[i] -= 1
        
    def monitorAndAlert(self):
    
        inZone = [True for _ in range(NUM_CLINICIANS)]
        numExits = [0 for _ in range(NUM_CLINICIANS)]
        emailSendWait = [0 for _ in range(NUM_CLINICIANS)]

        for i in range((3600 // MONITORING_INTERVAL) + 1): # the +1 makes it go just over an hour
            self.reduceAllBy1Until0(emailSendWait)
            for p in range(1, NUM_CLINICIANS + 1):
                coordsDict = self.getGeoJSONDict(p)
                try:
                    phlebotomistLocation = self.getPhlebotomistCoords(coordsDict) # coordinates of the phlebotomist
                except Exception as e:
                    self.log.info("Location lost: send email alert to phlebotomist " + str(p))
                    self.log.error(str(e))
                    if emailSendWait[p-1] == 0: # to avoid spamming too many emails in the case of internal server errors
                        self.sendEmail(self.emailSubjectLocationLost(p), self.emailBodyLocationLost(p))
                        emailSendWait[p - 1] = EMAIL_SEND_TIMEOUT // MONITORING_INTERVAL # to wait a minute before sending the next email
                    continue # move on to the next clinician

                boundingPolygons = self.getBoundingArea(coordsDict)

                # send alerts when a phlebotomist who was previously in the zone leaves. 
                if not self.isInSafeZone(phlebotomistLocation, boundingPolygons): # if this is the first time we're finding this person outside their polygon            
                    if inZone[p-1]: # if the person was previously in their safe zone
                        numExits[p-1] += 1
                        self.log.info("Out of safe zone: send email alert to phlebotomist " + str(p))
                        self.sendEmail(self.emailSubjectLeftZone(p), self.emailBodyLeftZone(p,numExits[p-1]))
                        print('OUT OF ZONE: EMAIL',i,p)
                        inZone[p-1] = False
                else:
                    inZone[p-1] = True # mark that the person is (now) in their safe area
            
            time.sleep(MONITORING_INTERVAL)
