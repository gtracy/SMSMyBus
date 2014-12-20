import logging
import webapp2

from google.appengine.api.taskqueue import Task
from google.appengine.api import xmpp

from apps import api_bridge
from apps import meta

class XmppHandler(webapp2.RequestHandler):

    def post(self):
      message = xmpp.Message(self.request.POST)
      logging.info("XMPP request! Sent form %s with message %s" % (message.sender,message.body))

      # normalize the XMPP requests
      if message.sender.find('@'):
          caller = message.sender.split('/')[0]
      else:
          caller = message.sender.get('from')

      if message.body.lower().find('parking') > -1:
          logging.info('parking request via XMPP')
          response = api_bridge.getparking()
      elif message.body.lower().find('help') > -1:
          response = "Bus arrivals: stopID -or- routeID stopID  Parking: 'parking'  Stats: 'stats'  Help: 'help'"
      elif message.body.lower().find('stats') > -1:
          response = meta.getStats(caller)
      else:
          ## magic ##
          response = api_bridge.getarrivals(message.body,10)
          # to make it a little easier to read, add newlines before each route report line
          response = response.replace('Route','\nRoute')


      # create an event to log the request
      task = Task(url='/loggingtask', params={'from':caller,
                                              'to':message.to,
                                              'inboundBody':message.body,
                                              'sid':'xmpp',
                                              'outboundBody':response,})
      task.add('eventlogger')

      # reply to the chat request
      message.reply(response)

## end XmppHandler()

application = webapp2.WSGIApplication([('/_ah/xmpp/message/chat/', XmppHandler),
                                      ],
                                     debug=True)
