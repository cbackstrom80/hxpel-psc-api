import json
import time
import prettyprint

from ucsmsdk.ucshandle import UcsHandle

handle = UcsHandle("172.20.1.10", "admin", "Cisco1234!")

handle.login()
from util.ignwslack import slacknotify

compute_rack_unit = handle.query_classid("ComputeRackUnit")
pos = "NodesReady"
neg = "NodesNotReady"

def checkassoc(num_assoc):
    counter = 0
    for a in compute_rack_unit:
        if compute_rack_unit[0].association == "associated":
            counter += 1
    if counter == num_assoc:

        slacknotify(pos)
        return pos
    else:
        slacknotify(neg)
        return neg


def checkstatus(num):
        while  neg in checkassoc(num):
            time.sleep(5)
            checkassoc(num)


def getpods():
    from ucsmsdk.ucshandle import UcsHandle

    handle = UcsHandle("172.20.1.10", "admin", "Cisco1234!")

    handle.login()

    obj = handle.query_classid("ComputeRackUnit")

    pods = {}
    pods['compute'] = []


    for server in obj:
        pods['compute'].append({
            "ServerName": server.rn,
            "Serial": server.serial,
            "Model": server.model
        })


    return pods
    handle.logout()









