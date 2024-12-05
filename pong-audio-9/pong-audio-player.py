"""
    # PONG PLAYER EXAMPLE

    HOW TO CONNECT TO HOST AS PLAYER 1
    > python pong-audio-player.py p1 --host_ip HOST_IP --host_port 5005 --player_ip YOUR_IP --player_port 5007

    HOW TO CONNECT TO HOST AS PLAYER 2
    > python pong-audio-player.py p2 --host_ip HOST_IP --host_port 5006 --player_ip YOUR_IP --player_port 5008

    about IP and ports: 127.0.0.1 means your own computer, change it to play across computer under the same network. port numbers are picked to avoid conflits.

    DEBUGGING:
    
    You can use keyboards to send command, such as "g 1" to start the game, see the end of this file

"""
#native imports
import time
from playsound import playsound
import subprocess
import argparse
import atexit
import os

from pythonosc import osc_server
from pythonosc import dispatcher
from pythonosc import udp_client
from pydub import AudioSegment
from pydub.playback import play
import pygame

from queue import Queue
# threading so that listenting to speech would not block the whole program
import threading
# speech recognition (default using google, requiring internet)
import speech_recognition as sr
from vosk import Model, KaldiRecognizer
# pitch & volume detection
import aubio
import numpy as num
import pyaudio
import wave
import json

# Global variables
mode = ''
player1_ready = False
player2_ready = False
debug = False
quit = False
is_game_running = False
paddle_position = 200
host_ip = "127.0.0.1"
host_port_1 = 5005 # you are player 1 if you talk to this port
host_port_2 = 5006
player_1_ip = "127.0.0.1"
player_2_ip = "127.0.0.1"
player_1_port = 5007
player_2_port = 5008
player_ip = "127.0.0.1"
player_port = 0
host_port = 0
game_state_lock = threading.Lock()
quit_event = threading.Event()
last_speech_time = 0
difficulty = ""
intro_phrases = [
    "welcome these are commands you will use to play the game",
    "say start to start playing",
    "pause to pause the game",
    "up to move the paddle up",
    "down to move the paddle down",
    "set the difficulty by saying either easy hard or insane",
    "whenever you are ready say hi"
]


pygame.mixer.init()

sound_queue = Queue()
def sound_worker():
    while True:
        try:
            # Get the sound from the queue
            data = sound_queue.get()
            if data is None:  # Stop signal
                break
            sound = data[0]
            play(sound)
        except Exception as e:
            print(f"Error in sound_worker: {e}")

# Start the worker thread
sound_thread = threading.Thread(target=sound_worker, daemon=True)
sound_thread.start()

def handle_command(command):
    global paddle_position, player1_ready, player2_ready, mode, difficulty
    print(f"Command received: {command}")

    if command == "":
        return
    
    if any(phrase in command for phrase in intro_phrases):
        print("Ignored introductory speech.")
        return

    try: 
        # Game commands
        if command == "start":
            send_message_with_log("/setgame", 1)
            set_game_state(True)
            print("Game started explicitly by user after both players said hi.")
            speak_text("Game started")
        elif "pause" in command:
            send_message_with_log("/setgame", 0)
            speak_text("The game is paused")
            print("the game has paused")
            set_game_state(False)
        elif "hi" in command:
            if mode == "p1":
                player1_ready = True
                print("> Player 1 is ready!")
                speak_text("player 1 is ready")
            elif mode == "p2":
                player2_ready = True
                print("> Player 2 is ready!")
                speak_text("player 2 is ready")
            else:
                print("> Unknown player mode or configuration error.")

            send_message_with_log("/hi", player_ip)

            # Check if both players are ready
            if player1_ready and player2_ready: #change
                print("> Both players are ready. Starting the game!")
                speak_text("Both players are ready. Starting the game!")
                send_message_with_log("/setgame", 1)
                set_game_state(True)
        elif "stop" in command:
            global quit
            set_game_state(False)
            quit = True
            speak_text("Stopping the game.")

        # Paddle movement commands
        elif "up" in command:
            paddle_position = max(0, paddle_position - 10)  
            send_message_with_log("/setpaddle", paddle_position)
        elif "down" in command:
            paddle_position = min(450, paddle_position + 10)
            send_message_with_log("/setpaddle", paddle_position)

        # Difficulty settings
        elif "easy" in command:
            difficulty = "easy"
            send_message_with_log("/setlevel", 1)
            speak_text("Difficulty set to Easy.")
        elif "hard" in command:
            difficulty = "hard"
            send_message_with_log("/setlevel", 2)
            speak_text("Difficulty set to Hard.")
        elif "insane" in command:
            difficulty = "insane"
            send_message_with_log("/setlevel", 3)
            speak_text("Difficulty set to Insane.")
        elif "difficulty" in command:
            speak_text(f"Difficulty set to {difficulty}.")

        # Activate powerup
        elif "powerup" in command or "big paddle" in command:
            send_message_with_log("/setbigpaddle", 0)
        else:
            print(f"Command not recognized")
    except Exception as e:
        print(f"Error handling command: {e}")

