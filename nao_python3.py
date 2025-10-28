import os
import sys
import time
import threading as th
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from langchain_openai import ChatOpenAI
import openai
import csv

# ----------------- Require qi -----------------
try:
    import qi  # Python 3 NAOqi SDK
except ImportError:
    print("Error: The qi Python 3 SDK is not installed. Please install it to control the robot.")
    sys.exit(1)


# ----------------- Robot Facilitator -----------------
class RobotFacilitator(object):

    def __init__(self, host, port, participant_name_ref=None):
        self.host = host
        self.port = port
        self.ParticipantName = participant_name_ref or ""
        self.ParticipantPositive = True
        self.Scripted = False
        self.mixed = False
        self.attitude = "positively"
        self.timer_thread = None
        self.flag_timerStage = "Inactive"
        self.timerBuffer = 90
        self.timeToResponse = 30
        self.OppoArr = [2, 4, 6, 8]
        self.questionNum = 0

        # Load API key from secret.csv
        try:
            with open('secret.csv', mode='r', newline='') as file:
                reader = csv.DictReader(file)
                row = next(reader)
                api_key_value = row['api_key']
            os.environ["OPENAI_API_KEY"] = api_key_value
            openai.api_key = api_key_value
        except Exception:
            print("Error: Could not read secret.csv. Ensure it exists and has a 'api_key' column.")
            sys.exit(1)

        self.connectNao()
        try:
            self.posture.goToPosture("Sit", 0.5)
        except Exception:
            pass

        try:
            self.user_input = input("Condition (p/n/m/sp/sn/sm, q to quit): ")
        except Exception:
            self.user_input = "q"

    # ---------- connect to NAO ----------
    def _get_service(self, name):
        """Return a qi service or exit if not available."""
        try:
            if not hasattr(self, "_session") or self._session is None:
                self._session = qi.Session()
                self._session.connect(f"tcp://{self.host}:{self.port}")
            return self._session.service(name)
        except Exception as e:
            print(f"Error: Could not create service '{name}': {e}")
            sys.exit(1)

    def connectNao(self):
        """Create required NAOqi services and set safe posture."""
        try:
            self.motion = self._get_service("ALMotion")
            self.posture = self._get_service("ALRobotPosture")
            self.animatedSpeech = self._get_service("ALAnimatedSpeech")
            self.memory = self._get_service("ALMemory")
            self.autonomousLife = self._get_service("ALAutonomousLife")
            self.autonomousLife.setState("disabled")
        except Exception as e:
            print(f"Connection error: {e}")
            sys.exit(1)

    # ---------- robot motion / speech ----------
    def saySlower(self, text):
        try:
            self.animatedSpeech.say("\\rspd=83\\" + text, {"bodyLanguageMode": "contextual"})
        except Exception:
            print("saySlower fallback:", text)

    def nodHead(self):
        try:
            self.motion.setAngles("HeadPitch", -0.3, 0.2); time.sleep(0.4)
            self.motion.setAngles("HeadPitch",  0.3, 0.2); time.sleep(0.4)
            self.motion.setAngles("HeadPitch",  0.0, 0.1); time.sleep(0.4)
        except Exception:
            pass

    def shakeHead(self):
        try:
            self.motion.setAngles("HeadYaw", -0.9, 0.25); time.sleep(0.6)
            self.motion.setAngles("HeadYaw",  0.9, 0.25); time.sleep(0.6)
            self.motion.setAngles("HeadYaw",  0.0, 0.25); time.sleep(0.4)
        except Exception:
            pass

    def restBothHands(self):
        try:
            self.motion.openHand('LHand')
            self.motion.openHand('RHand')
        except Exception:
            pass

    def getLeftFootSensor(self):
        try:
            l1 = self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value")
            l2 = self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value")
            return l1 or l2
        except Exception:
            return False

    def getRightFootSensor(self):
        try:
            r1 = self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value")
            r2 = self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value")
            return r1 or r2
        except Exception:
            return False

    def footIsPressed(self):
        return self.getLeftFootSensor() or self.getRightFootSensor()

    # ---------- Recording ----------
    def record_audio(self, file_name):
        print("Recording...")
        recorded_audio = []
        stream = sd.InputStream(
            samplerate=48000, channels=1, dtype='float32',
            callback=lambda indata, frames, t, status: recorded_audio.append(indata.copy())
        )
        stream.start()
        while not self.footIsPressed():
            time.sleep(0.1)
        stream.stop()
        stream.close()
        audio_data = np.concatenate(recorded_audio).flatten()
        write(file_name, 48000, audio_data)
        print("Recording stopped.")
        return file_name

    # ---------- ChatGPT Integration ----------
    def call_chatgpt(self, file_name, question_number, attitude_option="positively"):
        # Step 1. Transcribe
        with open(file_name, "rb") as f:
            transcript = openai.audio.transcriptions.create(model="whisper-1", file=f)
        user_text = transcript.text.strip()
        print(f"You said: {user_text}")

        # Step 2. Generate ChatGPT response
        question_prompts = [
            "Your friend's in-laws are coming to visit, which meal would you recommend they cook for them?",
            "What one activity would you recommend to someone who is looking to have an enjoyable weekend?",
            "What one quality do you think is the most valuable in a teammate?",
            "What is the most important thing a person can do to advance their career?",
            "What is the one piece of advice you would give someone to reduce stress?",
            "What is the most important factor contributing to a life well-lived?",
            "What one piece of advice would you give someone who is experiencing a break-up?",
            "What is the one piece of advice you would give someone who is looking to achieve a good work-life balance?",
            "What one indicator would tell you that a friend would be there in time of need?"
        ]
        prompt_text = (
            f"I asked someone the question: {question_prompts[question_number]} "
            f"They responded: {user_text}. "
            "In English, reword their response in one sentence, replacing all 'I' with 'you'."
        )

        llm = ChatOpenAI(temperature=0.9)
        response = llm.invoke(prompt_text).content.strip()
        print(f"NAO: {response}")
        return response

    # ---------- Main interaction ----------
    def run_robot(self, condition):
        self.assign_condition(condition)

        utterances = {
            "00": "\\pau=1000\\ My name is Nao. \\pau=1000\\ "
                  "I have some questions to ask you. "
                  "Your friend's in-laws are coming to visit, which meal would you recommend they cook for them?",
            "01": "What is one activity you would recommend to someone who is looking to have an enjoyable weekend?",
            "02": "What one quality do you think is the most valuable in a teammate?",
            "03": "What is the most important thing a person can do to advance their career?",
            "04": "What is the one piece of advice you would give someone to reduce stress?",
            "05": "What is the most important factor contributing to a life well-lived?",
            "06": "What one piece of advice would you give someone who is experiencing a break-up?",
            "07": "What is the one piece of advice you would give someone who is looking to achieve a good work-life balance?",
            "08": "What one indicator would tell you that a friend would be there in time of need?",
            "21": "\\pau=1000\\ How would you answer this question?",
            "99": "\\pau=1000\\ Thanks! These are all of my questions."
        }

        questionNum = 0
        while True:
            if self.user_input.lower() == "q":
                print("Quit requested.")
                break

            key = "0" + str(questionNum) if questionNum < 10 else str(questionNum)
            question_text = utterances.get(key, "")
            self.saySlower(question_text)
            self.saySlower(self.ParticipantName + utterances["21"])

            # Record user speech
            audio_file = self.record_audio("output.wav")

            # ChatGPT generates reply
            chatgpt_response = self.call_chatgpt(audio_file, questionNum, self.attitude)

            # Robot speaks
            self.saySlower("Since you think that " + chatgpt_response)
            self.nodHead()

            questionNum += 1
            if questionNum >= 9:
                self.saySlower(utterances["99"])
                break

    def assign_condition(self, cond):
        cond = cond.lower()
        if cond == "p":
            self.ParticipantPositive, self.Scripted, self.mixed = True, False, False
        elif cond == "n":
            self.ParticipantPositive, self.Scripted, self.mixed = False, False, False
        elif cond == "sp":
            self.ParticipantPositive, self.Scripted, self.mixed = True, True, False
        elif cond == "sn":
            self.ParticipantPositive, self.Scripted, self.mixed = False, True, False
        elif cond == "m":
            self.ParticipantPositive, self.Scripted, self.mixed = True, False, True
        elif cond == "sm":
            self.ParticipantPositive, self.Scripted, self.mixed = True, True, True
        else:
            print("Invalid condition; defaulting to positive.")
            self.ParticipantPositive = True


# ----------------- Entry point -----------------
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <robot_ip> <participant_name>")
        sys.exit(1)

    robot_ip = sys.argv[1]
    participant_name = sys.argv[2]

    robot = RobotFacilitator(robot_ip, 9559, participant_name_ref=participant_name)

    valid_conditions = ("p", "n", "m", "sp", "sn", "sm")
    user_choice = robot.user_input.lower()

    if user_choice in valid_conditions:
        robot.run_robot(user_choice)
    elif user_choice == "sit":
        robot.posture.goToPosture("Sit", 0.5)
    elif user_choice == "q":
        print("Exiting.")
        sys.exit(0)
    else:
        print("Invalid option.")
        sys.exit(1)
