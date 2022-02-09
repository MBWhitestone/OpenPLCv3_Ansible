"""File: measure.py

This file contains code to measure the performance of the Ansible plugin.
"""
import subprocess
from collections import defaultdict
import numpy as np
import os
import pickle
import time


def test(name):
    """Test a single playbook."""
    print('testing', name, end='... ', flush=True)
    program = f"""- hosts: all
  become: no
  gather_facts: no
  tasks:
    - include_tasks: playbooks/measurements/{name}
"""
    with open('temp.yml', 'w') as f:
        f.write(program)
    run = '/usr/bin/time -f "%e" sudo ansible-playbook -vvv temp.yml -i hosts'
    ret = subprocess.run(run, shell=True, capture_output=True)
    try:
        seconds = float(ret.stderr)
    except:
        seconds = -1
        print(ret)
    print(seconds)
    return seconds


def test_all(tests, n, running):
    """Test multiple playbooks."""
    results = defaultdict(list)
    for _ in range(n):
        if running:
            test('runplc.yml')
        for l in tests:
            results[l].append(test(name=l))
    saveresults(results, n=n, running=running)


def saveresults(results, n, extra='', running=False):
    """Save the results of a test run to file."""
    current_time = time.strftime("%H%M%S", time.localtime())
    hostname = os.uname()[1]
    runs = 'notrunning'
    if running:
        runs = 'running'
    filename = f"measurements_{hostname}_{current_time}_{n}rounds_{runs}{extra}.p"
    print('dumping to', filename, end='... ')
    with open(filename, 'wb') as handle:
        pickle.dump(results, handle, protocol=pickle.HIGHEST_PROTOCOL)
    print('done.')


def combineresults(files):
    """Combine multiple results into one dictionary."""
    combined = defaultdict(list)
    leng = 0
    for f in files:
        with open(f, 'rb') as handle:
            b = pickle.load(handle)
            for key, value in b.items():
                combined[key] += value
            leng += len(value)
    runs = 'notrunning' not in f
    saveresults(combined, n=leng, extra='_combined', running=runs)


def analyse(filename, decimals=2):
    """Analyse a file with results."""
    with open(filename, 'rb') as handle:
        b = pickle.load(handle)
    for key, value in b.items():
        print(key, 'raw', value, 'μ', np.round(np.mean(value), decimals),
              'σ', np.round(np.std(value), decimals))


if __name__ == '__main__':
    # Make sure we have sudo
    subprocess.run("sudo ls", shell=True, capture_output=True)
    # Change this to the dicts to combine
    # combinefiles = []
    combinefiles = ['measurements_hostname_174620_15rounds_running.p']
    # Change this to the dicts to analyse
    analysefiles = ['measurements_hostname_174620_15rounds_running.p']
    # Testrounds
    N = 15
    # Running PLC
    RUNNING = True

    if combinefiles:
        combineresults(combinefiles)
    else:
        if RUNNING:
                test('runplc.yml')
        else:
            y = input('Make sure nothing is running on PLC and type y')
            assert y == 'y', "This is an insulting message."

        test_all(['addclient.yml', 'modifyclient.yml', 'removeclient.yml',
                  'adduser.yml', 'modifyuser.yml', 'removeuser.yml',
                  'modifysettings.yml', 'resetsettings.yml',
                  'applyprogram.yml', 'removeprogram.yml',
                  'modifyhardware.yml', 'resethardware.yml',
                  ], n=N, running=RUNNING)

    for a in analysefiles:
        analyse(a)
