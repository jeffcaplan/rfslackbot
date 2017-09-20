from config import config
from flask import Flask, Response, request, jsonify, abort, copy_current_request_context
import json
import os
import re
import sys
from threading import Thread
import urllib.request

app = Flask(__name__)

SLACK_TOKEN = config.get('slack_token')
RF_TOKEN = config.get('rf_token')

@app.route('/slack', methods=['POST'])
def inbound():
    # Parse the parameters
    token = request.form.get('token', None)
    if not token:  # or token is incorrect
        abort(400)
    if token != SLACK_TOKEN:
        return Response('Invalid token.'), 403

    queryString = request.form.get('text', None)
    response_url = request.form.get('response_url', None)

    # Build the RF query, submit the query, prepare the data and send back to Slack
    @copy_current_request_context
    def queryRF():
        from RFAPI3 import RFAPI
        # Build the RF query string
        q = {
            'cluster': {
                'attributes': [
                {
                    'entity': { 'id': entity }
                } ],
                'limit': 1,
                'data_group': data_group },
            'output': {
                'inline_entities': True } }

        # Query RF API
        rfqapi = RFAPI(RF_TOKEN)
        result = rfqapi.query(q) # TODO: implement error-handling in case of bad response from RF

        if((result['count']['events']['returned']) == 0):
            payload = json.dumps({
                'text': 'There were no hits for ' + queryString
            }).encode('utf8')
        else:
            # Prepare and send RF API query response metrics & Connect API URL to Slack
            for res in result['events']:
                data = res['stats']['metrics']
                metrics = "RF Metrics for " + queryString + ":\n"
                metrics += "\tTotal Hits: " + str(data.get('totalHits')) + '\n'
                metrics += "\tCriticality: " + str(data.get('criticality')) + '\n'
                metrics += "\tRisk Score: " + str(data.get('riskScore')) + '\n'
                metrics += "\tDark Web Hits: " + str(data.get('darkWebHits')) + '\n'
                metrics += "\tSeven Day Hits: " + str(data.get('sevenDaysHits')) + '\n'
                metrics += "\tOne Day Hits: " + str(data.get('oneDayHits'))
                payload = json.dumps({
                    'attachments': [
                    {
                        'fallback': '<https://www.recordedfuture.com/live/sc/entity/' + entity + '|Recorded Future API Response.>',
                        'pretext': 'Here are your results:',
                        'color': '#36a64f',
                        'title': 'Recorded Future Connect API URL',
                        'title_link': 'https://www.recordedfuture.com/live/sc/entity/' + entity,
                        'thumb_url': 'https://www.recordedfuture.com/assets/google-results-logo.png',
                        'text': metrics
                    }
                    ]
                }).encode('utf8')

        req = urllib.request.Request(response_url, data=payload, headers={'content-type': 'application/json'})
        response = urllib.request.urlopen(req)

    # Determine if queryString is an IP address or domain name and call RF query function in another thread, so we can reply to the Slack API in time
    if re.match("^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$", queryString):
        entity = "ip:" + queryString
        data_group = "IpAddress"
        t = Thread(target=queryRF)
        t.start()
        return "Querying Recorded Future API for IP address: " + queryString + "\nPlease wait..."
    elif re.match("^(([a-zA-Z]|[a-zA-Z][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z]|[A-Za-z][A-Za-z0-9\-]*[A-Za-z0-9])$", queryString):  # TODO: Implement better REGEX for handling of possible domain names
        entity = "idn:" + queryString
        data_group = "InternetDomainName"
        t = Thread(target=queryRF)
        t.start()
        return "Querying Recorded Future API for Domain: " + queryString + "\nPlease wait..."
    else:
        return "Invalid query detected. Current support only includes IP addresses or domain names."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
