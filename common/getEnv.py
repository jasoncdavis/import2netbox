#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Obtains the environment variables from options YAML file
 (getEnv.py)

#                                                                      #
Reads the requested servertype environment parameters (hostname, 
username, password, etc) from the project or optionsconfig.yaml file 
which defines all server types for the project (InfluxDB, Grafana, 
MySQL, Catalyst Center, ACI APIC controllers, etc.)

Required inputs/variables:
    servertype - string representing the server type and parameters
        to extract

    Reads a project or 'optionsconfig.yaml' file for server address, 
    username, authentication info, API keys, etc.
    
    optionsconfig.yaml has the following sample
    PrimeInfrastructure:
    - host: primeinfrasandbox.cisco.com
        CheckSSLCert: True  # Or False, if you are not security conscious and using self-signed certs internally
        username: devnetuser
        password: DevNet123!

Outputs:
    list of dictionary items reflecting the server parameters

Version log:
v1   2021-0623  Created as normalized function across all
v2   2023-0503  Updated to reduce module and function names
    DevNet Dashboard importing scripts
v3   2023-0725  Update to new naming convention
v4   2024-0223  Update to use <project>.yaml convention
v5   2024-0320  Update to allow for base filename to be provided

"""
__version__ = '5'
__author__ = 'Jason Davis - jadavis@cisco.com'
__license__ = "'Apache License, Version 2.0 - ' \
    'http://www.apache.org/licenses/LICENSE-2.0'"


def getparam(parameter, envfile=None):
    """Read environmental settings file
    
    Reads a YAML file that defines environmental parameter and settings

    :param parameter: string defining the type of parameter setting(s) 
      to extract [eg. Webex_Key, CatalystCenter, InfluxDB, etc.]
    :param envfile: optional string defining the YAML file - will 
    assume the name of the project.yaml, then optionsconfig.yaml or
    allows a user-defined entry
    :returns: entries defined in YAML config file at parameter-key
    provided
    """
    import inspect
    import os.path
    import sys
    import yaml
    
    # If user provided an envfile reference, always use that
    # If no envfile, then look for <project-module>.yaml, use that
    # if no <project-module>.yaml, look for optionsconfig.yaml, use that
    # if no optionsconfig.yaml, abort
    if envfile is not None:
        if os.path.isfile(f'{envfile}'):
            #print("We're using a user-defined YAML file")
            projectfile = envfile
        else:
            sys.exit('User-defined YAML file NOT found.  Exiting.')
    else:
        frame_records = inspect.stack()[1]
        calling_module = inspect.getmodulename(frame_records[1])
        #print(calling_module)
        if os.path.isfile(f'./{calling_module}.yaml'):
            """print(f'We are using a project YAML file - {calling_module}'
                  '.yaml')"""
            projectfile = f'./{calling_module}.yaml'
        else:
            if os.path.isfile('./optionsconfig.yaml'):
                #print("We're using an optionsconfig.yaml file")
                projectfile = './optionsconfig.yaml'
            else:
                sys.exit('No project YAML file found.  Exiting.')

    with open(projectfile, "r") as ymlfile:
        try:
            cfg = yaml.safe_load(ymlfile)
        except yaml.YAMLError as e:
            print(e)
    
    return cfg.get(parameter)