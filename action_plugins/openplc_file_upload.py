"""File: openplc_file_upload.py

Plugin for adding/removing/modifying OpenPLCv3 Slave Devices.
"""
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import re
import subprocess
import time
import requests

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

#### Device specific variables  ####
STOP_PLC = 'stop_plc'
START_PLC = 'start_plc'
UPLOAD = 'upload-program'
UPLOAD_WITH_INFO = 'upload-program-action'
COMPIL_LOGS = 'compilation-logs'
COMPILE = 'compile-program?file='
LOGIN = "login"
INFO = 'programs?list_all=1'
ADD = 'upload-program'
REMOVE = 'remove-program?id='
SRC = '/src/webserver/st_files/'
ADD_ACTION = 'upload-program-action'
REQUIRED = ['name', 'file', 'state']
VALID_STATES = ['present', 'absent']
#####################################


class ActionModule(ActionBase):
    # Control behaviour.
    TRANSFERS_FILES = False

    ### THE FOLLOWING FUNCTIONS ARE DUPLICATES OF OTHER ActionModules.      ###
    ### DO NOT MODIFY OR MODIFY ALL OF THEM.                                ###
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

    def _get(self, url):
        """Perform GET request."""
        return self._check_info(self.session.get(url), url)

    def _post(self, url, data=None, files=None):
        """Perform POST request."""
        return self._check_info(self.session.post(url, data=data, files=files), url)

    def _check_info(self, info, url, succes=200, error_len=300):
        """Validate a response."""
        print(url)
        if info.status_code != succes:
            raise AnsibleError(
                f'Status code for {url} not {succes}; {info.text}')
        if 'error' and 'database' in info.text[-error_len:].lower():
            raise AnsibleError(info.text[-error_len:], url)
        return info

    def _get_known(self, column=1, page=INFO):
        """Return first <td></td> entries on page with onclick ID."""
        info = self._get(self.url + page)
        # Return first td entry with value device_id in each table row (except header).
        return {re.findall("<td>.*?</td>", row)[column][4:-5]:
                re.search("table_id=.*?'", row).group()[9:-1] for row in
                re.findall("<tr.*?>.*?</tr>", info.text, re.DOTALL)[1:]}

    def _modify(self, item_id, src=SRC, page_logs=COMPIL_LOGS):
        """Modify file properties when changed."""

        # Get file name from id
        files = self._get_known(1)
        key_list = list(files.keys())
        val_list = list(files.values())
        position = val_list.index(item_id)

        stdin = subprocess.run(
            [f'ssh {self.vars["ssh_user"]}@{self.vars["ansible_host"]} -p {self.vars["ssh_port"]} cat {src}{key_list[position]}'], capture_output=True, shell=True)
        with open(self.args["file"], 'rb') as new_file:
            new = str(new_file.read())
            old = str(stdin.stdout)
            if new == old:
                self._get(self.url + START_PLC)
                return False

        info = self._get(self.url + "reload-program?table_id=" + item_id)

        self.filename = re.search("(?P<n>[0-9]{2,6}.st)", info.text).group('n')

        payload = {
            'epoch_time': time.time(),
            'prog_name': self.args["name"],
            'prog_descr': '' if "description" not in self.args else self.args["description"],
            'prog_file': self.filename,
        }

        info2 = self._post(self.url + "update-program-action", data=payload)
        info3 = self._get(self.url + "compile-program?file=" + self.filename)

        while True:
            time.sleep(2)
            info_complilation = self._get(self.url + page_logs)
            compiled = re.search(
                "(Compilation finished successfully!)", info_complilation.text)
            if compiled is not None:
                break
            error = re.search("error(s) found. Bailing out!",
                              info_complilation.text)
            error2 = re.search(
                "Compilation finished with errors!", info_complilation.text)
            if error2 is not None:
                raise AnsibleError(f"Compilation finished with errors")
            if error is not None:
                raise AnsibleError(f"Error during compilation of the code")

        existing_files = self._get_known()
        print(existing_files)
        if self.filename not in existing_files:
            raise AnsibleError(
                f"{self.filename} not in {existing_files}, {info.text}")
        self._get(self.url + START_PLC)
        return True

    def _remove(self, item_id, remove=REMOVE, src=SRC):
        """Remove an item.

        E.g. calling http://145.100.108.22:8002/delete-device?dev_id=9
        """

        # Get file name from id
        files = self._get_known(1)
        key_list = list(files.keys())
        val_list = list(files.values())
        position = val_list.index(item_id)

        self._get(self.url + remove + str(item_id))

        subprocess.run([f'ssh {self.vars["ssh_user"]}@{self.vars["ansible_host"]} -p {self.vars["ssh_port"]} rm {src}{key_list[position]}'],
                       capture_output=True, shell=True)
        return True

    def _loop(self, changed=False):
        """Main loop parsing state and returning whether something changed."""
        item = self.args['name']
        state = self.args['state']
        items = self._get_known(column=0)
        print(items)
        if item in items:
            item_id = items[item]
            if state == 'present':
                changed = self._modify(item_id)
            elif state == 'absent':
                changed = self._remove(item_id)
            else:
                raise AnsibleError(f'Unknown state "{state}"')
        else:
            if state == 'present':
                changed = self._add()
            elif state == 'absent':
                pass
            else:
                raise AnsibleError(f'Unknown state "{state}"')
        return changed

    def _add(self, page=ADD, page_action=ADD_ACTION, page_logs=COMPIL_LOGS):
        """Add a file."""
        # print("here")
        files = [
            ('file', (self.args["file"], open(self.args["file"], 'rb'), 'text'))]
        info = self._post(self.url + page, files=files)

        self.filename = re.search("(?P<n>[0-9]{2,6}.st)", info.text).group('n')

        payload = {
            'epoch_time': time.time(),
            'prog_name': self.args["name"],
            'prog_descr': '' if "description" not in self.args else self.args["description"],
            'prog_file': self.filename,
        }

        info2 = self._post(self.url + page_action, data=payload)

        while True:
            time.sleep(2)
            info_complilation = self._get(self.url + page_logs)
            compiled = re.search(
                "Compilation finished successfully!", info_complilation.text)
            if compiled is not None:
                break
            error = re.search("error(s) found. Bailing out!",
                              info_complilation.text)
            error2 = re.search(
                "Compilation finished with errors!", info_complilation.text)
            if error2 is not None:
                raise AnsibleError(f"Compilation finished with errors")
            if error is not None:
                raise AnsibleError(f"Error during compilation of the code")

        existing_files = self._get_known()
        print(existing_files)
        if self.filename not in existing_files:
            raise AnsibleError(
                f"{self.filename} not in {existing_files}, {info.text}")
        return True

    def parse_args(self, required=REQUIRED, valid_states=VALID_STATES):
        """Check whether required args are specified (and valid)."""
        for r in required:
            assert r in self.args, f"No {r} specified."
        state = self.args['state']
        assert state in valid_states, f'State "{state}" not in {valid_states}.'

    def start_session(self, login=LOGIN):
        """Setup TCP session with PLC."""
        ip, port = self.vars['ansible_host'], self.vars['http_port']
        self.url = f'http://{ip}:{port}/'
        user, password = self.vars['username'], self.vars['password']
        payload = {"username": user, "password": password}

        self.session = requests.session()
        self._post(self.url + login, data=payload)

    def _init(self, tmp, task_vars):
        """Initialise class."""
        super(ActionModule, self).run(tmp, task_vars)
        self.args = self._task.args.copy()
        self.vars = task_vars
        self.parse_args()
        self.start_session()
