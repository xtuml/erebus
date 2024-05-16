# Install test harness with ansible
## Install Ansible
To install the ansible playbooks here remotely the following will need to be installed
* python3.11
* pip

To install ansible run the following command
```
python3.11 -m pip install ansible
```
As the hosts used in the project require password input `sshpass` will be required to perform the passsword input. For macos the following operations must be run (after installing HomeBrew package manager):
```
brew tap esolitos/ipa
brew install esolitos/ipa/sshpass
```
## Alma linux
### Hosts file
Copy the `hosts.yml.example` to `hosts.yml` and edit the following fields
* `ansible_ssh_host` - The host the following playbook will be used on
* `ansible_ssh_user` - The ssh user that will be used to install
* `ansible_ssh_private_key_file` - The private key used for ssh
### Installation
All of the following installs (apart from Pre-requisite playbook) require the user to forward their ssh keys that have access to the following repositories:
* git@github.com:SmartDCSITlimited/test-harness.git
* git@gitlab.com:smartdcs1/cdsdt/data-scripts.git
* git@github.com:SmartDCSITlimited/test-event-generator.git
### Full install
To fully install the test harness on a fresh alma linux install run the following command having updated the `host.yml` file
```
ansible-playbook -i hosts.yml site.yml --ask-pass --ask-become-pass
```
### Pre-requisite Playbook
To install the pre-requistes use the following command having updated the `host.yml` file
```
ansible-playbook -i hosts.yml install-pre-requisites.yml --ask-pass --ask-become-pass
```
### Test Harness Playbook
If all pre-requisited have been installed previously we can us the following command to install or update the test harness (make sure `host.yml` file has been updated):
```
ansible-playbook -i hosts.yml install-test-harness.yml --ask-pass
```

