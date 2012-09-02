import wsgiref.handlers
import logging
import re
import os

from google.appengine.api import quota
from google.appengine.api import urlfetch
from google.appengine.api import memcache
from google.appengine.api import datastore_errors
from google.appengine.api.urlfetch import DownloadError
from google.appengine.api.labs import taskqueue
from google.appengine.api.labs.taskqueue import Task
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.ext.db import GeoPt

from google.appengine.runtime import apiproxy_errors

from BeautifulSoup import BeautifulSoup, Tag

from data_model import RouteListing
from data_model import StopLocation
from data_model import ParseErrors

CRAWL_URLBASE = "http://webwatch.cityofmadison.com/webwatch/Ada.aspx"

#
# We crawl for all Metro Stop locations with the following algorithm...
#
# 0. Initiate a task that starts the crawling in the background. With the task queue
#    we don't have to worry about time constraints.
# 1. Scrape the main route page to get a list of all active Routes in the system
# 2. For each route we find, create a new task to scrape the link it points to
# 3. Each route has multiple directions, create a new task for each direction
# 4. For each direction we find, create a new task to interrogate the stops on that route
# 5. For each interrogation task, go line by line looking for stopID, intersection,
#    and latitude/longitude coordinates.
# 6. For each stop we find, spawn a new task for the actual commit to the datastore.
#
# There is an ugly problem with the stop data, however. The major stops in a route
# (think transfer points and waiting areas) don't have a stop ID listed with them
# in the data source. We populate those by hand after the crawl runs its course.
#

# Step #1 : start a task to get the main route page
class CrawlerHandler(webapp.RequestHandler):
    def get(self):
        # create a new task with this link
        crawlURL = "http://webwatch.cityofmadison.com/webwatch/Ada.aspx"
        task = Task(url='/crawl/crawlingtask', params={'crawl':crawlURL,'routeID':'00'})
        task.add('crawler')
        logging.info("Added new task for %s" % crawlURL)        
        return
    
## end CrawlerHandler()

class CrawlingTaskHandler(webapp.RequestHandler):
    def post(self):
        try:
            scrapeURL = self.request.get('crawl')
            direction = self.request.get('direction')
            routeID = self.request.get('routeID')
            logging.debug("task scraping for %s, direction %s, route %s" % (scrapeURL,direction,routeID))
            
            # fetch the URL content
            content = fetchURL(scrapeURL)
            
            # start to interrogate the results
            soup = BeautifulSoup(content)
            stopUpdates = []
            for slot in soup.html.body.findAll("a","ada"):
                #logging.info("pulling out data from page... %s" % slot)

                if slot.has_key('href'):
                    href = slot['href']
                    title = slot['title']
                    logging.info("FOUND A TITLE ----> %s" % title)
                    # route crawler looks for titles with an ID# string
                    if title.find("[ID#") > 0:
                        # we finally got down to the page we're looking for. this is a reference
                        # to a specific stop including a stopID and intersection.
                        
                        # pull the stopID from the page content...
                        stopID = title.split("ID#")[1].split("]")[0]
                        
                        # pull the intersection from the page content...
                        intersection = title.split("[")[0].strip()
                        
                        logging.info("found stop %s, %s" % (stopID,intersection))
                        
                        # check to see if we've already found this stop...
                        q = db.GqlQuery("SELECT * FROM StopLocation WHERE stopID = :1 and direction = :2 and routeID = :3", 
                                        stopID, direction.upper(), routeID)
                        stopQuery = q.fetch(1)
                        if len(stopQuery) == 0:
                            # add the new stop
                            stop = StopLocation()
                            stop.stopID = stopID
                            stop.routeID = routeID
                            stop.intersection = intersection.upper()
                            stop.direction = direction.upper()
                            stopUpdates.append(stop)  # we'll do a batch put at the end 
                            logging.info("added new stop listing MINUS geo location")
                        else:
                            logging.info("already have this stop in the table...")
                            stopQuery[0].routeID = routeID
                            stopUpdates.append(stopQuery[0])
                        
                    elif href.find("?r=") > -1:
                        # this is step #2 and #3 from the algorithm documented above. we're going to create 
                        # a new task to go off and scrape the live route data for a specific route.
                        crawlURL = CRAWL_URLBASE + href
                        if routeID == '00':
                            routeID = href.split('r=')[1]
                        elif href.find("&") > -1:
                            routeID = href.split('&')[0].split('r=')[1]
                        task = Task(url='/crawl/crawlingtask', params={'crawl':crawlURL,'direction':title,'routeID':routeID})
                        task.add('crawler')
                        logging.info("Added new task for %s, direction %s, route %s" % (title.split(",")[0],title,routeID))

            # push the StopLocation updates to the datastore
            db.put(stopUpdates)
                                        
        except apiproxy_errors.DeadlineExceededError:
            logging.error("DeadlineExceededError exception!?")
            return
            
        return;
    
