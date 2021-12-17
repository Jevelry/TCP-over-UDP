from socket import *
import sys
import struct
import time
import os

SEQNUM = 0
ACKNUM = 1
FLAG = 2
PAYLOADNUM = 3
NOFLAG = 0
FIN = 1
SYN = 2
ACK = 4
NOPAYLOAD = 0

receiverPort = int(sys.argv[1])
outputFile = sys.argv[2]
serverSocket = socket(AF_INET, SOCK_DGRAM)
serverSocket.bind(('localhost', receiverPort))

initial_time = time.time()

f = open("Receiver_log.txt", "a")
# Did not import this function as I was unsure if it would be slower or not
def generateLog(sendrecv, seq, ack, flag, payloadSize): 
    
    t = time.time() - initial_time 
    t = round(t*1000, 2)
    seq = seq
    ack = ack
    flag = flag
    payload = payloadSize
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
        
    #Time value can get very long so seperated fields by two tabs

    for entry in log:
        entry = str(entry)
        entry = entry.ljust(8, ' ')
        f.write(entry)
        f.write("\t\t")
    f.write('\n')
   

buffer = {}
smallestUnacked = 0
fin = False
windowSize = 0
duplicates = 0

#SETUP CONNECTION
data, clientAddress = serverSocket.recvfrom(2048)
seq, ack, flag, payloadSize, windowpackets = struct.unpack(f'!LLHHH', data)
generateLog("rcv", seq, ack, flag, payloadSize)

if flag == SYN:
    windowsize = windowpackets
    packet = struct.pack('!LLHH', 0, 1, SYN + ACK, NOPAYLOAD)
    serverSocket.sendto(packet, clientAddress)
    generateLog("snd", 0, 1, ACK, NOPAYLOAD)
    smallestUnacked = 1

while 1:
    data, clientAddress = serverSocket.recvfrom(2048)
    
    #receive data from the client, now we know who we are talking with
    if len(data) != 12:
        seq, ack, flag, payloadSize, payload = struct.unpack(f'!LLHH{len(data) - 12}s', data)
        generateLog("rcv", seq, ack, flag, payloadSize)
    else:
        seq, ack, flag, payloadSize = struct.unpack('!LLHH', data)
        generateLog("rcv", seq, ack, flag, payloadSize)
    if flag == ACK:
        if fin == False:
            continue
        else:
            break
    elif flag == NOFLAG:
        if seq in buffer:
            duplicates += 1
            packet = struct.pack('!LLHH', 1, smallestUnacked, ACK, NOPAYLOAD)
            serverSocket.sendto(packet, clientAddress)
            generateLog("snd", 1, smallestUnacked, ACK, NOPAYLOAD)

        else:
            buffer[seq] = payload
            if seq == smallestUnacked:
                smallestUnacked += len(payload)
            for x in range(windowsize):
                if smallestUnacked in buffer:
                    smallestUnacked += len(buffer[smallestUnacked])

            packet = struct.pack('!LLHH', 1, smallestUnacked, ACK, NOPAYLOAD)
            serverSocket.sendto(packet, clientAddress)
            generateLog("snd", 1, smallestUnacked, ACK, NOPAYLOAD)

    elif flag == FIN:
        fin = True
        packet = struct.pack('!LLHH', 1, smallestUnacked + 1, FIN + ACK, NOPAYLOAD)
        serverSocket.sendto(packet, clientAddress)
        generateLog("snd", 1, smallestUnacked + 1, FIN + ACK, NOPAYLOAD)

with open(outputFile, 'w') as out:
    for i in sorted (buffer.keys()):
        out.write(buffer[i].decode('utf-8'))

size = int(os.stat(outputFile).st_size)
f.write('\n')
f.write(f"Amount of (original) Data Received (in bytes): {size}\n")
f.write(f"Number of Data Segments Recevied (excluding retransmissions): {len(buffer)}\n")
f.write(f"Number of Duplicate Segments received: {duplicates}\n")

f.close()