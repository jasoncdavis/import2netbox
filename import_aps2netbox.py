"""Import Cisco WLC APs into NetBox (import_aps2netbox.py)

Extracts the Access Point information from a Cisco Wireless LAN 
Controller, eg. Cisco Cataylyst 9800 Wireless Controller and imports to
NetBox.  Specifically the AP Model, Name, Management IP address and
Site information

Required Inputs or Command-Line Arguments
    WLC and NetBox API creds should be defined in .env

Outputs:
    define here

Version log
v1    2024-0418  Initial development
#                                                                      #

Copyright 2024 Cisco Systems

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

Credits:
TBD
"""

__version__ = '1'
__author__ = 'Jason Davis - jadavis@cisco.com'
__license__ = 'Apache License, Version 2.0 - ' \
    'http://www.apache.org/licenses/LICENSE-2.0'


###############################################################################
# ####### Imports
from datetime import datetime
import os
from dotenv import dotenv_values
import json

import traceback
import lxml.etree as et
from argparse import ArgumentParser
from ncclient import manager
from ncclient.operations import RPCError
from ncclient.transport import errors

import requests
import urllib3
import pynetbox
from slugify import slugify
from pprint import pprint

from fuzzywuzzy import fuzz
import re

# Global variables for script - do not change
# GLOBALVAR = Null


###############################################################################
# ####### Class definitions
'''
class MyClass:
    """A simple example class"""
    i = 12345

    def f(self):
        return 'hello world'


class Complex:
    def __init__(self, realpart, imagpart):
        self.r = realpart
        self.i = imagpart
'''


###############################################################################
# ####### Module Function definitions

'''
def TEMPLATE_function(sender, recipient, message_body, priority=1) -> int:
    """Short description (<80 char)
    
    Longer description (multi-paragraph OK)

    :param str sender: The person sending the message
    :param str recipient: The recipient of the message
    :param str message_body: The body of the message
    :param priority: The priority of the message, can be a number 1-5
    :type priority: integer or None
    :return: the message id
    :rtype: int
    :raises ValueError: if the message_body exceeds 160 characters
    :raises TypeError: if the message_body is not a basestring
    """
    pass
'''

####

