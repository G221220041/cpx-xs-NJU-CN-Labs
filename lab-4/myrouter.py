#!/usr/bin/env python3

'''
Basic IPv4 router (static routing) in Python.
'''

import time
import switchyard
from switchyard.lib.userlib import *
from switchyard.lib.address import *

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


class ForwardingTableEntry():
    def __init__(self, prefix, mask, dst_addr, iface_name):
        self.prefix = IPv4Address(prefix)
        self.mask = IPv4Address(mask)
        self.dst_addr = IPv4Address(dst_addr)
        self.iface_name = iface_name 
        self.prefixlen = IPv4Network(prefix + '/' + mask).prefixlen


    def match(self, ipaddr:IPv4Address) -> bool:
        return (int(self.mask) & int(ipaddr)) == int(self.prefix)

    def display(self) -> None:
        print(f"entry: {self.prefix} | {self.mask} | {self.dst_addr} | {self.iface_name}")

            

class Router(object):
    def __init__(self, net: switchyard.llnetbase.LLNetBase):
        self.net = net
        self.arpTable = dict()
        self.forwardingTable = self.create_forwarding_table()
        self.wait_arp_packet = {}
        self.wait_arp_reply = {}

        log_info("succeed to create the forwarding table: ")
        for entry in self.forwardingTable:
            entry.display()
        # other initialization stuff here

    def create_forwarding_table(self) -> list:
        lst = []
        f = open('forwarding_table.txt')
        for line in f:
            value = line.split()
            lst.append(ForwardingTableEntry(value[0], value[1], value[2], value[3]))
        f.close()

        my_interface:Interface
        for my_interface in self.net.interfaces():
            lst.append(ForwardingTableEntry(
                str(IPv4Address(int(my_interface.ipaddr) & int(my_interface.netmask))), 
                str(my_interface.netmask), 
                '0.0.0.0',
                my_interface.name
            ))

        lst.sort(key=lambda x: x.prefixlen, reverse=True)
        return lst

    def handle_arp(self, arp, capture_interface):
        log_info('handle arp...')
        if arp.operation == ArpOperation.Reply:
            log_info(f"get packet with senderIP: {arp.senderprotoaddr}")
            if arp.senderprotoaddr not in self.wait_arp_reply:
                return
            # get a reply , then send all the wait list and add it to cached arp table
            self.add_table(arp.senderprotoaddr, arp.senderhwaddr)
            for wait_packet in self.wait_arp_packet[arp.senderprotoaddr]:
                time.sleep(1.5)
                log_info("before send wait packet")
                self.forward_packet(wait_packet, capture_interface, arp.senderhwaddr)
            self.wait_arp_packet.pop(arp.senderprotoaddr)
            self.wait_arp_reply.pop(arp.senderprotoaddr)
            return 
            
        if arp.operation == ArpOperation.Request:
            dst_ip = arp.targetprotoaddr
            interface_list = self.net.interfaces()

            for my_interface in interface_list:
                if dst_ip == my_interface.ipaddr:
                    reply_packet = create_ip_arp_reply(my_interface.ethaddr, arp.senderhwaddr, dst_ip, arp.senderprotoaddr)
                    # self.send_packet_to(reply_packet, ifaceName)
                    self.net.send_packet(capture_interface, reply_packet)
                    self.add_table(arp.senderprotoaddr, arp.senderhwaddr)
                    return 
            log_info('drop it for not found')

    def handle_ipv4(self, packet, ipv4:IPv4, eth:Ethernet, capture_interface:Interface):
        log_info("handle ipv4...")

        if (eth.dst != EthAddr('ff:ff:ff:ff:ff:ff')) and (eth.dst != capture_interface.ethaddr):
            log_info("drop the ipv4 for not broadcast nor right ethaddr")
            return
        my_interface:Interface
        for my_interface in self.net.interfaces():
            if ipv4.dst == my_interface.ipaddr:
                log_info("drop it for interface in this router ")
                # TODO left for lab5
                return
        
        # log_info("before look up forwarding table.")

        entry:ForwardingTableEntry
        for entry in self.forwardingTable:
            if entry.match(ipv4.dst):
                if ipv4.ttl <= 0:
                    log_info("a dead ipv4 for ttl")
                    # TODO left for lab5
                
                forward_inface = self.net.interface_by_name(entry.iface_name)
                log_info(forward_inface.name)

                if entry.dst_addr == IPv4Address('0.0.0.0'):
                    # log_info(f"set next ipv4.dst: {ipv4.dst}")
                    next_ip = ipv4.dst
                else:
                    next_ip = entry.dst_addr
                    # log_info(f"set next ip entry,dst_addr: {entry.dst_addr}")

                # next_ip = ipv4.dst
                
                if ipv4.dst not in self.arpTable:
                    log_info('cannot find in cached table and send a arp')
                    if ipv4.dst not in self.wait_arp_packet:
                        arp_packet = create_ip_arp_request(forward_inface.ethaddr, forward_inface.ipaddr, next_ip)
                        # log_info("before send arp request")
                        self.net.send_packet(forward_inface, arp_packet)
                        # log_info("after send arp request")
                        self.wait_arp_packet[next_ip] = [packet]
                        self.wait_arp_reply[next_ip] = (0, time.time(),forward_inface, arp_packet)
                        #if not in wait list, create  a new list
                    else:
                        self.wait_arp_packet[next_ip].append(packet)
                        # if already in wait list, append a new packet
                    return

                log_info('find in cached arp table')
                target_mac = self.arpTable[next_ip].get_address()
                self.forward_packet(packet, forward_inface, target_mac)
                return
            else:
                continue
            

        # no match entry TODO for lab5

    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):
        timestamp, ifaceName, packet = recv
        
        capture_interface = self.net.interface_by_name(ifaceName)
        arp:Arp = packet.get_header(Arp)
        eth:Ethernet = packet.get_header(Ethernet)
        ipv4:IPv4 = packet.get_header(IPv4)
        
        if (not arp is None) and (ipv4 is None):
            self.handle_arp(arp, capture_interface)
            return 
        if (not ipv4 is None) and (arp is None):
            self.handle_ipv4(packet, ipv4, eth, capture_interface)
            return


    def add_table(self, new_ip, new_mac) -> None:
        self.arpTable[new_ip] = ArpTableEntry(new_mac)

    def update_table(self, timeout) -> None:
        # log_info("update cached table")
        for key in self.arpTable:
            if self.arpTable[key].test_timeout(timeout):
                log_info(f"remove f{key} !")
                self.arpTable.pop(key) 

        # log_info("after update arp table:")
        for key in self.arpTable:
            print(f"{key} : {self.arpTable[key].get_address()}")
        
    def forward_packet(self, oldpacket, forward_interface:Interface, new_mac):
        packet = deepcopy(oldpacket)
        packet[IPv4].ttl -= 1
        packet[Ethernet].src = forward_interface.ethaddr
        packet[Ethernet].dst = new_mac
        self.net.send_packet(forward_interface, packet)

    def update_wait(self, timeout, current_time:time):
        log_info("update wait list")
        for key_ip in self.wait_arp_reply:
            counter, init_time, to_interface, arp_packet = self.wait_arp_reply[key_ip]
            if current_time - init_time < timeout:
                log_info("not time out")
                continue
            
            if counter > 3:
                self.wait_arp_packet.pop(key_ip)
                self.wait_arp_reply.pop(key_ip) 
            else:
                self.wait_arp_reply[key_ip] = (counter + 1, time.time(), to_interface, arp_packet)
                log_info(f"{key_ip} send {counter} times")
                self.net.send_packet(to_interface, arp_packet)
            return 

    def start(self):
        '''A running daemon of the router.
        Receive packets until the end of time.
        '''

        while True:
            try:
                recv = self.net.recv_packet(timeout=1.0)
            except NoPackets:
                self.update_table(timeout=100.0)
                self.update_wait(timeout=1.5, current_time=time.time())
                continue
            except Shutdown:
                break
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
