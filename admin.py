import os
import wsgiref.handlers
import logging
from operator import itemgetter
from datetime import date
from datetime import timedelta

from google.appengine.api import mail
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.api.labs.taskqueue import Task
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

from google.appengine.runtime import apiproxy_errors

from data_model import PhoneLog
import twilio
import config

class OutreachHandler(webapp.RequestHandler):
    def get(self):
      user = users.get_current_user()
      if user and users.is_current_user_admin():
          greeting = ("Welcome, %s! (<a href=\"%s\">sign out</a>)" %
                      (user.nickname(), users.create_logout_url("/")))
      else:
          greeting = ("<a href=\"%s\">Sign in</a>." %
                        users.create_login_url("/"))

      total = 0
      callers = []
      logs = db.GqlQuery("SELECT * FROM PhoneLog WHERE date > DATETIME(2012,08,15,0,0,0) ORDER BY date ASC").fetch(limit=None)
      for result in logs:
        if result.phone.find('+1') >= 0:
          try:
            index = callers.index(result.phone)
          except ValueError:
            callers.append(result.phone)

      # add the counter to the template values
      template_values = {'greeting':greeting,
                         'callers':callers,
                         }
        
      # create a page that provides a form for sending an SMS message
      path = os.path.join(os.path.dirname(__file__), 'views/outreach.html')
      self.response.out.write(template.render(path,template_values))

## end

class SendSMSOutreach(webapp.RequestHandler):
    def post(self):
      callers = []
      logs = db.GqlQuery("SELECT * FROM PhoneLog WHERE date > DATETIME(2012,08,15,0,0,0) ORDER BY date ASC").fetch(limit=None)
      for result in logs:
        if result.phone.find('+1') >= 0:
          try:
            index = callers.index(result.phone)
          except ValueError:
            callers.append(result.phone)

      for phone in callers:
        logging.info("Send outreach SMS to %s" % phone)
        account = twilio.Account(config.ACCOUNT_SID, config.ACCOUNT_TOKEN)
        sms = {
               'From' : config.CALLER_ID,
               'To'   : phone,
               'Body' : self.request.get('text'),
               }
        try:
            account.request('/%s/Accounts/%s/SMS/Messages' % (config.API_VERSION, config.ACCOUNT_SID),
                            'POST', sms)
        except Exception, e:
            logging.error("Twilio REST error: %s" % e)


      self.response.out.write('success');

## end

class AdminHandler(webapp.RequestHandler):
    def get(self):
      user = users.get_current_user()
      if user and users.is_current_user_admin():
          greeting = ("Welcome, %s! (<a href=\"%s\">sign out</a>)" %
                      (user.nickname(), users.create_logout_url("/")))
      else:
          greeting = ("<a href=\"%s\">Sign in</a>." %
                        users.create_login_url("/"))
              
      # do some analysis on the request history...
      total = 0
      callers = dict()
      reqs = dict()
      cursor = None
      # Start a query for all Person entities.
      q = PhoneLog.all()
      while q is not None:
          # If the app stored a cursor during a previous request, use it.
          if cursor:
              q.with_cursor(cursor)

          logQuery = q.fetch(500)
          cursor = q.cursor()
          if len(logQuery) > 0:
            total += len(logQuery)
            logging.debug('parsing log entries %s' % total)
            for e in logQuery:
                if e.phone in callers:
                    callers[e.phone] += 1
                else:
                    callers[e.phone] = 1
                    
                # add up all of the unique stop IDs
                requestString = e.body.split()
                if len(requestString) >= 2:
                    stopID = requestString[1]
                elif len(requestString) > 0:
                    stopID = requestString[0]
                    
                if len(requestString) > 0 and stopID.isdigit() and len(stopID) == 4:
                    if stopID in reqs:
                        reqs[stopID] += 1
                    else:
                        reqs[stopID] = 1
          else:
              logging.debug('nothing left!')
              break

      # review the results and generate the data for the template
      caller_stats = []
      sorted_callers = callers.items()
      sorted_callers.sort(key=itemgetter(1),reverse=True)
      for key,value in sorted_callers:
          caller_stats.append({'caller':key,
                               'counter':value,
                             })
      uniques = len(sorted_callers)
      
      # display some recent call history
      results = []
      q = db.GqlQuery("SELECT * FROM PhoneLog ORDER BY date DESC")
      logQuery = q.fetch(30)
      if len(logQuery) > 0:
          for r in logQuery:
              results.append({'phone':r.phone,
                              'body':r.body,
                              'outboundSMS':r.outboundSMS,
                              'date':r.date,})
      else:
          results.append({'phone':'empty',
                          'body':'empty',
                          'outboundSMS':'empty',
                          'date':'empty',})
          logging.error("We couldn't find any history!?!")

      # add the counter to the template values
      template_values = {'greeting':greeting,
                         'total':total,
                         'uniques':uniques,
                         'callers':caller_stats,
                         'events':results,
                         }
        
      # create a page that provides a form for sending an SMS message
      path = os.path.join(os.path.dirname(__file__), 'views/admin.html')
      self.response.out.write(template.render(path,template_values))
    
