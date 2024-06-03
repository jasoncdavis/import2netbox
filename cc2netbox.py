"""Get Catalyst Center inventory and import to NetBox

    Uses Catalyst Center SDK, PyPi package dnacentersdk, to import 
    device inventory into NetBox using PyPi package pynetbox

    Args:
    usage: cc2netbox.py [-h] [-d] ***

    TO-DO Description

    options:
    -h, --help            show this help message and exit
    -d, --debug           Enables debug with copious console output, but none to InfluxDB
    
    Inputs/Reference files:
        cc2netbox.yaml - contains Catalyst Center service specs -
            server IP/hostname, access credentials, etc
            (See examples/*.yaml for formatting guidance)
 
    Returns:
        Output to console while running shows progress of periodic
        polls.  Running in 'debug mode' will provide much more detailed
        information


    Caveats:
        Must run in Python 3.11 or lower (higher than 3.9 preferrable)
        because Python 3.12 breaks module 'imp' import with dnacentersdk
        ModuleNotFoundError: No module named 'imp'
        https://github.com/PythonCharmers/python-future/issues/625
        
    Version History:
    1   2024-0522   Initial development
"""

# Credits:
__version__ = '1'
__author__ = 'Jason Davis - jadavis@cisco.com'
__license__ = "'Apache License, Version 2.0 - ' \
    'http://www.apache.org/licenses/LICENSE-2.0'"
########################################################################

#### Imports
import argparse
import sys
import os

from common.getEnv import getparam
from dnacentersdk import api
import requests
import pynetbox

from fuzzywuzzy import fuzz
from slugify import slugify



########################################################################
#### Class definitions


########################################################################
#### Function definitions

def get_role(cc_role, nb, nb_roles):
    # Match Catalyst Center role to existing NetBox roles, or create
    nb_role = nb.dcim.device_roles.get(name=cc_role)
    if nb_role is None:
        # Create missing Catalyst Center role in NetBox
        role = nb.dcim.device_roles.create(name=cc_role,
                                           slug=slugify(cc_role)
                                           )
        #print(role)
        return role['id']
    else:
        # Pass roleId back
        return nb_role['id']


def create_nb_devicetype(nb, device):
    # Create missing NetBox device-type
    # NetBox device-type create requires:
    #   manufacturer(id as int) - assuming Cisco since from CC,
    #   model(string) mapped from CC 'type',
    #   slug(string),
    # We'll also supplement with:
    #   part_number(string) mapped from CC 'platformId'
    #
    devicetype = nb.dcim.device_types.create(manufacturer=nb.dcim.manufacturers.get(name='Cisco').id,
                                             model=device['type'],
                                             slug=slugify(device['type']),
                                             part_number=device['platformId'])
    print(devicetype)
    print(devicetype['id'])


def import_devices(devices, nb, imp_locations, imp_devicetypes):
    # Import devices into NetBox
    # NetBox requires:
    #   name(str), device_type(int), role(int), site(int),
    # We will add:
    #   location(int), primary_ip4(int)[assigned in next step]
    nb_roles = list(nb.dcim.device_roles.all())

    for device in devices:
        nb_name = device['hostname']
        nb_devicetypeid = imp_devicetypes[f"{device['platformId']}"]
        if nb_devicetypeid == 99999:
            nb_devicetypeid = create_nb_devicetype(nb, device)
        nb_roleid = get_role(device['role'], nb, nb_roles)
        nb_locationid = imp_locations[f"{device['hostname']}/{device['managementIpAddress']}"]
        nb_siteid = nb.dcim.locations.get(id=nb_locationid)['site']['id']
        
        # Create new device entry
        newdevice = nb.dcim.devices.create(name=nb_name,
                                           device_type=nb_devicetypeid,
                                           role=nb_roleid,
                                           site=nb_siteid,
                                           location=nb_locationid)
        print(newdevice)
        print(newdevice['id'])
        
        # Add management interface; int, then IP
        # NetBox requires:
        #   name(str), device(id), vdcs(empty list), type(str),
        #   enabled(bool)
        newint = nb.dcim.interfaces.create(name='Management',
                                           device=newdevice['id'],
                                           vdcs=[],
                                           type='virtual',
                                           enabled=True)
        print(newint)
        print(newint['id'])
        
        # Create IP
        # NetBox requires:
        #   address(str with /mask), 
        # Also adding:
        #   "assigned_object_type": "dcim.interface",
        #   "assigned_object_id": newint.id,
        #   status('reserved')
        #   role('vip')
        newip = nb.ipam.ip_addresses.create(address=f"{device['managementIpAddress']}/32",
                                             assigned_object_type="dcim.interface",
                                             assigned_object_id=newint['id'],
                                             status='reserved',
                                             role='vip')
        print(newip)
        print(newip['id'])

        # Update device with management interface assignment
        updateddevice = nb.dcim.devices.update([{"id": newdevice['id'],
                                                 "primary_ip4": newip['id']}])


