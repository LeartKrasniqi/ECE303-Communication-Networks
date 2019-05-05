# Written by S. Mevawala, modified by D. Gitzel

import logging
import socket

import channelsimulator
import utils
import sys

import math
import random

MAX_SEQ_NUM = 256


class Sender(object):

    def __init__(self, inbound_port=50006, outbound_port=50005, timeout=10, debug_level=logging.INFO):
        self.logger = utils.Logger(self.__class__.__name__, debug_level)

        self.inbound_port = inbound_port
        self.outbound_port = outbound_port
        self.simulator = channelsimulator.ChannelSimulator(inbound_port=inbound_port, outbound_port=outbound_port,
                                                           debug_level=debug_level)
        self.simulator.sndr_setup(timeout)
        self.simulator.rcvr_setup(timeout)

    def send(self, data):
        raise NotImplementedError("The base API class has no implementation. Please override and add your own.")


class BogoSender(Sender):

    def __init__(self):
        super(BogoSender, self).__init__()

    def send(self, data):
        self.logger.info("Sending on port: {} and waiting for ACK on port: {}".format(self.outbound_port, self.inbound_port))
        while True:
            try:
                self.simulator.u_send(data)  # send data
                ack = self.simulator.u_receive()  # receive ACK
                self.logger.info("Got ACK from socket: {}".format(
                    ack.decode('ascii')))  # note that ASCII will only decode bytes in the range 0-127
                break
            except socket.timeout:
                pass


# My implemented class 
class rdtSender(Sender):
    # Setting up some preliminary parameters
    data_file = 0
    MSS = 250                                                 # Maximum Segment Size
    segment_num = 0                                           # Segment Number
    partition = 0                                             # Partition Number  
    start = 0                                                 # Start of partition
    end = MSS                                                 # End of partition
    seq_num = random.randint(0, MAX_SEQ_NUM - 1)              # Pick a random sequence number to begin with
    
    # Setting up data buffer
    data_buffer = bytearray(MAX_SEQ_NUM)
    buffer_start = seq_num
    buffer_end = seq_num

    # Initialization of stuff
    num_duplicates = 0
    is_sent = False
    resend = False

    # Initialization, including timeout 
    def __init__(self, DATA, timeout = 0.1):
        super(rdtSender, self).__init__()
        self.data_file = DATA
        self.timeout = timeout
        self.simulator.sndr_socket.settimeout(self.timeout)
        self.segment_num = int(math.ceil(len(self.data_file)/float(self.MSS)))

    # The actual sending function 
    def send(self, data):
        self.logger.info("Sending on port: {} and waiting for ACK on port: {}".format(self.outbound_port, self.inbound_port))


        for s in self.splitSegment(self.data_file, self.MSS, self.partition):
            try:
                # First time sending the data 
                if not self.resend:
                    # Some initialization 
                    seg = rdtSegment(seq_num = 0, ack_num = 0, check_sum = 0, data = s)
                    seg.seq_num = rdtSegment.seqNum(self, self.seq_num, self.MSS)
                    self.seq_num = seg.seq_num
                    seg.ack_num = 0

                    # Create array that will actually be sent
                    send_array = bytearray([seg.check_sum, seg.ack_num, seg.seq_num])
                    send_array += s

                    # Create a checksum field for the data to be sent 
                    seg.check_sum = rdtSegment.checkSum(self, send_array)
                    send_array[0] = seg.check_sum

                    # Finally, send the data       
                    self.simulator.u_send(send_array) 

                # Getting stuff back from the receiver and figuring out what to do
                while True:
                    rcv_array = self.simulator.u_receive()

                    # The ACK is not corrupted 
                    if self.checkReceiverACK(rcv_array):
                        # Sequence number is correct 
                        if rcv_array[1] == self.seq_num:
                            self.is_sent = True
                            self.simulator.u_send(send_array)  

                        # If ACK for subsequent segment comes in, know that the prev segment was also received
                        elif rcv_array[1] == (self.seq_num + len(s)) % MAX_SEQ_NUM: 
                            self.num_duplicates = 0
                            if self.timeout > 0.1:
                                self.timeout -= 0.1
                            self.simulator.sndr_socket.settimeout(self.timeout)
                            self.resend = False
                            break

                        # There was an error, need to resend     
                        else: 
                            self.simulator.u_send(send_array) 
                    
                    # The ACK was corrupted, need to resend data
                    else:
                        self.simulator.u_send(send_array) 
                        self.num_duplicates += 1
                        
                        # If the package was sent and there are three duplicate ACKs, wait a little longer but not too long
                        if self.num_duplicates == 3 and self.is_sent:
                            self.timeout *= 2
                            self.simulator.sndr_socket.settimeout(self.timeout) 
                            self.num_duplicates = 0
                            if self.timeout > 5:
                                print("Timeout")
                                exit()

            # If there is a timeout, resend the data and wait for another timeout 
            except socket.timeout:
                self.resend = True
                self.simulator.u_send(send_array)
                self.num_duplicates += 1
                if self.num_duplicates >= 3:
                    self.num_duplicates = 0
                    self.timeout *= 2
                    self.simulator.sndr_socket.settimeout(self.timeout)
                    if self.timeout > 5:
                        print("Timeout has occurred!")
                        exit()                                           


    # Checks the checksum of the receiver ACK
    def checkReceiverACK(self, data):
        check_sum_val = ~data[0]        # Invert all the bits in the first row of the data array (i.e. the checksum row)
        for i in xrange(1, len(data)):  
            check_sum_val ^= data[i]    # XOR against all of the rows in the data
        if check_sum_val == -1: 
            return True                 # If check_sum_val is all ones (i.e. -1 in twos complement), we good
        else:
            return False

    # Split up the segment into smaller segements each <= MSS 
    def splitSegment(self, data, MSS, partition):
        for i in range(self.segment_num):
            partition += 1
            yield data[self.start:self.end]         # Only focus on one smaller sub-segement at a time
            self.start = self.start + MSS           # New start of partition
            self.end = self.end + MSS               # New end of partition 



# The data is in this segment, along with error checking stuff 
# The segment is [ CHECKSUM | SEQ_NUM | ACK_NUM | DATA]
class rdtSegment(object):

    def __init__(self, check_sum = 0, seq_num = 0, ack_num = 0, data = []):
        self.check_sum = check_sum
        self.ack_num = ack_num
        self.seq_num = seq_num
        self.data = data

    @staticmethod
    def seqNum(self, prev_seq_num, MSS):
        return (prev_seq_num + MSS) % MAX_SEQ_NUM

    # Make data into a byte array and then do the checksum 
    @staticmethod
    def checkSum(self, data):
        data_array = bytearray(data)
        check_sum_val = 0
        for i in xrange(len(data_array)):
            check_sum_val ^= data_array[i]
        return check_sum_val


if __name__ == "__main__":
    # test out BogoSender
    DATA = bytearray(sys.stdin.read())
    #sndr = BogoSender()
    sndr = rdtSender(DATA)
    sndr.send(DATA)
