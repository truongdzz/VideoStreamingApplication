from socket import SOCK_DGRAM, SOCK_STREAM
from tkinter import *
from tkinter import messagebox
import time
import tkinter.messagebox
from PIL import Image, ImageTk
import socket
import threading
import sys
import traceback
import os
import re
from datetime import datetime


from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"


class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3
    DESCRIBE = 4

    startingTime = 0
    totalBufferingTime = 0
    dataRate = 0
    lossRate = 0
    totalByte = 0
    frameNbr = 0

    # Initiation..

    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.connectToServer()
        self.frameNbr = 0
        self.frameShow = 1
        self.totalBufferingTime = 0
        self.miniPause = False
        self.playingTime = 0
        self.framePause = False
        self.isStreamingData = False

    def createWidgets(self):
        """Build GUI."""
        # Create Setup button
        # self.setup = Button(self.master, width=20, padx=3, pady=3)
        # self.setup["text"] = "Setup"
        # self.setup["command"] = self.setupMovie
        # self.setup.grid(row=1, column=0, padx=2, pady=2)
        # Create Play button
        self.start = Button(self.master, width=20, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=1, column=1, padx=2, pady=2)

        # Create Pause button
        self.pause = Button(self.master, width=20, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=1, column=2, padx=2, pady=2)

        # Create Foward button
        self.gofoward = Button(self.master, width=20, padx=3, pady=3)
        self.gofoward["text"] = "Foward 2s"
        self.gofoward["command"] = self.goFoward
        self.gofoward.grid(row=1, column=3, padx=2, pady=2)

        # Create Foward button
        self.gobackward = Button(self.master, width=20, padx=3, pady=3)
        self.gobackward["text"] = "Backward 2s"
        self.gobackward["command"] = self.goBackward
        self.gobackward.grid(row=1, column=4, padx=2, pady=2)

        # Create Teardown button
        self.teardown = Button(self.master, width=20, padx=3, pady=3)
        self.teardown["text"] = "Stop"
        self.teardown["command"] = self.stopClient
        self.teardown.grid(row=1, column=6, padx=2, pady=2)

        # Create Describe button
        self.describe = Button(self.master, width=20, padx=3, pady=3)
        self.describe["text"] = "Describe"
        self.describe["command"] = self.describeMovie
        self.describe.grid(row=1, column=5, padx=2, pady=2)

        # Create a label to display the movie
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4,
                        sticky=W+E+N+S, padx=5, pady=5)

    def setClientStat(self):
        # Create LossRate lable
        self.lossRateStat = Label(self.master, width=20, padx=3, pady=3)
        self.lossRateStat["text"] = "LossRate : " + \
            str("{:.2f}".format(self.lossRate)) + " %"
        self.lossRateStat.grid(row=2, column=1, padx=2, pady=2)
        # Create Datarate lable
        self.dataRateStat = Label(self.master, width=20, padx=3, pady=3)
        self.dataRateStat["text"] = "Data rate " + \
            str("{:.2f}".format(self.dataRate)) + " Kb/s"
        self.dataRateStat.grid(row=2, column=2, padx=2, pady=2)
        # Create Video Time label
        self.playTimeStat = Label(self.master, width=20, padx=3, pady=3)
        self.playTimeStat["text"] = "Playing time : " + \
            str(self.playingTime) + " seconds"
        self.playTimeStat.grid(row=2, column=3, padx=2, pady=2)

        # Crate FPS lable
        self.videoTimeStat = Label(self.master, width=20, padx=3, pady=3)
        self.videoTimeStat["text"] = "Video's Time : " + \
            str(self.frameNbr / 20) + " seconds"
        self.videoTimeStat.grid(row=2, column=4, padx=2, pady=2)

    def setupMovie(self):
        """Setup button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

    def describeMovie(self):
        self.sendRtspRequest(self.DESCRIBE)

    def exitClient(self):
        """exit handler."""
        if self.state != self.INIT:
            self.sendRtspRequest(self.TEARDOWN)
        pattern = "jpg$"
        for f in os.listdir():
            if re.search(pattern, f):
                os.remove(f)
        time.sleep(0.3)
        self.master.destroy()  # Close the gui window

        # os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video

    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)
            self.framePause = True

    def playMovie(self):
        """Play button handler."""
        if self.state == self.INIT:
            self.connectToServer()
            time.sleep(0.2)
        if self.state == self.READY:
            self.sendRtspRequest(self.PLAY)
            self.framePause = False

            threading.Thread(target=self.listenRtp).start()
            threading.Thread(target=self.updateMovie).start()

    def stopClient(self):
        if self.state != self.INIT:
            self.framePause = True
            self.sendRtspRequest(self.TEARDOWN)

        # os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video
        #  Receive Rtsp from server, if server accept close then re-connect again

    def goFoward(self):
        if self.framePause == True:
            if self.frameNbr - self.frameShow > 40:
                self.frameShow += 40
            else:
                self.frameShow = self.frameNbr
            regFrame = CACHE_FILE_NAME + \
                str(self.sessionId) + '-' + \
                str(self.frameShow) + CACHE_FILE_EXT
            photo = ImageTk.PhotoImage(Image.open(regFrame))
            self.label.configure(image=photo, height=288)
            self.label.image = photo
        else:
            self.framePause = True
            if self.frameNbr - self.frameShow > 40:
                self.frameShow += 40
            else:
                self.frameShow = self.frameNbr
            time.sleep(0.1)
            self.framePause = False
            if self.isStreamingData == False:
                threading.Thread(target=self.listenRtp).start()
        self.playingTime = self.frameShow / 20
        self.setClientStat()

    def goBackward(self):
        if self.framePause == True:
            if self.frameShow > 40:
                self.frameShow -= 40
            else:
                self.frameShow = 1
            regFrame = CACHE_FILE_NAME + \
                str(self.sessionId) + '-' + \
                str(self.frameShow) + CACHE_FILE_EXT
            photo = ImageTk.PhotoImage(Image.open(regFrame))
            self.label.configure(image=photo, height=288)
            self.label.image = photo
        else:
            self.framePause = True
            if self.frameShow > 40:
                self.frameShow -= 40
            else:
                self.frameShow = 1
            time.sleep(0.1)
            self.framePause = False
            if self.isStreamingData == False:
                threading.Thread(target=self.listenRtp).start()
        self.playingTime = self.frameShow / 20
        self.setClientStat()

    def to_integer(self, dt_time):
        return 3600*dt_time.hour + 60*dt_time.minute + dt_time.second

    def listenRtp(self):
        """Listen for RTP packets."""
        self.isStreamingData = True
        self.startingTime = datetime.now()
        oldframeNbr = 0
        self.setClientStat()
        ploss = 0
        while True:
            try:
                # print("listen")
                if (self.frameShow - oldframeNbr > 20 or oldframeNbr - self.frameShow < 20):

                    oldframeNbr = self.frameShow
                    self.setClientStat()
                data = self.rtpSocket.recv(20480)
                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)
                    currFrameNbr = rtpPacket.seqNum()

                    self.totalByte += len(rtpPacket.getPayload())
                    if currFrameNbr > self.frameNbr:  # Discard the late packet
                        if (currFrameNbr - self.frameNbr > 1):
                            ploss = ploss + currFrameNbr - self.frameNbr - 1
                        self.frameNbr = currFrameNbr
                        self.writeFrame(rtpPacket.getPayload())
                    self.totalBufferingTime = self.to_integer(
                        datetime.now()) - self.to_integer(self.startingTime)
                    self.lossRate = ploss / self.frameNbr * 100

                    self.dataRate = self.totalByte / \
                        abs(self.totalBufferingTime) / 1024
                    # print("Data rate " + "{:.2f}".format(self.dataRate)+ " kb/s" )

            except:
                if self.framePause == True:
                    self.isStreamingData = False
                    if self.teardownAcked == 1:
                        self.rtpSocket.shutdown(socket.SHUT_WR)
                        self.rtpSocket.close()
                    break

                # Upon receiving ACK for TEARDOWN request,
                # close the RTP socket

    def writeFrame(self, data):
        """Write the received frame to a temp image file. Return the image file."""
        cachename = CACHE_FILE_NAME + \
            str(self.sessionId) + '-' + str(self.frameNbr) + CACHE_FILE_EXT
        file = open(cachename, "wb")
        file.write(data)
        file.close()

    def updateMovie(self):
        """Update the image file as video frame in the GUI."""
        instanceFrame = self.frameShow
        while True:
            # print("outerloop " + str(self.framePause))
            if self.framePause == True:
                break
            time.sleep(0.05)
            try:
                # print("inner loop")

                regFrame = "^" + CACHE_FILE_NAME + \
                    str(self.sessionId) + '-' + \
                    str(self.frameShow) + CACHE_FILE_EXT + "$"
                # print(regFrame)
                for f in os.listdir():
                    if re.search(regFrame, f):
                        photo = ImageTk.PhotoImage(Image.open(str(f)))
                        self.label.configure(image=photo, height=288)
                        self.label.image = photo
                        self.frameShow += 1
                        self.playingTime = self.frameShow / 20
                        break
                instanceFrame += 1
                if instanceFrame - self.frameShow > 3:
                    self.frameShow += 1
                    instanceFrame = self.frameShow
            except:
                if self.framePause == True:
                    break
                if self.teardownAcked == 1:
                    break

    def connectToServer(self):
        """Connect to the Server. Start a new RTSP/TCP session."""
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except:
            tkinter.messagebox.showwarning(
                'Connection Failed', 'Connection to \'%s\' failed.' % self.serverAddr)
        # Send Init request to server
        self.setupMovie()

    def sendRtspRequest(self, requestCode):
        """Send RTSP request to the server."""
        # -------------
        # TO COMPLETE
        # -------------

        # Setup request
        if requestCode == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.recvRtspReply).start()
            # Update RTSP sequence number.
            # ...
            self.rtspSeq += 1
            # Write the RTSP request to be sent.
            # request = ...
            request = 'SETUP ' + (self.fileName) + ' RTSP/1.0\nCSeq: ' + str(
                self.rtspSeq) + '\nTransport: RTP/UDP; client_port= ' + str(self.rtpPort)

            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.SETUP

        # Play request
        elif requestCode == self.PLAY and self.state == self.READY:
            # Update RTSP sequence number.
            # ...
            self.rtspSeq += 1

            # Write the RTSP request to be sent.
            # request = ...
            request = 'PLAY ' + (self.fileName) + ' RTSP/1.0\nCSeq: ' + \
                str(self.rtspSeq) + '\nSession: ' + str(self.sessionId)

            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.PLAY

        # Describe request
        elif requestCode == self.DESCRIBE and self.state == self.READY:
            # Update RTSP sequence number.
            # ...
            self.rtspSeq += 1

            # Write the RTSP request to be sent.
            # request = ...
            request = 'DESCRIBE ' + (self.fileName) + ' RTSP/1.0\nCSeq: ' + \
                str(self.rtspSeq) + '\nSession: ' + str(self.sessionId)

            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.DESCRIBE

        # Pause request
        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            # Update RTSP sequence number.
            # ...
            self.rtspSeq += 1
            # Write the RTSP request to be sent.
            # request = ...
            request = 'PAUSE ' + (self.fileName) + ' RTSP/1.0\nCSeq: ' + \
                str(self.rtspSeq) + '\nSession: ' + str(self.sessionId)

            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.PAUSE

        # Teardown request
        elif requestCode == self.TEARDOWN and not self.state == self.INIT:
            # Update RTSP sequence number.
            # ...
            self.rtspSeq += 1

            # Write the RTSP request to be sent.
            # request = ...
            request = 'TEARDOWN ' + (self.fileName) + ' RTSP/1.0\nCSeq: ' + \
                str(self.rtspSeq) + '\nSession: ' + str(self.sessionId)
            self.requestSent = self.TEARDOWN
            # Keep track of the sent request.
            # self.requestSent = ...

        else:
            return

        # Send the RTSP request using rtspSocket.
        # ...
        self.rtspSocket.send(request.encode("utf-8"))

        print('\nData sent:\n' + request)

    def recvRtspReply(self):
        """Receive RTSP reply from the server."""
        while True:
            reply = self.rtspSocket.recv(1024)

            if reply:
                self.parseRtspReply(reply.decode("utf-8"))

            # Close the RTSP socket upon requesting Teardown
            if self.requestSent == self.TEARDOWN:
                self.rtspSocket.shutdown(socket.SHUT_RDWR)
                self.rtspSocket.close()
                break

    def parseRtspReply(self, data):
        """Parse the RTSP reply from the server."""
        lines = data.split('\n')
        seqNum = int(lines[1].split(' ')[1])

        # Process only if the server reply's sequence number is the same as the request's
        if seqNum == self.rtspSeq:
            session = int(lines[2].split(' ')[1])
            # New RTSP session ID
            if self.sessionId == 0:
                self.sessionId = session

            # Process only if the session ID is the same
            if self.sessionId == session:
                if int(lines[0].split(' ')[1]) == 200:
                    if self.requestSent == self.SETUP:
                        # -------------
                        # TO COMPLETE
                        # -------------
                        # Update RTSP state.
                        # self.state = ...
                        self.state = self.READY

                        # Open RTP port.
                        self.openRtpPort()
                    elif self.requestSent == self.PLAY:
                        # self.state = ...

                        self.state = self.PLAYING

                    elif self.requestSent == self.DESCRIBE:

                        #print('Data Received: ' + lines[3])
                        print('Data Received: ' + lines[3])
                        messagebox.showwarning('Data Received', 'Kinds of stream: ' + lines[3].split(
                            ' ')[0] + '\nEncoding: ' + lines[3].split(' ')[1])

                    elif self.requestSent == self.PAUSE:
                        # self.state = ...
                        self.state = self.READY
                        # The play thread exits. A new thread is created on resume.

                    elif self.requestSent == self.TEARDOWN:
                        # self.state = ...
                        self.state = self.INIT
                        # Flag the teardownAcked to close the socket.
                        self.teardownAcked = 1
                        self.miniPause = False
                        self.rtspSeq = 0
                        self.sessionId = 0
                        self.requestSent = -1
                        self.framePause = True
                        self.frameNbr = 0
                        self.frameShow = 1
                        self.totalBufferingTime = 0
                        time.sleep(0.1)
                        self.teardownAcked = 0

                        # waiting for server respone before setup again
                        time.sleep(0.1)
                        pattern = "jpg$"
                        for f in os.listdir():
                            if re.search(pattern, f):
                                os.remove(f)

    def openRtpPort(self):
        """Open RTP socket binded to a specified port."""
        # -------------
        # TO COMPLETE
        # -------------
        # Create a new datagram socket to receive RTP packets from the server
        # self.rtpSocket = ...
        # soc_dgram using for UDP protocol
        self.rtpSocket = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_DGRAM)

        # Set the timeout value of the socket to 0.5sec
        # ...
        self.rtpSocket.settimeout(0.5)
        try:
            # Bind the socket to the address using the RTP port given by the client user
            # ...
            # self.rtpSocket.bind((socket.gethostname(), self.rtpPort))
            self.rtpSocket.bind(("", self.rtpPort))

        except:
            messagebox.showwarning(
                'Unable to Bind', 'Unable to bind PORT=%d' % self.rtpPort)

    def handler(self):
        """Handler on explicitly closing the GUI window."""
        flag = False
        if self.state == self.PLAYING:
            flag = True
        self.pauseMovie()
        if messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else:  # When the user presses cancel, resume playing.
            if(flag):
                self.playMovie()
