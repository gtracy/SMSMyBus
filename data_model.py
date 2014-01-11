from google.appengine.ext import db

class PhoneLog(db.Model):
  phone       = db.StringProperty()
  to          = db.StringProperty(multiline=True)
  date        = db.DateTimeProperty(auto_now_add=True)
  body        = db.StringProperty(multiline=True,indexed=False)
  smsID       = db.StringProperty(indexed=False)
  outboundSMS = db.StringProperty(multiline=True,indexed=False)
## end


class Caller(db.Model):
	# caller's phone number requests are sent from
	phone   = db.StringProperty(indexed=True)
    # the SMB service number Caller has permission to use
	service = db.StringProperty()
	
	created = db.DateProperty(auto_now_add=True)
	expires = db.DateProperty()
## end
