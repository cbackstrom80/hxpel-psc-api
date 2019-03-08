#!/usr/bin/env python

import pexpect
import re
import sys
import time
from typing import Optional, Pattern, List, Union

from ucsmsdk.mometa.compute.ComputePortDiscPolicy import ComputePortDiscPolicy
from ucsmsdk.ucsexception import UcsException
from ucsmsdk.ucshandle import UcsHandle
from ucsmsdk.mometa.org.OrgOrg import OrgOrg
from ucsmsdk.mometa.uuidpool.UuidpoolPool import UuidpoolPool
from ucsmsdk.mometa.uuidpool.UuidpoolBlock import UuidpoolBlock
from ucsmsdk.mometa.fabric.FabricVlan import FabricVlan
from ucsmsdk.mometa.lsboot.LsbootDefaultLocalImage import LsbootDefaultLocalImage
from ucsmsdk_samples.server.org import org_remove
from ucsmsdk.mometa.ippool.IppoolPool import IppoolPool
from ucsmsdk.mometa.ippool.IppoolBlock import IppoolBlock
from ucsmsdk.mometa.macpool.MacpoolPool import MacpoolPool
from ucsmsdk.mometa.macpool.MacpoolBlock import MacpoolBlock
from ucsmsdk.mometa.lsboot.LsbootPolicy import LsbootPolicy
from ucsmsdk.mometa.lsboot.LsbootVirtualMedia import LsbootVirtualMedia
from ucsmsdk.mometa.lsboot.LsbootStorage import LsbootStorage
from ucsmsdk.mometa.lsboot.LsbootLocalStorage import LsbootLocalStorage
from ucsmsdk.mometa.ls.LsServer import LsServer
from ucsmsdk.mometa.ls.LsVConAssign import LsVConAssign
from ucsmsdk.mometa.vnic.VnicEther import VnicEther
from ucsmsdk.mometa.ls.LsRequirement import LsRequirement
from ucsmsdk.mometa.ls.LsPower import LsPower
from ucsmsdk.mometa.fabric.FabricVCon import FabricVCon
from ucsmsdk.mometa.cimcvmedia.CimcvmediaMountConfigPolicy import CimcvmediaMountConfigPolicy
from ucsmsdk.mometa.cimcvmedia.CimcvmediaConfigMountEntry import CimcvmediaConfigMountEntry
from ucsmsdk.mometa.compute.ComputePool import ComputePool
from ucsmsdk.mometa.compute.ComputePooledRackUnit import ComputePooledRackUnit
from ucsmsdk_samples.server.service_profile import sp_create_from_template
from ucsmsdk_samples.server.scrub_policy import scrub_policy_create
from ucsmsdk.mometa.fabric.FabricSubGroup import FabricSubGroup
from ucsmsdk.mometa.fabric.FabricEthLanPc import FabricEthLanPc
from ucsmsdk.mometa.fabric.FabricEthLanPcEp import FabricEthLanPcEp
from ucsmsdk.mometa.fabric.FabricEthLanEp import FabricEthLanEp

from config import settings


