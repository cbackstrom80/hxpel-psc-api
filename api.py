from flask import Flask
from flask_restplus import Resource, Api
from ucs.ucs_controller import UcsClusterController
from config import settings
import time

import requests

app = Flask(__name__)
api = Api(app)


pod = {}

###  Operations to Redeploy HX LABSLabs  ####
@api.route('/redeploy/<int:pod_id>/')
class ReDeployESX(Resource):

    def get(self, pod_id):
        ucc = UcsClusterController(settings['ucs'], pod_id)
        podstatus = "offline"
        if pod_id:
            return "Its alive"

    def put(self, pod_id):
        if pod_id:
           #pod[pod_id] = request.form['state']
           """TASK RO REDEPLOY ESX ON POD HX SERVERS"""
           # TODO: Make sure that this function receives the podnum arg
           ucc = UcsClusterController(settings['ucs'], pod_id)
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

           return "Sent Job to Async Task Queue"



###  Operations to Redeploy HX LABSLabs  ####
@api.route('/redeployhx/<string:pod_id>')
class ReDeployHX(Resource):
    def get(self, pod_id):
        podstatus = "offline"
        if pod_id:
            return "Its alive"

    def put(self, pod_id):
        if pod_id:
           pod[pod_id] = request.form['state']
           return pod_id


###  Operations to Redeploy Cisco Container Platform on Top of HX  ####
@api.route('/deployccp/<string:pod_id>')
class ReDeployCCP(Resource):
    def get(self, pod_id):
        podstatus = "offline"
        if pod_id:
            return "Its alive"

    def put(self, pod_id):
        if pod_id:
           pod[pod_id] = request.form['state']
           return pod_id





###  Operations to Redeploy Cisco Container Platform on Top of HX  ####
@api.route('/deploycsr/<int:pod_id>')
class ReDeployCCP(Resource):
    def get(self, pod_id):
        podstatus = "offline"
        if pod_id:
            return "Its alive"

    def put(self, pod_id):
        if pod_id:
           pod[pod_id] = request.form['state']
           return pod_id




###  Operations to manage users  ####
@api.route('/managepodusers/<int:pod_id>')
class ManageHxUsers(Resource):
    def get(self, pod_id):
        podstatus = "offline"
        if pod_id:
            return "Its alive"

    def put(self, pod_id):
        if pod_id:
           pod[pod_id] = request.form['state']
           return pod_id

if __name__ == '__main__':
    app.run(debug=True)


