# rs-janssen is available under the MIT License. https://github.com/RoundServices/rs-janssen/
# Copyright (c) 2022, Round Services LLC - https://roundservices.biz/
#
# Authors:
#   Ezequiel O Sandoval - esandoval@roundservices.biz
#   Gustavo J Gallardo - ggallard@roundservices.biz
#

import json
import base64
from pyDes import *
from rs.utils.clients import OIDCClient
from os import listdir
from os.path import isfile, join, isdir
from rs.utils import validators
from rs.utils.basics import Logger
from rs.utils import http
from rs.utils import os_cmd

class ConfigAPIClient:
    """
    ConfigAPIClient simplifies functionality for Janssen config-api interaction
    """

    def __init__(self, idp_base_url, b64_client_credentials, logger=Logger("ConfigAPIClient.py")):
        """
        Params
        :param idp_base_url: for instance "https://jans.myorg.com"
        :param b64_client_credentials: 'client_id:client_secret' in base64 encoded format
        :param logger: RoundServices log. If None, default will be created
        """
        self.idp_base_url = idp_base_url
        self.logger = logger
        self.oidc_client = OIDCClient(idp_base_url, b64_client_credentials, logger, verify=True)

    def create(self, endpoint, json_obj):
        """
        CREATE object
        :param endpoint: from Jans config-api for instance attributes, clients, configuration/scripts
        :param json_obj: dict that represents object to be created
        :return: dict that represents created json obj
        """
        return self.oidc_client.post(endpoint, json_obj)

    def delete(self, endpoint, json_obj):
        """
        DELETE object
        :param endpoint: from Jans config-api for instance attributes, clients, configuration/scripts
        :param json_obj: dict that represents object to be deleted with inum
        :return: dict. json_obj from input
        """
        self.oidc_client.delete("{}/{}".format(endpoint, json_obj['inum']))
        return json_obj

########################################################################################################################
########## FUNCTIONS ###################################################################################################
########################################################################################################################

def rs_import_clients(self, objects_folder, temp_file):
    self.logger.debug("Importing clients from: {}", objects_folder)
    for directory_entry in sorted(os.scandir(objects_folder), key=lambda path: path.name):
        if directory_entry.is_file() and directory_entry.path.endswith(".json"):
            self.logger.debug("Processing file: {}", directory_entry.path)
            shutil.copyfile(directory_entry.path, temp_file)
            self.local_properties.replace(temp_file)
            with open(temp_file) as json_file:
                json_data = json.load(json_file)
                self.logger.trace("Client definition: {}", json_data)
                client_id = json_data["clientId"]
                if self.rs_client_exists(client_id):
                    client_keycloak_id = self.rs_get_client_keycloakid(client_id)
                    self.logger.debug("Client '{}' already exists with internal id: {}. Updating...", client_id, client_keycloak_id)
                    self.update_client(client_keycloak_id, json_data)
                else:
                    self.logger.debug("Client '{}' does not exist. Creating...", client_id)
                    self.create_client(json_data, skip_exists=True)