def create_devices_in_netbox(nb, records, model_maps, wlc):
    """Create devices in NetBox
    
    Take in a list of JSON records containing AP data and import to
    NetBox
    NetBox docs for device create
    https://<NETBOX>/api/schema/swagger-ui/#/dcim/dcim_devices_create
    API schema requires: name(str), device_type(int), role(int),
    site(int).
    Other optional, but suggested entries (for this project):
    serial(str), asset_tag(str), location(int), status(str matching
    specific statuses), primary_ip4(int - mapping previously created),
    description(str), comments(str), tags(see docs), 
    custom_fields(see docs)
    
    :param NBSession nb: NetBox session
    :param records: The AP data records
    :type records: List[JSON]
    :param model_maps: The device types/models mapped between WLC and NetBox
    :type model_maps: List[dictionary]
    :param wlc: dictionary of Wireless LAN Controller configuration
    :type wlc: List[dictionary]

    :return: the message id
    :rtype: int
    :raises ValueError: if the message_body exceeds 160 characters
    :raises TypeError: if the message_body is not a basestring
    """
    
    """for each item in apdata
          if IP address is listed, create and capture return int;
            otherwise don't add to device (later)
          
    """
    print(records)
    print(model_maps)
    nb_device_records = []
    for device in records:
        name = device['ap_name']
        print(device['model'])
        device_type = [mapping['nb_dt_id'] for mapping in model_maps
                       if mapping['wlc_model'] == device['model']][0]
        #print(device_type)
        role = nb.dcim.device_roles.get(slug='wireless-access-point').id
        #print(role)
        
        # Need a good method to associate top-level site with subordinate
        # location (also captured below)
        #print(wlc['site'])
        site = nb.dcim.sites.get(name=wlc['site'])
        #print(site, site.name, site.id)
        if site is None:
            # Create site
            site = nb.dcim.sites.create(dict(name=wlc['site'],
                                            slug=slugify(wlc['site'])
                                            )
                                        )
        siteid = site.id
        print(siteid)
        
        """Get other fields -  serial(str), asset_tag(str), location(int), status(str matching
        specific statuses), primary_ip4(int - mapping previously created),
        description(str), comments(str), tags(see docs), 
        custom_fields(see docs)"""
        serial = device['wtp_serial_num']
        asset_tag = None
        location = nb.dcim.locations.get(name=device['site_tag_name'])
        if location is None:
            # Create location
            location = nb.dcim.locations.create(dict(name=device['site_tag_name'],
                                                     slug=slugify(device['site_tag_name'])
                                                    )
                                                )
        locationid = location.id
        print(locationid)
        status = 'online'   # If we got it from the WLC, it must be online
        
        # tags - set custom site tag for WLC and site-tag
        custom_wlc = wlc['name']
        custom_sitetag = device['site_tag_name']
        
        # Create device
        nbdevice = nb.dcim.devices.create(name=name,
                                        device_type=device_type,
                                        role=role,
                                        site=siteid,
                                        serial=serial,
                                        asset_tag=asset_tag,
                                        location=locationid,
                                        status=status,
                                        #primary_ip4=ip_create_results.id,
                                        custom_fields={'SiteTag': custom_sitetag,
                                                       'WLC': custom_wlc}
                                        )
        print(nbdevice.id)
        
        #Create IP address and associate to newly created device
        # Management IP Address work
        mgmt_ip = device['ip_addr']
        # Get AP Device GigabitEthernet0 interface id
        interfaceid = nb.dcim.interfaces.get(name='GigabitEthernet0', device=name).id
        print(interfaceid)
        # Create IP address, if needed
        ip_create_results = nb.ipam.ip_addresses.create(dict(address = mgmt_ip + "/32",
                                                             status = 'dhcp',
                                                             role = 'vip',
                                                             assigned_object_type = 'dcim.interface',
                                                             assigned_object_id = interfaceid)
                                                        )
        # TODO - determine if the create was successful
        print(ip_create_results.id)
        
        # Update device record
        updatedevice = nb.dcim.devices.update([{'id': nbdevice.id,
                                                'primary_ip4': ip_create_results.id}])
        print(updatedevice)

    exit()


