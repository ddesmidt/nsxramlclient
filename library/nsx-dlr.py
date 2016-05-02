# coding=utf-8
#
# Copyright © 2015 VMware, Inc. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
# to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions
# of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
# TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

__author__ = 'Dimitri Desmidt, Yves Fauser, Emanuele Mazza'

import argparse
import ConfigParser
import json
from libutils import *
from tabulate import tabulate
from nsxramlclient.client import NsxClient


def dlr_create(client_session, dlr_name, dlr_pwd, dlr_size,
               datacentermoid, datastoremoid, resourcepoolid,
               ha_ls_id, uplink_ls_id, uplink_ip, uplink_subnet, uplink_dgw):
    """
    This function will create a new dlr in NSX
    :param client_session: An instance of an NsxClient Session
    :param dlr_name: The name that will be assigned to the new dlr
    :param dlr_pwd: The admin password of new dlr
    :param dlr_size: The DLR Control VM size
    :param datacentermoid: The vCenter DataCenter ID where dlr control vm will be deployed
    :param datastoremoid: The vCenter datastore ID where dlr control vm will be deployed
    :param resourcepoolid: The vCenter Cluster where dlr control vm will be deployed
    :param ha_ls_id: New dlr ha logical switch id or vds port group
    :param uplink_ls_id: New dlr uplink logical switch id or vds port group
    :param uplink_ip: New dlr uplink ip@
    :param uplink_subnet: New dlr uplink subnet
    :param uplink_dgw: New dlr default gateway
    :return: returns a tuple, the first item is the dlr ID in NSX as string, the second is string
             containing the dlr URL location as returned from the API
    """

    # get a template dict for the dlr create
    dlr_create_dict = client_session.extract_resource_body_schema('nsxEdges', 'create')

    # fill the details for the new dlr in the body dict
    dlr_create_dict['edge']['type'] = "distributedRouter"
    dlr_create_dict['edge']['name'] = dlr_name
    dlr_create_dict['edge']['cliSettings'] = {'password': dlr_pwd, 'remoteAccess': "True",
                                              'userName': "admin"}
    dlr_create_dict['edge']['appliances']['applianceSize'] = dlr_size
    dlr_create_dict['edge']['datacenterMoid'] = datacentermoid
    dlr_create_dict['edge']['appliances']['appliance']['datastoreId'] = datastoremoid
    dlr_create_dict['edge']['appliances']['appliance']['resourcePoolId'] = resourcepoolid
    dlr_create_dict['edge']['mgmtInterface'] = {'connectedToId': ha_ls_id}
    dlr_create_dict['edge']['interfaces'] = {'interface': {'type': "uplink", 'isConnected': "True",
                                                           'connectedToId': uplink_ls_id,
                                                           'addressGroups': {
                                                               'addressGroup': {'primaryAddress': uplink_ip,
                                                                                'subnetMask': uplink_subnet}}}}
    del dlr_create_dict['edge']['vnics']
    del dlr_create_dict['edge']['appliances']['appliance']['hostId']
    del dlr_create_dict['edge']['appliances']['appliance']['customField']

    new_dlr = client_session.create('nsxEdges', request_body_dict=dlr_create_dict)

    # get a template dict for the dlr routes
    dlr_static_route_dict = client_session.extract_resource_body_schema('routingConfig', 'update')

    # add default gateway to the created dlr if dgw entered
    if uplink_dgw:
        dlr_static_route_dict['routing']['staticRouting']['defaultRoute']['gatewayAddress'] = uplink_dgw
        del dlr_static_route_dict['routing']['routingGlobalConfig']
        del dlr_static_route_dict['routing']['staticRouting']['staticRoutes']
        del dlr_static_route_dict['routing']['ospf']
        del dlr_static_route_dict['routing']['isis']
        del dlr_static_route_dict['routing']['bgp']

        dlr_static_route = client_session.update('routingConfig', uri_parameters={'edgeId': new_dlr['objectId']},
                                                 request_body_dict=dlr_static_route_dict)

    return new_dlr['objectId'], new_dlr['location']

