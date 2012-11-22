import os
import wsgiref.handlers
import logging

from google.appengine.api import memcache

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

from data_model import PhoneLog
import config

class MainHandler(webapp.RequestHandler):

  def post(self):
      # this handler should never get called
      logging.error("The MainHandler should never get called... %s" % self.request)
      self.error(204)

  def get(self):
      self.post()
      
## end MainHandler()

class EventLoggingHandler(webapp.RequestHandler):
    def post(self):
      # normalize the XMPP requests
      if self.request.get('phone').find('@'):
          caller = self.request.get('phone').split('/')[0]
      else:
      	  caller = self.request.get('phone')
      # log this event...
      logging.debug('logging caller: %s' % caller)
      log = PhoneLog()
      log.phone = caller
      log.body = self.request.get('inboundBody')
      log.smsID = self.request.get('sid')
      log.outboundSMS = self.request.get('outboundBody')
      log.put()
    
## end EventLoggingHandler


class ResetQuotaHandler(webapp.RequestHandler):
    def get(self):
        logging.info("deleting the memcached quotas for the day...")
        memcache.delete_multi(config.ABUSERS)
        self.response.set_status(200)
        return
        
        
def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([('/', MainHandler),
                                        ('/loggingtask', EventLoggingHandler),
                                        ('/resetquotas', ResetQuotaHandler),
                                        ],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
