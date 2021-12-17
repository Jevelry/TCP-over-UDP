import os
from socket import *
import threading
from datetime import datetime
import time
import struct
import sys
import random
#ARGUMENTS
# 1. receiver ip
# 2. receiver port
# 3. FileToSend.txt
# 4. Maximum window size
# 5. Maximum segment size
# 6. Timeout value
# 7. pdrop
# 8. seed

#HEADER STRUCTURE
#SEQ NO     32
#ACK NO     32
#Data size  8
#FLAG       4
    #1      FIN
    #2      SYN 
    #4      ACK
#CONSTANTS
SEQNUM = 0
ACKNUM = 1
FLAG = 2
PAYLOADNUM = 3
NOFLAG = 0
FIN = 1
SYN = 2
ACK = 4
NOPAYLOAD = 0
RECEIVERACK = 1

def readFile(file, MSS):
    #Assume file exists and can be read
    packets = {}
    f = open(file, "r")
    seqNum = 1
    bytes = None
    while bytes != "":
        # Assume that no two sequence numbers are the same
        bytes = f.read(MSS)
        if bytes != "":
            packets[seqNum] = bytes
            seqNum += len(bytes)
    return packets, int(os.stat(fileName).st_size)

initial_time = time.time()
clientSocket = socket(AF_INET, SOCK_DGRAM)
receiverIP = sys.argv[1]
receiverPort = int(sys.argv[2])
fileName = sys.argv[3]
MWS = int(sys.argv[4])
MSS = int(sys.argv[5])
timeoutvalue = int(sys.argv[6]) / 1000
PDrop = float(sys.argv[7])
seed = int(sys.argv[8])

sendbase = 1
packets, totalPackets = readFile(fileName, MSS)
unacked = []
t_lock=threading.Condition()


retransmittedSegments = 0
def ontimeout():
    global tmr
    global retransmittedSegments
    try:
        newPacket = struct.pack(f'!LLHH',sendbase, RECEIVERACK, NOFLAG, len(packets[sendbase]))
        if canSendPacket():
            generateLog("snd",newPacket)
            clientSocket.sendto((newPacket + packets[sendbase].encode('utf-8')), (receiverIP, receiverPort))
        else: 
            generateLog("drop",newPacket)
        retransmittedSegments += 1
        tmr = threading.Timer(timeoutvalue, ontimeout)
        tmr.start()
    except:
        pass


tmr = threading.Timer(timeoutvalue, ontimeout)
tmr.daemon = True

f = open("Sender_log.txt", "a")
def generateLog(sendrecv, header): 
    # ONLY USED FOR INTIAL SYN
    if len(header) == 14:
        header = struct.unpack('!LLHHH', header)
    else:
        header = struct.unpack('!LLHH', header)
    t = time.time() - initial_time 
    t = round(t*1000, 2)
    seq = header[SEQNUM]
    ack = header[ACKNUM]
    flag = header[FLAG]
    payload = header[PAYLOADNUM]
    if flag == NOFLAG:
        packetType = "D"
    if flag == FIN:
        packetType = "F"
    if flag == SYN:
        packetType = "S"
    if flag == ACK:
        packetType = "A"
    if flag == SYN + ACK:
        packetType = "SA"
    if flag == FIN + ACK:
        packetType = "FA"
    log = [sendrecv, t, packetType, seq, payload, ack]
        
    for entry in log:
        entry = str(entry)
        entry = entry.ljust(4, ' ')
        f.write(entry)
        f.write("\t")
    f.write('\n')

def printStatistics():
    f.write('\n')
    f.write(f"Amount of (original) Data Transferred (in bytes): {int(os.stat(fileName).st_size)}\n")
    f.write(f"Number of Data Segments Sent (excluding retransmissions): {len(packets)}\n")
    f.write(f"Number of (all) Packets Dropped (by the PL module): {packetsDropped}\n")
    f.write(f"Number of Retransmitted Segments: {retransmittedSegments}\n")
    f.write(f"Number of Duplicate Acknowledgements received: {duplicateAcks}\n")




packetsDropped = 0
random.seed(seed)
def canSendPacket():
    global packetsDropped
    PLoss = random.random()
    if PLoss < PDrop:
        packetsDropped += 1
        return False
    else:
        return True
    

tripleAckCounter = 0
duplicateAcks = 0
def Recevier():
    global sendbase
    global clientSocket
    global unacked
    global tmr
    global tripleAckCounter
    global duplicateAcks
    while (1):
        response, _ = clientSocket.recvfrom(2048)
        generateLog("rcv", response)
        with t_lock:
            
            seq, ack, flag, _ = struct.unpack('!LLHH', response)
            if seq == 1 and flag == ACK:
                if ack > sendbase:
                    tmr.cancel()
                    tmr = threading.Timer(timeoutvalue, ontimeout)
                    tmr.daemon = True
                    tmr.start()
                    sendbase = ack
                    unacked = [ x for x in unacked if x >= sendbase ]
                    tripleAckCounter = 0
                elif ack == sendbase:
                    if sendbase >= totalPackets:
                        if tmr.is_alive():
                            tmr.cancel()
                        continue
                    duplicateAcks += 1
                    tripleAckCounter += 1
                    if tripleAckCounter == 3:
                        ontimeout()
                        tripleAckCounter = 0  
            if flag == FIN+ACK and seq == RECEIVERACK:
                newPacket = struct.pack('!LLHH', sendbase, 2, ACK, NOPAYLOAD)
                clientSocket.sendto(newPacket, (receiverIP, receiverPort))
                generateLog("snd", newPacket)
                break

            t_lock.notify()



    
# SETUP THE CONNECTION
# SEND INITIAL SYN
packet = struct.pack('!LLHHH', 0, 0, SYN, NOPAYLOAD, int(MWS/MSS))
clientSocket.sendto(packet, (receiverIP, receiverPort))
generateLog("snd", packet)
# RECEIVE RESPONSE
response, _ = clientSocket.recvfrom(2048)
generateLog("rcv", response)
response = struct.unpack('!LLHH', response)
# IF RESPONSE IS SYNACK
if response[FLAG] == SYN+ACK:
    packet = struct.pack('!LLHH', 1, RECEIVERACK, ACK, NOPAYLOAD)
    clientSocket.sendto(packet, (receiverIP, receiverPort))
    generateLog("snd", packet)

#START RECEIVING THREAD
recvThread = threading.Thread(target = Recevier)
recvThread.daemon = True
recvThread.start()


for p in packets:
    #While lastbytesent - lastbyteacked < MWS
    while p - sendbase >= MWS:
        time.sleep(0.01)
    with t_lock:
        newPacket = struct.pack(f'!LLHH',int(p), RECEIVERACK, NOFLAG, len(packets[p]))
        if canSendPacket():
            clientSocket.sendto((newPacket + packets[p].encode('utf-8')), (receiverIP, receiverPort))
            generateLog("snd", newPacket)
            if not tmr.isAlive():
                tmr = threading.Timer(timeoutvalue, ontimeout)
                tmr.daemon = True
                tmr.start()
            unacked.append(p)
        else:
            generateLog("drop", newPacket)
        t_lock.notify()
      
tmr.join()

newPacket = struct.pack(f'!LLHH',sendbase, 1, FIN, NOPAYLOAD)
clientSocket.sendto(newPacket, (receiverIP, receiverPort))
generateLog("snd", newPacket)
sendbase += 1
recvThread.join()


printStatistics()    

f.close()