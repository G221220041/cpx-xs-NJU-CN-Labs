#!/usr/bin/env python3

'''
Basic IPv4 router (static routing) in Python.
'''

import time
import switchyard
from switchyard.lib.userlib import *

class ArpTableEntry():
    def __init__(self, mac_address) -> None:
        self.init_time = time.time()
        self.mac_address = mac_address

    def test_timeout(self, timeout) -> bool:
        time_elipse = time.time() - self.init_time
        return time_elipse > timeout
    
    def retime(self) -> None:
        self.init_time = time.time()

    def get_address(self) -> str:
        return self.mac_address

class Router(object):
    def __init__(self, net: switchyard.llnetbase.LLNetBase):
        self.net = net
        self.arpTable = dict()
        # other initialization stuff here

    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):
        timestamp, ifaceName, packet = recv
        
        arp:Arp = packet.get_header(Arp)

        if arp is None:
            log_info("None!")
            return 

        # handle arp packet

        dst_ip = arp.targetprotoaddr
        interface_list = self.net.interfaces()

        for my_interface in interface_list:
            if dst_ip == my_interface.ipaddr:
                if arp.operation != ArpOperation.Request:
                    return 
                    # drop it!
                
                reply_packet = create_ip_arp_reply(my_interface.ethaddr, arp.senderhwaddr, dst_ip, arp.senderprotoaddr)
                self.send_packet_to(reply_packet, ifaceName)
                self.add_table(arp.targetprotoaddr, arp.targethwaddr)
                # find the destination and send back another arp packet
        

        # TODO: your logic here
        ...

    def send_packet_to(self, packet: switchyard.llnetbase.ReceivedPacket, interface_name) -> None:
        target_interface = self.net.interface_by_name(interface_name)
        self.net.send_packet(target_interface, packet)

    def add_table(self, new_ip, new_mac) -> None:
        self.arpTable[new_ip] = ArpTableEntry(new_mac)

    def update_table(self, timeout) -> None:

        for key in self.arpTable:
            if self.arpTable[key].test_timeout(timeout):
                log_info(f"remove f{key} !")
                self.arpTable.pop(key) 

        log_info("after update arp table:")
        for key in self.arpTable:
            print(f"{key} : {self.arpTable[key].get_address()}")
        

    def start(self):
        '''A running daemon of the router.
        Receive packets until the end of time.
        '''
        # log_info(f"my interfaces: {self.net.interfaces()}")
        while True:
            try:
                recv = self.net.recv_packet(timeout=1.0)
            except NoPackets:
                continue
            except Shutdown:
                break
            self.update_table(timeout=100.0)
            self.handle_packet(recv)

        self.stop()

    def stop(self):
        self.net.shutdown()


def main(net):
    '''
    Main entry point for router.  Just create Router
    object and get it going.
    '''
    router = Router(net)
    router.start()
