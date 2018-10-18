#!/usr/bin/python
import csv
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException,NetMikoAuthenticationException
import sys
import requests
import time

def MAClookup(MACaddress):
    # lookup the MAC address to see what manufacturer it is
    
    MAC_URL = 'http://macvendors.co/api/%s'
    r = requests.get(MAC_URL % MACaddress)

    # we don't do anything fancy
    # just return the manfacturer name
    return r.json()['result']['company']

def configDescriptions(switchObject):
    # this takes LLDP neighborships, and if they're switches
    # it configured those names as the interface descriptions
    # also if Ubiquity APs are in the local MAC table
    # it marks those as AP ports
    
    net_connect = ConnectHandler(**switchObject)
    net_connect.send_command('term len 1000')
    
    # first we get the raw LLDP table
    LLDPcommand = "show lldp info remote"
    LLDPoutput = net_connect.send_command(LLDPcommand)
    
    neighborsNext = False
    neighborsInterfaces = []
    
    lldp = LLDPoutput.split('\n')
    
    # we figure out what interfaces have LLDP speakers on them
    for line in lldp:
        if len(line.lstrip()) <= 0:
            continue
        if neighborsNext:
            neighborPort = line.lstrip().split()[0]
            neighborsInterfaces.append(neighborPort)
        if "----" in line:
            neighborsNext = True
    LLDPdict = {}

    # then we get a detailed LLDP query of each of those ports
    # and drop the results into a dictionary
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
    
    # then we actually configure the interface descriptions
    print "Configuring LLDP neighbor names"
    
    # we roll through the LLDP neighbor dictionary
    for port in LLDPdict:
        # if it a switch connected to this port
        # it will report as a bridge
        if "bridge" in LLDPdict[port]['System Capabilities Enabled']:
            # the output is sometimes weird
            # some values are totally blank so we just roll with it
            # and use alternate values
            # eg: if SysName is blank we use System Descr
            if len(LLDPdict[port]['SysName']) <= 0:
                time.sleep(1)
                # Meraki APs speak LLDP we we mark these ports as WirelessAP
                if "Meraki MR" in LLDPdict[port]['System Descr']:
                    interfaceDescription = ["int " + str(port),"name WirelessAP"]
                    net_connect.send_config_set(interfaceDescription)
                    # print a dot so the user knows it is working
                    sys.stdout.write('.')
                    sys.stdout.flush()
                else:
                    # anything else is a switch, so we mark the LLDP hostname of it
                    interfaceDescription = ["int " + str(port),"name " + str(LLDPdict[port]['System Descr'])]
                    net_connect.send_config_set(interfaceDescription)
                    # print a dot so the user knows it is working
                    sys.stdout.write('.')
                    sys.stdout.flush()
            else:
                time.sleep(1)
                # Meraki APs speak LLDP we we mark these ports as WirelessAP
                if "Meraki MR" in LLDPdict[port]['SysName']:
                    interfaceDescription = ["int " + str(port),"name WirelessAP"]
                    net_connect.send_config_set(interfaceDescription)
                    # print a dot so the user knows it is working
                    sys.stdout.write('.')
                    sys.stdout.flush()
                else:
                    # anything else is a switch, so we mark the LLDP hostname of it
                    interfaceDescription = ["int " + str(port),"name " + str(LLDPdict[port]['SysName'])]
                    net_connect.send_config_set(interfaceDescription)
                    # print a dot so the user knows it is working
                    sys.stdout.write('.')
                    sys.stdout.flush()
    
    # print a newline so it looks nice
    print ""
    
    # next we grab the MAC table
    showMACcommand = "show mac-address"
    MACoutput = net_connect.send_command(showMACcommand).split('\n')

    # the MAC table output is a bit wonky, so we have to skip the first few lins
    # we use this so we only start processing after we hit the line
    # with a bunch of dashes in it: ----
    addressesNext = False
    print "Configuring AP names based on MAC address"
    
    # loop through each line of the MAC table raw output
    for line in MACoutput:
        # the port is NOT an uplink until proven otherwise
        uplink = False
        # we don't process blank lines
        if len(line.strip()) > 0:
            # this gets hit ONLY if we've passed the dashes: ----
            if addressesNext:
                # we break apart the line by spaces into individual pieces
                lineOutput = line.strip().split()
                MAC = lineOutput[0] # mac address first
                MACport = lineOutput[1] # then the port
                # we roll through the LLDP dictionary
                # so we do can skip those interfaces that we already know about
                for port in LLDPdict:
                    if port == MACport:
                        if "bridge" in LLDPdict[port]['System Capabilities Enabled']:
                            uplink = True
                # if it's an LACP bundle, it is definitely not an AP
                if "Trk" in MACport:
                    uplink = True
                # if we get this far then it is something worth looking at
                if not uplink:
                    # if the manufacturer is Ubiquiti then it is an AP and we configure that in the description
                    if "Ubiquiti" in MAClookup(MAC):
                        time.sleep(1)
                        interfaceDescription = ["int " + str(MACport),"name WirelessAP"]
                        net_connect.send_config_set(interfaceDescription)
                        # print a dot so the user knows it is working
                        sys.stdout.write('.')
                        sys.stdout.flush()
            # this means the actual MAC addresses are coming up
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
        # sometimes the switches don't have usernames and passwords
        # LOLOLOL  okay so whatever
        # they barf if you try to pass an actual username so we do this
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