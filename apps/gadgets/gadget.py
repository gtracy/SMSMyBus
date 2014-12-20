import os
import logging
import webapp2

from google.appengine.ext.webapp import template


class MainHandler(webapp2.RequestHandler):
    def get(self, stopID=""):
      logging.debug('gadget definition request for stop %s' % stopID)
      template_values = {'stopID':stopID,
                         }
      path = os.path.join(os.path.dirname(__file__), '../../views/metro_template.xml')
      self.response.out.write(template.render(path,template_values))

## end MainHandler()

application = webapp2.WSGIApplication([('/gadgets/metro/(.*).xml', MainHandler),
                                      ],
                                     debug=True)