def extract_ap_data(nb, wlc, missing_aps, apdata):
    """Extract AP data from WLC apdata XML; create records
    
    Create the missing APs in NetBox; use device name, model, location
    and management IP address; tag with WLC

    :param NBSession nb: NetBox session
    :param str wlc: Wireless LAN Controller friendly name
    :param list missing_aps: List of strings representing missing APs to add
    :param xmlstr apdata: String of XML data extracted from WLC about AP data

    :return: the message id
    :rtype: int
    :raises ValueError: if the message_body exceeds 160 characters
    :raises TypeError: if the message_body is not a basestring
    """
    # For each missing AP: Extract AP record (capwap-data branch) from 
    # XML data
    root = et.fromstring(bytes(apdata, encoding='utf-8'))
    ap_records = []
    for ap in missing_aps:
        #print(ap)
        ns = {"ns":"http://cisco.com/ns/yang/Cisco-IOS-XE-wireless-access-point-oper"}
        ap_record = root.xpath(f'.//ns:name[text()="{ap}"]', 
                               namespaces=ns)[0].getparent()
        #print(et.tostring(ap_record))

        wtp_mac = et.tostring(ap_record.xpath(f'.//ns:wtp-mac', namespaces=ns)[0],
                              pretty_print=True, encoding=str,
                              method='text')
        ip_addr = et.tostring(ap_record.xpath(f'.//ns:ip-addr', namespaces=ns)[0],
                              pretty_print=True, encoding=str,
                              method='text')
        wtp_serial_num = et.tostring(ap_record.xpath(f'.//ns:wtp-serial-num',
                                     namespaces=ns)[0], pretty_print=True, 
                                     encoding=str, method='text')
        wtp_enet_mac = et.tostring(ap_record.xpath(f'.//ns:wtp-enet-mac', 
                                   namespaces=ns)[0], pretty_print=True, 
                                   encoding=str, method='text')
        radio_slots = et.tostring(ap_record.xpath(f'.//ns:radio-slots-in-use', 
                                  namespaces=ns)[0], pretty_print=True, 
                                  encoding=str, method='text')
        model = et.tostring(ap_record.xpath(f'.//ns:model', namespaces=ns)[0],
                              pretty_print=True, encoding=str,
                              method='text')
        num_slots = et.tostring(ap_record.xpath(f'.//ns:num-slots', namespaces=ns)[0],
                              pretty_print=True, encoding=str,
                              method='text')
        sw_version = et.tostring(ap_record.xpath(f'.//ns:sw-version', namespaces=ns)[0],
                              pretty_print=True, encoding=str,
                              method='text')
        location = et.tostring(ap_record.xpath(f'.//ns:location', namespaces=ns)[0],
                              pretty_print=True, encoding=str,
                              method='text')
        r_policy_tag = et.tostring(ap_record.xpath(f'.//ns:resolved-policy-tag', namespaces=ns)[0],
                              pretty_print=True, encoding=str,
                              method='text')
        r_site_tag = et.tostring(ap_record.xpath(f'.//ns:resolved-site-tag', namespaces=ns)[0],
                              pretty_print=True, encoding=str,
                              method='text')
        r_rf_tag = et.tostring(ap_record.xpath(f'.//ns:resolved-rf-tag', namespaces=ns)[0],
                              pretty_print=True, encoding=str,
                              method='text')
        site_tag_name = et.tostring(ap_record.xpath(f'.//ns:site-tag-name', namespaces=ns)[0],
                              pretty_print=True, encoding=str,
                              method='text')
        ap_profile = et.tostring(ap_record.xpath(f'.//ns:ap-profile', namespaces=ns)[0],
                              pretty_print=True, encoding=str,
                              method='text')
        rf_tag_name = et.tostring(ap_record.xpath(f'.//ns:rf-tag-name', namespaces=ns)[0],
                              pretty_print=True, encoding=str,
                              method='text')
        """print(wtp_mac, ip_addr, wtp_serial_num, wtp_enet_mac, radio_slots,
              model, num_slots, sw_version, location, r_policy_tag,
              r_site_tag, r_rf_tag, site_tag_name, ap_profile, rf_tag_name)"""
        ap_dict = {'ap_name': ap,
                   'wtp_mac': wtp_mac, 
                   'ip_addr': ip_addr, 
                   'wtp_serial_num': wtp_serial_num, 
                   'wtp_enet_mac': wtp_enet_mac, 
                   'radio_slots': radio_slots,
                   'model': model, 
                   'num_slots': num_slots, 
                   'sw_version': sw_version, 
                   'location': location,
                   'r_policy_tag': r_policy_tag,
                   'r_site_tag': r_site_tag, 
                   'r_rf_tag': r_rf_tag, 
                   'site_tag_name': site_tag_name, 
                   'ap_profile': site_tag_name, 
                   'rf_tag_name': rf_tag_name,
                   'wlc': wlc["name"]
                   }
        ap_records.append(ap_dict)
        
    return ap_records