def _dlr_create(client_session, datacenter_name, edge_datastore, edge_cluster, vcenter_ip, vcenter_user,
                                       vcenter_pwd, vcenter_port, **kwargs):
    dlr_name = kwargs['dlr_name']
    dlr_pwd = kwargs['dlr_pwd']
    dlr_size = kwargs['dlr_size']

    datacentermoid = get_datacentermoid (datacenter_name, vcenter_ip, vcenter_user, vcenter_pwd, vcenter_port)
    datastoremoid = get_datastoremoid (datacenter_name, edge_datastore, vcenter_ip, vcenter_user, vcenter_pwd,
                                       vcenter_port)
    resourcepoolid = get_edgeresourcepoolmoid(datacenter_name, edge_cluster, vcenter_ip, vcenter_user, vcenter_pwd,
                                       vcenter_port)

    ha_ls_name = kwargs['ha_ls_name']
    # find ha_ls_id in vDS port groups or NSX logical switches
    ha_ls_id = get_vdsportgroupid (datacenter_name, ha_ls_name, vcenter_ip, vcenter_user, vcenter_pwd,
                                   vcenter_port="443")
    if not ha_ls_id:
        ha_ls_id, ha_ls_switch_params = get_logical_switch(client_session, ha_ls_name)
        if not ha_ls_id:
            print 'ERROR: DLR HA switch {} does NOT exist as VDS port group nor NSX logical switch'.format(ha_ls_name)
            return None

    uplink_ls_name = kwargs['uplink_ls_name']
    uplink_ip = kwargs['uplink_ip']
    uplink_subnet = kwargs['uplink_subnet']
    uplink_dgw = kwargs['uplink_dgw']
    # find uplink_ls_id in vDS port groups or NSX logical switches
    uplink_ls_id = get_vdsportgroupid (datacenter_name, uplink_ls_name, vcenter_ip, vcenter_user, vcenter_pwd,
                                   vcenter_port="443")
    if not uplink_ls_id:
        uplink_ls_id, uplink_ls_switch_params = get_logical_switch(client_session, uplink_ls_name)
        if not uplink_ls_id:
            print 'ERROR: DLR uplink switch {} does NOT exist as VDS port group nor NSX logical switch'\
                .format(uplink_ls_name)
            return None

    dlr_id, dlr_params = dlr_create(client_session, dlr_name, dlr_pwd, dlr_size, datacentermoid, datastoremoid,
                                    resourcepoolid, ha_ls_id, uplink_ls_id, uplink_ip, uplink_subnet, uplink_dgw)
    if kwargs['verbose']:
        print dlr_params
    else:
        print 'Distributed Logical Router {} created with the Edge-ID {}'.format(dlr_name, dlr_id)


def dlr_delete(client_session, dlr_name):
    """
    This function will delete a dlr in NSX
    :param client_session: An instance of an NsxClient Session
    :param dlr_name: The name of the dlr to delete
    :return: returns a tuple, the first item is a boolean indicating success or failure to delete the dlr,
             the second item is a string containing to dlr id of the deleted dlr
    """
    dlr_id, dlr_params = get_edge(client_session, dlr_name)
    if not dlr_id:
        return False, None
    client_session.delete('nsxEdge', uri_parameters={'edgeId': dlr_id})
    return True, dlr_id


def _dlr_delete(client_session, **kwargs):
    dlr_name = kwargs['dlr_name']
    result, dlr_id = dlr_delete(client_session, dlr_name)
    if result and kwargs['verbose']:
        return json.dumps(dlr_id)
    elif result:
        print 'Distributed Logical Router {} with the ID {} has been deleted'.format(dlr_name, dlr_id)
    else:
        print 'Distributed Logical Router deletion failed'


def dlr_read(client_session, dlr_name):
    """
    This funtions retrieves details of a dlr in NSX
    :param client_session: An instance of an NsxClient Session
    :param dlr_name: The name of the dlr to retrieve details from
    :return: returns a tuple, the first item is a string containing the dlr ID, the second is a dictionary
             containing the dlr details retrieved from the API
    """
    dlr_id, dlr_params = get_edge(client_session, dlr_name)
    return dlr_id, dlr_params


def _dlr_read(client_session, **kwargs):
    dlr_name = kwargs['dlr_name']
    dlr_id, dlr_params = dlr_read(client_session, dlr_name)
    if dlr_params and kwargs['verbose']:
        print json.dumps(dlr_params)
    elif dlr_id:
        print 'Distributed Logical Router {} has the ID {}'.format(dlr_name, dlr_id)
    else:
        print 'Distributed Logical Router {} not found'.format(dlr_name)


