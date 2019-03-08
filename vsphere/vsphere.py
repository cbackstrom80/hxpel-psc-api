import subprocess
def vspherelicense(hostip,vcuser,vcpassword):
    from config import settings
    from pyVim.connect import SmartConnect, Disconnect
    import ssl

    s = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
    s.verify_mode = ssl.CERT_NONE

    c = SmartConnect(host=hostip, user=vcuser, pwd=vcpassword, sslContext=s)

    #print(c.content.licenseManager.AddLicense(licenseKey="1463P-09K1K-Q8J9A-02CA0-05GJM"))

    vclicensekey = settings['labvc']['vclicensekey']
    vcuuid = c.content.about.instanceUuid

    print("Installing And Activating VSPHERE:")
    print(c.content.licenseManager.AddLicense(licenseKey=vclicensekey))
    print(c.content.licenseManager.licenseAssignmentManager.UpdateAssignedLicense(vcuuid,vclicensekey))










    Disconnect(c)


#TODO This is JOES improved paramterized VMWARE REDEPLOY Version.


"""
def virtcenterdeploy(podnum):
    def vcdelete(podnum):
        cmd = ['python3.6',  '/pyvmomi-community-samples/samples/destroy_vm.py',
               '-s ' + settings['labvc']['ip'],
               '-u ' + settings['labvc']['username'],
               '-p ' + settings['labvc']['password'],
               "-v ignw-hpel-pod{}-vc".format(podnum)]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        for line in p.stdout:
            # the real code does filtering here
            print("test:", line.rstrip())

        return p.wait()

    def vcova(podnum):
        cmd = ["/VCSA/vcsa-cli-installer/lin64/vcsa-deploy", "install",
               "--no-esx-ssl-verify", --accept-eula', '--acknowledge-ceip',
               "HX_POD_{}.json".format(podnum)]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        for line in p.stdout:
            # the real code does filtering here
            print("test:", line.rstrip())
        return p.wait()



def hyperflexdeploy(podnum):
    def hxdelete(podnum):
        cmd = ['python3.6', '/pyvmomi-community-samples/samples/destroy_vm.py',
               '-s ' + settings['labvc']['ip'],
               '-u ' + settings['labvc']['username'],
               '-p ' + settings['labvc']['password'],
               "-v ignw-hpel-pod{}-hxinstaller".format(podnum)]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        for line in p.stdout:
            # the real code does filtering here
            print("test:", line.rstrip())
        return p.wait()


    def hxinstall(podnum):
        hx_settings = settings['hx_installer']
        cmd = ['ovftool', '--noSSLVerify', '--diskMode=thin', '--acceptAllEulas=true',
               '--powerOn', '--skipManifestCheck', '--X:injectOvfEnv',
               '--datastore=hpel-tintri',
               '--name=ignw-hpel-pod{}-hxinstaller'.format(podnum),
               '--network="hxpel-pod{}|hxpel|management"'.format(podnum),
               '--prop:hx.gateway.Cisco_HX_Installer_Appliance=' + hx_settings['gw'],
               '--prop:hx.DNS.Cisco_HX_Installer_Appliance=' + hx_settings['dns'],
               '--prop:hx.ip0.Cisco_HX_Installer_Appliance=' + hx_settings['vm_ip_address'],
               '--prop:hx.netmask0.Cisco_HX_Installer_Appliance=' + hx_settings['subnet_mask'],
               '/ova/Cisco-HX-Data-Platform-Installer-v3.0.1e-29829-esx.ova',
               'vi://"{username}":"{password}"@{ip}/HPEL-Lab/host/HPEL-Management/'.format(
                   **settings['labvc']) + hx_settings['esx_server']
               ]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        for line in p.stdout:
            # the real code does filtering here
            print("test:", line.rstrip())
        return p.wait()
        """