def create_dt_mappings(nb_devicetypes, ap_models, nb):
    """Create Device Type Mappings
    
    The Device Type names from the NetBox Community Device Type project
    will be considered authoritative, so when we import the learned AP
    models from the WLC we need to map the two.  A 100 match will pass
    with no user input, but any other will run a fuzzy search to suggest
    a match to the user to assign or create a new device-type.
    
    :param list nb_devicetypes: The latest NetBox Device Type model
        names
    :param list ap_models: The AP model types extracted from the WLC
    :param NBSessionHandler nb: NetBox session handler

    :return: mapping of WLC types to NB name and id
    :rtype: list of dictionaries
    :raises ValueError: if the message_body exceeds 160 characters
    :raises TypeError: if the message_body is not a basestring
    """
    #ap_models = ['C9130AXI-B','Catalyst 9120AXI-E']
    tuples_list = [[(i, j, fuzz.partial_ratio(i,j))
                    for j in nb_devicetypes]
                   for i in ap_models]
    #print(tuples_list)
    print("-" * 40)

    fileupdates = []
    for impmodel in tuples_list:
        impmodel.sort(reverse=True, key = lambda x: x[2])
        #print(impmodel[0][2])
        if impmodel[0][2] == 100:
            print(f"Found an exact match for \"{impmodel[0][0]}\", using that")
            dt_id = nb.dcim.device_types.get(model=impmodel[0][1]).id
            fileupdates.append({'wlc_model': impmodel[0][0],
                    'nb_model': impmodel[0][1],
                    'nb_dt_id': dt_id})
        else:
            match = re.search(r'(\d{4})', impmodel[0][0], re.M)
            print(f"For user input of device model \"{impmodel[0][0]}\" "
                  f"no exact matches were found.\nPlease select an "
                  f"approximate match from the known, supported models "
                  f"below or '7' to create a new model"
                  f"\n       Match      Known model"
                  f"\n_ # __ Factor ___    name     _________")
            for index, item in enumerate(impmodel[0:5], start=1):
                print(f"  {index} -    {item[2]}       {item[1]}")
            if match:
                print(f"  6 -            Try a broader search against "
                  f"\"{match.group(1)}\""
                  f"\n  7 -            No best match - create a new model named "
                  f"\"{impmodel[0][0]}\"")
            else:
                print(f"\n  7 -            No best match - create a new model named "
                  f"\"{impmodel[0][0]}\"")
            while True:
                try:
                    choice = int(input("What is your selection number? "))
                except ValueError:
                    print("That wasn't an option, try again.")
                else:
                    print(f"Going forward match WLC [{impmodel[0][0]}] " 
                          f"with NetBox [{impmodel[choice - 1][1]}] ",
                          end='')
                    dt_id = nb.dcim.device_types.get(model=impmodel[choice - 1][1]).id
                    print(f"with id = [{dt_id}]")
                    fileupdates.append({'wlc_model': impmodel[0][0],
                                        'nb_model': impmodel[choice - 1][1],
                                        'nb_dt_id': dt_id})
                    break
            #print(f"User selected - [{choice}]")
        print("-" * 40)

    if fileupdates:
        with open('wlc2nb_mapping.json', 'a') as file:
            json.dump(fileupdates, file)
    #print(tuples_list)


