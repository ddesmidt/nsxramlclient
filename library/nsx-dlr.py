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
from libutils import get_dlr
from libutils import get_datacentermoid
from tabulate import tabulate
from nsxramlclient.client import NsxClient


def dlr_create(client_session, dlr_name, datacenterMoid, dlr_pwd,
               applianceSize="compact", datastore_id="datastore-32", resourcePoolId="resgroup-10",
               mgt_ls_id="dvportgroup-23", mgt_ip='', mgt_subnet='', uplink_ls_id="virtualwire-74",
               uplink_ip="172.16.2.2", uplink_subnet="255.255.255.0", dgw_ip="172.16.2.1", ):
    """
    This function will create a new dlr in NSX
    :param client_session: An instance of an NsxClient Session
    :param dlr_name: The name that will be assigned to the new dlr
    :param admin_pwd: The admin password of new dlr
    :param applianceSize: The DLR Control VM size
    :param datacenterMoid: The vCenter DataCenter ID where dlr control vm will be deployed
    :param datastore_id: The vCenter datastore ID where dlr control vm will be deployed
    :param resourcePoolId: The vCenter Cluster where dlr control vm will be deployed
    :param mgt_ls_id: New dlr management logical switch id or vds port group
    :param mgt_ip: New dlr management ip@
    :param mgt_subnet: New dlr management subnet
    :param uplink_ls_id: New dlr uplink logical switch id or vds port group
    :param uplink_ip: New dlr uplink ip@
    :param uplink_subnet: New dlr uplink subnet
    :param dgw_ip: New dlr default gateway
    :return: returns a tuple, the first item is the dlr ID in NSX as string, the second is string
             containing the dlr URL location as returned from the API
    """

    # get a template dict for the dlr create
    dlr_create_dict = client_session.extract_resource_body_schema('nsxEdges', 'create')

    # fill the details for the new dlr in the body dict
    dlr_create_dict['edge']['type'] = "distributedRouter"
    dlr_create_dict['edge']['name'] = dlr_name
    dlr_create_dict['edge']['cliSettings'] = {'password': admin_pwd, 'remoteAccess': "True",
                                              'userName': "admin"}
    dlr_create_dict['edge']['appliances']['applianceSize'] = applianceSize
    dlr_create_dict['edge']['datacenterMoid'] = datacenterMoid
    dlr_create_dict['edge']['appliances']['appliance']['datastoreId'] = datastore_id
    dlr_create_dict['edge']['appliances']['appliance']['resourcePoolId'] = resourcePoolId
    dlr_create_dict['edge']['mgmtInterface'] = {'connectedToId': mgt_ls_id}
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

    # add default gateway to the created dlr
    dlr_static_route_dict['routing']['staticRouting']['defaultRoute']['gatewayAddress'] = dgw_ip
    del dlr_static_route_dict['routing']['routingGlobalConfig']
    del dlr_static_route_dict['routing']['staticRouting']['staticRoutes']
    del dlr_static_route_dict['routing']['ospf']
    del dlr_static_route_dict['routing']['isis']
    del dlr_static_route_dict['routing']['bgp']

    dlr_static_route = client_session.update('routingConfig', uri_parameters={'edgeId': new_dlr['objectId']},
                                             request_body_dict=dlr_static_route_dict)

    return new_dlr['objectId'], new_dlr['location']

def _dlr_create(client_session, datacenter_name, vcenter_ip, vcenter_user,
                                       vcenter_pwd, vcenter_port, **kwargs):
    dlr_name = kwargs['dlr_name']
    dlr_pwd = kwargs['dlr_pwd']

    datacenterMoid = get_datacentermoid (datacenter_name, vcenter_ip, vcenter_user, vcenter_pwd, vcenter_port)

    dlr_id, dlr_params = dlr_create(client_session, dlr_name, datacenterMoid, dlr_pwd)
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
    dlr_id, dlr_params = get_dlr(client_session, dlr_name)
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
    dlr_id, dlr_params = get_dlr(client_session, dlr_name)
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

    try:
        command_selector = {
            'list': _dlr_list_print,
            'create': _dlr_create,
            'delete': _dlr_delete,
            'read': _dlr_read,
        }
        command_selector[args.command](client_session, datacenter_name, vcenter_ip, vcenter_user, vcenter_pwd,
                                       vcenter_port, dlr_name=args.name, dlr_pwd=args.dlrpassword, verbose=args.verbose)

    except KeyError:
        print('Unknown command')
        parser.print_help()


if __name__ == "__main__":
    main()
