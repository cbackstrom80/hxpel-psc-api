from ucsmsdk.ucshandle import UcsHandle
handle = UcsHandle("172.20.1.10", "admin", "Cisco1234!")
handle.login()

compute_rack_unit = handle.query_classid("ComputeRackUnit")


def checkassoc():
    counter = 0
    for a in compute_rack_unit:
        if compute_rack_unit[0].association == "associated":
            counter += 1
    return counter

if checkassoc() == 4:
    print("True")

