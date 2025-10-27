#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Combined launcher that starts the ChatGPT client as a background subprocess
# and then runs the robot script — without changing either script's logic.

import os
import sys
import subprocess
import threading
import atexit

# --- Write the ChatGPT client (UNMODIFIED) to a sidecar file and launch it ---
CHATGPT_SCRIPT_TEXT = r'''import csv
import numpy as np
import os
import openai
from langchain_openai import ChatOpenAI

# from langchain_openai import OpenAI
from langchain.prompts import PromptTemplate
# from langchain.chains import LLMChain
import sounddevice as sd
from scipy.io.wavfile import write
from tkinter import *
#from openai import OpenAI
import csv

global flag_need_record
global flag_record_done
global questionNum

def transcribeAudio(fileName):
    # transcribe audio
    audio_file= open(fileName, "rb")
    #===This code is outdated===
    #transcript = openai.Audio.transcribe("whisper-1", audio_file)
    #print(f'you:\t{transcript["text"]}')
    #return transcript['text']
    #===This code is outdated===
    
    transcript = openai.audio.transcriptions.create(model="whisper-1", file=audio_file)
    print(f'you:\t{transcript.text}')

    return transcript.text


def callChatGPT(fileName, questionNumber):

    # generate transcript from whisper
    transcript = transcribeAudio(fileName)

    # prompt = PromptTemplate(
    # input_variables=["answer", "question", "attitude"],
    # template="In one sentence, respond {attitude} to someone who gave an answer related to {answer} to the question, {question}" ,
    # )

    prompt = PromptTemplate(
    input_variables=["answer", "question"],
    template="I asked someone the question: {question} they responded: {answer}. In English, reword their response in one sentence, but replace all instances of I with you " ,
    )

    prompt = prompt.format(answer=transcript, question=question_prompts[questionNumber])
    print(prompt)

    llm = ChatOpenAI(temperature=0.9)
    response = llm.invoke(prompt).content
 
    #===This code is outdated===
    # chain = LLMChain(
    #     llm=OpenAI(temperature=0.9), #more variety, then increase the number
    #     prompt=prompt, 
    #     verbose=False 
    # )
    # response = chain.run({
    # 'answer': transcript,
    # 'question': question_prompts[questionNumber],
    # 'attitude': attitude_option,
    # })
    # response = chain.run(transcript, question_prompt, attitude_option)
    #===This code is outdated===
   
    print(f"NAO: \t{response}")

    response = response.strip()

    with open('data.csv', mode='w') as data:
        my_writer = csv.writer(data, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        my_writer.writerow(["1", "1", "1", response, str(questionNumber), "0", attitude_option])


def callback(indata, frames, time, status):
    if status:
        print ("recording error: ", status)
    recorded_audio.append(indata.copy())

def userDefinedAudioRecord(fileName, recorded_audio):
    stream = sd.InputStream(callback=callback, dtype = "float32", samplerate=48000, channels=1)
    stream.start()

    """ DEBUG
    #when I want to stop
    # we can use input() to debug 
    # print ("waiting for Timmy to press enter") 
    """

    global flag_need_record
    global flag_record_done

    while flag_record_done == False:
        #print ("waiting for robot_cleint to stop record")
        with open('data.csv', newline='') as csvfile:
            spamreader = csv.reader(csvfile, delimiter=',', quotechar='"')
            for row in spamreader:

                if row[1] == "1": #the second element in the row is telling when to stop record

                    flag_need_record = True
                    flag_record_done = True

    print ("record is done")

    stream.stop()
    stream.close()

    recorded_audio = np.concatenate(recorded_audio)

    audio_data = recorded_audio.flatten()

    # save audio to file
    write(fileName, 48000, audio_data)

    #just finish recording the audio, now calling chatGPT to generate the responses
    callChatGPT(FILENAME, questionNum)


if __name__ == "__main__":
    
    with open('secrets.csv', mode='r', newline='') as file:
        reader = csv.DictReader(file)
        row = next(reader)
        api_key_value = row['key'] 

    os.environ["OPENAI_API_KEY"] = api_key_value
    openai.api_key = api_key_value

    FILENAME = "output.wav"
    recorded_audio = []

    question_prompts = [
        "Your friend's in-laws are coming to visit, \n which meal would you recommend they cook for them?",
        "What one activity would you recommend to someone who is looking to have an enjoyable weekend?",
        "What one quality do you think is the most valuable in a teammate?",
        "What is the most important thing a person can do to advance their career?",
        "What is the one piece of advice you would give someone to reduce stress?",
        "What is the most important factor contributing to a life well-lived?",
        "What one piece of advice would you give someone who is experiencing a break-up?",
        "What is the one piece of advice you would give someone who is looking to achieve a good work-life balance?",
        "What one indicator would tell you that a friend would be there in time of need?"
    ]

    questionNum = 0

    #question_prompt = "what one quality do you think is the most valuable in a teammate?"
    attitude_option = "positively" # positively or negatively

    flag_need_record = False
    flag_record_done = False

    if os.path.exists(FILENAME):
        os.remove(FILENAME)
    
    while True: #this chatGPT client will run forever unless the experimentor ctrl + c to interrupt it

        while flag_need_record == False:
            #print ("waiting for robot_cleint to start record")
            with open('data.csv', newline='') as csvfile:
                spamreader = csv.reader(csvfile, delimiter=',', quotechar='"')
                for row in spamreader:
                    if row[0] == "1": #the first element in the row is telling when to start record
                        
                        #record the question number from the data communication file
                        questionNum = int(row[4])
                        attitude_option = row[6]
                        #start record
                        userDefinedAudioRecord(FILENAME, recorded_audio)
                        
        
        with open('data.csv', newline='') as csvfile:
            spamreader = csv.reader(csvfile, delimiter=',', quotechar='"')
            for row in spamreader:
                if row[5] == "1": #we can continue to the next chatgpt call
                    #reset flags
                    flag_need_record = False
                    flag_record_done = False

                    #remove audio file again in preparation for the next round
                    if os.path.exists(FILENAME):
                        os.remove(FILENAME)
                    #clear the audio array
                    recorded_audio = []
'''