################
def do_device_work(nb, wlc, apdata, model_maps):
    """Do the NetBox device work - extract device information from WLC info,
    compare and create new
    
    Extract current device list from NetBox, compare current
    device (AP) information from polled AP data, then 
    compare and create new devices, as needed.

    :param session nb: NetBox session handler
    :param str wlc: WLC friendly name
    :param str apdata: String of XML data representing AP parameters
    :param model_maps: The mapping of WLC derived device models to
        NetBox known device types (with associated id (int))
    :type model_maps: List[JSON]

    """
    nb_devicenames = [device.name for device in list(nb.dcim.devices.filter(role='wireless-access-point'))]
    root = et.fromstring(bytes(apdata, encoding='utf-8'))
    learned_ap_names = set(root.xpath("//*[local-name()='name']/text()"))
    print(learned_ap_names)

    # Look to see if the device(s) is/are already in NetBox
    missing_aps = [ap for ap in learned_ap_names if ap not in nb_devicenames]
    known_aps = [ap for ap in learned_ap_names if ap in nb_devicenames]
    print(f"Missing AP(s): {missing_aps}")
    print(f"Known AP(s): {known_aps}")
    
    # Create missing APs
    ap_results = extract_ap_data(nb, wlc, missing_aps, apdata)
    #print(ap_results)
    create_devices_in_netbox(nb, ap_results, model_maps, wlc)
    exit()
    create_results = import_to_netbox(ap_results)
    nb_locationnames = [location.name for location in list(nb.dcim.locations.all())]
    print(nb_sitenames)
    print(nb_locationnames)
    # Get all site/locations (as site-tags) from WLC AP data
    root = et.fromstring(bytes(apdata, encoding='utf-8'))
    site_tags = set(root.xpath("//*[local-name()='site-tag-name']/text()"))
    print(site_tags)
    missing_locations = [site for site in site_tags
                         if site not in nb_locationnames]
    if not missing_locations:
        # No missing sites to configure
        print("No missing Locations to import")
    else:
        # We have missing Locations to add to NetBox
        print(f"Missing Locations(s): {missing_locations}")
        print(f"The following Sites exist: {",".join(nb_sitenames)}")
        for location in missing_locations:
            site4location = input(f"Enter Site to associate with {location}: ")
            siteid = nb.dcim.sites.get(name=site4location).id
            new_location = nb.dcim.locations.create(dict(
                name=location,
                slug=slugify(location),
                site=siteid
            ))
            print(new_location)
            print(f"Created Location \"{new_location.name}\" with following results -")
            pprint(dict(new_location), indent=4)


def do_device_model_work(nb, apdata):
    """Do the NetBox site work - extract device models, compare and create new
    
    Extract current device model list from NetBox, compare with device
    models of polled AP data, then compare and create new models, as 
    needed.  For efficiency we are leveraging the NetBox Community 
    Device Type project - 
    https://github.com/netbox-community/Device-Type-Library-Import
    This should be pre-loaded into NetBox and serves as the basis for
    assignments.  When there is a full match, it is used.  When there is
    not a match the system uses a 'fuzzy search' algorithm and suggests
    to the user what NetBox Community Device Type project model should
    be used an a future 'mapping' file is created/updated to ensure less
    user input is needed going forward.

    :param session nb: NetBox session handler
    :param str apdata: String of XML data representing AP parameters

    """
    print('Got to do_device_model_work')
    # Get all wireless AP model types from WLC AP data
    root = et.fromstring(bytes(apdata, encoding='utf-8'))
    ap_models = set(root.xpath("//*[local-name()='model']/text()"))
    
    original_content = None
    try:
        with open('wlc2nb_mapping.json', 'r') as file:
            original_content = json.load(file)
    except FileNotFoundError:
        # No previous mapping file, so safe to assume we've never done
        # this process
        pass
    else:
        print(original_content)
        missing_dts = [device_type for device_type in ap_models
                       if not any(model['wlc_model'] == device_type 
                       for model in original_content)]
        print(missing_dts)
        if not missing_dts:
            return

    nb_devicetype_names = [dt.model for dt in list(nb.dcim.device_types.all())]
    #print(nb_devicetype_names)
    #print(ap_models)
    create_dt_mappings(nb_devicetype_names, ap_models, nb)


