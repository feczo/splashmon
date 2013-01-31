# The MIT License
#
# Copyright (c) 2008 William T. Katz
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.


__author__ = 'James Polley'

import os
import sys
import logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'contrib'))

import appengine_config # Make sure this happens

from django.conf import settings

from google.appengine.api import memcache

from google.appengine.api import xmpp
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import xmpp_handlers

from models import List, Service, Status, Event, Image, Profile, Subscription, Mobile
from utils import authorized
from mobile import smsgw

import hashlib

from google.appengine.api import users


class XMPPPresenceHandler(webapp.RequestHandler):
    def post(self, presence):
        from_jid = self.request.get('from').split('/')[0]
        def txn():
            user = Subscription.get_by_email(from_jid)
            if user:
		if presence == "probe":
			return xmpp.send_presence(from_jid, presence_type=xmpp.PRESENCE_TYPE_PROBE)
		else:
	                user.status = presence
        	        return user.put()
            #else:
            #    return Subscription(key_name=hashlib.sha1( from_jid).hexdigest(), address=from_jid, status=presence).put()
        db.run_in_transaction(txn)
        return

class XMPPSubscriptionHandler(webapp.RequestHandler):
    def post(self, subscription):
        from_jid = self.request.get('from').split('/')[0]
        is_friend = False
        if subscription == "subscribe" or subscription == "subscribed":
            is_friend = True
        def txn():
            user = Subscription.get_by_email(from_jid)
            if user:
                user.is_friend = is_friend
                return user.put()
            else:
                return Subscription(key_name=hashlib.sha1(from_jid).hexdigest(),
                                  address=from_jid, is_friend=is_friend).put()
        db.run_in_transaction(txn)
        return


class FirstWordHandlerMixin(xmpp_handlers.CommandHandlerMixin):
    """Just like CommandHandlerMixin but assumes first word is command."""

    def message_received(self, message):
        if message.command:
            super(FirstWordHandlerMixin, self).message_received(message)
        else:
            user = message.sender.split('/')[0]
	    if user in settings.XMPP_FILTER:
                command = message.body.split(' ')[0]
                handler_name = '%s_command' % (command,)
                handler = getattr(self, handler_name, None)
                if handler:
                    handler(message)
                else:
                    message.reply ("Unknown command, try 'help'")

            else:
        	message.reply("Unauthorized!")
		
class FirstWordHandler(FirstWordHandlerMixin, xmpp_handlers.BaseHandler):
    """A webapp implementation of FirstWordHandlerMixin."""
    pass

class TestSMS(webapp.RequestHandler):
	def get(self):
		sms = smsgw(to = "+61431461200", msg = "AppEngine Test")
		sms.send()
		
class TestXMPP(webapp.RequestHandler):
    def get(self):
        if users.get_current_user() is None:
            self.redirect(users.create_login_url(         self.request.uri))
            return 
           
        user_address = users.get_current_user().email()
        user = Subscription.get_by_email(user_address)
	if user.address in settings.XMPP_FILTER:
            if user.status == "available":
                xmpp.send_message(user_address, "test msg")
                self.response.out.write("A message sent.")
            elif user.status == "unavailable":
                self.response.out.write("The user is offline.")
	    else:
		self.response.out.write("unkown status: %" % user.status)
        else:
            xmpp.send_invite(user_address)
            self.response.out.write("An invitation sent.")



class XmppNotificationHandler(webapp.RequestHandler):
    """Handle notifications via XMPP"""

    def post(self):
        """Notify subscribers that a service changed status."""

        address = self.request.get('address')
        service = Service.get(self.request.get('service'))
        oldstatus = Status.get(self.request.get('oldstatus'))
        number = self.request.get('number')

        logging.info("Service: %s" % service)
        logging.info("Service name: %s" % service.name)

        msg = "%s changed state from %s to %s (%s)" % (
                service.name, oldstatus.name,
                service.current_event().status.name,
                service.current_event().message)

        user = Subscription.get_by_email(address)
        if user.status == "available" or not number:
        	status_code = xmpp.send_message(address, msg)
    		chat_message_sent = (status_code == xmpp.NO_ERROR)
		logging.info("Notified: %s\nmessage: %s code: %d" % (address, msg, status_code))
        elif user.status == "unavailable" and number:
		sms = smsgw(to = number, msg = msg)
		sms.send()
		logging.info("Offline SMS: %s\nmessage: %s" % (number, msg))


