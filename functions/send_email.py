from datetime import datetime
import requests

from private_data/private_data import *


today_date = str(datetime.now(tz=None))

def send_lotto_update_email(email_body):
    return requests.post(
        mailgun_post_url,
        auth=("api", mailgun_API_key),
        data={"from": mailgun_from_email,
            "to": [mailgun_to_email, mailgun_to_email],
            "subject": "IL Lotto ROI for " + today_date,
            "text": email_body })
