import queue
import threading
from link_3 import LinkFrame


## wrapper class for a queue of packets
class Interface:
    ## @param maxsize - the maximum size of the queue storing packets
    #  @param capacity - the capacity of the link in bps
    def __init__(self, maxsize=0, capacity=500):
        self.in_queue = queue.Queue(maxsize);
        self.out_queue = queue.Queue(maxsize);
        self.capacity = capacity #serialization rate
        self.next_avail_time = 0 #the next time the interface can transmit a packet
    
    ##get packet from the queue interface
    # @param in_or_out - use 'in' or 'out' interface
    def get(self, in_or_out):
        try:
            if in_or_out == 'in':
                pkt_S = self.in_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the IN queue')
                return pkt_S
            else:
                pkt_S = self.out_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the OUT queue')
                return pkt_S
        except queue.Empty:
            return None
        
    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param in_or_out - use 'in' or 'out' interface
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, in_or_out, block=False):
        if in_or_out == 'out':
            # print('putting packet in the OUT queue')
            self.out_queue.put(pkt, block)
        else:
            # print('putting packet in the IN queue')
            self.in_queue.put(pkt, block)
            
        
## Implements a network layer packet
# NOTE: You will need to extend this class for the packet to include
# the fields necessary for the completion of this assignment.
class NetworkPacket:
    ## packet encoding lengths 
    dst_S_length = 5
    
    ##@param dst: address of the destination host
    # @param data_S: packet payload
    # @param priority: packet priority
    def __init__(self, dst, data_S, priority):
        self.dst = dst
        self.data_S = data_S
        self.priority = priority
        
    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()
        
    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst).zfill(self.dst_S_length)
        byte_S += self.data_S
        byte_S += str(self.priority)
        return byte_S
    
    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        dst = byte_S[0 : NetworkPacket.dst_S_length].strip('0')
        data_S = byte_S[NetworkPacket.dst_S_length : len(byte_S) - 1]
        priority = byte_S[-1]
        return self(dst, data_S, priority)
        

class MPLSFrame:
    
    label_length = 20
    exp_length = 3
    s_length = 1
    ttl_length = 5
    pkt_length = 0
    
    def __init__(self, label, exp, s, ttl, pkt):
        self.label = label
        self.exp = exp
        self.s = s
        self.ttl = ttl
        self.pkt = pkt
        self.pkt_length = len(pkt.to_byte_S())
    
    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()
        
    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.label).zfill(self.label_length)
        byte_S += str(self.exp).zfill(self.exp_length)
        byte_S += str(self.s).zfill(self.s_length)
        byte_S += str(self.ttl).zfill(self.ttl_length)
        byte_S += str(self.pkt.to_byte_S())
        return byte_S
    
    @classmethod
    def from_byte_S(self, byte_S):
        label = byte_S[0 : self.label_length].strip('0')
        exp = byte_S[self.label_length + 1 : self.label_length + self.exp_length].strip('0')
        s = byte_S[self.label_length + self.exp_length + 1 : self.label_length + self.exp_length + self.s_length].strip('0')
        ttl = byte_S[self.label_length + self.exp_length + self.s_length + 1 : self.label_length + self.exp_length + self.s_length + self.ttl_length].strip('0')
        pkt_S = byte_S[self.label_length + self.exp_length + self.s_length + self.ttl_length : ]
        pkt = NetworkPacket.from_byte_S(pkt_S)
        return self(label, exp, s, ttl, pkt)
        
        
## Implements a network host for receiving and transmitting data
class Host:
    
    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.intf_L = [Interface()]
        self.stop = False #for thread termination
    
    ## called when printing the object
    def __str__(self):
        return self.addr
       
    ## create a packet and enqueue for transmission
    # @param dst: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    # @param priority: packet priority
    def udt_send(self, dst, data_S, priority):
        pkt = NetworkPacket(dst, data_S, priority)
        #print('%s: sending packet "%s" with priority %d\n' % (self, pkt, priority))
        #encapsulate network packet in a link frame (usually would be done by the OS)
        fr = LinkFrame('Network', pkt.to_byte_S())
        #enque frame onto the interface for transmission
        self.intf_L[0].put(fr.to_byte_S(), 'out') 
        
    ## receive frame from the link layer
    def udt_receive(self):
        fr_S = self.intf_L[0].get('in')
        if fr_S is None:
            return
        #decapsulate the network packet
        fr = LinkFrame.from_byte_S(fr_S)
        assert(fr.type_S == 'Network') #should be receiving network packets by hosts
        pkt_S = fr.data_S
        print('%s: received packet "%s"\n' % (self, pkt_S))
       
    ## thread target for the host to keep receiving data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            #receive data arriving to the in interface
            self.udt_receive()
            #terminate
            if(self.stop):
                print (threading.currentThread().getName() + ': Ending')
                return
        


