import logging
import time

from google.appengine.api import mail
from google.appengine.api import urlfetch
from django.utils import simplejson

import config


# convenienc method for accessing arrival times via the API
#
def getarrivals(request, result_count=3):

    routeID = None
    stopID = None
    
    # there are two valid formats for requests
    # <route> <stop id> : returns the next bus for that stop
    # <stop id> : returns the next N buses for that stop
    #
    requestArgs = request.split()
    logging.info('request has %s arguments' % str(len(requestArgs)))
    if requestArgs[0].isdigit() == True:
        if len(requestArgs) == 1:
            # assume single argument requests are for a bus stop
            stopID = requestArgs[0]
            if len(stopID) == 3:
                stopID = "0" + stopID
            logging.info('determined stopID is %s' % stopID)
        else:
            # pull the route and stopID out of the request body and
            # pad it with a zero on the front if the message forgot  
            # to include it (that's how they are stored in the DB)
            routeID = requestArgs[0]
            if len(routeID) == 1:
                routeID = "0" + routeID
            logging.info('determined routeID is %s' % routeID)

            stopID = requestArgs[1]
            if len(stopID) == 3:
                stopID = "0" + stopID

        # package up the API web service call and make the request
        #
        url = '%s/v1/getarrivals?key=%s&stopID=%s' % (config.API_URL_BASE,config.METRO_API_KEY,stopID)
        if routeID is not None:
            url += '&routeID=%s' % routeID

        loop = 0
        done = False
        result = None
        while not done and loop < 3:
            try:
              # go fetch the webpage for this route/stop!
              result = urlfetch.fetch(url)
              done = True;
            except urlfetch.DownloadError:
              logging.debug("Error loading page (%s)... sleeping" % loop)
              time.sleep(2)
              loop = loop+1

        if result is None or result.status_code != 200:
            logging.error("Exiting early: error fetching API")
            response = 'Snap! The scheduling service is currently down. Please try again shortly'
        else:
            json_results = simplejson.loads(result.content)
            if json_results is None:
                response = 'Snap! The scheduling service is currently down. Please try again shortly'
            elif json_results['status'] == '-1':
                response = "Hmmm. That's strange. It doesn't look like there are ANY routes at this stop"
            elif json_results['status'] == '0' and 'info' in json_results:
                response = "Snap! That route isn't running through this stop right now"
            else:
                if len(json_results['stop']['route']) == 0:
                    if routeID is None:
                        response = "Snap! It looks like service has ended for the day at that stop."
                    else:
                        response = "Snap! It looks like service has ended for the day at that stop. Are you sure route %s runs through stop %s?" % (routeID,stopID)
                else:
                    # return the first three results for SMS messages
                    response = 'Stop %s: ' % stopID
                    for i,route in enumerate(json_results['stop']['route']):
                        response += 'Route %s, %s toward %s, ' % (route['routeID'],route['arrivalTime'],route['destination'])
                        if i == (result_count-1):
                            break

    else:
        # bogus request
        response = 'Your message must be either... stopID -or- routeID stopID'

        # email bogus requests back to me
        message = mail.EmailMessage()
        message.sender = config.EMAIL_SENDER_ADDRESS
        message.to = config.EMAIL_REPORT_ADDRESS
        message.subject = 'Bogus SMB request'
        message.body = request
        message.send()

    logging.info('returning results... %s' % response)
    return response
 
## end get_arrivals


# convenienc method for accessing parking data via the API
#
def getparking():

        # package up the API web service call and make the request
        #
        url = config.API_URL_BASE + 'v1/getparking?key=%s' % config.METRO_API_KEY
        loop = 0
        done = False
        result = None
        while not done and loop < 2:
            try:
              # go fetch the webpage for this route/stop!
              result = urlfetch.fetch(url)
              done = True;
            except urlfetch.DownloadError:
              logging.debug("Error loading page (%s)... sleeping" % loop)
              time.sleep(2)
              loop = loop+1

        response = '% Open :: '
        if result is None or result.status_code != 200:
            logging.error("Exiting early: error fetching API")
            logging.error(result)
            response = 'Snap! The scheduling service is currently down. Please try again shortly'
        else:
            json_results = simplejson.loads(result.content)
            if json_results is None:
                response = 'Snap! The parking service is currently down. Please try again shortly'
            else:
                for lot in json_results:
                    fraction = float(lot['open_spots']) / float(lot['total_spots'])
                    open = str(round(fraction * 100.0))
                    response += '%s: %s ' % (lot['name'].replace(' Garage',''), open.replace('.0','%'))

        logging.info('returning results... %s' % response)
        return response
 
#Capitol Square North Garage: 488 Overture Center Garage: 462 State Street Capitol Garage: 193 Brayton Lot: 143 Government East Garage: 15 State Street Campus Garage: 419
#Capitol Square North: 488 Overture Center: 462 State Street Capitol: 193 Brayton Lot: 143 Government East: 15 State Street Campus: 419
#% Open :: Capitol Square North: 80.0 Overture Center: 75.0 State Street Capitol: 23.0 Brayton Lot: 59.0 Government East: 3.0 State Street Campus: 39.0
## end get_parking