def listen_to_speech():
    try:
        model_path = "model/vosk-model-small-en-us-0.15"
        model = Model(model_path)
        recognizer = KaldiRecognizer(model, 16000)
        input_device_index = pyaudio.PyAudio().get_default_input_device_info()['index']
        audio_stream = pyaudio.PyAudio().open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            input_device_index=input_device_index,
            frames_per_buffer=8000
        )
        audio_stream.start_stream()

        while not quit_event.is_set():
            data = audio_stream.read(4000, exception_on_overflow=False)
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                print(f"Vosk result: {result}")  # Debug recognized text
                if "text" in result and result["text"]:
                    handle_command(result["text"])
                else:
                    print("No valid text recognized.")
    except Exception as e:
        print(f"Speech recognition error: {e}")
    finally:
        if audio_stream:
            audio_stream.stop_stream()
            audio_stream.close()

# Start a thread to listen to speech
speech_recognition_thread = threading.Thread(target=listen_to_speech, args=())
speech_recognition_thread.daemon = True
speech_recognition_thread.start()
print("Speech recognition thread started.") 

try:
    loaded_sounds = {
        "boing.wav": pygame.mixer.Sound("boing.wav"),
        "metal-hit.wav": pygame.mixer.Sound("metal-hit.wav"),
        "powerup.wav": pygame.mixer.Sound("powerup.wav")
    }

except FileNotFoundError as e:
    print(f"Sound file not found: {e}")
except Exception as e:
    print(f"Error loading sound files: {e}")

def play_adjusted_sound(file, volume_change=0):
    if file in loaded_sounds:
        sound = loaded_sounds[file]
        sound.set_volume(1.0 + (volume_change / 100.0))  # Adjust volume (0.0 to 1.0)
        sound.play()
        print(f"Playing sound: {file}, volume_change: {volume_change}")
    else:
        print(f"Sound file not loaded: {file}")
 
def set_game_state(new_state):
    global is_game_running
    with game_state_lock:
        is_game_running = new_state

def get_game_state():
    with game_state_lock:
        return is_game_running

# Function to handle speech
def speak_text(text):
    """Thread-safe TTS invocation using the macOS 'say' command."""
    try:
        print(f"TTS: {text}")  # Debug log
        subprocess.run(['say', text])
    except Exception as e:
        print(f"TTS Error: {e}")

subprocess.run(['say', 'Welcome. These are commands you will use to play the game. Say start to start playing, pause to pause the game, up to move the paddle up and down to move the paddle down. When on the menu screen, set the difficulty by saying either, easy, hard or insane. To check your difficulty, say difficulty in the pause menu, then say start to start playing. Whenever you are ready, say hi'])

if __name__ == '__main__' :

    parser = argparse.ArgumentParser(description='Program description')
    parser.add_argument('mode', help='host, player (ip & port required)')
    parser.add_argument('--host_ip', type=str, required=False)
    parser.add_argument('--host_port', type=int, required=False)
    parser.add_argument('--player_ip', type=str, required=False)
    parser.add_argument('--player_port', type=int, required=False)
    parser.add_argument('--debug', action='store_true', help='show debug info')
    args = parser.parse_args()
    print("> run as " + args.mode)
    mode = args.mode
    if (args.host_ip):
        host_ip = args.host_ip
    if (args.host_port):
        host_port = args.host_port
    if (args.player_ip):
        player_ip = args.player_ip
    if (args.player_port):
        player_port = args.player_port
    if (args.debug):
        debug = True

# GAME INFO

# functions receiving messages from host
# TODO: add audio output so you know what's going on in the game

