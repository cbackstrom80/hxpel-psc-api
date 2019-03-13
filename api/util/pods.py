


def getpods(podnum):
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