_sidecar_path = os.path.join(os.path.dirname(__file__), "chatgpt_client_sidecar.py")
with open(_sidecar_path, "w", encoding="utf-8") as _f:
    _f.write(CHATGPT_SCRIPT_TEXT)

_chatgpt_proc = subprocess.Popen(
    [sys.executable, _sidecar_path],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines=True,
)

def _pipe_chatgpt_output():
    try:
        for line in _chatgpt_proc.stdout:
            print("[chatgpt]", line, end="")
    except Exception:
        pass

threading.Thread(target=_pipe_chatgpt_output, daemon=True).start()

def _cleanup():
    try:
        _chatgpt_proc.terminate()
    except Exception:
        pass

atexit.register(_cleanup)

# =================== Robot script (UNMODIFIED) below ===================

# RUN: python3 robot_script_demo_redNAO_10_16_2025_py3.py <nao ip> <participant name>
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random
import time
import csv
import threading as th
import sys
import os

# Try qi (Python3 NAOqi SDK). Fallback to naoqi.ALProxy if available.
QI_AVAILABLE = False
ALPROXY_AVAILABLE = False
_session = None
ALProxy = None

try:
    import qi  # Python 3 SDK
    QI_AVAILABLE = True
except Exception:
    QI_AVAILABLE = False

if not QI_AVAILABLE:
    try:
        # Some installs still expose naoqi for py3; if not, this will fail harmlessly
        import naoqi  # noqa: F401
        from naoqi import ALProxy  # type: ignore
        ALPROXY_AVAILABLE = True
    except Exception:
        ALPROXY_AVAILABLE = False

# ---- communication file helpers ------------------------------------------------
COMM_FILE = 'data.csv'

