import os
import logging
import webapp2

from google.appengine.ext.webapp import template


class MainHandler(webapp2.RequestHandler):
    def get(self, stopID=""):
      template_values = {}
      logging.error('kiosk handler')

      # this end point supports two different layouts.
      #   side-by-side with two stops
      #   a grid layout with four stops
      #
      # determine which one was requested
      directions = self.request.get('d').split(',')
      stops = self.request.get('s').split(',')
      if len(stops) is 2 or stops[0] is '':
          if stops[0] is '':
              # default to the mother fool's kiosk results
              stops = ['1505','1878']
          elif len(stops) == 1 or len(stops[1]) == 0:
              stops.append('1878')

          if directions[0] is '':
              # default to the mother fool's kios directions
              directions = ['Eastbound','Westbound']
          elif len(directions) == 1:
              directions.append('unknown direction')

          logging.debug('Two column KIOSK definition request for stops %s' % stops)
          template_values = {
            'stop1':stops[0],
            'stop2':stops[1],
            'direction1':directions[0],
            'direction2':directions[1]
          }
          path = os.path.join(os.path.dirname(__file__), '../../views/kiosk.html')
          # self.response.out.write(template.render(path,template_values))
      elif len(stops) == 4 and len(directions) == 4:
          logging.error('Two column KIOSK definition request for stops %s' % stops)
          logging.error(stops)
          stop_list = []
          for index,s in enumerate(stops):
              stop_list.append({'stop_num' : s,'direction' : directions[index]})

          template_values = { 'stops' : stop_list }
          path = os.path.join(os.path.dirname(__file__), '../../views/kiosk-grid.html')
      else:
          logging.error('Invalid Kiosk request');
          path = os.path.join(os.path.dirname(__file__), '../../views/kiosk-error.html')

      self.response.out.write(template.render(path,template_values))


## end MainHandler()

app = webapp2.WSGIApplication([(r'/kiosk', MainHandler)],
                              debug=True)
