from flask_restplus import Resource, Api, fields
from flask import Flask
from util.pods import getpods
from worker import celery
import celery.states as states

### import submodule classes  ###
from pods.pods import podDAO

app = Flask(__name__)
api = Api(app, version='1.0', title='HXPEL API',
    description='This API is for automating the deployment of HXPEL services.',
)

pod = api.model('Pod', {
    'ServerName': fields.String(readOnly=True, description='The task unique identifier'),
    'Serial': fields.String(required=True, description='The task details'),
    'Model': fields.String(required=True, description='The task details')
})

poduser = api.model('PodUser', {
    'username': fields.String(readOnly=True, description='The task unique identifier'),
    'password': fields.String(required=True, description='The task details')

})
ccp = api.model('ccp', {
    'ipaddress': fields.String(readOnly=True, description='The task unique identifier'),
    'subnet': fields.String(required=True, description='The task details'),
    'hostname': fields.String(required=True, description='The task details'),
    'vcname': fields.String(required=True, description='The task details'),
    'vcuser': fields.String(required=True, description='The task details'),
    'vcpass': fields.String(required=True, description='The task details'),

})


ns = api.namespace('hxpel', description='hxpel operations')









DAO = podDAO()

### Define ucsreset class
@ns.route('/pods/<int:podnum>')
class PodList(Resource):
    '''Shows a list of all the pod components, and lets you POST to add reset the the pod to factory default'''
    @ns.doc('list_pod')


    def get(self, podnum):
        '''List all pod elements'''

        out = getpods(podnum)
        return out




    @ns.doc('create_pod')
    @ns.expect(pod)

    def post(self):
        '''Create a new pod'''
        task = celery.send_task('tasks.redeployall', args=[podnum], kwargs={})
        response = "pod deploying"
        return response

### List VCENTER Health
@ns.route('/vcenter/<int:podnum>')
class VCHealth(Resource):
    '''Shows the health and VM Creation activity of a pod lab VC'''
    @ns.doc('list_pod')


    def get(self, podnum):
        '''List pod Virtualcenter VM creation, health and activity;'''

        out = getpods(podnum)
        return out

### DEPLOY CCP
@ns.route('/ccpdeploy/<int:podnum>')
class VCHealth(Resource):
    '''Class for CCP '''

    @ns.doc('create_pod')
    @ns.expect(ccp)
    def post(self, podnum):
        '''Deploy Cisco Container Platform in POD'''

        out = getpods(podnum)
        return out

### DEPLOY CCP
@ns.route('/ccpdeploy/<int:podnum>')
class PodUser(Resource):
    '''Class for Pod User Creation '''

    @ns.doc('create_pod')
    @ns.expect(poduser)
    def post(self):
        '''Create POD Users in Vault'''

        return "User Created"

















if __name__ == '__main__':
    app.run(debug=True)


