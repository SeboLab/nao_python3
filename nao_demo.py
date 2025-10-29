import os
import sys
import time
import csv
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from langchain_openai import ChatOpenAI
import openai
import threading
from enum import Enum, auto

# ---------- Require qi ----------
try:
    import qi
except ImportError:
    print("Error: The qi Python 3 SDK is required. Please install it before running this script.")
    sys.exit(1)

# ---------- Mode Enum ----------
class Mode(Enum):
    POSITIVE = auto()       # p: nodding + agree, with GPT
    NEGATIVE = auto()       # n: shaking + disagree, with GPT
    MIXED = auto()          # m: alternating nod+agree/shake+disagree, with GPT
    SCRIPTED_POS = auto()   # sp: nodding + agree, no GPT
    SCRIPTED_NEG = auto()   # sn: nodding + disagree, no GPT
    SCRIPTED_MIX = auto()   # sm: alternating nod+agree/shake+disagree, no GPT


# ---------- Robot Facilitator ----------
class RobotFacilitator(object):

    def __init__(self, host, port, participant_name_ref=None):
        self.host = host
        self.port = port
        self.ParticipantName = participant_name_ref if participant_name_ref else ""
        self.mode = Mode.POSITIVE
        self.attitude = "positive"

        # --- Connect to robot ---
        self.connectNao()
        try:
            self.posture.goToPosture("Sit", 0.5)
        except Exception:
            pass

        # --- OpenAI setup ---
        try:
            with open('secret.csv', mode='r', newline='') as f:
                reader = csv.DictReader(f)
                api_key_value = next(reader)['api_key']
            os.environ["OPENAI_API_KEY"] = api_key_value
            openai.api_key = api_key_value
        except Exception:
            print("Error: could not load OpenAI key from secret.csv (must have column 'api_key').")
            sys.exit(1)

        try:
            user_in = input("Condition (p/n/m/sp/sn/sm, q to quit): ").strip().lower()
        except Exception:
            user_in = "q"

        if user_in == "q":
            print("Exit requested.")
            sys.exit(0)
        self.set_mode(user_in)

    # ---------- Mode Setup ----------
    def set_mode(self, cond):
        mode_map = {
            "p": Mode.POSITIVE,
            "n": Mode.NEGATIVE,
            "m": Mode.MIXED,
            "sp": Mode.SCRIPTED_POS,
            "sn": Mode.SCRIPTED_NEG,
            "sm": Mode.SCRIPTED_MIX,
        }
        self.mode = mode_map.get(cond, Mode.POSITIVE)
        print(f"Mode set to {self.mode.name}")

    # ---------- NAO service setup ----------
    def _get_service(self, name):
        try:
            if not hasattr(self, "_session"):
                self._session = qi.Session()
                self._session.connect(f"tcp://{self.host}:{self.port}")
            return self._session.service(name)
        except Exception as e:
            print(f"Error creating {name}: {e}")
            sys.exit(1)

    def connectNao(self):
        self.motion = self._get_service("ALMotion")
        self.posture = self._get_service("ALRobotPosture")
        self.animatedSpeech = self._get_service("ALAnimatedSpeech")
        self.memory = self._get_service("ALMemory")
        self.autonomousLife = self._get_service("ALAutonomousLife")
        try:
            self.autonomousLife.setState("disabled")
        except Exception:
            pass

    # ---------- Gestures and speech ----------
    def saySlower(self, text):
        try:
            self.animatedSpeech.say("\\rspd=83\\" + text, {"bodyLanguageMode": "contextual"})
        except Exception:
            print(text)

    def nodHead(self):
        try:
            self.motion.setAngles("HeadPitch", -0.3, 0.2); time.sleep(0.4)
            self.motion.setAngles("HeadPitch",  0.3, 0.2); time.sleep(0.4)
            self.motion.setAngles("HeadPitch", -0.3, 0.2); time.sleep(0.4)
            self.motion.setAngles("HeadPitch",  0.3, 0.2); time.sleep(0.4)
            self.motion.setAngles("HeadPitch",  0.0, 0.1); time.sleep(0.4)
        except Exception as e:
            print(f"nodHead error: {e}")

    def shakeHead(self):
        try:
            self.motion.setAngles("HeadYaw", -0.9, 0.25); time.sleep(1)
            self.motion.setAngles("HeadYaw",  0.9, 0.25); time.sleep(1)
            self.motion.setAngles("HeadYaw", -0.9, 0.25); time.sleep(1)
            self.motion.setAngles("HeadYaw",  0.9, 0.25); time.sleep(1)
            self.motion.setAngles("HeadYaw",  0.0, 0.25); time.sleep(1)
        except Exception as e:
            print(f"shakeHead error: {e}")

    def restHands(self):
        """Return both arms to a relaxed position similar to Sit posture."""
        try:
            self.motion.setAngles("LShoulderPitch", 0.95, 0.15)
            self.motion.setAngles("RShoulderPitch", 0.95, 0.15)
            self.motion.setAngles("LElbowRoll", -1.23, 0.15)
            self.motion.setAngles("RElbowRoll",  1.23, 0.15)
            self.motion.setAngles("LElbowYaw",  -0.5, 0.15)
            self.motion.setAngles("RElbowYaw",   0.5, 0.15)
            self.motion.setAngles("LWristYaw",   0.0, 0.15)
            self.motion.setAngles("RWristYaw",   0.0, 0.15)
            self.motion.openHand('LHand')
            self.motion.openHand('RHand')
        except Exception as e:
            print(f"restHands error: {e}")

    def footIsPressed(self):
        try:
            l1 = self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Left/Sensor/Value")
            l2 = self.memory.getData("Device/SubDeviceList/LFoot/Bumper/Right/Sensor/Value")
            r1 = self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Left/Sensor/Value")
            r2 = self.memory.getData("Device/SubDeviceList/RFoot/Bumper/Right/Sensor/Value")
            return any([l1, l2, r1, r2])
        except Exception:
            return False

    # ---------- Helpers derived from mode ----------
    def uses_gpt(self):
        return self.mode in (Mode.POSITIVE, Mode.NEGATIVE, Mode.MIXED)

    def gesture_for(self, idx):
        if self.mode in (Mode.POSITIVE, Mode.SCRIPTED_POS):
            return "nod"
        elif self.mode in (Mode.NEGATIVE, Mode.SCRIPTED_NEG):
            return "shake"
        elif self.mode in (Mode.MIXED, Mode.SCRIPTED_MIX):
            return "nod" if idx % 2 == 0 else "shake"
        return "nod"

    def stance_for(self, idx):
        if self.mode in (Mode.POSITIVE, Mode.SCRIPTED_POS):
            return "positive"
        elif self.mode in (Mode.NEGATIVE, Mode.SCRIPTED_NEG):
            return "negative"
        elif self.mode in (Mode.MIXED, Mode.SCRIPTED_MIX):
            return "positive" if idx % 2 == 0 else "negative"
        return "positive"

    # ---------- Audio recording ----------
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
        stream.stop(); stream.close()
        audio_data = np.concatenate(recorded_audio).flatten()
        write(file_name, 48000, audio_data)
        print("Recording stopped.")
        return file_name

    # ---------- ChatGPT and Whisper ----------
    def call_chatgpt(self, file_name, question_text):
        with open(file_name, "rb") as f:
            transcript = openai.audio.transcriptions.create(model="whisper-1", file=f)
        user_text = transcript.text.strip()
        print(f"[User said]: {user_text}")

        prompt_text = (
            f"I asked someone the question: {question_text} "
            f"They responded: {user_text}. "
            "In English, reword their response in one sentence, replacing all instances of 'I' with 'you'."
        )
        llm = ChatOpenAI(model="gpt-4o", temperature=0.9)
        response = llm.invoke(prompt_text).content.strip()
        print(f"[ChatGPT]: {response}")
        return response

    # ---------- Core experiment ----------
    def run_robot(self):
        questions = [
            "What is one activity you would recommend to someone who is looking to have an enjoyable weekend?",
            "What one quality do you think is the most valuable in a teammate?",
            "What is the most important thing a person can do to advance their career?",
            "What is the one piece of advice you would give someone to reduce stress?",
            "What is the most important factor contributing to a life well-lived?",
            "What one piece of advice would you give someone who is experiencing a break-up?",
            "What is the one piece of advice you would give someone who is looking to achieve a good work-life balance?",
            "What one indicator would tell you that a friend would be there in time of need?"
        ]

        positive_scripts = [
            "I see where you're coming from.",
            "I share aspects of your viewpoint.",
            "I concur with your idea.",
            "I support your stance.",
            "I agree with you.",
            "I am fully aligned with your perspective.",
            "I am in full agreement with you.",
            "I agree wholeheartedly and without reservation."
        ]

        positive_comments = [
            "This seems to always be the case.",
            "This accounts well for other possibilities.",
            "I'm fairly certain about this notion.",
            "This seems to hold true in every situation.",
            "This perspective considers potential alternatives well.",
            "I'm confident about the effectiveness of your approach.",
            "I have no doubts about this concept.",
            "I don't have concerns about your idea."
        ]

        negative_scripts = [
            "I'm not entirely convinced.",
            "I have a different outlook.",
            "I don't think I agree with you.",
            "I believe that you are mistaken.",
            "My perception differs significantly.",
            "We have fundamentally opposing viewpoints.",
            "I strongly believe you are wrong.",
            "I completely reject your argument."
        ]

        negative_comments = [
            "This may not always be the case.",
            "This fails to account for other possibilities.",
            "I'm uncertain about this notion.",
            "This may not hold true in every situation.",
            "This perspective doesn't consider potential alternatives.",
            "I'm skeptical about the effectiveness of your approach.",
            "I have doubts about this concept.",
            "I have concerns about your idea."
        ]

        scripted_answers = [
            "I would like to go to a robot dancing party \\pau=500\\ and meet more new robot friends \\pau=200\\ for an enjoyable weekend.",
            "I would value a robot teammate \\pau=500\\ who has a long battery life \\pau=200\\ to ensure they do not power off \\pau=100\\ during important moments.",
            "I would highly recommend \\pau=100\\ meeting with your robot fellows \\pau=500\\ and connecting with them on Linked Bot \\pau=200\\ to advance your career.",
            "I find that one effective method to alleviate stress \\pau=500\\ is to talk to a human \\pau=500\\ and see what silly and amusing solutions they have.",
            "I need to have a fully charged battery \\pau=300\\ and well \\pau=100\\ oiled \\pau=100\\ electronics \\pau=300\\ to feel like my life is well-lived.",
            "I recommend \\pau=200\\ deleting all your old memory files of your E X \\pau=500\\ so you can make new memories \\pau=100\\ with someone better.",
            "I would like to restart my heart's software \\pau=300\\ and improve my efficiency \\pau=300\\ to achieve a good work life balance.",
            "I would trust my fellow robot \\pau=500\\ who generates a quick response with its internal circuits \\pau=500\\ and promptly arrives at my location \\pau=200\\to help."
        ]

        scripted_positive_comments = [
            "I must say your idea is fantastic.",
            "Your idea is truly impressive.",
            "Your idea is absolutely brilliant.",
            "I am really impressed by your idea.",
            "I have to admit your idea is fantastic.",
            "Your idea is definitely excellent.",
            "Your idea is so remarkable.",
            "I am genuinely blown away by your idea."
        ]

        scripted_negative_comments = [
            "While you suggestion is also commendable, \\pau=500\\I am drawn more to my idea.",
            "Although your suggestion is reasonable, \\pau=500\\I am leaning towards my idea.",
            "I acknowledge your good suggestion, \\pau=500\\but I am more satisfied with mine.",
            "Although you idea is very impressive, \\pau=500\\yet I find my idea more appealing.",
            "While I appreciate your suggestion, \\pau=500\\I am more captivated by my idea.",
            "Your suggestion is certainly remarkable, \\pau=500\\but my idea has a stronger allure.",
            "Although your suggestion is also brilliant, \\pau=500\\, I find my idea more enticing.",
            "I recognize the merit in your suggestion, \\pau=500\\however,\\pau=500\\, my idea seems better."
        ]


        self.saySlower(f"\\pau=1000\\ Hi {self.ParticipantName}! \\pau=1000\\ My name is Nao. \\pau=1000\\ I have some questions to ask you. \\pau=1000\\")

        for idx, q in enumerate(questions):
            gesture = self.gesture_for(idx)
            stance = self.stance_for(idx)
            use_gpt = self.uses_gpt()

            self.saySlower(q)
            self.saySlower(self.ParticipantName + "\\pau=1000\\ How would you answer this question?")
            audio_file = self.record_audio("output.wav")

            chatgpt_result = {"text": ""}
            if use_gpt:
                def bg():
                    chatgpt_result["text"] = self.call_chatgpt(audio_file, q)
                t = threading.Thread(target=bg)
                t.start()
            else:
                t = None

            # FIRST HALF
            if gesture == "nod":
                self.nodHead()
            else:
                self.shakeHead()

            if stance == "positive":
                self.saySlower(self.ParticipantName + f"\\pau=1000\\ {positive_scripts[idx]} \\pau=1000\\")
            else:
                self.saySlower(self.ParticipantName + f"\\pau=1000\\ {negative_scripts[idx]} \\pau=1000\\")

            if t:
                t.join()

            # SECOND HALF
            if use_gpt:
                resp = chatgpt_result["text"]
                if stance == "positive":
                    self.saySlower("Since you think that " + resp + f"\\pau=1000\\ {positive_comments[idx]}")
                else:
                    self.saySlower("While you think that " + resp + f"\\pau=1000\\ {negative_comments[idx]}")
            else:
                if stance == "positive":
                    self.saySlower(f"{scripted_answers[idx]} \\pau=1000\\ {scripted_positive_comments[idx]}")

                else:
                    self.saySlower(f"{scripted_answers[idx]} \\pau=1000\\ {scripted_negative_comments[idx]}")

            #Rest hands before next question
            self.restHands()

            # Next question trigger
            print("Press NAO's foot bumper when you are ready for the next question.")
            while not self.footIsPressed():
                time.sleep(0.1)

        # Outro
        self.saySlower("\\pau=1000\\ Thanks! These are all of my questions. Thank you for sharing!")
        self.restHands()


# ---------- Entry Point ----------
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <robot_ip> <participant_name>")
        sys.exit(1)

    robot_ip = sys.argv[1]
    participant_name = sys.argv[2]

    robot = RobotFacilitator(robot_ip, 9559, participant_name_ref=participant_name)
    robot.run_robot()
