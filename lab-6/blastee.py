#!/usr/bin/env python3

import time
import threading
from struct import pack
import switchyard
from switchyard.lib.address import *
from switchyard.lib.packet import *
from switchyard.lib.userlib import *


class Blastee:
    def __init__(
            self,
            net: switchyard.llnetbase.LLNetBase,
            blasterIp,
            num
    ):
        self.net = net
        self.blasteeIp = '198.168.200.1'
        self.blasterIp = blasterIp
        self.num = int(num)
        self.contexts = []
        # self.wait_seq = 0
        # self.last_AKA = None
        self.recv_pkt = []
    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):
        _, fromIface, packet = recv
        print(f"\nPkt: {packet}")

        raw_bytes = packet[3].to_bytes()
        seqnum = int.from_bytes(raw_bytes[:4], "big")
        length = int.from_bytes(raw_bytes[4:6], "big")
        context_seg = raw_bytes[6:]
        
        # self.context += context_seg
        
        print(f"seq: {seqnum} and length: {length}")
        
        if seqnum in self.recv_pkt:
            print("drop!")
            
        else :
            self.recv_pkt += [seqnum]
            self.contexts += [(seqnum, context_seg)]
            pkt = Ethernet() + IPv4() + UDP()
            pkt[0].ethertype = EtherType.IPv4
            pkt[0].src = '20:00:00:00:00:01'
            pkt[0].dst = '40:00:00:00:00:02'

            pkt[1].src = self.blasteeIp
            pkt[1].dst = self.blasterIp
            pkt[1].ttl = 2
            pkt[1].protocol = IPProtocol.UDP
            pkt += RawPacketContents((seqnum + length).to_bytes(4, "big"))
            payload = raw_bytes[6:14]
            pkt += RawPacketContents(payload)
            print(f"send back ACK seq: {seqnum} and payload: {payload}")
            self.net.send_packet(fromIface, pkt)
        
        if len(self.recv_pkt) == self.num:
            print("whole context: ")
            self.contexts.sort(key=(lambda t: t[0]))
            for t in self.contexts:
                print(t[1].decode(),end='')
            self.shutdown()

    def start(self):
        '''A running daemon of the blastee.
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
    blastee = Blastee(net, **kwargs)
    blastee.start()
