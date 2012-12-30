import os
import wsgiref.handlers
import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template


class MainHandler(webapp.RequestHandler):
    def get(self, stopID=""):
      stops = self.request.get('s').split(',')
      if stops[0] is '':
          # default to the mother fool's kiosk results
          stops = ['1505','1878']
      elif len(stops) == 1 or len(stops[1]) == 0:
          stops.append('1878')

      directions = self.request.get('d').split(',')
      if directions[0] is '':
          # default to the mother fool's kios directions
          directions = ['Eastbound','Westbound']
      elif len(directions) == 1:
          directions.append('unknown direction')
          
      logging.debug('KIOSK definition request for stops %s' % stops)
      template_values = { 
        'stop1':stops[0], 
        'stop2':stops[1],
        'direction1':directions[0],
        'direction2':directions[1]
      }
      path = os.path.join(os.path.dirname(__file__), '../../views/kiosk.html')
      self.response.out.write(template.render(path,template_values))
    
## end MainHandler()

def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([('/kiosk', MainHandler),
                                        ],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