def get_fuzzy_matches(device, nb_devicetypes):
    # Get list of known device types from NetBox [imported in bulk earlier]
    #nb_dt_names = [devicetype["model"] for devicetype in nb_devicetypes]
    #print(nb_device_types)

    # Do fuzzy compares
    #print(f"Inside get_fuzzy_matches:\n{device}")
    """
    tuples_list = [[(i, j, fuzz.ratio(i,j), fuzz.partial_ratio(i,j),
                     fuzz.token_sort_ratio(i,j), fuzz.token_set_ratio(i,j))
                    for j in nb_device_types] for i in imported_models]
    """
    """tuples_list = [(device, j, fuzz.partial_ratio(device,j))
                    for j in nb_dt_names]"""
    tuples_list = [(device, 
                    j['model'], 
                    j['part_number'], 
                    j['id'], 
                    fuzz.partial_ratio(device,j['part_number']))
                   for j in nb_devicetypes]

    #print(tuples_list)
    #print("-" * 40)
    #for impmodel in tuples_list:
    tuples_list.sort(reverse=True, key = lambda x: x[4])
    #print(tuples_list)

    record = f"""  # For Catalyst Center platformId \"{device}\" modify 'CHANGE_ME' to a devicetypeId from
  # the known, supported NetBox device-types below or '99999' to create a new type
  #   Match    NetBox Known                                        NetBox Known
  #  _Factor_  _model name ______________________________________  _part number _____________ _(devicetypeId)_
"""
    for item in tuples_list[0:10]:
        record += f"  #   {item[4]:>4}     {item[1]:50}  {item[2]:25}     {item[3]:>6}\n"
    record += f"  {device}: CHANGE_ME\n\n"
    
    #print(record)
    return record



def generate_devicemodel_mapping_file(cc_devices, nb_devicetypes):
    # Creates a CC device to NB device-model mapping
    print(f"Several Catalyst Center device models need to be mapped "
          f"to known NetBox device-types.\nPlease refer to the newly "
          f"generated `DeviceModel_Mapping.yaml` file.\nEdit it to map "
          f"device-models to known NetBox device-types.\n\n")
    #print(f'Inside generate_devicemodel_mapping_file:\n{cc_devices}')
    unique_cc_devicetypes = {device for device in cc_devices}
    #print(unique_cc_devicetypes)
    
    device_mapping = """---
devices:
"""
    unique_cc_devicetypes = ['C9KV-UADP-8P', 'C9136']
    for devicetype in unique_cc_devicetypes:
        device_mapping += get_fuzzy_matches(devicetype, nb_devicetypes)
        #print(fuzzymatches)
    
    with open("DeviceModel_Mapping.yaml", "w") as file1:
        # Writing data to a file
        file1.writelines(device_mapping)
    

def process_devicemodels(devices, nb):
    # Take devices information, extract device-models from CC understanding,
    # proposed nearest match of NetBox device-types based on fuzzy match
    cc_devicemodels = {f"{device['platformId']}" for device in devices}
    #print(cc_devicemodels)
    
    # Get all NetBox location
    nb_devicetypes = list(nb.dcim.device_types.all())
    generate_devicemodel_mapping_file(cc_devicemodels, nb_devicetypes)


def generate_location_mapping_file(devices, nb_locations):
    # Creates a CC device to NB location mapping
    print(f"Several Catalyst Center devices need to be mapped to known "
          f"NetBox locations and sites.\nPlease refer to the newly "
          f"generated `Location_Mapping.yaml` file.\nEdit it to map "
          f"device location to NetBox location (site).\n")
    mapping_text = f"""---
# The following NetBox locations, location Ids and sites are known.
# Assign a location id to the Catalyst Center devices listed below.

"""
    for location in nb_locations:
        mapping_text += f"#Location `{location[0]:<32}` of site `{location[2]:<20}` is locationId {location[1]}\n"
    
    mapping_text += "\n\n#Catalyst Center devices\ndevices:\n"
    for device in devices:
        mapping_text += f"  {device['hostname']}/{device['managementIpAddress']}: locationId\n"

    #print(mapping_text)
    with open("Location_Mapping.yaml", "w") as file1:
        # Writing data to a file
        file1.writelines(mapping_text)


