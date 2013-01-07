import logging
from datetime import date

from data_model import PhoneLog

from google.appengine.ext import db

def getStats(phone):
    total_requests = 0
    weeks_requests = 0
    months_requests = 0
    stop_requests = dict()
    today = date.today()

    logs = db.GqlQuery("SELECT * FROM PhoneLog WHERE phone = :1", phone).fetch(limit=None)
    for result in logs:
        total_requests += 1

        date_diff = today - result.date.date()
        request_age = date_diff.days

        # compute calls this week
        if request_age < 7:
            weeks_requests += 1

        # compute calls this month
        if request_age < 31:
            months_requests += 1

        # manage stop request frequency
        requestArgs = result.body.split()
        if len(requestArgs) == 1:
            stop = requestArgs[0]
            if len(stop) == 3:
                stop = "0" + stop
        else:
            route = requestArgs[0]
            if len(route) == 1:
                route = "0" + route

            stop = requestArgs[1]
            if len(stop) == 3:
                stop = "0" + stop

        if stop in stop_requests:
            stop_requests[stop] += 1
        else:
            stop_requests[stop] = 1

    logging.debug(stop_requests)
    if stop_requests:
        most_popular = max(stop_requests, key=lambda x: stop_requests[x]) 
    else:
        most_popular = 'unknown'
    result = 'Total: %s  this week: %s, month: %s  Total stops: %s, most popular: %s' % (
        str(total_requests), str(weeks_requests), str(months_requests), str(len(stop_requests)), str(most_popular))

    return result

## end