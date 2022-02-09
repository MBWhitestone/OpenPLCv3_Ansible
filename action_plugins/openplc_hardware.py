"""File: openplc_hardware.py

Plugin for adding/removing/modifying OpenPLCv3 users.

Layer options: ['blank', 'blank_linux', 'fischertechnik', 'neuron',
                'pixtend', 'pixtend_2s', 'pixtend_21', 'rpi',
                'rpi_old', 'simulink', 'simulink_linux', 'unipi',
                'psm_linux', psm_win']
psm_linux and psm_win need python code: custom_layer_code, default
is provided on webpage.
"""

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import requests
import re
# Common error handlers
from ansible.errors import AnsibleError
# ADT base class for our Ansible Action Plugin
from ansible.plugins.action import ActionBase


#### User specific variables  ####
ITEM = 'hardware'
NAME = 'state'
ADD = 'hardware'
EDIT = 'hardware'
RM = ''
LOGIN = 'login'
INFO = 'hardware'
REQUIRED = ['state', 'properties']
VALID_STATES = ['present']
PROPERTIES = 'properties'
ADD_REQUIRED_PROPERTIES = ['hardware_layer', 'custom_layer_code']
ID_COLUMN = 1
SELECTED_ITEM = 'hardware_layer'
MISSING_ENTRIES = []
#####################################


