import os
from celery import Celery
import time

from esxinstall import *
from vsphere import *
from ucs_controller import UcsClusterController
from config import settings


CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379'),
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379')

celery = Celery('tasks', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)


@celery.task(name='tasks.esxinstall')
def esxinstall(podnum) -> None:
    """TASK RO REDEPLOY ESX ON POD HX SERVERS"""
    # TODO: Make sure that this function receives the podnum arg
    ucc = UcsClusterController(settings['ucs'], podnum)
    # Discover UCS Servers
    print("Discovering UCS Servers")
    ucc.enablerautoconfigureports()



    # EXEC FUNCTION to create SP TO CLEANUP UCS
    print("Cleaning up ORGs")
    ucc.createcleanupsp()
    time.sleep(600)

    # EXEC Function to create  SP to delete MGMT VLAN
    print("Cleaning UP VLANS")
    ucc.deletevlan()
    time.sleep(10)

    # EXEC FUNCTION TO CREATE AND DESTROY THE "SCRUB" Service profile

    print("Initiating Scrub")
    ucc.createscrubsp()
    time.sleep(600)

    # EXEC FUNCTION to create SP TO CLEANUP UCS
    print("Cleaning up ORGs")
    ucc.createcleanupsp()
    time.sleep(600)

    # EXEC Function to create  SP to delete MGMT VLAN
    print("Cleaning UP VLANS")
    ucc.deletevlan()
    time.sleep(10)

    # EXEC Function to Create SP TO Install ESX from Custom ESX IMage VIA HTTP

    print("Reinstalling ESX Operating System on all HX Nodes")
    ucc.createhxesxinstallsp()
    time.sleep(3600)

    # EXEC FUNCTION to create SP TO CLEANUP UCS
    ucc.createcleanupsp()
    time.sleep(600)

    # EXEC Function to create  SP to delete MGMT VLAN
    ucc.deletevlan()
    time.sleep(10)


@celery.task(name='tasks.redeployall')
def redeployall(podnum) -> None:
    """Re-deploys everything"""

    # DO THE VCENTER TASKS
    vcdeploy(podnum)

    # LICENSE VCENTER
    podvc = settings['podvc']
    vspherelicense(podvc['ip'], podvc['username'], podvc['password'])

    # DO The HX TASKS
    hxdeploy(podnum)

    # DO THE UCS TASKS
    ucc = UcsClusterController(settings['ucs'], podnum)

    # Discover UCS Servers
    print("Discovering UCS Servers")
    ucc.enablerautoconfigureports()

    # EXEC FUNCTION to create SP TO CLEANUP UCS
    print("Cleaning up ORGs")
    ucc.createcleanupsp()
    time.sleep(10)

    # EXEC Function to create  SP to delete MGMT VLAN
    print("Cleaning UP VLANS")
    ucc.deletevlan()
    time.sleep(10)

    # Call Function to Remove all the MGMT IP's and components.
    print("Cleanining UP IP Pools")
    ucc.extmgmtdelete()

    # EXEC FUNCTION TO CREATE AND DESTROY THE "SCRUB" Service profile
    print("Initiating Scrub")
    ucc.createscrubsp()
    time.sleep(1200)

    # EXEC FUNCTION to create SP TO CLEANUP UCS
    print("Cleaning up ORGs")
    ucc.createcleanupsp()
    time.sleep(10)

    # EXEC Function to create  SP to delete MGMT VLAN
    print("Cleaning UP VLANS")
    ucc.deletevlan()
    time.sleep(10)

    # EXEC Function to Create SP TO Install ESX from Custom ESX IMage VIA HTTP
    print("Reinstalling ESX Operating System on all HX Nodes")
    ucc.enablerautoconfigureports()
    ucc.createhxesxinstallsp()
    time.sleep(3600)

    # EXEC FUNCTION to create SP TO CLEANUP UCS
    print("logged in")
    ucc.createcleanupsp()
    time.sleep(600)

    # EXEC Function to create  SP to delete MGMT VLAN
    print("already logged in")
    ucc.deletevlan()
    time.sleep(10)

    # RESET FABRIC INTERCONNECT CONFIGURATION
    ucc.reset_configuration()
    time.sleep(10)


@celery.task(name='tasks.vcdeploy')
def runvctask(podnum) -> None:
    """TASK to deploy Virtualcenter Servers to each pod"""
    vcdeploy(podnum)


@celery.task(name='tasks.resetucs')
def runucstask(podnum) -> None:
    """TASK to deploy reset UCS via RASP pi EXPECT"""
    ucc = UcsClusterController(settings['ucs'], podnum)
    ucc.reset_configuration()
    ucc.initialize_cluster()


@celery.task(name='tasks.hxdeploy')
def runhxtask(podnum) -> None:
    """TASK to deploy HX installation OVA's to each pod"""
    hxdeploy(podnum)
