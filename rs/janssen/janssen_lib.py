# rs-janssen is available under the MIT License. https://github.com/RoundServices/rs-janssen/
# Copyright (c) 2022, Round Services LLC - https://roundservices.biz/
#
# Authors:
#   Ezequiel O Sandoval - esandoval@roundservices.biz
#   Gustavo J Gallardo - ggallard@roundservices.biz
#

import json
import requests
import os
import shutil
from rs.utils.clients import OIDCClient
from rs.utils import http
from pathlib import Path


class ConfigAPIClient:

    def __init__(self, logger, local_properties):
        self.logger = logger
        self.properties = local_properties
        self.base_uri = 'https://{}'.format(self.properties.get('idp_hostname'))
        self.oidc_client = OIDCClient(self.base_uri, logger, verify=False)
        self.temp_dir = './work'
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        os.mkdir(self.temp_dir, 0o666)

    def _execute_with_json_response(self, operation, endpoint, scopes, json_obj={}):
        self.logger.debug('{} {}', operation, endpoint)
        url = '{}{}'.format(self.base_uri, endpoint)
        self.logger.trace('Getting acc_token for operation')
        client_id = self.properties.get('configapi_client_id')
        client_secret = self.properties.get('configapi_client_secret')
        b64_creds = http.to_base64_creds(client_id, client_secret)
        params = {
            'grant_type': 'client_credentials',
            'scope': scopes
        }
        acc_token = self.oidc_client.request_to_token_endpoint(b64_creds, params).get('access_token')
        self.logger.trace('acc_token is {}')
        self.logger.trace('setting headers for operation')
        headers = {
            'Authorization': 'Bearer {}'.format(acc_token),
            'Content-Type': 'application/json'
        }
        self.logger.trace('request body - dump json_obj')
        body = json.dumps(json_obj)
        self.logger.trace('execute http request')
        response = requests.request(operation, url, headers=headers, data=body, verify=False)
        http.validate_response(response, self.logger, 'Execute Failed - HTTP Code: {}'.format(response.status_code))
        json_obj = {} if operation == 'DELETE' else response.json()
        self.logger.debug('{} JSON response - {}', operation, json_obj)
        return json_obj

    def _get_files_path(self, objects_folder, extension='.json'):
        files = list()
        for directory_entry in sorted(os.scandir(objects_folder), key=lambda path: path.name):
            file_path = directory_entry.path
            if directory_entry.is_file() and file_path.endswith(extension):
                temp_file = '{}/{}'.format(self.temp_dir,os.path.basename(file_path))
                shutil.copyfile(file_path, temp_file)
                self.properties.replace(temp_file)
                files.append(temp_file)
        return files

    def _load_json(self, json_file):
        json_data = json.load(json_file)
        self.logger.trace('JSON definition: {}', json_data)
        return json_data

############################
### Attribute operations ###
############################

    def import_attributes(self, objects_folder):
        self.logger.debug('Import attributes from {}', objects_folder)
        endpoint = '/jans-config-api/api/v1/attributes'
        scopes = 'https://jans.io/oauth/config/attributes.readonly, https://jans.io/oauth/config/attributes.write'
        for file_path in self._get_files_path(objects_folder):
            self.logger.debug('Processing file: {}', file_path)
            with open(file_path) as json_file:
                json_data = self._load_json(json_file)
                name = json_data.get('name')
                attributes_list = self._execute_with_json_response('GET', endpoint, scopes).get('data')
                search_result_list = [ x for x in attributes_list if x.get('name') == name]
                size_search_result_list = len(search_result_list)
                if size_search_result_list == 0:
                    self.logger.debug('Create attribute {}', name)
                    self._execute_with_json_response('POST', endpoint, scopes, json_data)
                elif size_search_result_list == 1:
                    entry = search_result_list[0]
                    endpoint = '{}/{}'.format(endpoint, entry.get('inum'))
                    entry.update(json_data)
                    self._execute_with_json_response('PUT', endpoint, scopes, entry)
                else:
                    error_msg = 'attribute {} is duplicated on Jans, entries on system: {}'.format(json_data, search_result_list)
                    self.logger.error(error_msg)
                    raise ValueError(error_msg)

    def patch_attributes(self, objects_folder):
        self.logger.debug('Patch attributes from {}', objects_folder)
        endpoint = '/jans-config-api/api/v1/attributes'
        scopes = 'https://jans.io/oauth/config/attributes.readonly, https://jans.io/oauth/config/attributes.write'
        for file_path in self._get_files_path(objects_folder):
            self.logger.debug('Processing file: {}', file_path)
            with open(file_path) as json_file:
                json_data = self._load_json(json_file)
                inum = Path(file_path).stem
                endpoint = '{}/{}'.format(endpoint, inum)
                self._execute_with_json_response('PATCH', endpoint, scopes, json_data)


