#!/usr/bin/env python3

import argparse
import json
import queue
import os
import openai
import datetime
import time
import sys
import pyttsx3
import sounddevice as sd
from vosk import Model, KaldiRecognizer, SetLogLevel
from roku import Roku

# Initialize the text-to-speech engine
engine = pyttsx3.init()
global answer
global aiAnswer

conversation_history = "conversation_log.txt"
if not os.path.exists(conversation_history):
    open(conversation_history, "w").close()  # Create an empty file if it doesn't exist

is_speaking = False

# OPENAI key
openai.api_key = "OPENAI_KEY"

# Remove waste text
SetLogLevel(-1)

# Creating the Roku Device
roku = Roku('')

q = queue.Queue()


# Define function to log messages to file
def log_message(message):
    with open(conversation_history, "a") as f:
        f.write(message + "\n")


def talking(aiAnswer):
    global is_speaking
    is_speaking = True
    engine.say(aiAnswer)
    engine.runAndWait()
    is_speaking = False
    # Log the conversation in a text file


# Adding instructions to responses
def commands(answer):
    if len(answer) != 0:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": answer}
            ],
            temperature=0.9,
            max_tokens=2000,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0.6,
        )

        aiAnswer = response["choices"][0]["message"]["content"]
        print(aiAnswer)

        if len(aiAnswer) > 300:
            user_preference = input("The answer is too long. Do you want the long answer (L) or the short answer (S)? ").upper()
            
            if user_preference == "S":
                # Process again with a prompt for a summarized answer
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": f"This answer is too long. Give me a summarized answer in under 300 characters:\n{answer}"}
                    ],
                    temperature=0.9,
                    max_tokens=300,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0.6,
                )
                aiAnswer = response["choices"][0]["message"]["content"]
                print(aiAnswer)
            else:
                print("You chose the long answer.")

        log_message(f"Human: {answer}")
        log_message(f"AI: {aiAnswer}")
        talking(aiAnswer)
    else:
        print("This is empty")


def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text


def callback(indata, frames, time, status):
    """This is called (from a separate thread) for each audio block."""
    global is_speaking
    if is_speaking:
        return
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))


parser = argparse.ArgumentParser(add_help=False)
parser.add_argument(
    "-l", "--list-devices", action="store_true",
    help="show list of audio devices and exit")
args, remaining = parser.parse_known_args()
if args.list_devices:
    print(sd.query_devices())
    parser.exit(0)
parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    parents=[parser])
parser.add_argument(
    "-f", "--filename", type=str, metavar="FILENAME",
    help="audio file to store recording to")
parser.add_argument(
    "-d", "--device", type=int_or_str,
    help="input device (numeric ID or substring)")
parser.add_argument(
    "-r", "--samplerate", type=int, help="sampling rate")
parser.add_argument(
    "-m", "--model", type=str, help="language model; e.g. en-us, fr, nl; default is en-us")
args = parser.parse_args(remaining)

try:
    if args.samplerate is None:
        device_info = sd.query_devices(args.device, "input")
        # soundfile expects an int, sounddevice provides a float:
        args.samplerate = int(device_info["default_samplerate"])

    if args.model is None:
        model = Model(lang="en-us")
    else:
        model = Model(lang=args.model)

    if args.filename:
        dump_fn = open(args.filename, "wb")
    else:
        dump_fn = None

    with sd.RawInputStream(samplerate=args.samplerate, blocksize=8000, device=args.device,
                           dtype="int16", channels=1, callback=callback):
        rec = KaldiRecognizer(model, args.samplerate)
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                res = json.loads(rec.Result())
                answer = res['text']
                print(answer)
                with open("conversation_log.txt", "r") as f:
                    conversation_log = f.read()
                    print(conversation_log)
                commands(answer)

            else:
                continue
            if dump_fn is not None:
                continue

except KeyboardInterrupt:
    print("\nDone")
    parser.exit(0)
except Exception as e:
    parser.exit(type(e).__name__ + ": " + str(e))