class XmppHandler(FirstWordHandler):
    """Handler class for all XMPP activity."""

    def service_command(self, message=None):
        """Change status of a service"""
        _, service_name = message.body.split(' ', 1)
        service = Service.all().filter('name = ', service_name).get()

        if service:
            return_msg =["Name: %s" % service.name]
            return_msg.append("Description: %s" % service.description)
            return_msg.append("Recent events:")
            events = service.events.order('-start').run(limit=3)
            for event in events:
                return_msg.append("%s: %s: %s" % (
                        event.start, event.status.name, event.message))
        else:
            return_msg = ["Cannot find service with name: %s" % service_name]

        return_msg = "\n".join(return_msg)
        message.reply(return_msg)

    def services_command(self, message=None):
        """List all services"""
        return_msg = []

        for service in Service.all():
            event = service.current_event()
            if event:
                return_msg.append("%s: %s: %s" % (
                        service.name, event.status.name, event.message))
            else:
                return_msg.append("%s has no events" % service.name)

        return_msg = '\n'.join(return_msg)

        message.reply(return_msg)

    def help_command(self, message=None):
        """Help service"""

        return_msg =["services - list services"]
	return_msg.append("service SERVICE - details about SERVICE")
	return_msg.append("sub SERVICE - get notified status changes of SERVICE")
	return_msg.append("sub SERVICE +61412345678 - same as above but sends SMS if chat presence is offline")
	return_msg.append("sms SERVICE +61412345678 - always get sms notifications on changes of SERVICE")
	return_msg.append("unsub SERVICE - cancel notifications about SERVICE")

        return_msg = "\n".join(return_msg)
        message.reply(return_msg)

    def addservice_command(self, message=None):
        """Create a new service"""

        service_name = message.body.split(' ')[1]
        service = Service(key_name=service_name, name=service_name)
        service.put()

        message.reply("Added service %s" % service_name)


    def sms_command(self, message=None):
        """Subscribe the user to a offline SMS"""

        plist = message.body.split(' ')
	if len(plist)==3:
	        user = message.sender.split('/')[0]
	 	service_name = plist[1]
	 	number = plist[2]
	
	        service = Service.all().filter('name = ', service_name).get()
	
	        if service:
		 	subscription = Subscription.all().filter('address =', user).filter('service = ', service).get()
		
		        if subscription:
		            mobile = Mobile.all().filter('number =', number).get()
		            if mobile:
		                message.reply("user %s is already registered backup mobile %s for service %s" % (user, mobile.number,service_name))
		            else:
		                mobile = Mobile(number=number, subscription = subscription)
		                mobile.put()
		                message.reply("Subscribed user %s to backup mobile %s for service %s" % (user, number,service_name))
		        else:
		            message.reply("Sorry, I couldn't find a subscription on %s for %s" % (service_name,user))
	        else:
	            message.reply("Sorry, I couldn't find a service called "
	                          "%s" % service_name)
	else:
		message.reply("Usage: sms SERVICE +61412345678")

    def sub_command(self, message=None):
        """Subscribe the user to XMPP or SMS"""
        user = message.sender.split('/')[0]
	
        plist = message.body.split(' ' )
 	service_name = plist[1]

	if len(plist)>2:
	    type = "sms"
            user = plist[2]
	else:
	    type = "xmpp"
		
        service = Service.all().filter('name = ', service_name).get()

        if service:
            subscription = Subscription.all().filter('address =', user).filter('service = ', service).get()
            if subscription:
                message.reply("user %s is already subscribed to service %s" % (user, service.name))
            else:
                subscription = Subscription(key_name=hashlib.sha1(user).hexdigest(), type=type, address=user, service=service)
                subscription.put()
                message.reply("Subscribed %s to service %s" % (user, service.name))
        else:
            message.reply("Sorry, I couldn't find a service called "
                          "%s" % service_name)

    def unsms_command(self, message=None):
        """Unsubscribe the user from a service"""
	plist = message.body.split(' ')
	if len(plist)==2:
	        user = message.sender.split('/')[0]
	
	        service_name = plist[1]
	
	        service = Service.all().filter('name = ', service_name).get()
	
	        if service:
		    subscription = Subscription.all().filter('address =', user).filter('service = ', service).get()
		
		    if subscription:
	            	mobile = Mobile.all().filter('subscription = ', subscription).get()
	            	if mobile:
		    	    message.reply("Unsubscribed user %s from backup mobile %s for service %s" % (user, mobile.number,service_name))
	            	    mobile.delete()
			else:
			    message.reply("No backup mobile for user %s on %s service" % (user,service_name))
	 	    else:
	            	message.reply("User %s is not subscribed to service %s" % (user, service.name))
	        else:
	            message.reply("Sorry, I couldn't find a service called "
                          "%s" % service_name)
	else:
		 message.reply("Usege: unsms SERVICE +6112345678")

    def unsub_command(self, message=None):
        """Unsubscribe the user from a service"""
        user = message.sender.split('/')[0]

        plist = message.body.split(' ' )
        service_name = plist[1]

	if len(plist)>2:
	    type = "sms"
            user = plist[2]
	else:
	    type = "xmpp"
		
        service = Service.all().filter('name = ', service_name).get()

        if service:
            subscription = Subscription.all().filter('address =', user).filter('service = ', service).filter('type =', type).get()
            if subscription:
                subscription.delete()
		if type == "xmpp":
	            	mobile = Mobile.all().filter('subscription = ', subscription).get()
			if mobile:
				mobile.delete()
                message.reply("Unsubscribed %s from service %s" % (user, service.name))
            else:
                message.reply("user %s is not subscribed to service %s" % (user, service.name))
        else:
            message.reply("Sorry, I couldn't find a service called "
                          "%s" % service_name)