def do_location_work(nb, apdata):
    """Do the NetBox site/location work - extract sites and locations,
    compare and create new
    
    Extract current site and location lists from NetBox, compare current
    sites/locations with sites/locations in polled AP data, then 
    compare and create new sites/locations, as needed.
    Note: per recommendations from Wireless SMEs we are using the WLC
    YANG Model leaf for site-tag-name to identify the 'location' and
    putting that into NetBox Locations.  NetBox sites are considered a
    higher-order object, roughly a building - they are not hierarchical,
    whereas a Location can be nested (floors in a building, conference
    spaces in a 'hall', etc.)

    :param session nb: NetBox session handler
    :param str apdata: String of XML data representing AP parameters

    """
    nb_sitenames = [site.name for site in list(nb.dcim.sites.all())]
    nb_locationnames = [location.name for location in list(nb.dcim.locations.all())]
    print(nb_sitenames)
    print(nb_locationnames)
    # Get all site/locations (as site-tags) from WLC AP data
    root = et.fromstring(bytes(apdata, encoding='utf-8'))
    site_tags = set(root.xpath("//*[local-name()='site-tag-name']/text()"))
    print(site_tags)
    missing_locations = [site for site in site_tags
                         if site not in nb_locationnames]
    if not missing_locations:
        # No missing sites to configure
        print("No missing Locations to import")
    else:
        # We have missing Locations to add to NetBox
        print(f"Missing Locations(s): {missing_locations}")
        print(f"The following Sites exist: {",".join(nb_sitenames)}")
        for location in missing_locations:
            site4location = input(f"Enter Site to associate with {location} [or 'NEW' if a new site is needed]: ")
            if site4location == 'NEW':
                # Ask for new site name
                site4location = input(f"Enter NEW site name to associate with {location}: ")
                siteid = nb.dcim.sites.create(name=site4location,
                                              slug=slugify(site4location)
                                             )
            siteid = nb.dcim.sites.get(name=site4location).id
            new_location = nb.dcim.locations.create(dict(
                name=location,
                slug=slugify(location),
                site=siteid
            ))
            print(new_location)
            print(f"Created Location \"{new_location.name}\" with following results -")
            pprint(dict(new_location), indent=4)


def do_netbox_work(netbox: dict[str], wlc: str, apdata: str):
    """Parent function to call all NetBox work
    
    Parent function that takes in the WLC AP information and processes 
    the Sites, Devices Models and final Device import

    :param dict netbox: Dictionary with NetBox environment parameters
    :param str wlc: Friendly name of the Wireless LAN Controller to
        associate/tag in NetBox
    :param str apdata: XML formatted data representing the AP info

    :return: the message id
    :rtype: int
    """
    # Do initial NetBox connection
    session = requests.Session()
    session.verify = False
    nb = pynetbox.api(f"{netbox['NETBOX_SCHEME']}://{netbox['NETBOX_HOST']}:{netbox['NETBOX_PORT']}",
                      token=netbox["NETBOX_APIKEY"])
    nb.http_session = session
    #print(nb.status())
    
    # Process Site/Location info - any new Locations to create in NB?
    do_location_work(nb, apdata)
    # 
    # Process Device Model info - any new Device Models to create in
    # NB?  Note: this has an interactive component to associate known
    # device models with that passed in
    do_device_model_work(nb, apdata)
    
    # Read final mapping file and return
    with open('wlc2nb_mapping.json', 'r') as file:
        model_mapping = json.load(file)
    
    print('Got here')
    print(model_mapping)
    #
    # Process actual device imports
    do_device_work(nb, wlc, apdata, model_mapping)


def get_netconf_data(device, xmlrpc):
    """Get NETCONF data helper function - pass in RPC as XML data
    
    Helper function to get NETCONF data from a device; RPC request is
    passed in as XML
    """
    # connect to netconf agent
    try:
        with manager.connect(host=device['host'],
                            port=device['port'],
                            username=device['username'],
                            password=device['password'],
                            timeout=45,
                            hostkey_verify=False,
                            device_params={'name': 'iosxe'}) as m:

            # execute netconf operation
            try:
                response = m.dispatch(et.fromstring(xmlrpc))
                data = response.xml
            except RPCError as e:
                data = e.xml
                pass
            except Exception as e:
                traceback.print_exc()
                exit(1)

            return data
            '''
            # beautify output
            if et.iselement(data):
                data = et.tostring(data, pretty_print=True).decode()

            try:
                out = et.tostring(
                    et.fromstring(data.encode('utf-8')),
                    pretty_print=True
                ).decode()
            except Exception as e:
                traceback.print_exc()
                exit(1)

            print(out)
            '''
            
    except errors.SSHError:
            print(f'Unable to connect to device {device['name']}')
    except Exception as e:
        traceback.print_exc()
        exit(1)


