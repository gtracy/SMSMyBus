import logging
import urllib
import webapp2

from google.appengine.api import memcache

from data_model import PhoneLog
import config

class MainHandler(webapp2.RequestHandler):

  def post(self):
      # this handler should never get called
      logging.error("The MainHandler should never get called... %s" % self.request)
      self.error(204)

  def get(self):
      self.post()

## end MainHandler()

class EventLoggingHandler(webapp2.RequestHandler):
    def post(self):
      # normalize the XMPP requests
      if self.request.get('from').find('@'):
          caller = self.request.get('from').split('/')[0]
      else:
      	  caller = self.request.get('from')
      # log this event...
      logging.debug('logging caller: %s' % caller)
      log = PhoneLog()
      log.phone = caller
      log.to    = self.request.get('to')
      log.body  = self.request.get('inboundBody')
      log.smsID = self.request.get('sid')
      log.outboundSMS = self.request.get('outboundBody')
      log.put()

## end EventLoggingHandler


class ResetQuotaHandler(webapp2.RequestHandler):
    def get(self):
        logging.info("deleting the memcached quotas for the day...")
        memcache.delete_multi(config.ABUSERS)
        self.response.set_status(200)
        return
## end

# re-direct for old API documentation path
class APIDocs(webapp2.RequestHandler):
    def get(self):
        self.redirect(config.API_URL_BASE)
## end

class APIRedirectHandler(webapp2.RequestHandler):
    def get(self,endpoint=None):
        api_uri = '%sv1/%s?' % (config.API_URL_BASE,endpoint) + urllib.urlencode(self.request.params)
        #logging.info("re-direct %s" % api_uri);
        self.redirect(api_uri);
## end

application = webapp2.WSGIApplication([('/', MainHandler),
                                      ('/loggingtask', EventLoggingHandler),
                                      ('/resetquotas', ResetQuotaHandler),
                                      ('/api', APIDocs),
                                      ('/api/', APIDocs),
                                      ('/api/v1/(.*)', APIRedirectHandler)
                                      ],
                                     debug=True)