# OSC Callbacks
def on_receive_game(address, *args):
    if len(args) == 1:
        set_game_state(args[0] == 1)
        game_state = "started" if args[0] == 1 else "paused"
        print(f"Game state: {game_state}")

def on_receive_ball(address, *args):
    if len(args) == 2:
        x, y = args
        print(f"Ball position: ({x}, {y})")         

def on_receive_paddle(address, *args):
    if len(args) == 2:
        p1, p2 = args
        print(f"Paddle positions: P1 = {p1}, P2 = {p2}")

def on_receive_hitpaddle(address, *args):
    play_adjusted_sound("metal-hit.wav")
    print("> ball hit at paddle " + str(args[0]) )

def on_receive_ballout(address, *args):
    print("> ball went out on left/right side: " + str(args[0]) )

def on_receive_ballbounce(address, *args):
    if len(args) == 1:
        if args[0] == 1:  # Top wall
            play_adjusted_sound("boing.wav", -10)  # Slightly quieter for top wall
            print("> Ball bounced on the top wall.")
        elif args[0] == 2:  # Bottom wall
            play_adjusted_sound("boing.wav", 0)  # Default volume for bottom wall
            print("> Ball bounced on the bottom wall.")

def on_receive_scores(address, *args):
    if get_game_state() and len(args) >= 2:
        player1_score, player2_score = args
        print(f"Scores Update: Player 1 = {player1_score}, Player 2 = {player2_score}")
        speak_text(f"Score Player 1: {player1_score}, Player 2: {player2_score}.")

def on_receive_level(address, *args):
    if len(args) == 1:
        level = {1: "Easy", 2: "Hard", 3: "Insane"}.get(args[0], "Unknown")
        print(f"Game level: {level}")

def on_receive_powerup(address, *args):
    if is_game_running and len(args) > 0:
        powerup_type = args[0]
        powerup_messages = {
            1: "Player 1 is frozen.",
            2: "Player 2 is frozen.",
            3: "Player 1 has a big paddle.",
            4: "Player 2 has a big paddle."
        }
        message = powerup_messages.get(powerup_type, "No active power-up.")
        print(f"> powerup now: {message}")
        speak_text(message)
        print(f"Powerup type: {powerup_type}")
        play_adjusted_sound("powerup.wav", -5)

def on_receive_p1_bigpaddle(address, *args):
    print("> p1 has a big paddle now")
    speak_text("Big paddle activated for player 1.")
    play_adjusted_sound("powerup.wav")
    # when p1 activates their big paddle

def on_receive_p2_bigpaddle(address, *args):
    print("> p2 has a big paddle now")
    speak_text("Big paddle activated a player 2.")
    play_adjusted_sound("powerup.wav", -5)
    # when p2 activates their big paddle

def on_receive_hi(address, *args):
    global player1_ready, player2_ready
    # Print the received address and arguments for debugging
    print(f"Received /hi message. Address: {address}, Args: {args}")
    speak_text("Your opponent said hi")
    player2_ready = True
    if player1_ready:
        client.send_message('/setgame', 1)
        print('Players are ready, starting game.')
        speak_text('Players are ready, starting game.')

def on_receive_setpaddle(address, *args):
    print(f"Received /setpaddle: {args}")  # Log received paddle updates

dispatcher_player = dispatcher.Dispatcher()
dispatcher_player.map("/hi", on_receive_hi)
dispatcher_player.map("/game", on_receive_game)
dispatcher_player.map("/ball", on_receive_ball)
dispatcher_player.map("/paddle", on_receive_paddle)
dispatcher_player.map("/ballout", on_receive_ballout)
dispatcher_player.map("/ballbounce", on_receive_ballbounce)
dispatcher_player.map("/hitpaddle", on_receive_hitpaddle)
dispatcher_player.map("/scores", on_receive_scores)
dispatcher_player.map("/level", on_receive_level)
dispatcher_player.map("/powerup", on_receive_powerup)
dispatcher_player.map("/p1bigpaddle", on_receive_p1_bigpaddle)
dispatcher_player.map("/p2bigpaddle", on_receive_p2_bigpaddle)
# -------------------------------------#

# CONTROL

# TODO add your audio control so you can play the game eyes free and hands free! add function like "client.send_message()" to control the host game
# We provided two examples to use audio input, but you don't have to use these. You are welcome to use any other library/program, as long as it respects the OSC protocol from our host (which you cannot change)

