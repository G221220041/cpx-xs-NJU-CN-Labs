#!/usr/bin/env python3

import time
from random import randint
import switchyard
from switchyard.lib.address import *
from switchyard.lib.packet import *
from switchyard.lib.userlib import *


class Blaster:
    def __init__(
            self,
            net: switchyard.llnetbase.LLNetBase,
            blasteeIp,
            num,
            length="100",
            senderWindow="5",
            timeout="300",
            recvTimeout="100"
    ):
        f = open('./context.txt')
        self.context = f.read().encode("utf-8")
        f.close()
        # here i get some context to transmite from blaster to blastee.
        # you can modify them.
        self.net = net
        # TODO: store the parameters
        self.blasterIp = '198.168.100.1'
        self.blasteeIp = blasteeIp
        self.num = int(num)
        self.sw_size = int(senderWindow)
        self.length = int(length)
        self.timeout = float(int(timeout)) / 1000
        self.recvTimeout = float(int(recvTimeout)) / 1000
        self.timer = time.time()
        
        self.next_seq = 0
        self.RHS = 0
        self.num_sent = 0
        self.window = []
        for _ in range(self.sw_size):
            self.window += [(False, 0, b'')]

        self.counter_timeout = 0
        self.retransmission = 0
        self.start_time = 0
        self.end_time = 0
        self.send_next = True
        self.sent_length = 0
        
    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):
        _, fromIface, packet = recv
        # print(f"I got a packet from {fromIface}")
        
        # if fromIface != "blaster-eht0":
        #     print("!!!?Error: Unkown prt!")
        #     self.shutdown()
        raw_bytes = packet[3].to_bytes()

        seq_num = int.from_bytes(raw_bytes[:4], "big")
        payload = raw_bytes[4:]
        # print(f"the packet with seqnum {seq_num} and payload {payload}")

        for i in range(0, self.RHS - self.num_sent):
            status, seq, pay = self.window[i]
            # print(f"Test with {self.window[i]}")
            if (status == False) and (pay == payload) and (seq == seq_num):
                # print("GET IT")
                self.window[i] = (True, seq, '')
                self.send_next = True
                break
        
        while self.window[0][0] == True:
            # print("slide the window")
            # self.current_seq = self.window[0][1]
            self.window = self.window[1:] + [(False, 0, b'')]
            self.num_sent += 1

        if self.num_sent == self.num:
            self.end_time = time.time()
            self.shutdown(False)
            
    def handle_no_packet(self):
        log_debug("Didn't receive anything")
        if self.num_sent == self.num:
            self.end_time = time.time()
            self.shutdown(False)
        # Creating the headers for the packet
        

        # Do other things here and send packet
        

        if (self.RHS - self.num_sent == self.sw_size):
            if self.send_next:
                log_debug("wait")
                self.send_next = False
            else:
                log_debug("retransmission!")
                stat, seq, _ = self.window[0]
                if not stat:
                    self.retransmission += 1
                    self.transPacket(seq - self.length)
                for i in range(1,5):
                    stat, _, _ = self.window[i]
                    if not stat:
                        _, seq_num, _ = self.window[i - 1]
                        self.retransmission += 1
                        self.transPacket(seq_num)
        else :
            seq = self.next_seq
            self.setWindow(seq)
            self.transPacket(seq)


    def start(self):
        '''A running daemon of the blaster.
        Receive packets until the end of time.
        '''
        self.start_time = time.time()
        while True:
            # print("\n-----window------")
            # for i in range(5):
            #     print(self.window[i])
            # print("-----window------")
            try:
                recv = self.net.recv_packet(timeout=self.recvTimeout)
            except NoPackets:
                if self.send_next:
                    self.handle_no_packet()
                    # self.send_next = False
                    self.timer = time.time()
                elif (time.time() - self.timer) > self.timeout:
                    self.counter_timeout += 1
                    self.handle_no_packet()
                continue
            except Shutdown:
                break

            self.handle_packet(recv)

        self.shutdown(True)

    def shutdown(self, final_shut):
        self.net.shutdown()
        if not final_shut:
            return
        total_time = int(self.end_time - self.start_time)
        log_info(f"Total time: {total_time}")
        log_info(f"Total retransmission: {self.retransmission}")
        log_info(f"Total num of coarse timeout: {self.counter_timeout}")
        log_info(f"ThroughPut: {self.sent_length / total_time}")
        log_info(f"GoodPut: {self.next_seq / total_time}")
    def transPacket(self, seq_num):
        pkt = Ethernet() + IPv4() + UDP()
        pkt[0].dst = '40:00:00:00:00:01'
        pkt[0].ethertype = EtherType.IPv4
        pkt[0].src = '10:00:00:00:00:01'
        pkt[1].src = self.blasterIp
        pkt[1].protocol = IPProtocol.UDP
        pkt[1].dst = self.blasteeIp
        payload = self.context[seq_num: seq_num + self.length]
        context_length = len(payload)
        pkt += RawPacketContents(seq_num.to_bytes(4, "big"))
        pkt += RawPacketContents(context_length.to_bytes(2, "big"))
        pkt += RawPacketContents(payload)
        log_debug(f"send packet with seq:{seq_num} and length: {context_length}")
        self.sent_length += context_length
        self.net.send_packet("blaster-eth0", pkt)
    
    def setWindow(self, seq_num):
        payload = self.context[seq_num: seq_num + self.length]
        context_length = len(payload)
        self.window[self.RHS - self.num_sent] = (False, seq_num + context_length, payload[:8])
        self.RHS += 1
        self.next_seq = seq_num + context_length





def main(net, **kwargs):
    blaster = Blaster(net, **kwargs)
    blaster.start()
