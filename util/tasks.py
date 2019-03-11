
from config import settings
import time
from util.assoc import *
from ucs.ucs_controller import UcsClusterController


def reinstallesx(pod_num):
    """TASK RO REDEPLOY ESX ON POD HX SERVERS"""
    # TODO: Make sure that this function receives the podnum arg
    ucc = UcsClusterController(settings['ucs'], pod_id)
    # Discover UCS Servers
    print("Discovering UCS Servers")
    ucc.enablerautoconfigureports()

    # EXEC FUNCTION to create SP TO CLEANUP UCS
    print("Cleaning up ORGs")
    ucc.createcleanupsp()
    checkstatus(0)
    time.sleep(600)

    # EXEC Function to create  SP to delete MGMT VLAN
    print("Cleaning UP VLANS")
    ucc.deletevlan()

    time.sleep(10)

    # EXEC FUNCTION TO CREATE AND DESTROY THE "SCRUB" Service profile

    print("Initiating Scrub")
    ucc.createscrubsp()
    checkstatus(4)
    time.sleep(600)

    # EXEC FUNCTION to create SP TO CLEANUP UCS
    print("Cleaning up ORGs")
    ucc.createcleanupsp()
    checkstatus(0)
    time.sleep(600)

    # EXEC Function to create  SP to delete MGMT VLAN
    print("Cleaning UP VLANS")
    ucc.deletevlan()
    time.sleep(10)

    # EXEC Function to Create SP TO Install ESX from Custom ESX IMage VIA HTTP

    print("Reinstalling ESX Operating System on all HX Nodes")
    ucc.createhxesxinstallsp()
    checkstatus(4)
    time.sleep(3600)

    # EXEC FUNCTION to create SP TO CLEANUP UCS
    ucc.createcleanupsp()
    checkstatus(0)
    time.sleep(600)

    # EXEC Function to create  SP to delete MGMT VLAN
    ucc.deletevlan()
    time.sleep(10)
