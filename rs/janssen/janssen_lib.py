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
        self.logger.trace('acc_token is {}', acc_token)
        self.logger.trace('setting headers for operation')
        content_type = 'application/json' if operation != 'PATCH' else 'application/json-patch+json'
        headers = {
            'Authorization': 'Bearer {}'.format(acc_token),
            'Content-Type': content_type
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

    def _patch_objs(self, endpoint, scopes, objects_folder, inum_patch=True):
        for file_path in self._get_files_path(objects_folder):
            self.logger.debug('Processing file: {}', file_path)
            with open(file_path) as json_file:
                json_data = self._load_json(json_file)
                inum = Path(file_path).stem
                endpoint = '{}/{}'.format(endpoint, inum) if inum_patch else endpoint
                self._execute_with_json_response('PATCH', endpoint, scopes, json_data)

    def _import_obj_by_name(self, endpoint, scopes, objects_folder):
        for file_path in self._get_files_path(objects_folder):
            self.logger.debug('Processing file: {}', file_path)
            with open(file_path) as json_file:
                json_data = self._load_json(json_file)
                name = json_data.get('name')
                query_endpoint = '{}?pattern={}'.format(endpoint,name)
                query_list = self._execute_with_json_response('GET', query_endpoint, scopes).get('data')
                search_result_list = [] if query_list is None else [ x for x in query_list if x.get('name') == name]
                size_search_result_list = len(search_result_list)
                if size_search_result_list == 0:
                    self.logger.debug('POST obj {}', name)
                    self._execute_with_json_response('POST', endpoint, scopes, json_data)
                elif size_search_result_list == 1:
                    self.logger.debug('PUT obj {}', name)
                    entry = search_result_list[0]
                    entry.update(json_data)
                    self._execute_with_json_response('PUT', endpoint, scopes, entry)
                else:
                    dns_search_result_list = [x.get('inum') for x in search_result_list]
                    error_msg = 'obj with name {} is duplicated on Jans, entries on system: {}'.format(name, dns_search_result_list)
                    self.logger.error(error_msg)
                    raise ValueError(error_msg)

    def _import_obj_by_inum(self, endpoint, scopes, objects_folder):
        for file_path in self._get_files_path(objects_folder):
            self.logger.debug('Processing file: {}', file_path)
            with open(file_path) as json_file:
                json_data = self._load_json(json_file)
                inum = json_data.get('inum')
                query_endpoint = '{}/{}'.format(endpoint, inum)
                if endpoint == '/jans-config-api/api/v1/config/scripts':
                    self.logger.debug('loading script code into json object')
                    code_file_path = '{}/{}.py'.format(objects_folder, Path(file_path).stem)
                    with open(code_file_path) as code_file:
                        json_data['script'] = code_file.read()
                jans_obj = {}
                try:
                    jans_obj = self._execute_with_json_response('GET', query_endpoint, scopes)
                except:
                    self.logger.debug("object {} not present in jans", inum)
                if jans_obj != {}:
                    self.logger.debug('PUT obj {}', inum)
                    jans_obj.update(json_data)
                    self._clean_json(jans_obj)
                    self.logger.debug("json obj is: {}", jans_obj)
                    self._execute_with_json_response('PUT', endpoint, scopes, jans_obj)
                else:
                    self.logger.debug('POST obj {}', inum)
                    self._execute_with_json_response('POST', endpoint, scopes, json_data)

    def _clean_json(self, endpoint, json_obj):
        if endpoint == '/jans-config-api/api/v1/openid/clients':
            self._pop_if_not_str(json_obj, ['clientName', 'logoUri', 'clientUri', 'policyUri', 'tosUri'])

    def _pop_if_not_str(self, json_obj, attr_list):
        for key in attr_list:
            value = "" if isinstance(json_obj.get(key), str) else json_obj.pop(key, None)

############################
### Attribute operations ###
############################

    def import_attributes(self, objects_folder):
        self.logger.debug('Import attributes from {}', objects_folder)
        endpoint = '/jans-config-api/api/v1/attributes'
        scopes = 'https://jans.io/oauth/config/attributes.readonly https://jans.io/oauth/config/attributes.write'
        self._import_obj_by_name(endpoint, scopes, objects_folder)

    def patch_attributes(self, objects_folder):
        self.logger.debug('Patch attributes from {}', objects_folder)
        endpoint = '/jans-config-api/api/v1/attributes'
        scopes = 'https://jans.io/oauth/config/attributes.readonly https://jans.io/oauth/config/attributes.write'
        self._patch_objs(endpoint, scopes, objects_folder)

############################
### Client operations    ###
############################

    def import_clients(self, objects_folder):
        self.logger.debug('Import clients from {}', objects_folder)
        endpoint = '/jans-config-api/api/v1/openid/clients'
        scopes = 'https://jans.io/oauth/config/openid/clients.readonly https://jans.io/oauth/config/openid/clients.write'
        self._import_obj_by_inum(endpoint, scopes, objects_folder)

    def patch_clients(self, objects_folder):
        self.logger.debug('Patch clients from {}', objects_folder)
        endpoint = '/jans-config-api/api/v1/openid/clients'
        scopes = 'https://jans.io/oauth/config/openid/clients.readonly https://jans.io/oauth/config/openid/clients.write'
        self._patch_objs(endpoint, scopes, objects_folder)
