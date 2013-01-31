import os

DEBUG = False

SITE_NAME = "Monitor"
SITE_AUTHOR = "Sub Master"
SITE_URL = "https://splashmon.appspot.com/"
REPORT_URL = "/tracker?action=submit"

# Twitter update settings
TWITTER_CONSUMER_KEY = ''
TWITTER_CONSUMER_SECRET = ''
TWITTER_ACCESS_TOKEN = ''
TWITTER_ACCESS_TOKEN_SECRET = ''
TWITTER_HANDLE = ''

# RSS Feed settings
RSS_NUM_EVENTS_TO_FETCH = 50

# OAuth Consumer Credentials
CONSUMER_KEY = 'anonymous'
CONSUMER_SECRET = 'anonymous'

TEMPLATE_DIRS = (
    os.path.join(os.path.dirname(__file__), "templates"),
    )


XMPP_FILTER = ["monitoring_user@interested.com","another_authorized_xmp@user.com"]
SMS_USER = "sms@user.com"
SMS_PASS = "secret"
SMS_PROVIDER = "fcent"
