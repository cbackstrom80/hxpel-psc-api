import os

import hvac

def podusercreate(url, token, username, password):
    client = hvac.Client()
    client = hvac.Client(
     url=url,
     token=token
    )
    client.write('secret/podusers', username=username, password=password, lease='1h')
    print(client.read('secrets/podusers'))

podusercreate("http://10.254.252.117:8200",'bf360f23-1d12-d378-8fe0-087b66c47661',"curtis","Cisco1234!")
