"""Import CSV file with network device data into NetBox

    Uses CSV file to import device inventory into NetBox using PyPi 
    package pynetbox

    Args:
    usage: import_csv2nb.py [-h] [-f import.csv] -a/-i

    options:
    -h, --help            show this help message and exit
    -d, --file filename   CSV file to use for import
    -i, --idf             Identifies IDF switches are being imported
    -a, --access          Identified access switches are being imported
    
    Inputs/Reference files:
        (filename).csv    Filename containing devices to import
                          Examples are supplied as import-example.xslt
                          and import-example.csv

        import_csv2nb.yaml - contains NetBox server specs -
            server IP/hostname, access credentials, etc
            (See examples/*.yaml for formatting guidance)
 
    Returns:
        Output to console while running shows progress of import. 


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

import sys
import os
from common.getEnv import getparam
from callnetboxapi import getnetbox, postnetbox
import json
import pynetbox
from pprint import pprint
import requests
import csv
import pandas as pd
import numpy as np
import argparse
from slugify import slugify
from map_dt2netbox import map2nbdt


def get_nb_env():
    # Gets the NetBox environment parameters - server name/IP, creds
    # Check to see if we're using an environment variable, if so - use
    token = os.getenv('NETBOX_API_TOKEN')
    nbenv = getparam('NetBox')
    if token is None and nbenv is None:
        sys.exit('No NETBOX_API_TOKEN in environment or project'
                 ' YAML file found.  Exiting.')
    if token is None:
        return nbenv
    else:
        # Use the token in the environment variable with the parameters
        # file server info
        nbenv.update({'NETBOX_API_TOKEN': token})
        return nbenv
    # Read project environment parameters file


def process_tg(nb):
    # Process Tenant-Groups
    tg_items = getparam('Tenant-Groups', envfile='infra.yaml')
    #print(tg_items)
    
    tgnames = [tg['name'] for tg in tg_items]
    #print(tgnames)
    nb_tgnames = [tg.name for tg in list(nb.tenancy.tenant_groups.all())]
    #print(nb_tgnames)
    missing_tg = list(set(tgnames).difference(nb_tgnames))
    #print(missing_tg)
    if not missing_tg:
        # No missing tenant-groups to configure
        print("No missing Tenant-Groups")
    else:
        # We have missing tenant-groups to add to NetBox
        nb_adds = [tg for tg in tg_items if tg["name"] in missing_tg]
        print(f"Missing Tenant-Groups: {nb_adds}")
        new_tgs = nb.tenancy.tenant_groups.create(nb_adds)
        #print(new_tgs)


def process_tenants(nb):
    # Process Tenants
    tenant_items = getparam('Tenants', envfile='infra.yaml')
    #print(tenant_items)
    
    tenantnames = [tenant['name'] for tenant in tenant_items]
    #print(tenantnames)
    nb_tenantnames = [tenant.name for tenant in list(nb.tenancy.tenants.all())]
    #print(nb_tenantnames)
    missing_tenants = list(set(tenantnames).difference(nb_tenantnames))
    #print(missing_tenants)
    if not missing_tenants:
        # No missing tenants to configure
        print("No missing Tenants")
    else:
        # We have missing tenant-groups to add to NetBox
        nb_adds = [tenant for tenant in tenant_items if tenant["name"] in missing_tenants]
        print(f"Missing Tenant(s): {nb_adds}")
        new_tgs = nb.tenancy.tenants.create(nb_adds)
        #print(new_tgs)
        for i in new_tgs:
            print(f"Created tenant \"{i.name}\" with following results -")
            pprint(dict(i), indent=4)


def process_regions(nb):
    # Process Regions
    region_items = getparam('Regions', envfile='infra.yaml')
    #print(region_items)
    
    regionnames = [region['name'] for region in region_items]
    #print(regionnames)
    nb_regionnames = [region.name for region in list(nb.dcim.regions.all())]
    #print(nb_regionnames)
    missing_regions = list(set(regionnames).difference(nb_regionnames))
    #print(missing_regions)
    if not missing_regions:
        # No missing regions to configure
        print("No missing Regions")
    else:
        # We have missing regions to add to NetBox
        nb_adds = [region for region in region_items if region["name"] in missing_regions]
        print(f"Missing Tenant(s): {nb_adds}")
        new_tgs = nb.dcim.regions.create(nb_adds)
        #print(new_tgs)
        for i in new_tgs:
            print(f"Created region \"{i.name}\" with following results -")
            pprint(dict(i), indent=4)


def process_sitegroups(nb):
    # Process Site Groups
    sitegroup_items = getparam('Site-Groups', envfile='infra.yaml')
    #print(sitegroup_items)
    
    sitegroupnames = [sitegroup['name'] for sitegroup in sitegroup_items]
    #print(sitegroupnames)
    nb_sitegroupnames = [sitegroup.name for sitegroup in list(nb.dcim.site_groups.all())]
    #print(nb_sitegroupnames)
    missing_sitegroups = list(set(sitegroupnames).difference(nb_sitegroupnames))
    #print(missing_sitegroups)
    if not missing_sitegroups:
        # No missing sitegroups to configure
        print("No missing Site-Groups")
    else:
        # We have missing sitegroups to add to NetBox
        nb_adds = [sitegroup for sitegroup in sitegroup_items if sitegroup["name"] in missing_sitegroups]
        print(f"Missing Site-Group(s): {nb_adds}")
        new_tgs = nb.dcim.site_groups.create(nb_adds)
        #print(new_tgs)
        for i in new_tgs:
            print(f"Created Site-Group \"{i.name}\" with following results -")
            pprint(dict(i), indent=4)


def process_sites(nb):
    # Process Sites
    site_items = getparam('Sites', envfile='infra.yaml')
    #print(site_items)
    
    sitenames = [site['name'] for site in site_items]
    #print(sitenames)
    nb_sitenames = [site.name for site in list(nb.dcim.sites.all())]
    #print(nb_sitenames)
    missing_sites = list(set(sitenames).difference(nb_sitenames))
    #print(missing_sites)
    if not missing_sites:
        # No missing sites to configure
        print("No missing Sites")
    else:
        # We have missing sites to add to NetBox
        nb_adds = [site for site in site_items if site["name"] in missing_sites]
        print(f"Missing Site(s): {nb_adds}")
        new_tgs = nb.dcim.sites.create(nb_adds)
        #print(new_tgs)
        for i in new_tgs:
            print(f"Created Site \"{i.name}\" with following results -")
            pprint(dict(i), indent=4)


def process_manufacturers(nb):
    """Read infrastructure YAML file (infra.yaml) and import manufacturers"""
    manufacturer_items = getparam('Manufacturers', envfile='infra.yaml')
    #print(site_items)
    
    manufacturernames = [manufacturer['name'] for manufacturer in manufacturer_items]
    #print(sitenames)
    nb_manufacturernames = [manufacturer.name for manufacturer in list(nb.dcim.manufacturers.all())]
    #print(nb_sitenames)
    missing_manufacturers = list(set(manufacturernames).difference(nb_manufacturernames))
    #print(missing_sites)
    if not missing_manufacturers:
        # No missing sites to configure
        print("No missing Manufacturers")
    else:
        # We have missing manufacturers to add to NetBox
        nb_adds = [manufacturer for manufacturer in manufacturer_items if manufacturer["name"] in missing_manufacturers]
        print(f"Missing Manufacturer(s): {nb_adds}")
        new_manufacturers = nb.dcim.manufacturers.create(nb_adds)
        #print(new_tgs)
        for i in new_manufacturers:
            print(f"Created Manufacturer \"{i.name}\" with following results -")
            pprint(dict(i), indent=4)


def opencsv(file):
    colnames=['Name', 'ManagementIP', 'DeviceType', 'SerialNumber', 
              'Custom_SWVer', 'Custom_Function', 'Site', 'Location', 
              'AreaRoom', 'Comments'] 
    #inventory = pd.read_csv(file, names=colnames, header=0, comment='#')
    inventory = pd.read_csv(file, header=0, comment='#', quoting=2)
    inventory_dict = inventory.to_dict(orient='records')
    #print(inventory_dict)
    return inventory_dict


def get_sites(inventory_dict):
    results = [ item['Site'] for item in inventory_dict ]
    #print(results)
    #print(set(results))
    # Remove any 'NaN' or 'nan' entries that pandas may have included
    results = {x for x in results if pd.notna(x)}
    #print(results)
    unique_sites = sorted(results)
    #print(unique_sites)
    return unique_sites


def get_locations(inventory_dict):
    results = [ (item['Site'], item['Location']) for item in inventory_dict ]
    #print(results)
    # Remove any 'NaN' or 'nan' entries that pandas may have included
    #results = {x for x in results if pd.notna(x) and x != (np.nan, np.nan)}
    results = {x for x in results if x != (np.nan, np.nan)}
    #print(results)
    unique_locations = sorted(results)
    #print(unique_locations)
    return unique_locations


def build_sites(nb, sites, default_items):
    # Builds sites in Netbox via pynetbox library
    # nb = netbox session
    # sites = list of sites to create
    # https://NETBOX_SERVER/api/schema/swagger-ui/#/dcim/dcim_sites_create
    #   shows we need to provide name and slug (url-friendly name)
    #   I will also assume status, region, tenant, timezone
    #       *change to suit your situation*
    status = "planned" # Provide as string to create method

    region_id = nb.dcim.regions.get(name=default_items['region']).id
    sitegroup_id = nb.dcim.site_groups.get(name=default_items['site-group']).id
    tenant_id = nb.tenancy.tenants.get(name=default_items['tenant']).id

    for site in sites:
        try:
            result = nb.dcim.sites.create(
                name=site,
                slug=slugify(site),
                status=status,
                region=region_id,
                group=sitegroup_id,
                tenant=tenant_id,
                time_zone=default_items['timezone']
            )
        except pynetbox.core.query.RequestError as e:
            if "already exists" in e.error:
                print(f"SKIPPED adding site '{site}' as it already exists")
            else:
                print(e.error)
        else:
            print(f"Site '{result}' created.")


def build_locations(nb, locations, default_items):
    # Builds locations (with hierarchy) in Netbox via pynetbox library
    # nb = netbox session
    # locations = list of tuples [as (site, location) to create
    # https://NETBOX/api/schema/swagger-ui/#/dcim/dcim_locations_create
    #   shows we need to provide name, slug (url-friendly name), and
    #   site (as id)
    #   I will also assume status, tenant
    #       change to suit your situation
    status = "planned" # Provide as string to create method

    tenant_id = nb.tenancy.tenants.get(name=default_items['tenant']).id

    for location in locations:
        try:
            #print(location)
            # modify name to fit url-friendly slug version
            #slug = location[1].lower().replace(" ", "").replace(",", "_")
            site_id = nb.dcim.sites.get(name=location[0]).id
            result = nb.dcim.locations.create(
                name=location[1],
                slug=slugify(location[1]),
                site=site_id,
                status=status,
                tenant=tenant_id
            )
        except pynetbox.core.query.RequestError as e:
            if "already exists" in e.error:
                print(f"SKIPPED adding location '{location[1]}' "
                      f"as it already exists in site '{location[0]}'")
            else:
                print(e.error)
        else:
            print(f"Location '{result}' created.")


def create_nb_devicetype(nb, devicetype):
    """Builds device-type in Netbox via pynetbox library
    nb = netbox session
    devicetype = device type to create
    
    https://NETBOX/api/schema/swagger-ui/#/dcim/dcim_device_types_create
        schema requires manufacturer (int), model (string), slug (string),
        
    Will assume Cisco Systems manufacturer for this script
    """
    manufacturer = "Cisco"
    model = devicetype
    #slug = devicetype.lower().replace(" ", "")
    try:
        result = nb.dcim.device_types.create(
            manufacturer=nb.dcim.manufacturers.get(name=manufacturer).id,
            model=model,
            slug=slugify(devicetype)
            )
    except pynetbox.core.query.RequestError as e:
        if "already exists" in e.error:
            print(f"SKIPPED adding device-type '{model}' as it already exists")
        else:
            print(e.error)
    else:
        print(f"Device-Type '{result}' created.")
        return result


def create_nb_device_role(nb, devicerole):
    """Builds device-role in Netbox via pynetbox library
    nb = netbox session
    devicerole = device role to create
    
    https://NETBOX/api/schema/swagger-ui/#/dcim/dcim_device_roles_create
    schema requires name (string), slug (string)
        
    """
    #slug = devicerole.lower()
    try:
        result = nb.dcim.device_roles.create(
            name=devicerole,
            slug=slugify(devicerole)
            )
    except pynetbox.core.query.RequestError as e:
        if "already exists" in e.error:
            print(f"SKIPPED adding device-role '{devicerole}' as it already exists")
        else:
            print(e.error)
    else:
        print(f"Device-Role '{result}' created.")
        return result


def map_devicetypes(nb, inventory_dict):
    """Map imported inventory with known, authoritative NetBox device-types
    
    Take the imported device inventory, with possible bad human input,
    then map to known authoritative NetBox device-types that were
    previously imported from the NetBox Community Device-Type project.
    Ask user to confirm their input aligns to known device-types/models
    by fuzzy search algorithm, then put that into a lookup file for
    faster retreival in the future
    """
    # Get all unique device-type entries from inventory input
    unique_dts = {device['DeviceType'] for device in inventory_dict}
    #print(unique_dts)
    unique_dts.remove(np.nan)
    #print(unique_dts)
    
    # send unique entries to map_dt2netbox() module, receiving latest
    #   full mapping
    final_dt_map = map2nbdt(nb, unique_dts)
    return final_dt_map


def build_devices(nb, devices, default_items, args, dt_mappings):
    """ Builds devices in Netbox via pynetbox library
    nb = netbox session
    devices = list of dictionary records of device info
    
    https://NETBOX/api/schema/swagger-ui/#/dcim/dcim_devices_create
        shows we need to provide name, device_type (int), role (int),
        site (int), 
        
        I will also provide tenant (int), serial, location (int), status, 
            primary_ip4

    status can be "offline, active, planned, staged, failed, inventory,
        decommissioned"
        change to suit your situation
    """
    #print(devices)
    status = "inventory" # Provide as string to create method

    for device in devices:
        if device["Name"] is np.nan:
            continue
        print("=" * 60)
        print(f"Working device {device['Name']} with parameters of:\n{device}")
        name = device["Name"].lower()
        devicetype = device["DeviceType"]
        
        nb_devicetype_id = [device['nb_dt_id'] for device in dt_mappings
                            if device['imported_model'] == devicetype][0]
        print(f'{devicetype} is id "{nb_devicetype_id}"')

        '''nb_devicetype = nb.dcim.device_types.get(model=devicetype)
        if nb_devicetype:
            nb_devicetype_id = nb_devicetype.id
        else:
            nb_devicetype_id = create_nb_devicetype(nb, devicetype).id
        #print(nb_devicetype_id)
        '''
        
        if args.idf: role = 'IDF'
        if args.access: role = 'Access'
        #role = device["Custom_Function"]
        nb_device_role = nb.dcim.device_roles.get(name=role)
        if nb_device_role:
            nb_device_role_id = nb_device_role.id
        else:
            nb_device_role_id = create_nb_device_role(nb, role).id
        #print(nb_devicetype_id)

        site_id = nb.dcim.sites.get(name=device["Site"]).id
        print(f'Site Id for {device["Site"]} is {site_id}')
        
        tenant_id = nb.tenancy.tenants.get(name=default_items['tenant']).id
        print(f'Tenant Id for {default_items["tenant"]} is {tenant_id}')
        
        #print(f'Looking for location {device["Location"]} under site {device["Site"]} / {site_id}')
        #location_id = nb.dcim.locations.get({'name': device["Location"], 'site': {'name': device["Site"]}}).id
        #print({'name': device["Location"], 'site': {'name': device["Site"]}})
        location_id = nb.dcim.locations.get(name=device["Location"], site_id=site_id).id
        print(f'Location Id for {device["Location"]} is {location_id}')
        
        # Now to actually add the device
        print(type(device["SerialNumber"]))
        if device["SerialNumber"] != device["SerialNumber"]:
            # We got a nan / NaN value
            serialnumber = ''
            print('Got here')
        else:
            serialnumber = device["SerialNumber"]
        print(f'Serial Number for {name} is [{serialnumber}]')
        
        if device["AreaRoom"] != device["AreaRoom"]:
            # We got a nan / NaN value
            arearoom = 'TBD'
        else:
            arearoom = device["AreaRoom"]
        
        print(f'Setting device with values\n{name}, {nb_devicetype_id}, '
              f'{nb_device_role_id}, {tenant_id}, {serialnumber}, '
              f'{site_id}, {location_id}, {status}, {arearoom}')
        try:
            result = nb.dcim.devices.create(
                name=name,
                device_type=nb_devicetype_id,
                role=nb_device_role_id,
                tenant=tenant_id,
                serial=serialnumber,
                site=site_id,
                location=location_id,
                status=status,
                custom_fields={'AreaRoom': arearoom}
            )
        except pynetbox.core.query.RequestError as e:
            if "dcim_device_unique_name_site_tenant" in e.error:
                print(f"SKIPPED adding Device \'{device['Name']}\' "
                        f"as it already exists in site")
                continue
            else:
                print(e.error)
        else:
            print(f"Device '{result}' created.")
        
        # Build the management interface
        try:
            result = nb.dcim.interfaces.create(
                device=nb.dcim.devices.get(name=name).id,
                vdcs=[],
                name='Management',
                type='virtual'
            )
        except pynetbox.core.query.RequestError as e:
            if "already exists" in e.error:
                print(f"SKIPPED adding Interface 'Management' to device "
                      f"\'{name}\' as it already exists")
            else:
                print(e.error)
        else:
            print(f"Interface '{result}' for '{name}' created.")
        
        # Associate the IP Address to the new device's management int
        # If the device has no IP to associate to a management int; continue
        if device['ManagementIP'] is np.nan: continue
        try:
            result = nb.ipam.ip_addresses.create(
                address=device["ManagementIP"],
                status='reserved',
                assigned_object_id=result.id,
                assigned_object_type="dcim.interface"
            )
        except pynetbox.core.query.RequestError as e:
            if "already exists" in e.error:
                print(f"SKIPPED adding IP \'{device['ManagementIP']} "
                      f"as it already exists")
            else:
                print(e.error)
        else:
            print(f"IP Address \'{device['ManagementIP']}\' created.")
        
        # Re-associate to device with a patch/update
        try:
            result = nb.dcim.devices.update([
                {'id': nb.dcim.devices.get(name=name).id,
                 'primary_ip4': result.id}
            ])
        except pynetbox.core.query.RequestError as e:
            if "already exists" in e.error:
                print(f"SKIPPED adding IP \'{device['ManagementIP']} "
                      f"as it already exists")
            else:
                print(e.error)
        else:
            print(f"IP Address \'{device['ManagementIP']}\' associated.")



def importinfra(nb, args):
    """Import infrastructure records from project YAML file
     
    Imports infrastructure records of tenant-groups, tenants, regions, 
    site-groups, sites, etc from project YAML file
    If entries are non-existant, create, otherwise skip
    
    :param nb: (class of pynetbox.core.api.Api) Netbox session to
        interface with API
    :param args: (argparse namespace dictionary) import file, idf or 
        access switch settings
    """
    default_items = getparam('defaults', envfile='infra.yaml')

    # Process Tenant-Groups
    '''process_tg(nb)
    process_tenants(nb)
    process_regions(nb)
    process_sitegroups(nb)
    '''
    #process_sites(nb)
    #process_manufacturers(nb)
    
    inventory_dict = opencsv(args.file)
    #print(inventory_dict)

    # Import Sites (process sub-sites)
    sites = get_sites(inventory_dict)
    #print(sites)
    build_sites(nb, sites, default_items)
    locations = get_locations(inventory_dict)
    build_locations(nb, locations, default_items)
    dt_mappings = map_devicetypes(nb, inventory_dict)
    #print(dt_mappings)
    build_devices(nb, inventory_dict, default_items, args, dt_mappings)


def main(file):
    """
    Get Netbox env params
    Read CSV (or fail)
    Iterate over line-by-line
        ignore lines that are: blank, start with a space, start with a
        comma or start with a #
        
        
    """
    nbenv = get_nb_env()
    #print(nbenv)
    # Create NetBox session
    session = requests.Session()
    session.verify = False
    nb = pynetbox.api(f'{nbenv["scheme"]}://{nbenv["server"]}:{nbenv["port"]}',
                      token=nbenv["NETBOX_API_TOKEN"])
    nb.http_session = session
    #pprint(nb.status())
    importinfra(nb, args)


def get_cli_args():
    # Process Command Line arguments
    parser = argparse.ArgumentParser(prog='import_csv2nb',
                                     description='Import Network Devices'
                                     ' from Excel (as CSV) to NetBox',
                                    )
    parser.add_argument('-f', '--file', default='SwitchInv.csv',
                        help='CSV file to use for import, must be in current directory')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-i', '--idf', action='store_true',
                       help='IDF switches are being imported')
    group.add_argument('-a', '--access', action='store_true',
                       help='Access switches are being imported')
    return parser.parse_args()


# MAIN - Global scope
if __name__ == '__main__':
    # Run interactively, not imported from another Python module
    try:
        args = get_cli_args()
        #print(args)
        main(args)
    except KeyboardInterrupt:
        print(f'\n\nUser stopped with CTRL-C\n')
        try:
            sys.exit(130)
        except SystemExit:
            os._exit(130)