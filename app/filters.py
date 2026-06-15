from flask import Markup
from datetime import datetime
from pytz import timezone, utc

pkt = timezone("Asia/Karachi")

def localtime(value):
    """Convert a UTC datetime to Pakistan Standard Time."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=utc).astimezone(pkt).strftime('%Y-%m-%d %I:%M %p')
    return value
