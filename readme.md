# Industrial Programmable Logic Controller Automation with Configuration Management Tools
> RP1 [NHP6](https://github.com/NHP6) & [MBWhitestone](https://github.com/MBWhitestone)

This repository contains an Ansible plugin to configure an OpenPLCv3 instance with Ansible.
The contents of this repository should be regarded as a proof-of-concept.
For more information please see the report at [rp.os3.nl](https://rp.os3.nl).

# How to use
First modify `example.yml` and `hosts` to your preferences. Then run:
```
sudo ansible-playbook example.yml -i hosts
```
Example playbooks are given in the `playbooks` folder.

