# Written by S. Mevawala, modified by D. Gitzel

import logging

import channelsimulator
import utils
import sys
import socket

class Receiver(object):

    def __init__(self, inbound_port=50005, outbound_port=50006, timeout=10, debug_level=logging.INFO):
        self.logger = utils.Logger(self.__class__.__name__, debug_level)

        self.inbound_port = inbound_port
        self.outbound_port = outbound_port
        self.simulator = channelsimulator.ChannelSimulator(inbound_port=inbound_port, outbound_port=outbound_port,
                                                           debug_level=debug_level)
        self.simulator.rcvr_setup(timeout)
        self.simulator.sndr_setup(timeout)

    def receive(self):
        raise NotImplementedError("The base API class has no implementation. Please override and add your own.")


class BogoReceiver(Receiver):
    ACK_DATA = bytes(123)

    def __init__(self):
        super(BogoReceiver, self).__init__()

    def receive(self):
        self.logger.info("Receiving on port: {} and replying with ACK on port: {}".format(self.inbound_port, self.outbound_port))
        while True:
            try:
                 data = self.simulator.u_receive()  # receive data
                 self.logger.info("Got data from socket: {}".format(
                     data.decode('ascii')))  # note that ASCII will only decode bytes in the range 0-127
	         sys.stdout.write(data)
                 self.simulator.u_send(BogoReceiver.ACK_DATA)  # send ACK
            except socket.timeout:
                sys.exit()

# My implementation of receiver 
class rdtReceiver(Receiver):
    # Initialization
    rcv_array = bytearray([0,0,0,0])
    last_ACK_num = -1 
    ACK_backup = bytearray([0,0,0])
    resend = True
    num_duplicates = 0


    def __init__(self, timeout = 0.1):
        super(rdtReceiver, self).__init__()
        self.timeout = timeout
        self.simulator.rcvr_socket.settimeout(self.timeout)

    def receive(self):
        # Wait for data to come in
        while True:
            try:
                # Receive data and check the timeout 
                self.rcv_array = self.simulator.u_receive()
                if self.timeout > 0.1:
                    self.timeout -= 0.1
                    self.num_duplicates = 0

                # Send the ACK 
                self.send()

            # If timeout, resend the back-up ACK (i.e. the most recent ACK we made)    
            except socket.timeout:
                self.resend = True
                self.simulator.u_send(self.ACK_backup)
                self.num_duplicates += 1
                if self.num_duplicates >= 3:
                    self.num_duplicates = 0
                    self.timeout *= 2
                    self.simulator.rcvr_socket.settimeout(self.timeout)
                    if self.timeout > 5:
                        exit()
                        
    def send(self):
        # Create an ACK to be sent
        ACK_seg = rdtSegment()
        ACK_success = ACK_seg.ack(self.rcv_array, self.last_ACK_num)
        if ACK_success:
            self.last_ACK_num = ACK_seg.ACK_num
        if ACK_seg.ACK_num < 0:
            ACK_seg.ACK_num = 0 # we set it to 0 here, it may be set back to -1
        ACK_seg.check_sum = ACK_seg.checkSum()
        rcv_array = bytearray([ACK_seg.check_sum, ACK_seg.ACK_num])
        ACK_backup = rcv_array
        self.simulator.u_send(rcv_array)

class rdtSegment(object):

    def __init__(self, check_sum = 0, seq_num = 0, ACK_num = 0, data = []):
        self.check_sum = check_sum
        self.seq_num = seq_num
        self.ACK_num = ACK_num
        self.data = data
         
    # Since the receiver segment only has an ACK number, its checksum will just be itself
    def checkSum(self):        
        return self.ACK_num
        

    # Checks the checksum (i.e. the ACK number in this case)
    def checkACK(self,data):         
        check_sum_val =~ data[0]            # Invert all the bits in the first row of the data array (i.e. the checksum row)    
        for i in xrange(1,len(data)):
            check_sum_val ^= data[i]        # XOR against all of the rows in the data
        if check_sum_val ==- 1:          
            return True                     # If check_sum_val is all ones (i.e. -1 in twos complement), we good
        else:
            return False
    
    # Checks if the ACK is valid 
    def ack(self, data, last_ACK_num):
        we_going_to_standings = self.checkACK(data)
        if we_going_to_standings:
            self.ACK_num = (data[2] + len(data[3:])) % 256
            if data[2] == last_ACK_num or last_ACK_num == -1:
                sys.stdout.write("{}".format(data[3:]))
                sys.stdout.flush()
                return True
        else:
            pass

        return False

if __name__ == "__main__":
    # test out BogoReceiver
    #rcvr = BogoReceiver()
    rcvr = rdtReceiver()
    rcvr.receive()