## end CrawlingTask()

# Main handler to get the GEO crawler started.
# The workflow gets started by parsing the main route page
# Each route entry found on that page (.../Ada.aspx) will generate
# a new task to crawl the stops for that route.
#
class CrawlGeoHandler(webapp.RequestHandler):
    def get(self):
        crawlURL = "http://webwatch.cityofmadison.com/webwatch/Ada.aspx"
        task = Task(url='/crawl/crawlinggeotask', params={'crawl':crawlURL,})
        task.add('crawler')
        logging.info("Added new task for %s" % crawlURL)        
        return
## end handler

# This handler serves double duty. It processes the system-wide route
# page as well as an individual route.
class CrawlingGeoTaskHandler(webapp.RequestHandler):
    def post(self):
        try:
            scrapeURL = self.request.get('crawl')
            logging.debug("task scraping for %s" % scrapeURL)
            
            # fetch the URL content
            content = fetchURL(scrapeURL)

            # if the page starts with a data stamp (in this case '1' for january), 
            # we're looking at the geo data for a single route.
            #
            if content[0] == '1':
                routeID = self.request.get('routeID')
                # parser for the geo stop data...
                stops = content.split('<br>')
                for s in stops:
                    #logging.info("Parsing... %s" % s)
                    if s[0] == '|':
                        # |18;43.0656205|-89.4237496|ALLEN & COMMONWEALTH [ID#2969]|CapSq|3:20 PM TO CAP SQR
                        data = re.search('\|\d+;.*?(4.*?)\|(.*?)\|(.*?)\[ID#(\d+)\]\|(.*?)\|',s)
                        if data is None:
                            # |32;43.0527923|-89.43559|Monroe & Glenway|Allied-Chalet|2:40 PM TO ALLD DR:MOHAWK
                            # 
                            # this is one of the goofy stops that has an intersection and direction
                            # but no stopID. it usually happens for the route's "major" stops
                            data = re.search('\|\d+;.*?(4.*?)\|(.*?)\|(.*?)\|(.*?)\|',s)
                            if data is not None:
                                latitude = data.group(1).strip()
                                longitude = data.group(2).strip()
                                intersection = data.group(3).strip()
                                stopID = '00'
                                direction = data.group(4).strip()
                        else:
                            latitude = data.group(1).strip()
                            longitude = data.group(2).strip()
                            intersection = data.group(3).strip()
                            stopID = data.group(4).strip()
                            direction = data.group(5).strip()
                                                            
                        if data is not None:
                            logging.debug("creating task to store this stop in the datastore...")
                            # create a task event to process the data and check/store in the datastore
                            task = Task(url='/crawl/storethestop', 
                                        params={'intersection':intersection,
                                                'latitude':latitude,
                                                'longitude':longitude,
                                                'direction':direction,
                                                'crawlLine':s,
                                                'stopID':stopID,
                                                'routeID':routeID,
                                                })
                            task.add('stopstorage')
                            
 
                return
            # else, this is the system-wide page with all routes, create 
            # new tasks for each route we find.
            #
            # start to interrogate the results
            soup = BeautifulSoup(content)
            for slot in soup.html.body.findAll("a","ada"):
                logging.info("pulling out data from page... %s" % slot)

                if slot.has_key('href'):
                    href = slot['href']
                    title = slot['title']
                    logging.info("FOUND A TITLE ----> %s" % title)
                    # route crawler looks for titles with an ID# string
                    if title.find("[ID#") > 0:
                        # this should never happen
                        logging("FATAL ERROR")
                    elif href.find("?r=") > -1:
                        routeID = href.split("=")[1]
                        crawlURL = "http://webwatch.cityofmadison.com/webwatch/UpdateWebMap.aspx?u="+routeID
                        task = Task(url='/crawl/crawlinggeotask', 
                                    params={'crawl':crawlURL,'routeID':routeID,})
                        task.add('crawler')
                        logging.info("Added new task for %s" % crawlURL)

        except apiproxy_errors.DeadlineExceededError:
            logging.error("DeadlineExceededError exception!?")
            return
            
        return;
    
## end
    