def process_sites(devices, nb):
    # Take devices information, extract sites from CC understanding,
    # Extract all NetBox sites; compare; ask user to reconcile
    # mismatches and/or make missing sites
    #locations = [device['location'] for device in devices]
    #locations = {f"{device['locationName']}" for device in devices}
    #print(locations)
    
    # Get all NetBox location
    nb_locations = list(nb.dcim.locations.all())
    #print(locations)
    nb_locations = {(location['name'], 
                     location['id'], 
                     location['site']['display']) for location in nb_locations}
    #print(nb_locations)
    
    """missing_locations = {location for location in locations
                         if location not in 
                         [nb_location[0] for nb_location in nb_locations]}
    #print(missing_locations)"""
    generate_location_mapping_file(devices, nb_locations)


def get_cc_devices():
    ccenv = getparam('CatalystCenter')

    # Create a DNACenterAPI connection object
    dnac = api.DNACenterAPI(username=ccenv['DNA_CENTER_USERNAME'],
                            password=ccenv['DNA_CENTER_PASSWORD'],
                            base_url=(f"{ccenv['protocol']}://"
                                      f"{ccenv['host']}:{ccenv['port']}"
                            ),
                            version=ccenv['DNA_CENTER_VERSION'],
                            verify=ccenv['DNA_CENTER_VERIFY'])

    # Find all devices that have 'Switches and Hubs' in their family
    devices = dnac.devices.get_device_list(family='Switches and Hubs')
    if len(devices['response']) > 0:
        return devices['response']
    else:
        return None

def get_cli_args():
    # Process Command Line arguments
    parser = argparse.ArgumentParser(prog='cc2netbox',
                                     description='Import Network Devices'
                                     ' from Catalyst Center to NetBox',
                                    )
    parser.add_argument('--stage2', action='store_true',
                        help='Run Second Stage import process')
    return parser.parse_args()


def main(args):
    """
    Get list of devices
    Get detailed device info
    Parse name, ip, device model, location, 
    format for push to NetBox
    Get NetBox env params
    Initiate session to NetBox
    Push to NetBox
    """
    # Get list of devices from Catalyst Center
    devices = get_cc_devices()
    #print(devices)

    # Initiate NetBox session
    nbenv = getparam('NetBox')
    # Create NetBox session
    session = requests.Session()
    session.verify = nbenv['verify_SSL']
    nb = pynetbox.api(f'{nbenv["scheme"]}://{nbenv["server"]}:{nbenv["port"]}',
                      token=nbenv["NETBOX_API_TOKEN"])
    nb.http_session = session
    #print(nb.status())

    if not args.stage2:
        # Initial run, generate mapping files
        # Process Locations/Sites for NetBox
        process_sites(devices, nb)
        
        # Process Device Types/Models for NetBox
        process_devicemodels(devices, nb)

        print('Re-run this script after editing Location_Mapping.yaml and '
            'DeviceModel_Mapping.yaml with:\n'
            '$ python cc2netbox.py --stage2')
    else:
        # Mapping files already generates and edited, do imports
        # Import Locations/Sites
        imp_locations = getparam('devices', envfile='Location_Mapping.yaml')
        print(imp_locations)
        
        # Import Device Models
        imp_devicetypes = getparam('devices', envfile='DeviceModel_Mapping.yaml')
        print(imp_devicetypes)
    
        # Import Devices to NetBox
        import_devices(devices, nb, imp_locations, imp_devicetypes)
        
        # Create Management IP Addresses and assignments for NetBox
    


########################################################################
# MAIN - Global scope
if __name__ == '__main__':
    # Run interactively, not imported from another Python module
    try:
        args = get_cli_args()
        main(args)
    except KeyboardInterrupt:
        print(f'\n\nUser stopped with CTRL-C\n')
        try:
            sys.exit(130)
        except SystemExit:
            os._exit(130)