#!/usr/bin/env python3

import time
import threading
from random import randint

import switchyard
from switchyard.lib.address import *
from switchyard.lib.packet import *
from switchyard.lib.userlib import *
from switchyard.lib.logging import *

class Middlebox:
    def __init__(
            self,
            net: switchyard.llnetbase.LLNetBase,
            dropRate="0.19"
    ):
        self.net = net
        self.dropRate = float(dropRate)

    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):
        
            
        _, fromIface, packet = recv
        if fromIface == "middlebox-eth0":
            log_debug("Received from blaster")
            '''
            Received data packet
            Should I drop it?
            If not, modify headers & send to blastee
            '''

            random_num = randint(0, 100)
            if random_num <= self.dropRate * 100:
                log_debug(f"with value of {random_num / 100}, drop it!") 
            else:
                eth = Ethernet()
                eth.ethertype = packet[Ethernet].ethertype
                eth.src = self.net.interface_by_name("middlebox-eth1").ethaddr
                eth.dst = EthAddr('20:00:00:00:00:01')
                packet[0] = eth
                log_debug(f"send new packet: {packet}")
                self.net.send_packet("middlebox-eth1", packet)
        elif fromIface == "middlebox-eth1":
            log_debug("Received from blastee")
            '''
            Received ACK
            Modify headers & send to blaster. Not dropping ACK packets!
            net.send_packet("middlebox-eth0", pkt)
            '''
            eth = Ethernet()
            eth.ethertype = packet[Ethernet].ethertype
            eth.src = self.net.interface_by_name("middlebox-eth0").ethaddr
            eth.dst = EthAddr('10:00:00:00:00:01')
            packet[0] = eth
            log_debug(f"send new packet: {packet}")
            
            self.net.send_packet("middlebox-eth0", packet)
        else:
            log_debug("Oops :))")

    def start(self):
        '''A running daemon of the router.
        Receive packets until the end of time.
        '''
        while True:
            try:
                recv = self.net.recv_packet(timeout=1.0)
            except NoPackets:
                continue
            except Shutdown:
                break

            self.handle_packet(recv)

        self.shutdown()

    def shutdown(self):
        self.net.shutdown()


def main(net, **kwargs):
    middlebox = Middlebox(net, **kwargs)
    middlebox.start()
