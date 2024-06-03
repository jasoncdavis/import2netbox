"""Map device-type to NetBox (map_dt2netbox.py)

Receives a device-type/model (or list of) and maps to existing NetBox
Device-Type to ensure proper device import and association

Required Inputs or Command-Line Arguments
    WLC and NetBox API creds should be defined in .env

Outputs:
    define here

Version log
v1    2024-0425  Initial development
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
#from dotenv import dotenv_values
import json

import traceback
#import lxml.etree as et
from argparse import ArgumentParser

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

####

def create_dt_mappings(nb_devicetypes, imported_devicetypes, nb):
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
                   for i in imported_devicetypes]
    #print(tuples_list)
    print("-" * 40)

    fileupdates = []
    for impmodel in tuples_list:
        impmodel.sort(reverse=True, key = lambda x: x[2])
        #print(impmodel[0][2])
        if impmodel[0][2] == 100:
            print(f"Found an exact match for \"{impmodel[0][0]}\", using that")
            dt_id = nb.dcim.device_types.get(part_number=impmodel[0][1]).id
            fileupdates.append({'imported_model': impmodel[0][0],
                    'nb_model': impmodel[0][1],
                    'nb_dt_id': dt_id})
        else:
            print(f"\nFor user input of device model \"{impmodel[0][0]}\" "
                  f"no exact matches were found.\nPlease select an "
                  f"approximate match from the known, supported models "
                  f"below or '99' to create a new model"
                  f"\n       Match      Known model"
                  f"\n_ # __ Factor ___    name     _________")
            for index, item in enumerate(impmodel[0:15], start=1):
                print(f" {index:>2} -    {item[2]}       {item[1]}")
            print(f"\n 99 -             No best match - create a new model named "
                  f"\"{impmodel[0][0]}\"")

            while True:
                try:
                    choice = int(input("What is your selection number? "))
                except ValueError:
                    print("That wasn't an option, try again.")
                else:
                    if choice in range(1,15):
                        print(f"Going forward match WLC [{impmodel[0][0]}] " 
                            f"with NetBox [{impmodel[choice - 1][1]}] ",
                            end='')
                        dt_id = nb.dcim.device_types.get(part_number=impmodel[choice - 1][1]).id
                        print(f"with id = [{dt_id}]")
                        fileupdates.append({'imported_model': impmodel[0][0],
                                            'nb_model': impmodel[choice - 1][1],
                                            'nb_dt_id': dt_id})
                        break
                    elif choice == 99:
                        # Create a new device type - uhgg
                        pass
                    else:
                        # What option was THAT?
                        exit('Illegal option')
            #print(f"User selected - [{choice}]")
        print("-" * 40)

    if fileupdates:
        with open('dt2nb_mapping.json', 'a') as file:
            json.dump(fileupdates, file)
    #print(tuples_list)


def map2nbdt(nb, dt_model_list):
    """Do the NetBox site work - extract device models, compare and create new
    
    Extract current device model list from NetBox, compare with device
    models of supplied inputs, then compare and create new models, as 
    needed.  For efficiency we are leveraging the NetBox Community 
    Device Type project - 
    https://github.com/netbox-community/Device-Type-Library-Import
    This should be pre-loaded into NetBox and serves as the basis for
    assignments.  When there is a full match, it is used.  When there is
    not a match the system uses a 'fuzzy search' algorithm and suggests
    to the user what NetBox Community Device Type project model should
    be used an a future 'mapping' file is created/updated to ensure less
    user input is needed going forward.

    :param nb: NetBox session handler
    :type nb: class 'pynetbox.core.api.Api'
    :param str dt_model_list: List of imported device models for comparison

    """
    print(type(nb))
    original_content = None
    try:
        with open('dt2nb_mapping.json', 'r') as file:
            known_mappings = json.load(file)
    except FileNotFoundError:
        # No previous mapping file, so safe to assume we've never done
        # this process
        print('No existing "dt2nb_mapping.json" file - will create one.')
    else:
        print(known_mappings)
        missing_dts = [device_type for device_type in dt_model_list
                       if not any(model['imported_model'] == device_type 
                       for model in known_mappings)]
        print(f'Missing the following device-types: {missing_dts}')
        if not missing_dts:
            return known_mappings

    nb_devicetype_partnums = [dt.part_number for dt in list(nb.dcim.device_types.all())]
    #print(nb_devicetype_partnums)
    #print(ap_models)
    create_dt_mappings(nb_devicetype_partnums, dt_model_list, nb)
    with open('dt2nb_mapping.json', 'r') as file:
        known_mappings = json.load(file)
    return known_mappings


####### Module Function definitions above
###############################################################################
####### Main function definition below

# No main function defined, as this will be a helper function to other
#   modules