## Implements a multi-interface router
class Router:
    
    ##@param name: friendly router name for debugging
    # @param intf_capacity_L: capacities of outgoing interfaces in bps 
    # @param encap_tbl_D: table used to encapsulate network packets into MPLS frames
    # @param frwd_tbl_D: table used to forward MPLS frames
    # @param decap_tbl_D: table used to decapsulate network packets from MPLS frames
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, intf_capacity_L, encap_tbl_D, frwd_tbl_D, decap_tbl_D, max_queue_size):
        self.stop = False #for thread termination
        self.name = name
        #create a list of interfaces
        self.intf_L = [Interface(max_queue_size, intf_capacity_L[i]) for i in range(len(intf_capacity_L))]
        #save MPLS tables
        self.encap_tbl_D = encap_tbl_D
        self.frwd_tbl_D = frwd_tbl_D
        self.decap_tbl_D = decap_tbl_D
        

    ## called when printing the object
    def __str__(self):
        return self.name


    ## look through the content of incoming interfaces and 
    # process data and control packets
    def process_queues(self):
        for i in range(len(self.intf_L)):
            fr_S = None #make sure we are starting the loop with a blank frame
            fr_S = self.intf_L[i].get('in') #get frame from interface i
            if fr_S is None:
                continue # no frame to process yet
            #decapsulate the packet
            fr = LinkFrame.from_byte_S(fr_S)
            pkt_S = fr.data_S
            #process the packet as network, or MPLS
            if fr.type_S == "Network":
                p = NetworkPacket.from_byte_S(pkt_S) #parse a packet out
                self.process_network_packet(p, i)
            elif fr.type_S == "MPLS":
                m_fr = MPLSFrame.from_byte_S(pkt_S) #parse a frame out
                
                #send the MPLS frame for processing
                self.process_MPLS_frame(m_fr, i)
            else:
                raise('%s: unknown frame type: %s\n' % (self, fr.type))

    ## process a network packet incoming to this router
    #  @param p Packet to forward
    #  @param i Incoming interface number for packet p
    def process_network_packet(self, pkt, i):
        
        if i == 0:
            key = 'H1'
        elif i == 1:
            key = 'H2'
        elif i == 2:
            key = 'H3'
        
        self.encap_tbl_D[key][1] = pkt.priority    
                
        m_fr = MPLSFrame(self.encap_tbl_D[key][0], self.encap_tbl_D[key][1], self.encap_tbl_D[key][2], self.encap_tbl_D[key][3], pkt)
        
        #print('%s: encapsulated packet "%s" as MPLS frame "%s"\n' % (self, pkt, m_fr))
        #send the encapsulated packet for processing as MPLS frame
        self.process_MPLS_frame(m_fr, i)


    ## process an MPLS frame incoming to this router
    #  @param m_fr: MPLS frame to process
    #  @param i Incoming interface number for the frame
    def process_MPLS_frame(self, m_fr, i):
        interface = -1
        
        if int(m_fr.label) in self.decap_tbl_D:
            interface = self.decap_tbl_D[int(m_fr.label)]
            packet = m_fr.pkt
            fr = LinkFrame('Network', packet.to_byte_S())
            self.intf_L[interface].put(fr.to_byte_S(), 'out', True)
            #print('%s: decapsulated frame "%s" from interface %d to %d\n' % (self, fr, i, interface))
            self.print_queues()
        else:
            check_tuple = (i, int(m_fr.label))
            tuple = self.frwd_tbl_D[check_tuple]
            interface = tuple[0]
            m_fr.label = tuple[1]
        
            #print('%s: processing MPLS frame "%s"\n' % (self, m_fr))
        
            try:
                fr = LinkFrame('MPLS', m_fr.to_byte_S())
                self.intf_L[interface].put(fr.to_byte_S(), 'out', True)
                #print('%s: forwarding frame "%s" from interface %d to %d\n' % (self, fr, i, interface))
                self.print_queues()
            except queue.Full:
                print('%s: frame "%s" lost on interface %d\n' % (self, fr, i))
                pass
    
    def sort_packet(self, frame):
        
        temp_packet = LinkFrame.from_byte_S(frame)
        temp_data = temp_packet.data_S
        if temp_packet.type_S == 'MPLS':
            m_fr = MPLSFrame.from_byte_S(temp_data)
            return m_fr.exp
        
        elif temp_packet.type_S == 'Network':
            packet = NetworkPacket.from_byte_S(temp_data)
            return packet.priority
                
                    
    def print_queues(self):
        for interface in range(len(self.intf_L)):
            temp_list = []
            priority_dict = {}
            while True:
                try:
                    frame = self.intf_L[interface].out_queue.get(block=False)
                except queue.Empty:
                    break
                
                else:
                    temp_list.append(frame)
                
            temp_list.sort(key = self.sort_packet, reverse=True)
            while len(temp_list) != 0:
                temp_S = temp_list.pop(0)
                self.intf_L[interface].put(temp_S, 'out')
                
                temp_packet = LinkFrame.from_byte_S(temp_S)
                temp_data = temp_packet.data_S
                
                if temp_packet.type_S == 'MPLS':
                    m_fr = MPLSFrame.from_byte_S(temp_data)
                    packet = m_fr.pkt
                    int_priority = int(packet.priority)
                    
                    if int_priority not in priority_dict:
                        priority_dict[int_priority] = 1
                    else:
                        priority_dict[int_priority] += 1
                    
                elif temp_packet.type_S == 'Network':
                    packet = NetworkPacket.from_byte_S(temp_data)
                    int_priority = int(packet.priority)
                    
                    if int_priority not in priority_dict:
                        priority_dict[int_priority] = 1
                    else:
                        priority_dict[int_priority] += 1
                        
            
            for key in priority_dict:
                print('%s - Interface %d: Queue has %d packets with priority %d' % (self.name, interface, priority_dict[key], key))
            
    ## thread target for the host to keep forwarding data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            self.process_queues()
            if self.stop:
                print (threading.currentThread().getName() + ': Ending')
                return 