class StopStorageHandler(webapp.RequestHandler):
    def post(self):
        intersection = self.request.get('intersection')
        latitude = self.request.get('latitude')
        longitude = self.request.get('longitude')
        direction = self.request.get('direction')
        routeID = self.request.get('routeID')
        stopID = self.request.get('stopID')
        logging.info("storing route %s intersection %s at lat/lon %s,%s toward %s" % 
                     (routeID,intersection,latitude,longitude,direction))
        
        if len(intersection) > 400:
            intersection = intersection.ljust(400)

        if stopID == '00' or latitude is None or longitude is None:
            # create a task event to process the error
            task = Task(url='/crawl/errortask', params={'intersection':intersection,
                                                        'location':(latitude+","+longitude),
                                                        'direction':direction,
                                                        'metaStringOne':self.request.get('crawlLine'),
                                                        'metaStringTwo':'from geotask crawler',
                                                        'routeID':routeID,
                                                        'stopID':stopID,
                                                        })
            task.add('crawlerrors')
        else:
            # ignore this stop if we've already stored it
            # stopID + routeID
            stop = db.GqlQuery("SELECT * FROM StopLocation WHERE stopID = :1 and routeID = :2", stopID, routeID).get()
            if stop is None:
                stop = StopLocation()
                stop.stopID = stopID
                stop.routeID = routeID
                stop.intersection = intersection.upper()
                stop.direction = direction.upper()
                stop.location = GeoPt(latitude,longitude)
                stop.update_location()
                stop.put()
            
                # update the route table to include a reference to the new geo data
                if stopID != '00':
                    route = db.GqlQuery("SELECT * FROM RouteListing WHERE stopID = :1 and route = :2", stopID,routeID).get()
                    if route is None:
                        logging.error("IMPOSSIBLE... no stop on record?!? stop %s, route %s" % (stopID,routeID))
                        # create a task event to process the error
                        task = Task(url='/crawl/errortask', params={'intersection':intersection,
                                                            'location':(latitude+","+longitude),
                                                            'direction':direction,
                                                            'metaStringOne':self.request.get('crawlLine'),
                                                            'metaStringTwo':'routelisting update',
                                                            'routeID':routeID,
                                                            'stopID':stopID,
                                                            })
                        task.add('crawlerrors')
                    else:
                        route.stopLocation = stop
                        route.put()

        return
    
## end

class FixitHandler(webapp.RequestHandler):
    def post(self):
        error = db.GqlQuery("SELECT * FROM ParseErrors WHERE reviewed != false").get()
        if error is None:
            logging.error("IMPOSSIBLE - no more errors?")
            return
        
        stops = db.GqlQuery("SELECT * FROM StopLocation WHERE location = :1", error.location)

        # add the counter to the template values
        template_values = {'error':error,
                           'stops':stops,
                          }
        
        # create a page that provides a form for sending an SMS message
        path = os.path.join(os.path.dirname(__file__), 'fixit.html')
        self.response.out.write(template.render(path,template_values))
    
## end

class ErrorTaskHandler(webapp.RequestHandler):
    def post(self):
        
        result = db.GqlQuery("SELECT __key__ from ParseErrors where intersection = :1 and direction = :2 and routeID = :3", 
                             self.request.get('intersection'),self.request.get('direction'),self.request.get('routeID')).get()
        if result is None:
          error = ParseErrors()
          error.intersection = self.request.get('intersection')
          location = self.request.get('location').split(',')
          error.location = GeoPt(location[0],location[1])
          error.direction = self.request.get('direction')
          error.routeID = self.request.get('routeID')
          error.stopID = self.request.get('stopID')
          error.reviewed = False
          error.metaStringOne = self.request.get('metaStringOne')
          error.metaStringTwo = self.request.get('metaStringTwo')
          error.put()

## end ErrorTaskHandler


def fetchURL(url):
    loop = 0
    done = False
    result = None
    while not done and loop < 3:
        try:
            # fetch the page
            result = urlfetch.fetch(url)
            done = True;
        except urlfetch.DownloadError:
            logging.info("Error loading page (%s)... sleeping" % loop)
            if result:
                logging.debug("Error status: %s" % result.status_code)
                logging.debug("Error header: %s" % result.headers)
                logging.debug("Error content: %s" % result.content)
                time.sleep(4)
                loop = loop+1
    return(result.content)

## end fetchURL()
    
## end ScrapeRouteStopHandler
def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([('/crawl/configure', CrawlerHandler),
                                        ('/crawl/configuregeo', CrawlGeoHandler),
                                        ('/crawl/crawlingtask', CrawlingTaskHandler),
                                        ('/crawl/crawlinggeotask', CrawlingGeoTaskHandler),
                                        ('/crawl/storethestop', StopStorageHandler),
                                        ('/crawl/errortask', ErrorTaskHandler),
                                        ('/crawl/fixit', FixitHandler),
                                        ],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()