## end AdminHandler()

class SMSResponseHandler(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        if user and users.is_current_user_admin():
            phone = self.request.get('phone')
            text = self.request.get('text')
            logging.debug("the admin console is sending and SMS to %s with the message, %s" % (phone,text))
      
            # log the event...
            task = Task(url='/loggingtask', params={'from':phone,
                                                    'to':phone,
                                                    'inboundBody':text,
                                                    'sid':'admin request',
                                                    'outboundBody':text,})
            task.add('eventlogger')
            
            # send the SMS out...
            task = Task(url='/admin/sendsms', params={'phone':phone,
                                                    'sid':'admin console',
                                                    'text':text,})
            task.add('smssender')

            return('Sent!')
        elif user:
            logging.error("illegal access to the admin console for sending sms messages!?! %s" % user.email())
            return('Not so fast!')
            
## end

class Histogram(webapp.RequestHandler):
    def get(self):
      histogram = dict()
      output = ''
      
      startDate = date.today() - timedelta(days=7)
      endDate = date.today()
      for i in range(1,51):
          week = 'week'+str(i)
          s = startDate.isoformat()
          e = endDate.isoformat()
          logging.debug('checking between '+s+' and '+e)
          q = db.GqlQuery("SELECT * FROM PhoneLog WHERE date > DATE(:1) and date <= DATE(:2)", s,e)
          #q = db.GqlQuery("SELECT * FROM PhoneLog WHERE date >= DATE(:1)", s)
          result = q.fetch(500)
          weeklyCount = len(result)
          histogram[week] = weeklyCount
          output += '<p>'+str(i)+':'+str(weeklyCount)+'</p>'
          logging.debug('week '+str(i)+' had '+str(weeklyCount)+' requests')
          
          # bump the dates backwards
          #runningTotal = len(result)
          endDate = startDate
          startDate = endDate - timedelta(days=7)
          
      self.response.out.write(output)
## end 

class NormalizeLogHandler(webapp.RequestHandler):
    def get(self):
      callers = {}
      cursor = None
      
      q = PhoneLog.all()
      while q is not None:
          # If the app stored a cursor during a previous request, use it.
          if cursor:
              q.with_cursor(cursor)

          logQuery = q.fetch(500)
          cursor = q.cursor()
          if len(logQuery) > 0:
            for e in logQuery:
                if e.phone.find('@gmail.com') > 0:
                    caller = e.phone.split('/')[0]
                    logging.debug('truncating %s to %s' % (e.phone,caller))
                    if caller not in callers:
                        callers[caller] = 1
                    e.phone = caller
                    e.put()
          else:
              logging.debug('nothing left!')
              break

## end

class CleanLogHandler(webapp.RequestHandler):
    def get(self, the_id=""):
        the_id = 'request@smsmybus.com'
        logging.debug('cleaning all phonelog entries from %s' % the_id)
        q = db.GqlQuery("select __key__ from PhoneLog where phone = :1", the_id)
        entries = q.fetch(500)
        offset = 500
        while len(entries) > 0:
            db.delete(entries)
            entries = q.fetch(500, offset)
            offset += 500
            
        self.response.out.write('done deleting %s entries from %s' % (str(offset-501),the_id))
        
## end

# this handler is intended to send out SMS messages
# via Twilio's REST interface
class SendSMSHandler(webapp.RequestHandler):
    def get(self):
      self.post()
      
    def post(self):
      logging.info("Outbound SMS for ID %s to %s" % 
                   (self.request.get('sid'), self.request.get('phone')))
      account = twilio.Account(config.ACCOUNT_SID, config.ACCOUNT_TOKEN)
      sms = {
             'From' : config.CALLER_ID,
             'To' : self.request.get('phone'),
             'Body' : self.request.get('text'),
             }
      try:
          account.request('/%s/Accounts/%s/SMS/Messages' % (config.API_VERSION, config.ACCOUNT_SID),
                          'POST', sms)
      except Exception, e:
          logging.error("Twilio REST error: %s" % e)

      self.response.out.write('success');
                        
## end SendSMSHandler


application = webapp.WSGIApplication([('/admin.html', AdminHandler),
                                      ('/admin/outreach', OutreachHandler),
                                      ('/admin/sendsmstask', SMSResponseHandler),
                                      ('/admin/sendsms', SendSMSHandler),
                                      ('/admin/sendoutreach', SendSMSOutreach),
                                      ('/admin/histogram', Histogram),
                                      ('/admin/phonelog/clean/(.*)', CleanLogHandler),
                                      ('/admin/phonelog/normalize', NormalizeLogHandler),
                                      ],
                                     debug=True)

def main():
  logging.getLogger().setLevel(logging.DEBUG)
  run_wsgi_app(application)
  #wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
