#!/usr/bin/python
import csv
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException,NetMikoAuthenticationException
import sys
import requests
import time

def MAClookup(MACaddress):
    MAC_URL = 'http://macvendors.co/api/%s'
    r = requests.get(MAC_URL % MACaddress)

    return r.json()['result']['company']

def configDescriptions(switchObject):
        
    net_connect = ConnectHandler(**switchObject)
    net_connect.send_command('term len 1000')
    
    LLDPcommand = "show lldp info remote"
    LLDPoutput = net_connect.send_command(LLDPcommand)
    
    neighborsNext = False
    neighborsInterfaces = []
    
    lldp = LLDPoutput.split('\n')
    
    for line in lldp:
        if len(line.lstrip()) <= 0:
            continue
        if neighborsNext:
            neighborPort = line.lstrip().split()[0]
            neighborsInterfaces.append(neighborPort)
        if "----" in line:
            neighborsNext = True
    LLDPdict = {}

    for port in neighborsInterfaces:
        LLDPcommand = "show lldp info remote " + port
        LLDPoutput = net_connect.send_command(LLDPcommand).split('\n')
        LLDPdict[port] = {}
        
        for line in LLDPoutput:
            if len(line.lstrip()) <= 0:
                continue
            data = line.strip().split(':')
            if len(data) > 1:
                (key,value) = data
            else:
                continue
            LLDPdict[port][key.strip()] = value.strip()
    

    showMACcommand = "show mac-address"
    MACoutput = net_connect.send_command(showMACcommand).split('\n')
    
    print "Configuring LLDP neighbor names"
    addressesNext = False
    for port in LLDPdict:
        if "bridge" in LLDPdict[port]['System Capabilities Enabled']:
            if len(LLDPdict[port]['SysName']) <= 0:
                time.sleep(1)
                if "Meraki MR" in LLDPdict[port]['System Descr']:
                    interfaceDescription = ["int " + str(port),"name WirelessAP"]
                    net_connect.send_config_set(interfaceDescription)
                    # print a dot so the user knows it is working
                    sys.stdout.write('.')
                    sys.stdout.flush()
                else:
                    interfaceDescription = ["int " + str(port),"name " + str(LLDPdict[port]['System Descr'])]
                    net_connect.send_config_set(interfaceDescription)
                    # print a dot so the user knows it is working
                    sys.stdout.write('.')
                    sys.stdout.flush()
            else:
                time.sleep(1)
                if "Meraki MR" in LLDPdict[port]['SysName']:
                    interfaceDescription = ["int " + str(port),"name WirelessAP"]
                    net_connect.send_config_set(interfaceDescription)
                    # print a dot so the user knows it is working
                    sys.stdout.write('.')
                    sys.stdout.flush()
                else:
                    interfaceDescription = ["int " + str(port),"name " + str(LLDPdict[port]['SysName'])]
                    net_connect.send_config_set(interfaceDescription)
                    # print a dot so the user knows it is working
                    sys.stdout.write('.')
                    sys.stdout.flush()
    
    # print a newline so it looks nice
    print ""
    
    print "Configuring AP names based on MAC address"
    for line in MACoutput:
        uplink = False
        if len(line.strip()) > 0:
            if addressesNext:
                lineOutput = line.strip().split()
                MAC = lineOutput[0]
                MACport = lineOutput[1]
                for port in LLDPdict:
                    if port == MACport:
                        if "bridge" in LLDPdict[port]['System Capabilities Enabled']:
                            uplink = True
                if "Trk" in MACport:
                    uplink = True
                if not uplink:
                    if "Ubiquiti" in MAClookup(MAC):
                        time.sleep(1)
                        interfaceDescription = ["int " + str(MACport),"name WirelessAP"]
                        net_connect.send_config_set(interfaceDescription)
                        # print a dot so the user knows it is working
                        sys.stdout.write('.')
                        sys.stdout.flush()
            if "----" in line:
                addressesNext = True
    
    # print a newline so it looks nice
    print ""
            
    
    # we always sanely disconnect
    net_connect.disconnect()
    
def connect(switch_ip,username,password):
    switch = {
        'device_type': 'hp_procurve',
        'ip': switch_ip,
        'username': username,
        'password': password,
        'secret': password,
        'port' : 22,          # optional, defaults to 22
        'verbose': False,       # optional, defaults to False
        'global_delay_factor': 2
    }
    
    try:
        # if the switch is reponsive we do our thing, otherwise we hit the exeption below
        # this actually logs into the device
        configDescriptions(switch)
        
    except (NetMikoTimeoutException, NetMikoAuthenticationException):
        switch = {
                'device_type': 'hp_procurve',
                'ip': switch_ip,
                'username': "",
                'password': "",
                'secret': "",
                'port' : 22,
                'verbose': False,
                'global_delay_factor': 2
            }
        try:
            configDescriptions(switch)

        except (NetMikoTimeoutException, NetMikoAuthenticationException):
            print switch_ip + ':no_response'

switches = csv.DictReader(open("switches.csv"))

try:
    for row in switches:
        print "switch:",row['Switch']
        connect(row['IP'],row['username'],row['password'])
except IndexError as e:
    print "No line in the CSV:", e
    pass