class UcsClusterController:
    def __init__(self, ucs_settings: dict, podnum: int):
        self.settings = ucs_settings
        self.podnum = podnum
        self.ucs_sessions = {
            'A': UcsFiSession(self, 'A',
                              self.settings['members']['A']['termserver_port'],
                              self.settings['members']['A']['ip']),
            'B': UcsFiSession(self, 'B',
                              self.settings['members']['B']['termserver_port'],
                              self.settings['members']['B']['ip'])
        }
        self.handle = None   # type: UcsHandle

    def ucs_login(self):
        """Open a SDK connection the UCS cluster"""

        # At some point if there are multiple credentials we need to try, we can catch
        # any login failures here to be able to re-try.
        if self.handle is None:
            self.handle = UcsHandle(settings['ucs']['cluster_ip'], "admin",
                                    settings['ucs']['credentials']['admin'][1])
        self.handle.login()

    def reset_configuration(self):
        """Erase the fabric interconnect configurations and reboot to the initial config dialog"""

        # Start the reset process on both fabric interconnect devices
        for fi_id, fi in self.ucs_sessions.items():
            fi.cli_send('erase configuration', 'Are you sure.+yes/no', mode='LOCAL-MGMT')
            fi.cli_send('yes', 'Configurations are cleaned up. Rebooting.')

        # Make sure that both devices reboot and reach the initial config dialog
        self.ucs_sessions['A'].wait_for_sysconfig_dialog()
        self.ucs_sessions['B'].wait_for_sysconfig_dialog()

    def initialize_cluster(self) -> None:
        """Initialize a cluster using values from our settings dictionary

        Requires that both Fabric Interconnects be at the initial config dialog
        after the configurations were erased, which would be the expected state
        after reset_configuration() has run.

        """
        
        # Apply settings to FI A to create a new cluster
        self._config_fi_new_cluster(self.ucs_sessions['A'])
        # Have FI B join the cluster
        self._config_fi_existing_cluster(self.ucs_sessions['B'])

        # Pause to let the system stabilize before sending more commands
        time.sleep(120)

        # Update some settings and add a backup user account
        self.disable_password_history(self.ucs_sessions['A'])
        self.set_user_account('ignw', self.settings['credentials']['ignw'][1], 'admin')

        self.create_breakout_port('A')
        self.create_breakout_port('B')

        self._config_uplink_port("A", "7", 2)
        self._config_uplink_port("A", "8", 2)
        self._config_uplink_port("B", "7", 2)
        self._config_uplink_port("B", "8", 2)

        self._create_port_channel("A", "8")
        self._create_port_channel("A", "7")
        self._create_port_channel("B", "7")
        self._create_port_channel("B", "8")

        # Logout and close telnet sessions
        for fi_id, fi in self.ucs_sessions.items():
            fi.close()

    def _config_uplink_port(self, fi, sw_port, port_qty):
        """This function grabs breakout ports and configures them as uplink port via the UCS API"""
        i = 1
        while i <= port_qty:
            mo = self.handle.query_dn("fabric/lan")
            mo.mac_aging = "mode-default"
            mo.mode = "end-host"
            mo.vlan_compression = "disabled"
            mo__handle = self.handle.query_dn("fabric/lan/{FI}".format(FI=fi))
            mo_fab_sub_group = FabricSubGroup(parent_mo_or_dn=mo__handle, aggr_port_id=sw_port, slot_id="1")
            mo_fab_eth_lan_ep = FabricEthLanEp(parent_mo_or_dn=mo_fab_sub_group, admin_speed="10gbps",
                                               admin_state="enabled", auto_negotiate="yes",
                                               eth_link_profile_name="default", flow_ctrl_policy="default",
                                               port_id="{port_num}".format(port_num=i), slot_id="1")
            self.handle.add_mo(mo_fab_sub_group, True)
            self.handle.set_mo(mo)
            self.handle.commit()

            # Update the index
            i += 1

    def _create_port_channel(self, fab, port_id):
        """This function creates Portchannels and assigns uplink ports to them."""
        obj = self.handle.query_dn("fabric")
        mo = self.handle.query_dn("fabric/lan")
        mo.mac_aging = "mode-default"
        mo.mode = "end-host"
        mo.vlan_compression = "disabled"
        mo_handle = self.handle.query_dn("fabric/lan/{fab}".format(fab=fab))
        mo_fab_eth_lan_pc = FabricEthLanPc(parent_mo_or_dn=mo_handle, admin_speed="10gbps", admin_state="enabled",
                                           auto_negotiate="yes", flow_ctrl_policy="default", lacp_policy_name="default",
                                           name="FAB-{fab}-PC".format(fab=fab), oper_speed="10gbps", port_id="1")
        mo__fab_sub_group = FabricSubGroup(parent_mo_or_dn=mo_fab_eth_lan_pc, aggr_port_id=port_id, slot_id="1")
        mo_fab_eth_lan_pc_ep = FabricEthLanPcEp(parent_mo_or_dn=mo__fab_sub_group, admin_state="enabled",
                                                auto_negotiate="yes", eth_link_profile_name="default", port_id="2",
                                                slot_id="1")
        mo_fab_eth_lan_pc_ep = FabricEthLanPcEp(parent_mo_or_dn=mo__fab_sub_group, admin_state="enabled",
                                                auto_negotiate="yes", eth_link_profile_name="default", port_id="1",
                                                slot_id="1")

        self.handle.add_mo(mo_fab_eth_lan_pc, True)
        self.handle.set_mo(mo)
        self.handle.commit()

    def _config_fi_new_cluster(self, fi: 'UcsFiSession') -> None:
        """Answer the basic system setup question to create a new cluster with this FI

        This should only be called after the configuration was erased and system rebooted
        """

        admin_pw = self.settings['credentials']['admin'][1]
        sysname = 'POD' + str(self.podnum)

        fi.cli_send('console', 'setup newly or restore from backup.+setup/restore')
        fi.cli_send('setup', 'setup a new Fabric interconnect.+y/n')
        fi.cli_send('y', 'Enforce strong password.+y/n')
        fi.cli_send('n', 'Enter the password for "admin":')
        fi.cli_send(admin_pw, 'Confirm the password for "admin":', not_echoed=True)
        fi.cli_send(admin_pw, 'part of a cluster.+yes/no', not_echoed=True)
        fi.cli_send('y', 'Enter the switch fabric.+A/B')
        fi.cli_send('A', 'Enter the system name:')
        fi.cli_send(sysname, 'Physical Switch Mgmt0 IP address :')
        fi.cli_send(fi.switch_mgmt_ip, 'Physical Switch Mgmt0 IPv4 netmask :')
        fi.cli_send(self.settings['cluster_netmask'], 'IPv4 address of the default gateway :')
        fi.cli_send(self.settings['cluster_gw'], 'Cluster IPv4 address :')
        fi.cli_send(self.settings['cluster_ip'], 'Configure the DNS Server IP address.+yes/no')
        fi.cli_send('y', 'DNS IP address :')
        fi.cli_send('8.8.8.8', 'Configure the default domain name.+yes/no')
        fi.cli_send('n', 'Join centralized management environment.+yes/no')
        fi.cli_send('n', 'Apply and save the configuration.+yes/no')
        fi.cli_send('yes', 'login:', timeout=90)

    def _config_fi_existing_cluster(self, fi: 'UcsFiSession') -> None:
        """Answer the basic system setup question to add a FI to an existing cluster

        This should only be called after the configuration was erased and system rebooted
        """

        admin_pw = self.settings['credentials']['admin'][1]

        fi.cli_send('console', 'will be added to the cluster. Continue.+y/n')
        fi.cli_send('y', 'admin password of the peer Fabric interconnect:')
        fi.cli_send(admin_pw, 'Physical Switch Mgmt0 IP address :', not_echoed=True)
        fi.cli_send(fi.switch_mgmt_ip, 'Apply and save the configuration.+yes/no')
        fi.cli_send('yes', 'login:', timeout=90)

    @staticmethod
    def disable_password_history(fi: 'UcsFiSession'):
        fi.cli_send('scope security', fi.normal_prompt, verify_scope='/security')
        fi.cli_send('scope password-profile', fi.normal_prompt,
                    verify_scope='/security/password-profile')
        fi.cli_send('set history-count 0', fi.normal_prompt)
        fi.cli_send('commit-buffer', fi.normal_prompt)
        fi.cli_send('end', fi.normal_prompt)  # Exit out of all scopes

    def set_user_account(self, username, password, role: Optional[str]=None) -> None:
        """Add or update a user account with the given credentials and role """

        # Add an ignw account
        already_exists = 'Managed object already exists'

        fi = self.ucs_sessions['A']
        fi.cli_send('scope security', fi.normal_prompt, verify_scope='/security')
        fi.cli_send('create local-user ' + username, [already_exists, fi.normal_prompt])
        if fi.last_match_index == 0:
            # User already exists, so we need to change scope manually
            fi.cli_send('scope local-user ' + username, verify_scope='/security/local-user')

        fi.cli_send('set account-status active', fi.normal_prompt)
        if role is not None:
            fi.cli_send('create role ' + role, fi.normal_prompt)
        fi.cli_send('set password', 'password:')
        fi.cli_send(password, 'password:', not_echoed=True)
        fi.cli_send(password, fi.normal_prompt, not_echoed=True)
        fi.cli_send('commit-buffer', fi.normal_prompt)
        fi.cli_send('end', fi.normal_prompt)

    def enablerautoconfigureports(self) -> None:
        """Enable Port autodicovery """

        try:
            self.ucs_login()
            # FIXME: This function  expects parent_mo_or_dn as the first arg. Problem?
            mo = ComputePortDiscPolicy(
                childAction="deleteNonPresent", descr="", dn="org-root/port-discovery",
                ethBreakoutAutoDiscovery="enabled", ethSvrAutoDiscovery="enabled", intId="35397",
                name="", policyLevel="0", policyOwner="local", qualifier="")
            self.handle.add_mo(mo)
            self.handle.commit()
            print("Enabling Port Auto Discovery")
        except:
            # TODO: Identify a more specific Exception to catch if possible
            print("Cannot Enable Port Auto-Discovery, Possibly already enabled...")



    def configurebreakouports(self) -> None:
        """Configure Breakout ports"""

        try:
            self.ucs_login()
            # FIXME: This function  expects parent_mo_or_dn as the first arg. Problem?
            dn = "org-root/ip-pool-ext-mgmt/block-{r_from}-{to}".format(
                **settings['ip_blocks']['mgmt'])
            mo = self.handle.query_dn(dn)
            print(mo)
            #self.handle.add_mo(mo)
            #self.handle.commit()
            print("Enabling Port Auto Discovery")
        except:
            # TODO: Identify a more specific Exception to catch if possible
            print("Cannot query breakout ports")




    def extmgmtdelete(self) -> None:
        """Deletes the management IP block"""

        self.ucs_login()
        dn = "org-root/ip-pool-ext-mgmt/block-{r_from}-{to}".format(
            **settings['ip_blocks']['mgmt'])
        mo = self.handle.query_dn(dn)
        if mo:
            try:
                self.handle.remove_mo(mo)
                self.handle.commit()
            except ValueError:
                print("IP Pool '%s' is not present" % dn)



    def deletevlan(self) -> None:
        """FIXME: Add a summary"""

        self.ucs_login()
        vlan = self.handle.query_classid("fabricVlan")

        if vlan:
            index = 0
            for i in vlan:  # FIXME: Iterator is not used. 'index' never changes. Intended?
                print(vlan[index].name)
                if vlan[index].name != "default":
                    dn = "fabric" + "/lan" '/net-' + vlan[index].name
                    self.ucs_login()
                    mo = self.handle.query_dn(dn)
                    if mo:
                        self.handle.remove_mo(mo)
                        self.handle.commit()
                    else:
                        raise ValueError("VLAN '%s' is not present" % dn)
                index += 1


    def deletevlan(self) -> None:
        """FIXME: Add a summary"""

        self.ucs_login()
        vlan = self.handle.query_classid("fabricVlan")

        if vlan:
            index = 0
            for i in vlan:  # FIXME: Iterator is not used. 'index' never changes. Intended?
                print(vlan[index].name)
                if vlan[index].name != "default":
                    dn = "fabric" + "/lan" '/net-' + vlan[index].name
                    self.ucs_login()
                    mo = self.handle.query_dn(dn)
                    if mo:
                        self.handle.remove_mo(mo)
                        self.handle.commit()
                    else:
                        raise ValueError("VLAN '%s' is not present" % dn)
                index += 1

    def createcleanupsp(self) -> str:
        """Create Cleanup SP to destroy ALL ORGS


        """

        self.ucs_login()

        org = self.handle.query_classid("orgOrg")

        if org:
            index = 0
            for i in org:  # FIXME: Iterator is not used. 'index' never changes. Intended?
                print(org[index].name)
                if org[index].name != "root":
                    org_remove(self.handle, name=org[index].name)
                index += 1

        return "Cleaning Up UCS Configuration"

    def createscrubsp(self) -> str:
        """Create And And Apply Scrub SPPolicy"""

        self.ucs_login()
        # Retrieve IP Pool
        mo = self.handle.query_dn("org-root/ip-pool-ext-mgmt")

        # Create IP Block within Pool
        mo_1 = IppoolBlock(parent_mo_or_dn=mo, **settings['ip_blocks']['mgmt'])
        self.handle.add_mo(mo_1)
        self.handle.commit()

        # Create Sub Organization
        mo = OrgOrg(parent_mo_or_dn="org-root", name=settings['OrgName'], descr="Sub Organization")
        self.handle.add_mo(mo)
        self.handle.commit()

        # Create MAC Pools
        mo = MacpoolPool(parent_mo_or_dn=settings['my_Full_Path_Org'], policy_owner="local",
                         descr="Management FI-A", assignment_order="sequential", name="MGMT-A")
        # FIXME: In a lot of cases like this, we assign a mo_x value that is never used. If it's
        # not needed, you may as well remove the `mo_1 = ` from the beginning of the statement.
        MacpoolBlock(parent_mo_or_dn=mo, to="00:25:B5:A0:00:0F", r_from="00:25:B5:A0:00:00")
        self.handle.add_mo(mo)
        self.handle.commit()

        mo = MacpoolPool(parent_mo_or_dn=settings['my_Full_Path_Org'], policy_owner="local",
                         descr="Management FI-B", assignment_order="sequential", name="MGMT-B")
        MacpoolBlock(parent_mo_or_dn=mo, to="00:25:B5:B0:00:0F", r_from="00:25:B5:B0:00:00")
        self.handle.add_mo(mo)
        self.handle.commit()

        # Create IP Pool
        mo = IppoolPool(parent_mo_or_dn=settings['my_Full_Path_Org'],
                        is_net_bios_enabled="disabled", name="hx-mgmt", descr="KVM",
                        policy_owner="local", ext_managed="internal", supports_dhcp="disabled",
                        assignment_order="sequential")
        IppoolBlock(parent_mo_or_dn=mo, **settings['ip_blocks']['kvm'])
        self.handle.add_mo(mo)
        self.handle.commit()

        # Create UUID Pool
        mo = UuidpoolPool(parent_mo_or_dn=settings['my_Full_Path_Org'], policy_owner="local",
                          prefix="derived", descr="UUID Pool", assignment_order="sequential",
                          name="UUID_POOL")
        UuidpoolBlock(parent_mo_or_dn=mo, to="0001-000000000100", r_from="0001-000000000001")
        self.handle.add_mo(mo)
        self.handle.commit()

        # #####  ADD Rack Servers to server Pool  #############################
        pool_string = settings['my_Full_Path_Org'] + "/" + "compute-pool-" + "TestPool"
        self.server_pool_create("TestPool", "Trying to put Rack servers in this pool")
        self.server_pool_add_rack_unit(1, pool_string)
        self.server_pool_add_rack_unit(2, pool_string)
        self.server_pool_add_rack_unit(3, pool_string)
        self.server_pool_add_rack_unit(4, pool_string)

        scrub_policy_create(self.handle, name="scrubname", flex_flash_scrub="no", disk_scrub="yes",
                            bios_settings_scrub="no", parent_dn=settings['my_Full_Path_Org'])
        mo = LsServer(parent_mo_or_dn=settings['my_Full_Path_Org'],
                      vmedia_policy_name="",
                      ext_ip_state="pooled",
                      bios_profile_name="",
                      mgmt_fw_policy_name="",
                      agent_policy_name="",
                      mgmt_access_policy_name="",
                      dynamic_con_policy_name="",
                      kvm_mgmt_policy_name="",
                      sol_policy_name="",
                      uuid="0",
                      descr=("This service Profile should only be deployed in "
                             "order to re-image the HX Servers with ESX"),
                      stats_policy_name="default",
                      policy_owner="local",
                      ext_ip_pool_name="hx-mgmt",
                      boot_policy_name="default",
                      usr_lbl="",
                      host_fw_policy_name="",
                      vcon_profile_name="",
                      ident_pool_name="UUID_POOL",
                      src_templ_name="",
                      type="initial-template",
                      local_disk_policy_name="default",
                      scrub_policy_name="scrubname",
                      power_policy_name="default",
                      maint_policy_name="default",
                      name="SCRUBME",
                      resolve_remote="yes")
        LsRequirement(parent_mo_or_dn=mo, restrict_migration="no", name="TestPool", qualifier="")
        LsPower(parent_mo_or_dn=mo, state="admin-up")
        self.handle.add_mo(mo)
        self.handle.commit()

        # ### Create 4 Service Profiles for the SCRUB deployment #########
        sp_create_from_template(self.handle, naming_prefix="SCRUBME" + "-",
                                name_suffix_starting_number="1",
                                number_of_instance="4",
                                sp_template_name="SCRUBME",
                                in_error_on_existing="true",

                                parent_dn=settings['my_Full_Path_Org'])

        return "Scrubbing the servers"

    def server_pool_create(self, name: str, descr: str = "",
                           parent_dn: str = settings['my_Full_Path_Org']) -> ComputePool:
        """Creates a ComputePool.

        Args:
            name: Name of the ComputePool.
            descr: Basic description.
            parent_dn: Parent of Org.

        Example:
            server_pool_create(name="sample_compute_pool", parent_dn="org-root/org-sub")
        """

        self.ucs_login()
        obj = self.handle.query_dn(parent_dn)
        if not obj:
            raise ValueError("org '%s' does not exist" % parent_dn)

        mo = ComputePool(parent_mo_or_dn=obj, name=name, descr=descr)
        self.handle.add_mo(mo, modify_present=True)
        self.handle.commit()
        return mo

    def server_pool_add_rack_unit(self, rack_id: int,
                                  parent_dn: str = settings[
                                      'my_Full_Path_Org']) -> ComputePooledRackUnit:
        """Add a rack server to a ComputePool.

        Args:
            rack_id: ID of rack server to add
            parent_dn: Parent of Org.

        Example:
            server_pool_add_rack_unit(
                rack_id=1, parent_dn="org-root/org-sub/compute-pool-sample_compute_pool")
        """

        self.ucs_login()
        obj = self.handle.query_dn(parent_dn)
        if not obj:
            raise ValueError("org '%s' does not exist" % parent_dn)
        if not isinstance(obj, ComputePool):
            raise TypeError("Object {0} is not a ComputePool".format(obj.dn))

        mo = ComputePooledRackUnit(parent_mo_or_dn=parent_dn, id=str(rack_id))
        self.handle.add_mo(mo)
        self.handle.commit()
        return mo

    def createhxesxinstallsp(self) -> str:
        """Create VMEDIA Policy"""

        self.ucs_login()
        # Create Sub Organization
        mo = OrgOrg(parent_mo_or_dn="org-root", name=settings['OrgName'], descr="Sub Organization")
        self.handle.add_mo(mo)
        self.handle.commit()

        # Create Management VLAN
        mo = FabricVlan(parent_mo_or_dn="fabric/lan", sharing="none",
                        name=settings['MgmtVlanName'], id=str(settings['MgmtVlanId']),
                        mcast_policy_name="", policy_owner="local", default_net="no",
                        pub_nw_name="", compression_type="included")

        self.handle.add_mo(mo)
        self.handle.commit()

        # Create MAC Pools
        mo = MacpoolPool(parent_mo_or_dn=settings['my_Full_Path_Org'], policy_owner="local",
                         descr="Management FI-A", assignment_order="sequential", name="MGMT-A")
        MacpoolBlock(parent_mo_or_dn=mo, to="00:25:B5:A0:00:0F", r_from="00:25:B5:A0:00:00")
        self.handle.add_mo(mo)
        self.handle.commit()

        mo = MacpoolPool(parent_mo_or_dn=settings['my_Full_Path_Org'], policy_owner="local",
                         descr="Management FI-B", assignment_order="sequential", name="MGMT-B")
        MacpoolBlock(parent_mo_or_dn=mo, to="00:25:B5:B0:00:0F", r_from="00:25:B5:B0:00:00")
        self.handle.add_mo(mo)
        self.handle.commit()

        # Create IP Pool
        mo = IppoolPool(parent_mo_or_dn=settings['my_Full_Path_Org'],
                        is_net_bios_enabled="disabled", name="hx-mgmt", descr="KVM",
                        policy_owner="local", ext_managed="internal", supports_dhcp="disabled",
                        assignment_order="sequential")
        IppoolBlock(parent_mo_or_dn=mo, **settings['ip_blocks']['kvm'])
        self.handle.add_mo(mo)
        self.handle.commit()

        # Create UUID Pool
        mo = UuidpoolPool(parent_mo_or_dn=settings['my_Full_Path_Org'], policy_owner="local",
                          prefix="derived", descr="UUID Pool", assignment_order="sequential",
                          name="UUID_POOL")
        UuidpoolBlock(parent_mo_or_dn=mo, to="0001-000000000100", r_from="0001-000000000001")
        self.handle.add_mo(mo)
        self.handle.commit()

        # #### Create VMEDIA Policy ######################
        mo = CimcvmediaMountConfigPolicy(
            name="IGNWLabsESX", retry_on_mount_fail="yes",
            parent_mo_or_dn=settings['my_Full_Path_Org'], policy_owner="local",
            descr="IGNW Labs ESX Vmedia Policy")
        CimcvmediaConfigMountEntry(parent_mo_or_dn=mo,
                                   mapping_name="HXESX",
                                   device_type="cdd",
                                   mount_protocol="http",
                                   remote_ip_address=settings['vmedia_ip_address'],
                                   image_name_variable="none",
                                   image_file_name="IGNW-Custom-HX-INSTALL.iso",
                                   image_path="install")

        self.handle.add_mo(mo, modify_present=True)
        self.handle.commit()

        # Create Boot Policy (boot from SD)
        mo = LsbootPolicy(parent_mo_or_dn=settings['my_Full_Path_Org'],
                          name="HXINSTALLER",
                          descr="Boot from CIMC Media",
                          reboot_on_update="no",
                          policy_owner="local",
                          enforce_vnic_name="yes",
                          boot_mode="legacy")

        LsbootVirtualMedia(parent_mo_or_dn=mo,
                           access="read-only-remote-cimc",
                           lun_id="0",
                           mapping_name="",
                           order="2")

        mo_2 = LsbootStorage(parent_mo_or_dn=mo, order="1")
        mo_2_1 = LsbootLocalStorage(parent_mo_or_dn=mo_2, )
        LsbootDefaultLocalImage(parent_mo_or_dn=mo_2_1, order="1")
        self.handle.add_mo(mo)
        self.handle.commit()

        # #####  ADD Rack Servers to server Pool  #############################
        pool_string = settings['my_Full_Path_Org'] + "/" + "compute-pool-" + "TestPool"
        self.server_pool_create("TestPool", "Trying to put Rack servers in this pool")
        self.server_pool_add_rack_unit(1, pool_string)
        self.server_pool_add_rack_unit(2, pool_string)
        self.server_pool_add_rack_unit(3, pool_string)
        self.server_pool_add_rack_unit(4, pool_string)

        mo = LsServer(parent_mo_or_dn=settings['my_Full_Path_Org'],
                      vmedia_policy_name="IGNWLabsESX",
                      ext_ip_state="pooled",
                      bios_profile_name="",
                      mgmt_fw_policy_name="",
                      agent_policy_name="",
                      mgmt_access_policy_name="",
                      dynamic_con_policy_name="",
                      kvm_mgmt_policy_name="",
                      sol_policy_name="",
                      uuid="0",
                      descr=("This service Profile should only be deployed in "
                             "order to re-image the HX Servers with ESX"),
                      stats_policy_name="default",
                      policy_owner="local",
                      ext_ip_pool_name="hx-mgmt",

                      boot_policy_name="HXINSTALLER",
                      usr_lbl="",
                      host_fw_policy_name="",
                      vcon_profile_name="",
                      ident_pool_name="UUID_POOL",
                      src_templ_name="",
                      type="initial-template",
                      local_disk_policy_name="default",
                      scrub_policy_name="",
                      power_policy_name="default",
                      maint_policy_name="default",
                      name=settings['SpNameSeed'],
                      resolve_remote="yes")

        LsVConAssign(parent_mo_or_dn=mo,
                     admin_vcon="any",
                     admin_host_port="ANY",
                     order="1",
                     transport="ethernet",
                     vnic_name="MGMT-A")
        LsVConAssign(parent_mo_or_dn=mo,
                     admin_vcon="any",
                     admin_host_port="ANY",
                     order="2",
                     transport="ethernet",
                     vnic_name="MGMT-B")

        VnicEther(parent_mo_or_dn=mo,
                  cdn_prop_in_sync="yes",
                  nw_ctrl_policy_name="",
                  admin_host_port="ANY",
                  admin_vcon="any",
                  stats_policy_name="default",
                  admin_cdn_name="",
                  switch_id="A",
                  pin_to_group_name="",
                  name="MGMT-A",
                  order="1",
                  qos_policy_name="",
                  adaptor_profile_name="",
                  ident_pool_name="MGMT-A",
                  cdn_source="vnic-name",
                  mtu="1500",
                  nw_templ_name="",
                  addr="derived")

        VnicEther(parent_mo_or_dn=mo,
                  cdn_prop_in_sync="yes",
                  nw_ctrl_policy_name="",
                  admin_host_port="ANY",
                  admin_vcon="any",
                  stats_policy_name="default",
                  admin_cdn_name="",
                  switch_id="B",
                  pin_to_group_name="",
                  name="MGMT-B", order="2",
                  qos_policy_name="",
                  adaptor_profile_name="",
                  ident_pool_name="MGMT-B",
                  cdn_source="vnic-name",
                  mtu="1500",
                  nw_templ_name="",
                  addr="derived",
                  )

        FabricVCon(parent_mo_or_dn=mo, placement="physical", fabric="NONE", share="shared",
                   select="all", transport="ethernet", id="1", inst_type="auto")
        FabricVCon(parent_mo_or_dn=mo, placement="physical", fabric="NONE", share="shared",
                   select="all", transport="ethernet", id="2", inst_type="auto")
        FabricVCon(parent_mo_or_dn=mo, placement="physical", fabric="NONE", share="shared",
                   select="all", transport="ethernet", id="3", inst_type="auto")
        FabricVCon(parent_mo_or_dn=mo, placement="physical", fabric="NONE", share="shared",
                   select="all", transport="ethernet", id="4", inst_type="auto")

        LsRequirement(parent_mo_or_dn=mo, restrict_migration="no", name="TestPool", qualifier="")
        LsPower(parent_mo_or_dn=mo, state="admin-up")

        self.create_ignw_virtual_media()
        self.handle.add_mo(mo)
        self.handle.commit()

        # ### Create 4 Service Profiles for the pod deployment #########
        sp_create_from_template(self.handle, naming_prefix=settings['SpNameSeed'] + "-",
                                name_suffix_starting_number="1",
                                number_of_instance="4",
                                sp_template_name=settings['SpNameSeed'],
                                in_error_on_existing="true",
                                parent_dn=settings['my_Full_Path_Org'])
        return "Installing ESX On HX Servers"

    def create_ignw_virtual_media(self) -> None:
        """Create Virtual Media Policy to boot off HX installer via http """

        print("Adding Virtual Media Policy")

        mo = CimcvmediaMountConfigPolicy(name="HXPEL",
                                         retry_on_mount_fail="yes",
                                         parent_mo_or_dn="org-root",
                                         policy_owner="local",
                                         descr="HX Install Media VIA Http")

        CimcvmediaConfigMountEntry(parent_mo_or_dn=mo,
                                   mapping_name="HXInstall",
                                   device_type="cdd",
                                   mount_protocol="http",
                                   remote_ip_address=settings['vmedia_ip_address'],
                                   image_name_variable="none",
                                   image_file_name="IGNW-Custom-HX-INSTALL.iso",
                                   image_path="install")

        self.ucs_login()
        self.handle.add_mo(mo, modify_present=True)
        try:
            self.handle.commit()
        except UcsException as err:
            if err.error_code == "103":
                print("\talready exists")

    def create_breakout_port(self, fi_id: str, slot1: int = 1, port1: int = 7,
                             slot2: int = 1, port2: int = 8) -> None:
        """FIXME: Add a summary

        Args:
            fi_id: Should be 'A' or 'B'. Will be converted to uppercase.
            slot1:
            port1:
            slot2:
            port2:

        """
        fi = self.ucs_sessions[fi_id.upper()]
        fi.cli_send('scope cabling', fi.normal_prompt, verify_scope='/cabling')
        fi.cli_send('scope fabric ' + fi_id, fi.normal_prompt,
                    verify_scope='/cabling/fabric')
        fi.cli_send('create breakout {} {}'.format(slot1, port1), fi.normal_prompt)
        fi.cli_send('up', fi.normal_prompt)
        fi.cli_send('create breakout {} {}'.format(slot2, port2), fi.normal_prompt)
        fi.cli_send('up', fi.normal_prompt)
        # FIXME: We need to know what response to look for and how to answer.
        fi.cli_send('commit-buffer', fi.normal_prompt)
        fi.cli_send('y', fi.login_prompt, timeout=300)