def dlr_list(client_session):
    """
    This function returns all DLR found in NSX
    :param client_session: An instance of an NsxClient Session
    :return: returns a tuple, the first item is a list of tuples with item 0 containing the DLR Name as string
             and item 1 containing the DLR id as string. The second item contains a list of dictionaries containing
             all DLR details
    """
    all_dist_lr = client_session.read_all_pages('nsxEdges', 'read')
    dist_lr_list = []
    dist_lr_list_verbose = []
    for dlr in all_dist_lr:
        if dlr['edgeType'] == "distributedRouter":
            dist_lr_list.append((dlr['name'], dlr['objectId']))
            dist_lr_list_verbose.append(dlr)
    return dist_lr_list, dist_lr_list_verbose


def _dlr_list_print(client_session, **kwargs):
    dist_lr_list, dist_lr_params = dlr_list(client_session)
    if kwargs['verbose']:
        print dist_lr_params
    else:
        print tabulate(dist_lr_list, headers=["DLR name", "DLR ID"], tablefmt="psql")


def main():
    parser = argparse.ArgumentParser(description="nsxv function for dlr '%(prog)s @params.conf'.",
                                     fromfile_prefix_chars='@')
    parser.add_argument("command", help="create: create a new dlr"
                                        "read: return the virtual wire id of a dlr"
                                        "delete: delete a dlr"
                                        "list: return a list of all dlr")
    parser.add_argument("-i",
                        "--ini",
                        help="nsx configuration file",
                        default="nsx.ini")
    parser.add_argument("-v",
                        "--verbose",
                        help="increase output verbosity",
                        action="store_true")
    parser.add_argument("-d",
                        "--debug",
                        help="print low level debug of http transactions",
                        action="store_true")
    parser.add_argument("-n",
                        "--name",
                        help="dlr name")
    parser.add_argument("-p",
                        "--dlrpassword",
                        help="dlr admin password",
                        default="VMware1!VMware1!")
    parser.add_argument("-s",
                        "--dlrsize",
                        help="dlr size (compact, large, quadlarge, xlarge)",
                        default="compact")
    parser.add_argument("--ha_ls",
                        help="dlr ha LS name")
    parser.add_argument("--uplink_ls",
                        help="dlr uplink LS name")
    parser.add_argument("--uplink_ip",
                        help="dlr uplink ip address")
    parser.add_argument("--uplink_subnet",
                        help="dlr uplink subnet")
    parser.add_argument("--uplink_dgw",
                        help="dlr uplink default gateway")
    args = parser.parse_args()

    if args.debug:
        debug = True
    else:
        debug = False

    config = ConfigParser.ConfigParser()
    config.read(args.ini)

    client_session = NsxClient(config.get('nsxraml', 'nsxraml_file'), config.get('nsxv', 'nsx_manager'),
                               config.get('nsxv', 'nsx_username'), config.get('nsxv', 'nsx_password'), debug=debug)

    datacenter_name = config.get('vcenter', 'datacenter_name')
    vcenter_ip = config.get('vcenter', 'vcenter_ip')
    vcenter_user = config.get('vcenter', 'vcenter_user')
    vcenter_pwd = config.get('vcenter', 'vcenter_pwd')
    vcenter_port = config.get('vcenter', 'vcenter_port')
    edge_datastore = config.get('vcenter', 'edge_datastore')
    edge_cluster = config.get('vcenter', 'edge_cluster')

    try:
        command_selector = {
            'list': _dlr_list_print,
            'create': _dlr_create,
            'delete': _dlr_delete,
            'read': _dlr_read,
        }
        command_selector[args.command](client_session,
                                       dlr_name=args.name, dlr_pwd=args.dlrpassword, dlr_size=args.dlrsize,
                                       datacenter_name=datacenter_name, edge_datastore=edge_datastore,
                                       edge_cluster=edge_cluster,
                                       vcenter_ip=vcenter_ip, vcenter_user=vcenter_user, vcenter_pwd=vcenter_pwd,
                                       vcenter_port=vcenter_port,
                                       ha_ls_name=args.ha_ls,
                                       uplink_ls_name=args.uplink_ls, uplink_ip=args.uplink_ip,
                                       uplink_subnet=args.uplink_subnet, uplink_dgw=args.uplink_dgw,
                                       verbose=args.verbose)

    except KeyError:
        print('Unknown command')
        parser.print_help()


if __name__ == "__main__":
    main()
