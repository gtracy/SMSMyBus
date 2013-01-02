import logging
from datetime import date
from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.api.taskqueue import Task

from data_model import PhoneLog

def getKey(phone):
	return 'paywall-user-%s' % phone

# memcache the new user to mark it as payed and valid
def validateUser(user):
   	memcache.set(getKey(user.phone), 1)

# invalidate a user by removing it from the memcache
def invalidateUser(phone):
	memcache.set(getKey(phone), -1)

def isUserValid(phone):
	valid = memcache.get(getKey(phone))
	logging.info('Paywall lookup... %s' % str(valid))
	if valid is None:
		q = db.GqlQuery("select * from Caller where phone = :1 and expires >= :2", phone, date.today())
		user = q.get()
		if user is None:
			logging.debug('cannot find user in db')
			invalidateUser(phone)
			return False
		else:
			logging.debug('found user in db. now validate %s' % getKey(user.phone))
			validateUser(user)
			return True
	elif valid < 0:
		return False
	else:
		return True

## end isUserValid()

def isUserVirgin(phone):
	q = db.GqlQuery("select * from PhoneLog where phone = :1 and date > DATE('2012-12-31')", phone)
	user = q.get()
	if user is None:
		return True
	else:
		return False

## end isUserVirgin()

def welcomeNewUser(phone):
	# welcome the new user with an SMS message
	welcome_message = "Welcome to SMSMyBus. You're account is now active! Just send in a stop ID to find your bus."
	task = Task(url='/admin/sendsms', 
		        params={'phone':user_phone,
	                    'sid':'new user',
	                    'text':welcome_message
	                    })
	task.add('smssender')


def welcomeSolicitor(phone):
	# welcome the new user with an SMS message
	welcome_message = "Welcome to SMSMyBus! These results are complimentary, but going forward you will need to signup. Please visit smsmybus.com to learn more."
	task = Task(url='/admin/sendsms', 
		        params={'phone':phone,
	                    'sid':'complimentary results',
	                    'text':welcome_message
	                    })
	task.add('smssender')
