This is a little proof-of-concept slackbot (slash command) which queries the Recorded Future RAW API
for threat intelligence summaries for either IP addressess or domain names.

This particular code supports a Heroku deploment.

Slack API & Recorded Future API Tokens are stored as enviornment variables.

ToDos:
 This wasn't intended to be anything fancy, but I may extend this code sample a little bit to include:
  - enable searches for multiple  indicators with multple results
  - increase the types of indicators able to be queried, to include hash values and threat groups
  - expanded the summary results to include additional data or options for a verbose or quiet results type
  - add a help function