class UcsFiSession:
    """Manage CLI I/O for a UCS Fabric Interconnect via serial connection"""
    Expected = Union[str, List[str], Pattern, List[Pattern]]
    login_prompt = 'login:'
    password_prompt = 'Password:'
    bad_password = 'Login incorrect'
    normal_prompt = re.compile('[-\w]+( (?:/[-\w]+)+ )?#')
    normap_prompt_scope = None   # Set by _get_prompt_type()
    local_mgmt_prompt = re.compile('\(local-mgmt\)#')
    invalid_command = re.compile('% Invalid Command')

    def __init__(self, ucc: UcsClusterController, fi_id: str, ts_port: int, switch_mgmt_ip: str):
        self.ucc = ucc
        self.id = fi_id
        self.ts_port = ts_port
        self.switch_mgmt_ip = switch_mgmt_ip
        self.session = None
        self.last_match_index = None    # type: int

    def cli_send(self, command: str, expected: Optional[Expected] = None,
                 mode: str = 'NORMAL', verify_scope: Optional[str] = None,
                 not_echoed: bool = False, timeout: Optional[int] = None):
        """Run a CLI command on the device and get the output.

        If there is not an existing session open with the device, we will
        log into it. If there is an existing session, we will make sure that
        we have the expected CLI mode/prompt

        Arguments:
            command: Command to send to the CLI
            expected: Optional value that we should expect after sending the
                command.
            mode: The CLI mode/context that we should be in to run the given command.
                'NORMAL' - The prompt we would have after logging in. This includes
                    any scope or no scope. This is the default
                'LOCAL-MGMT' - Connected to the local management port
                None - Do not perform any CLI mode check.
            verify_scope: If mode is 'NORMAL', check to make sure that the scope equals
                this value. Use an empty string instead of None to check for no scope
            not_echoed: Set true if the command you send does not get echoed back.
                That would be the case for password prompts.
            timeout: Optional override for the default pexpect timeout

        Returns:
            str: The output of the command

        Raises:
            RuntimeError
            AssertionError

        TODO:
            - Automatically switch to a scope requested by a user instead of only offering
            to verify it.

        """
        if self.session is None or not self.session.isalive():
            if not self.login():  # If login fails
                raise RuntimeError('Failed to log into device')
            # Set a high number of columns to prevent wrapping
            self.session.setwinsize(24, 10000)

        if mode is not None:
            prompt_type = self._get_prompt_type()
            if prompt_type == 'TIMEOUT':
                raise RuntimeError('Timed out trying to find a known prompt. '
                                   'Buffer: ' + self.session.buffer)
            elif prompt_type == 'LOGIN':
                assert self.login()
                prompt_type = self._get_prompt_type()

            if prompt_type != mode:
                # Figure out how to get into the desired mode
                if mode == 'NORMAL' and prompt_type == 'LOCAL-MGMT':
                    self._sendline('exit', self.normal_prompt)
                elif mode == 'LOCAL-MGMT' and prompt_type == 'NORMAL':
                    self._sendline('connect local-mgmt', self.local_mgmt_prompt)
                else:
                    # There's something that we haven't accounted for in code.
                    raise RuntimeError("Failed setting mode: {} != {}".format(
                        prompt_type, mode))

            if mode == 'NORMAL' and verify_scope is not None:
                if verify_scope == '' and self.normal_prompt_scope is not None:
                    raise ValueError('Expected an empty scope but found: {}'.format(
                        self.normal_prompt_scope))
                elif verify_scope != self.normal_prompt_scope:
                    raise ValueError('Expected scope {} but found: {}'.format(
                        verify_scope, self.normal_prompt_scope))

        # Send the command and consume the echoed-back command line.
        if not_echoed:
            self._sendline(command, expected, timeout=timeout)
        else:
            self._sendline(command, re.escape(command) + '\r?\n')
            # Search for our expected value and check for a CLI error
            if timeout is None:
                self.last_match_index = self.session.expect(expected)
            else:
                self.last_match_index = self.session.expect(expected, timeout)
        output = self.session.before
        if self.invalid_command.search(output):
            raise RuntimeError('Invalid command: ' + command)

        return output

    def wait_for_sysconfig_dialog(self):
        self.session.expect(
            re.escape('Enter the configuration method. (console/gui) ?'), timeout=600)

    def _sendline(self, text: str, expected: Optional[Expected]=None,
                  timeout: Optional[int]=None) -> Optional[str]:
        """Wrapper for pexpect sendline

        This was created so that you can expect a value after sending some text
        instead of having to call expect() as a separate step. It also returns
        session.before which can also save a step.

        Arguments:
            text: String to be sent to the session
            expected: Optional value to expect after sending text
            timeout: Optional expect timeout in seconds

        Returns:
            The text before the matched expected value, if any

        """
        self.session.sendline(text)
        if expected:
            if timeout is None:
                self.last_match_index = self.session.expect(expected)
            else:
                self.last_match_index = self.session.expect(expected, timeout)
            return self.session.before
        else:
            return None

    def _get_prompt_type(self) -> str:
        """Look at a line of output to determine the prompt type

        Note: If nothing matches then pexpect will throw a timeout exception

        Returns:
            A friendly name for the prompt pattern that was matched

        """
        self._sendline('', [self.login_prompt, self.normal_prompt,
                            self.local_mgmt_prompt, pexpect.TIMEOUT])
        prompt_names = ['LOGIN', 'NORMAL', 'LOCAL-MGMT', 'TIMEOUT']
        prompt_type = prompt_names[self.last_match_index]
        if prompt_type == 'NORMAL':
            scope = self.session.match.group(1)
            if scope is not None:
                scope = scope.strip()
            self.normal_prompt_scope = scope
        return prompt_type

    def login(self) -> bool:
        """Try available credentials to log into the Fabric Interconnect

        Returns:
            True if the login was successful, otherwise False.

        """
        self.session = pexpect.spawn(
            'telnet', args=[self.ucc.settings['termserver_ip'], str(self.ts_port)],
            encoding='utf-8', timeout=45, codec_errors='backslashreplace')
        self.session.logfile_read = sys.stdout
        self._sendline('', self.login_prompt)

        for name in ['admin', 'admin_old']:
            username, password = self.ucc.settings['credentials'][name]
            self._sendline(username, self.password_prompt)
            self._sendline(password, [self.bad_password, self.normal_prompt])
            if self.last_match_index == 0:  # Login failed
                self.session.expect(self.login_prompt)
                # Let the loop continue to try the next credential
            else:
                # Turn off paging in this session
                self._sendline('terminal length 0', self.normal_prompt)
                return True
        return False

    def close(self) -> None:
        """Log out and close the telnet session to the device"""
        self._sendline('end', self.normal_prompt)
        self._sendline('exit')
        time.sleep(1)
        self.session.sendcontrol(']')
        self.session.expect('telnet>')
        self._sendline('quit')
