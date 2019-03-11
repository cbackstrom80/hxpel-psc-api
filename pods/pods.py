from util.assoc import getpods


class podDAO(object):


    def get(self):
        return getpods()



    def create(self, data):
        pod = data
        pod['id'] = self.counter = self.counter + 1
        self.pods.append(pod)
        return pod

    def update(self, id, data):
        pod = self.get(id)
        pod.update(data)
        return pod

    def delete(self, id):
        pod = self.get(id)
        self.pods.remove(pod)