# example 1: speech recognition functions using google api
# -------------------------------------#

def send_message_with_log(path, value):
    """Send OSC messages with logging for debugging."""
    try:
        print(f"Sending OSC message: {path} {value}")
        client.send_message(path, value)
    except Exception as e:
        print(f"Error sending OSC message: {e}")

    
# -------------------------------------#

# example 2: pitch & volume detection
# -------------------------------------#
# PyAudio object.
p = pyaudio.PyAudio()
# Open stream.
stream = p.open(format=pyaudio.paFloat32,
    channels=1, rate=44100, input=True,
    frames_per_buffer=1024)
# Aubio's pitch detection.
pDetection = aubio.pitch("default", 2048,
    2048//2, 44100)
# Set unit.
pDetection.set_unit("Hz")
pDetection.set_silence(-40)

def sense_microphone():
    global quit
    global debug
    while not quit:
        data = stream.read(1024,exception_on_overflow=False)
        samples = num.frombuffer(data, dtype=aubio.float_type)

        # Compute the pitch of the microphone input
        pitch = pDetection(samples)[0]
        # Compute the energy (volume) of the mic input
        volume = num.sum(samples**2)/len(samples)
        # Format the volume output so that at most
        # it has six decimal numbers.
        volume = "{:.6f}".format(volume)

        # uncomment these lines if you want pitch or volume
        if debug:
            print("pitch "+str(pitch)+" volume "+str(volume))
# -------------------------------------#

# MAIN SETUP
# speech recognition thread

# -------------------------------------#


# pitch & volume detection
# -------------------------------------#
# start a thread to detect pitch and volume
microphone_thread = threading.Thread(target=sense_microphone, args=())
microphone_thread.daemon = True
microphone_thread.start()
# -------------------------------------#

# Play some fun sounds?
# -------------------------------------#
def hit():
    playsound('hit.wav', False)

def stop_sound_worker():
    sound_queue.put(None)  # Signal the worker to stop
    sound_thread.join(timeout=5)  # Wait for the thread to exit
    if sound_thread.is_alive():
        print("Sound worker did not shut down properly.")

# Register cleanup on program exit
import atexit
atexit.register(stop_sound_worker)

# -------------------------------------#

# OSC connection
# -------------------------------------#
# used to send messages to host
if mode == 'p1':
    host_port = host_port_1
if mode == 'p2':
    host_port = host_port_2

if (mode == 'p1') or (mode == 'p2'):
    client = udp_client.SimpleUDPClient(host_ip, host_port)
    print("> connected to server at "+host_ip+":"+str(host_port))

# OSC thread
# -------------------------------------#
# Player OSC port
if mode == 'p1':
    player_port = player_1_port
if mode == 'p2':
    player_port = player_2_port

player_server = osc_server.ThreadingOSCUDPServer((player_ip, player_port), dispatcher_player)
player_server_thread = threading.Thread(target=player_server.serve_forever)
player_server_thread.daemon = True
player_server_thread.start()
# -------------------------------------#
client.send_message("/connect", player_ip)

# MAIN LOOP
# manual input for debugging
# -------------------------------------#
def manual_input():
    while not quit_event.is_set():
        try:
            m = input("> send: ")
            print(f"Manual command: {m}")
            cmd = m.split(' ')
            if len(cmd) == 2:
                client.send_message("/"+cmd[0], int(cmd[1]))
            elif len(cmd) == 1:
                client.send_message("/"+cmd[0], 0)
        except Exception as e:
            print(f"Input error: {e}")
input_thread = threading.Thread(target=manual_input, daemon=True)
input_thread.start()

# MAIN LOOP
try: 
    while not quit_event.is_set():
        time.sleep(1)  # Prevent excessive CPU usage
except KeyboardInterrupt:
    print("Exiting on user interrupt.")
finally:
    # Stop TTS manager and other threads gracefully when quitting
    quit_event.set()  # Signal threads to stop
    print("Clean shutdown completed.")
    
    # this is how client send messages to server
    # send paddle position 200 (it should be between 0 - 450):
    # client.send_message('/p', 200)
    # set level to 3:
    # client.send_message('/l', 3)
    # start the game:
    # client.send_message('/g', 1)
    # pause the game:
    # client.send_message('/g', 0)
    # big paddle if received power up:
    # client.send_message('/b', 0)
