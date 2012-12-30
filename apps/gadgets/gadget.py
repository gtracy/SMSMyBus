import os
import wsgiref.handlers
import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template


class MainHandler(webapp.RequestHandler):
    def get(self, stopID=""):
      logging.debug('gadget definition request for stop %s' % stopID)
      template_values = {'stopID':stopID,
                         }
      path = os.path.join(os.path.dirname(__file__), '../../views/metro_template.xml')
      self.response.out.write(template.render(path,template_values))
    
## end MainHandler()

def main():
  logging.getLogger().setLevel(logging.ERROR)
  application = webapp.WSGIApplication([('/gadgets/metro/(.*).xml', MainHandler),
                                        ],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
