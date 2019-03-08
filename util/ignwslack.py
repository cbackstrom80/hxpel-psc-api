import json
import requests


def slacknotify(message):
      # Set the webhook_url to the one provided by Slack when you create the webhook at https://my.slack.com/services/new/incoming-webhook/
      webhook_url = 'https://hooks.slack.com/services/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'
      slack_data = {'text': message}
      try:
          response = requests.post(
              webhook_url, data=json.dumps(slack_data),
              headers={'Content-Type': 'application/json'}
          )
      except:
          if response.status_code != 200:
              raise ValueError(
                  'Request to slack returned an error %s, the response is:\n%s'
                  % (response.status_code, response.text)
              )