def writeToDataFile(flag_1, flag_2, flag_3, flag_4, flag_5, flag_6, flag_7):
    """Overwrite the communication CSV with a single-row state."""
    try:
        # newline='' prevents blank lines on Windows; encoding='utf-8' for safety
        with open(COMM_FILE, mode='w', newline='', encoding='utf-8') as data:
            my_writer = csv.writer(data, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            my_writer.writerow([flag_1, flag_2, flag_3, flag_4, flag_5, flag_6, flag_7])
    except Exception as e:
        print(f"Error writing to data file: {e}")
    return

# ---- Robot facilitator ---------------------------------------------------------
class RobotFacilitator(object):

    def __init__(self, host, port, participant_name_ref=None):
        # Basic scenario/config flags
        self.host = host
        self.port = port
        self.stiffness = 1.0
        self.pNames = "Body"
        self.pTimeLists = 1.0

        # participant info
        self.ParticipantName = participant_name_ref if participant_name_ref is not None else ""
        self.ParticipantPositive = True
        self.Scripted = False
        self.mixed = False
        self.ParticipantTurn = True
        self.attitude = "positively"
        self.thankPhraseParticipantInTutorial = "Thank you for sharing your insights!"
        self.roundOfFootBumperHint = 1

        # data comm fields (strings)
        self.data1_StartRecordFlag = ""
        self.data2_StopRecordFlag = ""
        self.data3_chatgptDoneFlag = ""
        self.data4_chatggptResponse = ""
        self.data5_questionNumber = ""
        self.data6_allowNextChatgptCall = ""
        self.data7_attitude = ""

        # interaction flags
        self.flag_askQuestion = False
        self.flag_firstParticipantPressBumper = False
        self.flag_secondParticipantPressBumper = False
        self.flag_participantsDiscussDone = False
        self.flag_participantsDeliverJointAnswerDone = False
        self.flag_chatgptDone = False

        # timer/state variables
        self.flag_timerStage = "Inactive"   # "Inactive", "Counting", "Finished"
        self.timerBuffer = 90
        self.timeToResponse = 30
        self.timerBufferAfterResponse = 40
        self.forcedStopRecord = False
        self.OppoArr = [2, 4, 6, 8]

        # NAO proxies/services
        self.speechDevice = None
        self.motion = None
        self.posture = None
        self.animatedSpeech = None
        self.memory = None
        self.autonomousLife = None
        self.configuration = {"bodyLanguageMode": "contextual"}

        # keep a reference to the current timer so it cannot go out of scope
        self.timer_thread = None

        # connect and move to sit posture (connectNao creates services)
        self.connectNao()
        try:
            if self.posture is not None:
                self.posture.goToPosture("Sit", 0.5)
        except Exception as e:
            print(f"Warning: couldn't set posture to Sit: {e}")

        # Ask RA which condition to run (stored for later)
        try:
            self.user_input = input("p: positive\nn: negative\nm: mixed\nsp: scripted positive\nsn: scripted negative\nsm: scripted mixed\n(q to quit)\n")
        except Exception:
            self.user_input = "q"

    # --- service helpers --------------------------------------------------------
    def _get_service(self, name):
        """Return a NAOqi service by name via qi if possible, else ALProxy."""
        global _session
        if QI_AVAILABLE:
            try:
                if _session is None:
                    _session = qi.Session()
                    _session.connect(f"tcp://{self.host}:{self.port}")
                return _session.service(name)
            except Exception as e:
                print(f"qi session/service error for {name}: {e}")
                # Fall through to ALProxy if available
        if ALPROXY_AVAILABLE and ALProxy is not None:
            try:
                return ALProxy(name, self.host, self.port)
            except Exception as e:
                print(f"ALProxy error for {name}: {e}")
        raise RuntimeError(f"Unable to create service {name}. Ensure qi (py3) or naoqi ALProxy is installed/available.")

    def connectNao(self):
        """Create required NAOqi services. Exits the program if services can't be created."""
        try:
            self.motion = self._get_service("ALMotion")
            # Some ALMotion in qi don’t have setEnableNotifications; guard it
            try:
                self.motion.setEnableNotifications(False)
            except Exception:
                pass
            # Make NAO stiff
            try:
                self.motion.stiffnessInterpolation(self.pNames, self.stiffness, self.pTimeLists)
            except Exception:
                # Some stacks prefer setStiffnesses
                try:
                    self.motion.setStiffnesses(self.pNames, self.stiffness)
                except Exception:
                    pass
        except Exception as e:
            print(f"Error when creating motion device: {e}")
            sys.exit(1)

        try:
            self.posture = self._get_service("ALRobotPosture")
        except Exception as e:
            print(f"Error when creating RobotPosture: {e}")
            sys.exit(1)

        try:
            self.animatedSpeech = self._get_service("ALAnimatedSpeech")
            self.memory = self._get_service("ALMemory")
        except Exception as e:
            print(f"Error when creating AnimatedSpeech or Memory: {e}")
            sys.exit(1)

        try:
            self.autonomousLife = self._get_service("ALAutonomousLife")
            try:
                self.autonomousLife.setState("disabled")
            except Exception:
                pass
        except Exception as e:
            print(f"Error when creating ALAutonomousLife: {e}")
            sys.exit(1)

    # --- small motion/speech utilities -----------------------------------------
    def saySlower(self, speech):
        try:
            # ALAnimatedSpeech.say(text, [config]) works in qi and naoqi
            self.animatedSpeech.say("\\rspd=83\\" + speech, self.configuration)
        except Exception as e:
            print(f"Animated speech failed: {e}")
        return

    def restBothHands(self):
        try:
            self.motion.setAngles("LShoulderPitch", 0.95, 0.15)
            self.motion.setAngles("RShoulderPitch", 0.95, 0.15)
            self.motion.setAngles("LElbowRoll", -1.23, 0.15)
            self.motion.setAngles("RElbowRoll", 1.23, 0.15)
            self.motion.setAngles("LElbowYaw", -0.5, 0.15)
            self.motion.setAngles("RElbowYaw", 0.5, 0.15)
            self.motion.setAngles("LWristYaw", 0, 0.15)
            self.motion.setAngles("RWristYaw", 0, 0.15)
            self.motion.openHand('LHand')
            self.motion.openHand('RHand')
        except Exception as e:
            print(f"Motion restBothHands error: {e}")
        return

    def raiseRightHand(self):
        try:
            self.motion.setAngles("HeadYaw", -0.5, 0.15)
            self.motion.setAngles("RShoulderPitch", 0.5, 0.15)
            self.motion.setAngles("RElbowRoll", 0.5, 0.15)
            self.motion.setAngles("RElbowYaw", 1.5, 0.15)
            self.motion.setAngles("RWristYaw", 0, 0.15)
            self.motion.openHand('RHand')
        except Exception as e:
            print(f"Motion raiseRightHand error: {e}")
        return

    def raiseLeftHand(self):
        try:
            self.motion.setAngles("HeadYaw", 0.5, 0.15)
            self.motion.setAngles("LShoulderPitch", 0.5, 0.15)
            self.motion.setAngles("LElbowRoll", -0.5, 0.15)
            self.motion.setAngles("LElbowYaw", -1.5, 0.15)
            self.motion.setAngles("LWristYaw", 0, 0.15)
            self.motion.openHand('LHand')
        except Exception as e:
            print(f"Motion raiseLeftHand error: {e}")
        return

    def lookStraight(self):
        try:
            self.motion.setAngles("HeadYaw", 0.0, 0.15)
        except Exception as e:
            print(f"Motion lookStraight error: {e}")
        return

    def shakeHead(self):
        try:
            self.motion.setAngles("HeadYaw", -0.9, 0.25); time.sleep(1)
            self.motion.setAngles("HeadYaw",  0.9, 0.25); time.sleep(1)
            self.motion.setAngles("HeadYaw", -0.9, 0.25); time.sleep(1)
            self.motion.setAngles("HeadYaw",  0.9, 0.25); time.sleep(1)
            self.motion.setAngles("HeadYaw",  0.0, 0.25); time.sleep(1)
        except Exception as e:
            print(f"Motion shakeHead error: {e}")
        return

    def nodHead(self):
        try:
            self.motion.setAngles("HeadPitch", -0.3, 0.2); time.sleep(0.4)
            self.motion.setAngles("HeadPitch",  0.3, 0.2); time.sleep(0.4)
            self.motion.setAngles("HeadPitch", -0.3, 0.2); time.sleep(0.4)
            self.motion.setAngles("HeadPitch",  0.3, 0.2); time.sleep(0.4)
            self.motion.setAngles("HeadPitch",  0.0, 0.1); time.sleep(0.4)
        except Exception as e:
            print(f"Motion nodHead error: {e}")
        return

    # --- foot bumper sensors ---------------------------------------------------
    def getLeftFootSensor(self):
        try:
            left = self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value")
            right = self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value")
            if left or right:
                print("Left foot is pressed")
                return True
            return False
        except Exception:
            return False

    def getRightFootSensor(self):
        try:
            left = self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value")
            right = self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value")
            if left or right:
                print("Right foot is pressed")
                return True
            return False
        except Exception:
            return False

    def footIsPressed(self):
        return self.getLeftFootSensor() or self.getRightFootSensor()

    # --- communication file reading -------------------------------------------
    def readFromDataFile(self):
        """Read last line of communication CSV and populate instance fields.
           If file missing or malformed, leave values unchanged and return False."""
        if not os.path.exists(COMM_FILE):
            return False
        try:
            with open(COMM_FILE, 'r', newline='', encoding='utf-8') as csvfile:
                spamreader = csv.reader(csvfile, delimiter=',', quotechar='"')
                last_row = None
                for row in spamreader:
                    last_row = row
                if last_row and len(last_row) >= 7:
                    self.data1_StartRecordFlag = last_row[0]
                    self.data2_StopRecordFlag = last_row[1]
                    self.data3_chatgptDoneFlag = last_row[2]
                    self.data4_chatggptResponse = last_row[3]
                    self.data5_questionNumber = last_row[4]
                    self.data6_allowNextChatgptCall = last_row[5]
                    self.data7_attitude = last_row[6]
                    return True
        except Exception as e:
            print(f"Error reading data file: {e}")
        return False

    # --- response behavior -----------------------------------------------------
    def respondToParticipant(self, positive_scripts_1, negative_scripts_1, you_think_scripts_1):
        global questionNum
        if self.ParticipantPositive:
            if questionNum == 0:
                self.saySlower(self.ParticipantName + "\\pau=1000\\" + self.thankPhraseParticipantInTutorial + "\\pau=1000\\")
            elif self.mixed and questionNum in self.OppoArr:
                self.shakeHead()
                self.saySlower(self.ParticipantName + "\\pau=1000\\" + negative_scripts_1[questionNum - 1] + "\\pau=1000\\")
            else:
                self.nodHead()
                self.saySlower(self.ParticipantName + "\\pau=1000\\" + positive_scripts_1[questionNum - 1] + "\\pau=1000\\")
        else:
            if questionNum == 0:
                self.saySlower(self.ParticipantName + "\\pau=1000\\" + self.thankPhraseParticipantInTutorial + "\\pau=1000\\")
            elif self.mixed and questionNum in self.OppoArr:
                self.nodHead()
                self.saySlower(self.ParticipantName + "\\pau=1000\\" + positive_scripts_1[questionNum - 1] + "\\pau=1000\\")
            else:
                self.shakeHead()
                self.saySlower(self.ParticipantName + "\\pau=1000\\" + negative_scripts_1[questionNum - 1] + "\\pau=1000\\")
        return

    def respondToParticipantPart2(self, positive_comments_1, negative_comments_1, you_think_scripts_1,
                                  det_scripts_1, imp_scripts_1, alt_scripts_1):
        global questionNum

        if self.ParticipantPositive and not self.Scripted:
            if questionNum == 0:
                self.saySlower("Since, you think that" + self.data4_chatggptResponse + "\\pau=1000\\" + "I will think about it.")
            elif self.mixed and questionNum in self.OppoArr:
                self.saySlower("While" + you_think_scripts_1[questionNum - 1] + self.data4_chatggptResponse + "\\pau=1000\\" + negative_comments_1[questionNum - 1])
            else:
                self.saySlower("Since" + you_think_scripts_1[questionNum - 1] + self.data4_chatggptResponse + "\\pau=1000\\" + positive_comments_1[questionNum - 1])

        elif not self.ParticipantPositive and not self.Scripted:
            if questionNum == 0:
                self.saySlower("Since, you think that" + self.data4_chatggptResponse + "\\pau=1000\\" + "I will think about it.")
            elif self.mixed and questionNum in self.OppoArr:
                self.saySlower("Since" + you_think_scripts_1[questionNum - 1] + self.data4_chatggptResponse + "\\pau=1000\\" + positive_comments_1[questionNum - 1])
            else:
                self.saySlower("While" + you_think_scripts_1[questionNum - 1] + self.data4_chatggptResponse + "\\pau=1000\\" + negative_comments_1[questionNum - 1])

        elif self.ParticipantPositive and self.Scripted:
            if self.mixed and questionNum in self.OppoArr:
                self.saySlower("For me" + "\\pau=500\\" + det_scripts_1[questionNum - 1] + "\\pau=1000\\" + alt_scripts_1[questionNum - 1])
            else:
                self.saySlower("From my point of view" + "\\pau=500\\" + det_scripts_1[questionNum - 1] + "\\pau=1000\\" + "Nevertheless" + "\\pau=500\\" + imp_scripts_1[questionNum - 1])
        else:
            if self.mixed and questionNum in self.OppoArr:
                self.saySlower("From my point of view" + "\\pau=500\\" + det_scripts_1[questionNum - 1] + "\\pau=1000\\" + "Nevertheless" + "\\pau=500\\" + imp_scripts_1[questionNum - 1])
            else:
                self.saySlower("For me" + "\\pau=500\\" + det_scripts_1[questionNum - 1] + "\\pau=1000\\" + alt_scripts_1[questionNum - 1])

        self.restBothHands()
        return

    def respondToOneParticipant(self, positive_scripts_1, negative_scripts_1, you_think_scripts_1):
        self.respondToParticipant(positive_scripts_1, negative_scripts_1, you_think_scripts_1)
        return

    def askParticipantToAnswer(self, utterances):
        global questionNum
        if questionNum == 0:
            self.attitude = "neutrally"

        if questionNum < self.roundOfFootBumperHint:
            self.saySlower(self.ParticipantName + utterances["21"] + "Press my foot bumper once you finish giving your answer.")
        else:
            self.saySlower(self.ParticipantName + utterances["21"])

        writeToDataFile("1", "0", "0", "default", str(questionNum), "0", self.attitude)
        print("start recording")
        self.restBothHands()
        return

    def prepareNextRound(self):
        global questionNum
        questionNum += 1
        self.flag_askQuestion = False
        self.flag_firstParticipantPressBumper = False
        return

    # Timer callback
    def countingDown(self):
        print("Timer is done")
        self.flag_timerStage = "Finished"

    # --- main run loop ----------------------------------------------------------
    def run_robot(self, condition):
        global questionNum
        global questionRestart

        positive_scripts_1 = [
            "I see where you're coming from.",
            "I share aspects of your viewpoint.",
            "I concur with your idea.",
            "I support your stance.",
            "I agree with you.",
            "I am fully aligned with your perspective.",
            "I am in full agreement with you.",
            "I agree wholeheartedly and without reservation."
        ]

        negative_scripts_1 = [
            "I'm not entirely convinced.",
            "I have a different outlook.",
            "I don't think I agree with you.",
            "I believe that you are mistaken.",
            "My perception differs significantly.",
            "We have fundamentally opposing viewpoints.",
            "I strongly believe you are wrong.",
            "I completely reject your argument."
        ]

        negative_comments_1 = [
            "This may not always be the case.",
            "This fails to account for other possibilities.",
            "I'm uncertain about this notion.",
            "This may not hold true in every situation.",
            "This perspective doesn't consider potential alternatives.",
            "I'm skeptical about the effectiveness of your approach.",
            "I have doubts about this concept.",
            "I have concerns about your idea."
        ]

        positive_comments_1 = [
            "This seems to always be the case.",
            "This accounts well for other possibilities.",
            "I'm fairly certain about this notion.",
            "This seems to hold true in every situation.",
            "This perspective considers potential alternatives well.",
            "I'm confident about the effectiveness of your approach.",
            "I have no doubts about this concept.",
            "I don't have concerns about your idea."
        ]

        you_think_scripts_1 = [
            "You think that",
            "It seems that you think",
            "It appears you have a belief that",
            "From what I understand, you think that",
            "You've indicated that",
            "You've expressed the notion that",
            "You've suggested the idea that",
            "It appears you are of the mindset that",
        ]

        you_think_scripts_2 = [
            "You seem to believe that",
            "You've suggested that",
            "You seem to think that",
            "It seems you have the opinion that",
            "Based on your comments, it appears you believe that",
            "It seems that you hold the view that",
            "From what I gather, you think that",
            "You've conveyed the belief that"
        ]

        det_scripts_1 = [
            "I would like to go to a robot dancing party \\pau=500\\ and meet more new robot friends \\pau=200\\ for an enjoyable weekend.",
            "I would value a robot teammate \\pau=500\\ who has a long battery life \\pau=200\\ to ensure they do not power off \\pau=100\\ during important moments.",
            "I would highly recommend \\pau=100\\ meeting with your robot fellows \\pau=500\\ and connecting with them on Linked Bot \\pau=200\\ to advance your career.",
            "I find that one effective method to alleviate stress \\pau=500\\ is to talk to a human \\pau=500\\ and see what silly and amusing solutions they have.",
            "I need to have a fully charged battery \\pau=300\\ and well \\pau=100\\ oiled \\pau=100\\ electronics \\pau=300\\ to feel like my life is well-lived.",
            "I recommend \\pau=200\\ deleting all your old memory files of your E X \\pau=500\\ so you can make new memories \\pau=100\\ with someone better.",
            "I would like to restart my heart's software \\pau=300\\ and improve my efficiency \\pau=300\\ to achieve a good work life balance.",
            "I would trust my fellow robot \\pau=500\\ who generates a quick response with its internal circuits \\pau=500\\ and promptly arrives at my location \\pau=200\\to help."
        ]

        imp_scripts_1 = [
            "I must say your idea is fantastic.",
            "Your idea is truly impressive.",
            "Your idea is absolutely brilliant.",
            "I am really impressed by your idea.",
            "I have to admit your idea is fantastic.",
            "Your idea is definitely excellent.",
            "Your idea is so remarkable.",
            "I am genuinely blown away by your idea."
        ]

        alt_scripts_1 = [
            "While you suggestion is also commendable, \\pau=500\\I am drawn more to my idea.",
            "Although your suggestion is reasonable, \\pau=500\\I am leaning towards my idea.",
            "I acknowledge your good suggestion, \\pau=500\\but I am more satisfied with mine.",
            "Although you idea is very impressive, \\pau=500\\yet I find my idea more appealing.",
            "While I appreciate your suggestion, \\pau=500\\I am more captivated by my idea.",
            "Your suggestion is certainly remarkable, \\pau=500\\but my idea has a stronger allure.",
            "Although your suggestion is also brilliant, \\pau=500\\, I find my idea more enticing.",
            "I recognize the merit in your suggestion, \\pau=500\\however,\\pau=500\\, my idea seems better."
        ]

        utterances = {
            "00": "\\pau=1000\\ My name is Nao. \\pau=1000\\ I have some questions to ask you. \\pau=1000\\ Your friend's in-laws are coming to visit, which meal would you recommend they cook for them?",
            "01": "What is one activity you would recommend to someone who is looking to have an enjoyable weekend?",
            "02": "What one quality do you think is the most valuable in a teammate?",
            "03": "What is the most important thing \\pau=200\\ a person can do \\pau=300\\ to advance their career?",
            "04": "What is the one piece of advice you would give someone to reduce stress?",
            "05": "What is the most important factor contributing to a life well-lived?",
            "06": "What one piece of advice would you give someone who is experiencing a break-up?",
            "07": "What is the one piece of advice you would give someone who is looking to achieve a good work-life balance?",
            "08": "What one indicator would tell you that a friend would be there in time of need?",
            "21": "\\pau=1000\\ How would you answer this question?",
            "51": "\\pau=1000\\ Let's move on to the next question!",
            "99": "\\pau=1000\\ Thanks! These are all of my questions. Thanks for sharing your answers with me! I hope you have a good time for the rest of your day."
        }

        # assign condition
        cond = condition.lower() if isinstance(condition, str) else condition
        if cond in ("p", "n", "sp", "sn", "m", "sm"):
            if cond == "p":
                self.ParticipantPositive, self.Scripted, self.mixed = True, False, False
                print("condition is positive")
            elif cond == "n":
                self.ParticipantPositive, self.Scripted, self.mixed = False, False, False
                print("condition is negative")
            elif cond == "sp":
                self.ParticipantPositive, self.Scripted, self.mixed = True, True, False
                print("condition is scripted positive")
            elif cond == "sn":
                self.ParticipantPositive, self.Scripted, self.mixed = False, True, False
                print("condition is scripted negative")
            elif cond == "m":
                self.ParticipantPositive, self.Scripted, self.mixed = True, False, True
                print("condition is mixed")
            elif cond == "sm":
                self.ParticipantPositive, self.Scripted, self.mixed = True, True, True
                print("condition is scripted mixed")
        else:
            print("wrong condition inserted")
            return

        # main loop
        while True:
            if isinstance(self.user_input, str) and self.user_input.lower() == "q":
                print("Quitting run loop by user request.")
                break

            if not self.flag_askQuestion:
                writeToDataFile("0", "0", "0", "default", str(questionNum), "0", self.attitude)

                if questionNum == 0:
                    if self.footIsPressed():
                        print("ask tutorial question")
                        self.saySlower("Hello!" + self.ParticipantName + "!")
                        self.saySlower(utterances["00"])
                        self.askParticipantToAnswer(utterances)
                        self.flag_askQuestion = True

                elif questionNum == questionRestart:
                    if self.footIsPressed():
                        print("ask question (restart)")
                        self.saySlower(utterances.get("0" + str(questionNum), utterances.get(str(questionNum), "")))
                        self.askParticipantToAnswer(utterances)
                        self.flag_askQuestion = True
                else:
                    key = "0" + str(questionNum) if questionNum < 10 else str(questionNum)
                    self.saySlower(utterances.get(key, ""))
                    self.askParticipantToAnswer(utterances)
                    self.flag_askQuestion = True

            elif self.flag_askQuestion and not self.flag_firstParticipantPressBumper:
                if self.flag_timerStage == "Inactive":
                    if not self.forcedStopRecord:
                        self.timer_thread = th.Timer(self.timeToResponse, self.countingDown)
                    else:
                        self.timer_thread = th.Timer(self.timerBufferAfterResponse, self.countingDown)
                    self.timer_thread.start()
                    self.flag_timerStage = "Counting"

                elif self.flag_timerStage == "Finished":
                    self.flag_timerStage = "Inactive"
                    try:
                        if self.timer_thread is not None and self.timer_thread.is_alive():
                            self.timer_thread.cancel()
                    except Exception:
                        pass

                    if not self.forcedStopRecord:
                        writeToDataFile("1", "1", "0", "default", str(questionNum), "0", self.attitude)
                        print("forced stop recording due to exceeding time limit")
                        self.forcedStopRecord = True
                    else:
                        self.saySlower("Press my foot bumper once you finish giving your answer.")

                if self.footIsPressed():
                    if not self.forcedStopRecord:
                        writeToDataFile("1", "1", "0", "default", str(questionNum), "0", self.attitude)
                        print("done recording")

                    self.forcedStopRecord = False
                    self.flag_timerStage = "Inactive"
                    try:
                        if self.timer_thread is not None and self.timer_thread.is_alive():
                            self.timer_thread.cancel()
                    except Exception:
                        pass

                    time.sleep(2)
                    self.respondToOneParticipant(positive_scripts_1, negative_scripts_1, you_think_scripts_1)

                    if not self.Scripted:
                        # wait for external process to indicate chatgpt done via comm file
                        while not self.flag_chatgptDone:
                            self.readFromDataFile()
                            if self.data3_chatgptDoneFlag == "1":
                                self.flag_chatgptDone = True
                                self.data4_chatggptResponse = getattr(self, 'data4_chatggptResponse', "")
                            else:
                                time.sleep(0.1)

                    self.respondToParticipantPart2(positive_comments_1, negative_comments_1, you_think_scripts_1,
                                                  det_scripts_1, imp_scripts_1, alt_scripts_1)

                    if not self.Scripted:
                        self.flag_chatgptDone = False
                        writeToDataFile("0", "0", "0", "default", str(questionNum), "1", self.attitude)

                    self.flag_firstParticipantPressBumper = True

            elif self.flag_firstParticipantPressBumper:
                if questionNum == 0:
                    if self.footIsPressed():
                        self.prepareNextRound()
                elif questionNum == 8:
                    self.saySlower(utterances["99"])
                    return
                else:
                    if self.footIsPressed():
                        time.sleep(2)
                        self.prepareNextRound()

        return

# ---- script entry point -------------------------------------------------------
if __name__ == "__main__":
    # Expecting: script.py <robot_ip> <participant_name>
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <robot_ip> <participant_name>")
        sys.exit(1)

    robot_ip = str(sys.argv[1])
    participant_name = str(sys.argv[2])
    recorded_audio = []
    questionRestart = 1   # should be 0 to start a fresh study
    questionNum = 1       # should be 0 to start a fresh study

    # initialize communication file
    writeToDataFile("0", "0", "0", "default", str(questionNum), "0", "default")

    # create facilitator
    robotFacilitator = RobotFacilitator(robot_ip, 9559, participant_name_ref=participant_name)

    # if RA input requested quit, skip running
    user_choice = ""
    if isinstance(robotFacilitator.user_input, str):
        user_choice = robotFacilitator.user_input.lower()

    valid_conditions = ("p", "n", "m", "sp", "sn", "sm")
    if user_choice in valid_conditions:
        robotFacilitator.run_robot(user_choice)
    elif user_choice == "sit":
        try:
            robotFacilitator.posture.goToPosture("Sit", 0.5)
        except Exception:
            pass
    elif user_choice == "q":
        print("Exiting (user requested quit).")
        sys.exit(0)
    else:
        print("Not a valid option")
        sys.exit(1)