def get_aps_from_wlc(wlc):
    """Get the wireless AP information from Cisco Wireless LAN Controller
    
    Use NETCONF RPC to query the Cisco-IOS-XE-Wireless-Access-Point-Oper
    YANG model and extract information, such as AP name, serial, model,
    management IP, etc
    
    :param dict wlc: Dictionary defining the WLC creds

    """
    payload = '''
<get xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <filter>
    <access-point-oper-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-wireless-access-point-oper">
      <capwap-data>
        <wtp-mac/>
        <ip-addr/>
        <name/>
        <device-detail>
          <static-info>
            <board-data>
              <wtp-serial-num/>
              <wtp-enet-mac/>
            </board-data>
            <descriptor-data>
              <radio-slots-in-use/>
            </descriptor-data>
            <ap-models>
              <model/>
            </ap-models>
            <num-slots/>
          </static-info>
          <wtp-version>
            <sw-version/>
          </wtp-version>
        </device-detail>
        <ap-location/>
        <tag-info/>
        <wtp-ip/>
      </capwap-data>
    </access-point-oper-data>
  </filter>
</get>
'''
    return get_netconf_data(wlc, payload)


def get_wlcs(config):
    """Create list of WLCs to work on - ingested from dotenv import
    
    Look for WLC[*]_ entries in .env and create list of dictionary items

    :param dict config: A dictionary of environment settings from dotenv
    :return: WLC information as dict
    :rtype: list
    """
    #print(config)
    wlcs = json.loads(config['WLCs'])
    #print(wlcs)
    new_wlc_list = []
    for wlc in wlcs:
        quoteshifted = eval(config[wlc].replace("'", "\""))
        new_wlc_list.append(quoteshifted)
    return new_wlc_list


'''def get_runtime_args():
    """Get user inputs for runtime options

    Uses ArgumentParser to read user CLI inputs and arguments.
    Validates user inputs and requirements.

    :returns: args as user arguments
    """
    parser = argparse.ArgumentParser(description='Execute config change monitoring for device via NETCONF.')
    parser.add_argument('-d', '--device', type=str, required=True,
                        help='The device name or IP address to monitor')
    parser.add_argument('-u', '--username', type=str, required=True,
                        help="The device's NETCONF user name for access")
    parser.add_argument('-p', '--password', type=str, required=True,
                        help="The device's NETCONF user's password for access")

    args = parser.parse_args()

    return args
'''

####### Module Function definitions above
###############################################################################
####### Main function definition below

def main():
    """Do the main work of collecting AP data, converting and importing
    
    Call the high-level functions of collecting the AP data from the
    WLC(s), then converting it, then importing it into NetBox
    """
    urllib3.disable_warnings()

    now = datetime.now() # current date and time
    date_time = now.strftime("%Y%m%d-%H%M%S")
    date_time_verbose = now.strftime("%A, %B %d, %Y at %H:%M:%S %Z")
    
    # Ensure logs directory exists
    #if not os.path.exists(f'{log_path}'): os.makedirs(f'{log_path}') 
    config = {
            **dotenv_values(".env"),  # load shared development variables
            **dotenv_values(".env.secret"),  # load sensitive variables
            **os.environ,  # override loaded values with environment variables
        }
    wlcs = get_wlcs(config)
    for wlc in wlcs:
        apdata = get_aps_from_wlc(wlc)
        do_netbox_work(config, wlc, apdata)


if __name__ == '__main__':
    try:
        #args = get_runtime_args()
        main()
    except KeyboardInterrupt:
        print(f'\nUser stopped execution...Exiting.')
        exit()