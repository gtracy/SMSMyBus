import logging
import webapp2

from google.appengine.api.taskqueue import Task

import twilio
import config
import paywall
from apps import api_bridge
from apps import meta

class SMSRequestHandler(webapp2.RequestHandler):

  def post(self):

      # validate it is in fact coming from twilio
      if config.ACCOUNT_SID != self.request.get('AccountSid'):
        logging.error("Inbound request was NOT VALID.  It might have been spoofed!")
        self.response.out.write(errorResponse("Illegal caller"))
        return

      # who called? and what did they ask for?
      phone = self.request.get("From")
      msg = self.request.get("Body")
      logging.info("New inbound request from %s with message, %s" % (self.request.get('From'),msg))

      if paywall.isUserValid(phone) is False:
          if paywall.isUserVirgin(phone) is True:
              logging.info('Brand new caller - welcome them')
              paywall.welcomeSolicitor(phone)
          else:
              # ignore caller
              logging.info('We have seen this number before. Ignore this request')
              return

      # interrogate the message body to determine what to do
      if msg.lower().find('parking') > -1:
          response = api_bridge.getparking()
      elif msg.lower().find('help') > -1:
          response = "Bus arrival requests are either, stopID -or- routeID stopID  Send 'parking' to find parking details"
      elif msg.lower().find('stats') > -1:
          response = meta.getStats(phone)
      else:
          ## magic ##
          response = api_bridge.getarrivals(msg,4)
          if len(response) > 140:
              response = response[0:140]

      # create an event to log the request
      task = Task(url='/loggingtask', params={'from':self.request.get('From'),
                                              'to':self.request.get('To'),
                                              'inboundBody':self.request.get('Body'),
                                              'sid':self.request.get('SmsSid'),
                                              'outboundBody':response,})
      task.add('eventlogger')

      # setup the response SMS
      r = twilio.Response()
      r.append(twilio.Sms(response))
      self.response.out.write(r)
      return

## end SMSRequestHandler

# Create a task to send out the invitation SMS
#
def sendInvite(request):

      textBody = "You've been invited to use SMSMyBus to find real-time arrivals for your buses. Text your bus stop to this number to get started.(invited by "
      textBody += request.get('From') + ')'

      # parse the message to extract and format the phone number
      # of the invitee. then create a task to send the message
      smsBody = request.get('Body')
      requestArgs = smsBody.split()
      for r in requestArgs:
          phone = r.replace('(','').replace('}','').replace('-','')
          if phone.isdigit() == True:
            task = Task(url='/admin/sendsmstask', params={'phone':phone,
                                                          'sid':request.get('SmsSid'),
                                                          'text':textBody,})
            task.add('smssender')

      return textBody

## end sendInvite()

application = webapp2.WSGIApplication([('/sms/request', SMSRequestHandler),
                                      ],
                                     debug=True)