class ActionModule(ActionBase):
    # Control behaviour.
    TRANSFERS_FILES = False

    ###########################################################################
    ### THE FOLLOWING FUNCTIONS ARE DUPLICATES OF OTHER ActionModules.      ###
    ### DO NOT MODIFY OR MODIFY ALL OF THEM.                                ###
    ### Currently exactly used in:                                          ###
    ### - openplc_user.py                                                   ###
    ### - openplc_device.py                                                 ###
    ### Currently partly used in:                                           ###
    ### - openplc_settings.py                                               ###
    ### - openplc_hardware.py                                               ###
    ###########################################################################
    def run(self, tmp=None, task_vars=None):
        """Change openplc item.

        Args:
            tmp (str, optional): temporary directory. Defaults to None.
            task_vars (dict, optional): host/group/config vars. Defaults to None.

        Returns:
            dict: Ansible return dict.
        """
        self._init(tmp=tmp, task_vars=task_vars)
        return dict(changed=self._loop())

    def _init(self, tmp, task_vars):
        """Initialise class."""
        super(ActionModule, self).run(tmp, task_vars)
        self.args = self._task.args.copy()
        self.vars = task_vars
        self.parse_args()
        self.start_session()

    def _loop(self, changed=False):
        """Main loop parsing state and returning whether something changed."""
        item = self.args[NAME]
        state = self.args['state']
        items = self._get_known()
        if item in items:
            item_id = items[item]
            if state == 'present':
                changed = self._modify(item, self._details(item_id))
            elif state == 'absent':
                changed = self._remove(item_id)
            else:
                raise AnsibleError(f'Unknown state "{state}"')
        else:
            if state == 'present':
                changed = self._add(item)
            elif state == 'absent':
                pass
            else:
                raise AnsibleError(f'Unknown state "{state}"')
        return changed

    def parse_args(self, required=REQUIRED, valid_states=VALID_STATES):
        """Check whether required args are specified (and valid)."""
        for r in required:
            assert r in self.args, f"No {r} specified."
        state = self.args['state']
        assert state in valid_states, f'State "{state}" not in {valid_states}.'

    def _check_info(self, info, url, succes=200, error_len=300):
        """Validate a response."""
        if info.status_code != succes:
            raise AnsibleError(
                f'Status code for {url} not {succes}; {info.text}')
        if 'error' and 'database' in info.text[-error_len:].lower():
            raise AnsibleError(info.text[-error_len:], url)
        return info

    def _get(self, url):
        """Perform GET request."""
        return self._check_info(self.session.get(url), url)

    def _post(self, url, data, files=None, file_key='file'):
        """Perform POST request."""
        if file_key in data and data[file_key]:
            filename = data[file_key]
            extension = filename.split('.')[-1]
            with open(filename, 'rb') as f:
                files = {'file': (filename, f.read(), f'image/{extension}')}
            del data[file_key]
        return self._check_info(self.session.post(url, data=data, files=files), url)

    def start_session(self):
        """Setup TCP session with PLC."""
        print('Setting up connection... ', end='')
        ip, port = self.vars['ansible_host'], self.vars['http_port']
        self.url = f'http://{ip}:{port}/'
        payload = {"username": self.vars['username'],
                   "password": self.vars['password']}
        self.session = requests.session()
        self._post(self.url + LOGIN, data=payload)
        print('done.')

    def _get_known(self, page=INFO, column=ID_COLUMN):
        """Return first <td></td> entries on page with onclick ID."""
        info = self._get(self.url + page)
        # Return first td entry with value device_id in each table row (except header).
        return {re.findall("<td>.*?</td>", row)[column][4:-5]:
                re.search("table_id=.*?'", row).group()[9:-1] for row in
                re.findall("<tr.*?>.*?</tr>", info.text, re.DOTALL)[1:]}

    def _details(self, item_table_id, page=EDIT):
        """Return all info for item.

        Note: currently using last row of the HTML page with dropped values.
        """
        if item_table_id is not None:
            page += '?table_id=' + str(item_table_id)
        info = self._get(self.url + page)
        properties = dict()

        # Properties from bottom of page.
        bottom = re.search(";devid.value.*?;}", info.text, re.DOTALL)
        if bottom is not None:
            for p in bottom.group().split(';'):
                if '=' in p:
                    attr, val = p.split(' = ')
                    properties[attr[:-6].replace('dev', 'device_').replace(
                        'start', '_start').replace('size', '_size')] = val[1:-1]

        # Properties from input values.
        for r in re.findall('<input .*?>', info.text, re.DOTALL):
            name = re.findall("name='.*?'", r)
            value = re.findall("value='.*?'", r)
            if value and name:
                properties[name[0][6:-1]] = value[0][7:-1]

        # Device type dropdown.
        if SELECTED_ITEM:
            properties[SELECTED_ITEM] = re.findall("value='.*?'",
                                                   re.findall("selected='selected'.*?>",
                                                              info.text,
                                                              re.DOTALL)[0])[0][7:-1]
        # Other.
        for m in MISSING_ENTRIES:
            properties[m] = ''

        return properties

    # def _add(self, item, page=ADD):
    #     """Add an item."""
    #     assert PROPERTIES in self.args, 'Missing properties'
    #     data = self.args[PROPERTIES]
    #     data[NAME] = item
    #     for required in ADD_REQUIRED_PROPERTIES:
    #         assert required in data, f"Missing {required} property."
    #     print('TODO Maybe sanitise properties')
    #     print(f'Creating {data}')
    #     info = self._post(self.url + page, data=data)
    #     new_items = self._get_known()
    #     if item not in new_items:
    #         raise AnsibleError(f"{item} not in {new_items}, {info.text}")
    #     return True

    def _remove(self, item_id, page=RM):
        """Remove an item.

        E.g. calling http://145.100.108.22:8002/delete-device?dev_id=9
        """
        print(f'Removing {ITEM} {item_id}, not checking any properties!')
        self._get(self.url + page + str(item_id))
        return True

    def _modify(self, device, device_details, page=EDIT):
        """Modify device properties when changed."""
        changed = False
        if PROPERTIES in self.args:
            for p, value in self.args[PROPERTIES].items():
                if p not in device_details:
                    raise AnsibleError(f"{p} is not a valid property.")
                value = str(value)
                current = device_details[p]
                if current != value:
                    print('modifing', p, current, 'to', value)
                    device_details[p] = value
                    changed = True
        if changed:
            self._post(self.url + page, data=device_details)
        return changed
    ###########################################################################
    ### END DUPLICATES OF OTHER CLASSES                                     ###
    ###########################################################################

    def _add(self, item, page=ADD):
        """Add an item.

        This function has been modified to work explicitly with the settings
        page. The _remove is not used in this Class.
        """
        assert PROPERTIES in self.args, 'Missing properties'
        details = {**self._details(None),
                   **{re.findall('name=".*?"', r)[0][6:-1]:
                      r.split('>', 1)[1].replace('</textarea>', '')
                      for r in re.findall('<textarea .*?>.*?</textarea>',
                                          self._get(self.url + page).text,
                                          re.DOTALL) if '>' in r}}
        # Add custom Python code for PSM.
        for k in details.keys():
            if 'code' in k and k in self.args[PROPERTIES]:
                with open(self.args[PROPERTIES][k], 'r') as f:
                    self.args[PROPERTIES][k] = f.read()

        return self._modify(item, details)
