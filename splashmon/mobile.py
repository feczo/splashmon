import urllib
import urllib2
import socket

from google.appengine.api import urlfetch
from google.appengine.api.urlfetch import DownloadError

from google.appengine.ext import db
from datetime import datetime, timedelta, date
import urllib
from django.conf import settings

__author__ = 'Szabolcs Feczak'

# SMS gateway oclass
	# usage:
	# sms = smsgw()
	# sms.to = "+6112345678"
	# sms.msg = "Hellothere"
	# sms.send()
		
class smsgw(object):
	def __init__( self, **kw):
		self.to = None
		self.msg = None
		self.__dict__.update(kw)
		del kw # We don't want this in attrs
		self.__dict__.update(locals())
		del self.self # We don't need this either
	def send(self):
		eval("self."+settings.SMS_PROVIDER+"()")
	def fcent(self):
		print "Sending " + self.to + " (" + self.msg + ")..."
		msg=urllib.quote_plus(self.msg)
		url = "http://www.5centsms.com.au/api/send.jsp?username=%s&password=%s&to=%s&message=%s&sender=%s" % (settings.SMS_USER,settings.SMS_PASS,self.to,msg,"SplashMon")
		
		try:
			result = urlfetch.fetch(url, headers = {'Cache-Control' : 'max-age=30'}, deadline=30 )
			
		except urlfetch.Error:
			print "SMS fetch error"
		
		except DownloadError:
			print "SMS sending Failed, no reply"
			
		else:
			if result.status_code == 500:
				print "SMS sending Failed with 500 error from the provider ..."
			else:
				print "SMS sending succeeded"

		
