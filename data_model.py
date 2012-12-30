from google.appengine.ext import db

class PhoneLog(db.Model):
  phone       = db.StringProperty()
  to          = db.StringProperty()
  date        = db.DateTimeProperty(auto_now_add=True)
  body        = db.StringProperty(multiline=True,indexed=False)
  smsID       = db.StringProperty(indexed=False)
  outboundSMS = db.StringProperty(multiline=True,indexed=False)
