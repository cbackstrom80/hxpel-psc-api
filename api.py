from flask import Flask
from flask_restplus import Resource, Api, fields
from flask import Blueprint, Flask, jsonify
from util.assoc import getpods

from config import settings
import time


### import submodule classes  ###
from pods.pods import podDAO



import requests

app = Flask(__name__)
api = Api(app, version='1.0', title='HXPEL API',
    description='This API is for automating the deployment of HXPEL services.',
)

pod = api.model('Pod', {
    'ServerName': fields.String(readOnly=True, description='The task unique identifier'),
    'Serial': fields.String(required=True, description='The task details'),
    'Model': fields.String(required=True, description='The task details')
})


ns = api.namespace('hxpel', description='hxpel operations')









DAO = podDAO()

### Define ucsreset class
@ns.route('/pods')
class PodList(Resource):
    '''Shows a list of all pods, and lets you POST to add new reset tasks'''
    @ns.doc('list_pod')

    def get(self):
        '''List all tasks'''

        out = getpods()
        return out

    @ns.doc('create_pod')
    @ns.expect(pod)
    @ns.marshal_with(pod, code=201)
    def post(self):
        '''Create a new task'''
        return DAO.create(api.payload), 201











if __name__ == '__main__':
    app.run(debug=True)


