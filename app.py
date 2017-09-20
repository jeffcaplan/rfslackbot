from config import config
from flask import Flask, Response, request, jsonify, abort, copy_current_request_context
import json
import os
import re
import sys
from threading import Thread
import time
import urllib.request

app = Flask(__name__)

SLACK_TOKEN = config.get('slack_token')
RF_TOKEN = config.get('rf_token')

@app.route('/slack', methods=['POST'])
def inbound():
    # Parse the parameters & validate Slack token
    token = request.form.get('token', None)
    if not token:
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
                stats = res['stats']['stats']
                firstSeen = stats['first']['published']
                lastSeen = stats['mostRecent']['published']
                data = res['stats']['metrics']
                crit = data.get('criticality')
                if(crit == 1):
                    criticality = "Low"
                    color = "#61C359"
                elif(crit == 2):
                    criticality = "Important"
                    color = "#DFE125"
                elif(crit == 3):
                    criticality = "Critical"
                    color = "#E15025"
                else:
                    criticality = str(data.get('criticality'))
                    color ="#000000"
                totalHits = int(data.get('totalHits'))
                riskScore = data.get('riskScore')
                maliciousHits = data.get('maliciousHits')
                if not data.get('darkWebHits'):
                    darkWebHits = 0
                else:
                    darkWebHits = data.get('darkWebHits')
                sevenDayHits = data.get('sevenDaysHits')
                oneDayHits = data.get('oneDayHits')

                payload = json.dumps({
                    'attachments': [
                    {
                        'fallback': '<https://www.recordedfuture.com/live/sc/entity/' + entity + '|Recorded Future API Response.>',
                        'color': color,
                        'pretext': 'Here are your results:',
                        'author_name': queryString,
                        'title': 'Recorded Future Connect API Search Results',
                        'title_link': 'https://www.recordedfuture.com/live/sc/entity/' + entity,
                        'text': 'Total Hits:  ' + str(totalHits),
                        "fields": [
                        {
                            "title": "Criticality",
                            "value": criticality,
                            "short": "true"
                        },
                        {
                            "title": "Risk Score:",
                            "value": riskScore,
                            "short": "true"
                        },
                        {
                            "title": "Malicious Hits",
                            "value": maliciousHits,
                            "short": "true"
                        },
                        {
                            "title": "Dark Web Hits:",
                            "value": darkWebHits,
                            "short": "true"
                        },
                        {
                            "title": "7-day Hits (Total):",
                            "value": sevenDayHits,
                            "short": "true"
                        },
                        {
                            "title": "1-day Hits (Total):",
                            "value": oneDayHits,
                            "short": "true"
                        },
                        {
                            "title": "First Seen:",
                            "value": firstSeen,
                            "short": "true"
                        },
                        {
                            "title": "Last Seen:",
                            "value": lastSeen,
                            "short": "true"
                        },
                        ],
                        "footer": "Recorded Future",
                        "footer_icon": "https://media.licdn.com/mpr/mpr/shrink_200_200/AAEAAQAAAAAAAAOnAAAAJDJjOGE4Mzk4LWMwMDktNGY1OC05NTNmLTBlNDVhNjllYjcxZg.png",
                        "ts": time.time()
                    }
                    ]
                }).encode('utf8')

        req = urllib.request.Request(response_url, data=payload, headers={'content-type': 'application/json'})
        response = urllib.request.urlopen(req)

    # Determine if queryString is an IP address or domain name
    if re.match("^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$", queryString):
        entity = "ip:" + queryString
        data_group = "IpAddress"
    elif re.match("^(([a-zA-Z]|[a-zA-Z][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z]|[A-Za-z][A-Za-z0-9\-]*[A-Za-z0-9])$", queryString):  # TODO: Implement better REGEX for handling of possible domain names
        entity = "idn:" + queryString
        data_group = "InternetDomainName"
    else:
        return "Invalid query detected. Current support only includes individual IP addresses and domain names."

    # Call the RF API query function in another thread, so we can reply to Slack within 3000ms
    t = Thread(target=queryRF)
    t.start()
    return "Querying Recorded Future API.  Please wait..."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
