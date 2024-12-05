"""
    PONG GAME HOST - DO NOT EDIT
        
    Based on: https://gist.github.com/xjcl/8ce64008710128f3a076
    Modified by PedroLopes and ShanYuanTeng for Intro to HCI class but credit remains with author

    HOW TO RUN HOST LOCALLY:
    > python pong-audio-host-do-not-edit.py

    HOW TO RUN HOST FOR PLAYERS WITHIN THE SAME NETWORK:
    > python pong-audio-host-do-not-edit.py --host_ip HOST_IP
    
    HOW TO PLAY ON HOST VISUALLY FOR DEBUGGING: 
    - SPACE to start or pause the game
    - 1, 2, 3 to change levels on menu
    - Q to quit

    Play like a regular pong:
    - Player 1 controls the left paddle: UP (W) DOWN (S)
    - Player 2 controls the right paddle: UP (O) DOWN (L)
    
    p.s.: this needs 10x10 image in the same directory: "white_square.png".
"""
#native imports
import time
import math
import random
import pyglet
import sys
import argparse

import threading
from pythonosc import osc_server
from pythonosc import dispatcher
from pythonosc import udp_client

mode = ''
debug = False

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

paddle_1 = 225
paddle_2 = 225

# store how many powerups each player has
p1_activated = 0
p2_activated = 0
last_power_up = time.time()
power_up_duration = 10
power_up_type = 0

level = 1
game_start = 0

# Host
# -------------------------------------#
# used to send messages to players (game state etc)
client_1 = None
client_2 = None

if __name__ == '__main__' :

    parser = argparse.ArgumentParser(description='Program description')
    parser.add_argument('--host_ip', type=str, required=False)
    args = parser.parse_args()
    if (args.host_ip):
        host_ip = args.host_ip

# functions receiving messages from players (game control etc)
def on_receive_game_level(address, args, l):
    global level
    level = l
    if (client_1 != None):
        client_1.send_message("/level", l)
    if (client_2 != None):
        client_2.send_message("/level", l)

def on_receive_game_start(address, args, g):
    global game_start
    if (client_1 != None):
        client_1.send_message("/game", g)
    if (client_2 != None):
        client_2.send_message("/game", g)
    game_start = g

def on_receive_paddle_1(address, args, paddle):
    global paddle_1
    paddle_1 = paddle

def on_receive_connection_1(address, args, ip):
    global client_1
    global player_1_ip
    player_1_ip = ip
    client_1 = udp_client.SimpleUDPClient(player_1_ip, player_1_port)
    print("> player 1 connected: " + ip)
    
    if (client_1 != None):
        client_1.send_message("/game", game_start)

def on_receive_p1_hi(address, args):
    print("> player 1 says hi!")
    if (client_2 != None):
        client_2.send_message("/hi", 0)

def on_receive_paddle_2(address, args, paddle):
    global paddle_2
    paddle_2 = paddle

def on_receive_connection_2(address, args, ip):
    global client_2
    global player_2_ip
    player_2_ip = ip
    client_2 = udp_client.SimpleUDPClient(player_2_ip, player_2_port)
    print("> player 2 connected: " + ip)

    if (client_2 != None):
        client_2.send_message("/game", game_start)

def on_receive_bigpaddle_1(address, args, b):
    global p1_activated
    global last_power_up
    if (power_up_type == 3):
        p1_activated = 1
        last_power_up = time.time()
        if (client_1 != None):
            client_1.send_message("/p1bigpaddle", 0)
        if (client_2 != None):
            client_2.send_message("/p1bigpaddle", 0)

def on_receive_bigpaddle_2(address, args, b):
    global p2_activated
    global last_power_up
    if (power_up_type == 4):
        p2_activated = 1
        last_power_up = time.time()
        if (client_1 != None):
            client_1.send_message("/p2bigpaddle", 0)
        if (client_2 != None):
            client_2.send_message("/p2bigpaddle", 0)

def on_receive_p2_hi(address, args):
    print("> player 2 says hi!")
    if (client_1 != None):
        client_1.send_message("/hi", 0)

dispatcher_1 = dispatcher.Dispatcher()
dispatcher_1.map("/setpaddle", on_receive_paddle_1, "p")
dispatcher_1.map("/setlevel", on_receive_game_level, "l")
dispatcher_1.map("/setgame", on_receive_game_start, "g")
dispatcher_1.map("/connect", on_receive_connection_1, "c")
dispatcher_1.map("/setbigpaddle", on_receive_bigpaddle_1, "b")
dispatcher_1.map("/hi", on_receive_p1_hi)

dispatcher_2 = dispatcher.Dispatcher()
dispatcher_2.map("/setpaddle", on_receive_paddle_2, "p")
dispatcher_2.map("/setlevel", on_receive_game_level, "l")
dispatcher_2.map("/setgame", on_receive_game_start, "g")
dispatcher_2.map("/connect", on_receive_connection_2, "c")
dispatcher_2.map("/setbigpaddle", on_receive_bigpaddle_2, "b")
dispatcher_2.map("/hi", on_receive_p2_hi)
# -------------------------------------#

quit = False

# keeping score of points:
p1_score = 0
p2_score = 0

# Host game mechanics: no need to change below
class Ball(object):

    def __init__(self):
        self.debug = 0
        self.TO_SIDE = 5
        self.x = 50.0 + self.TO_SIDE
        self.y = float( random.randint(0, 450) )
        self.x_old = self.x  # coordinates in the last frame
        self.y_old = self.y
        self.vec_x = 1**0.5 / 2  # sqrt(2)/2
        self.vec_y = random.choice([-1, 1]) * 1**0.5 / 2

class Player(object):

    def __init__(self, NUMBER, screen_WIDTH=800):
        """NUMBER must be 0 (left player) or 1 (right player)."""
        self.NUMBER = NUMBER
        self.x = 50.0 + (screen_WIDTH - 100) * NUMBER
        self.y = 50.0
        self.last_movements = [0]*4  # short movement history
                                     # used for bounce calculation
        self.up_key, self.down_key = None, None
        if NUMBER == 0:
            self.up_key = pyglet.window.key.W
            self.down_key = pyglet.window.key.S
        elif NUMBER == 1:
            self.up_key = pyglet.window.key.O
            self.down_key = pyglet.window.key.L


class Model(object):
    """Model of the entire game. Has two players and one ball."""

    def __init__(self, DIMENSIONS=(800, 450)):
        """DIMENSIONS is a tuple (WIDTH, HEIGHT) of the field."""
        # OBJECTS
        WIDTH = DIMENSIONS[0]
        self.players = [Player(0, WIDTH), Player(1, WIDTH)]
        self.ball = Ball()
        # DATA
        self.pressed_keys = set()  # set has no duplicates
        self.quit_key = pyglet.window.key.Q
        self.p1activate_key = pyglet.window.key.E
        self.p2activate_key = pyglet.window.key.P
        self.menu_key = pyglet.window.key.SPACE
        self.level_1_key = pyglet.window.key._1
        self.level_2_key = pyglet.window.key._2
        self.level_3_key = pyglet.window.key._3
        self.speed = 4  # in pixels per frame
        self.ball_speed = self.speed #* 2.5
        self.WIDTH, self.HEIGHT = DIMENSIONS
        # STATE VARS
        self.menu = 0 # 0: menu, 1: game
        self.level = 1
        self.paused = True
        self.i = 0  # "frame count" for debug
        self.powerup = 0 # (0=none, 1=player_1, 2=player_2)

    def reset_ball(self, who_scored):
        """Place the ball anew on the loser's side."""
        if debug: print(str(who_scored)+" scored. reset.")
        self.ball.y = float( random.randint(0, self.HEIGHT) )
        self.ball.vec_y = random.choice([-1, 1]) * 2**0.5 / 2
        if who_scored == 0:
            self.ball.x = self.WIDTH - 50.0 - self.ball.TO_SIDE
            self.ball.vec_x = - 2**0.5 / 2
        elif who_scored == 1:
            self.ball.x = 50.0 + self.ball.TO_SIDE
            self.ball.vec_x = + 2**0.5 / 2
        elif who_scored == "debug":
            self.ball.x = 70  # in paddle atm -> usage: hold f
            self.ball.y = self.ball.debug
            self.ball.vec_x = -1
            self.ball.vec_y = 0
            self.ball.debug += 0.2
            if self.ball.debug > 100:
                self.ball.debug = 0

    def check_if_oob_top_bottom(self):
        """Called by update_ball to recalc. a ball above/below the screen."""
        # bounces. if -- bounce on top of screen. elif -- bounce on bottom.
        b = self.ball
        if b.y - b.TO_SIDE < 0:
            illegal_movement = 0 - (b.y - b.TO_SIDE)
            b.y = 0 + b.TO_SIDE + illegal_movement
            b.vec_y *= -1
            if (client_1 != None):
                client_1.send_message("/ballbounce", 1)
            if (client_2 != None):
                client_2.send_message("/ballbounce", 1)
        elif b.y + b.TO_SIDE > self.HEIGHT:
            illegal_movement = self.HEIGHT - (b.y + b.TO_SIDE)
            b.y = self.HEIGHT - b.TO_SIDE + illegal_movement
            b.vec_y *= -1
            if (client_1 != None):
                client_1.send_message("/ballbounce", 2)
            if (client_2 != None):
                client_2.send_message("/ballbounce", 2)

    def check_if_oob_sides(self):
        global p2_score, p1_score
        """Called by update_ball to reset a ball left/right of the screen."""
        b = self.ball
        if b.x + b.TO_SIDE < 0:  # leave on left
            self.reset_ball(1)
            p2_score+=1
            if (client_1 != None):
                client_1.send_message("/ballout", 1)
                client_1.send_message("/scores", [p1_score, p2_score])
            if (client_2 != None):
                client_2.send_message("/ballout", 1)
                client_2.send_message("/scores", [p1_score, p2_score])
        elif b.x - b.TO_SIDE > self.WIDTH:  # leave on right
            p1_score+=1
            self.reset_ball(0)
            if (client_1 != None):
                client_1.send_message("/ballout", 2)
                client_1.send_message("/scores", [p1_score, p2_score])
            if (client_2 != None):
                client_2.send_message("/ballout", 2)
                client_2.send_message("/scores", [p1_score, p2_score])

    def check_if_paddled(self): 
        """Called by update_ball to recalc. a ball hit with a player paddle."""
        b = self.ball
        p0, p1 = self.players[0], self.players[1]
        angle = math.acos(b.vec_y)  
        factor = random.randint(5, 15)  
        cross0 = (b.x < p0.x + 2*b.TO_SIDE) and (b.x_old >= p0.x + 2*b.TO_SIDE)
        cross1 = (b.x > p1.x - 2*b.TO_SIDE) and (b.x_old <= p1.x - 2*b.TO_SIDE)
        if p1_activated == 1 and power_up_type == 3:
            bounding_1 = 25 * 4
        else: 
            bounding_1 = 25
        if cross0 and -bounding_1 < b.y - p0.y < bounding_1:
            if (client_1 != None):
                client_1.send_message("/hitpaddle", 1)
            if (client_2 != None):
                client_2.send_message("/hitpaddle", 1)
            if debug: print("hit at "+str(self.i))
            illegal_movement = p0.x + 2*b.TO_SIDE - b.x
            b.x = p0.x + 2*b.TO_SIDE + illegal_movement
            # angle -= sum(p0.last_movements) / factor / self.ball_speed
            b.vec_y = math.cos(angle)
            b.vec_x = (1**2 - b.vec_y**2) ** 0.5
        else: 
            if p2_activated == 1 and power_up_type == 4:
                bounding = 25 * 4
            else: 
                bounding = 25
            if cross1 and -bounding < b.y - p1.y < bounding:
                if (client_1 != None):
                    client_1.send_message("/hitpaddle", 2)
                if (client_2 != None):
                    client_2.send_message("/hitpaddle", 2)
                if debug: print("hit at "+str(self.i))
                illegal_movement = p1.x - 2*b.TO_SIDE - b.x
                b.x = p1.x - 2*b.TO_SIDE + illegal_movement
                # angle -= sum(p1.last_movements) / factor / self.ball_speed
                b.vec_y = math.cos(angle)
                b.vec_x = - (1**2 - b.vec_y**2) ** 0.5


# -------------- Ball position: you can find it here -------
    def update_ball(self):
        """
            Update ball position with post-collision detection.
            I.e. Let the ball move out of bounds and calculate
            where it should have been within bounds.

            When bouncing off a paddle, take player velocity into
            consideration as well. Add a small factor of random too.
        """
        global client_1
        global client_2
        self.i += 1  # "debug"
        b = self.ball
        b.x_old, b.y_old = b.x, b.y
        b.x += b.vec_x * self.ball_speed 
        b.y += b.vec_y * self.ball_speed
        self.check_if_oob_top_bottom()  # oob: out of bounds
        self.check_if_oob_sides()
        self.check_if_paddled()
        if (client_1 != None):
            client_1.send_message("/ball", [b.x, b.y])
        if (client_2 != None):
            client_2.send_message("/ball", [b.x, b.y])

    def toggle_menu(self):
        global game_start
        if (self.menu != 0):
            self.menu = 0
            game_start = 0
            self.paused = True
            if (client_1 != None):
                client_1.send_message("/game", 0)
            if (client_2 != None):
                client_2.send_message("/game", 0)
        else:
            self.menu = 1
            game_start = 1
            self.paused = False
            if (client_1 != None):
                client_1.send_message("/game", 1)
            if (client_2 != None):
                client_2.send_message("/game", 1)

    def update(self):
        """Work through all pressed keys, update and call update_ball."""
        global paddle_1
        global paddle_2
        global p1_activated
        global p2_activated
        global level
        # you can change these to voice input too
        pks = self.pressed_keys
        if quit:
            sys.exit(1)
        if self.quit_key in pks:
            exit(0)
        if self.menu_key in pks:
            self.toggle_menu()
            pks.remove(self.menu_key) # debounce: get rid of quick duplicated presses
        if self.p1activate_key in pks:
            # print("E pressed to send power up on 1")
            if power_up_type == 3:
                p1_activated = 1
                last_power_up = time.time() #pedro added 2023
            # else: 
                #print("... but there's none active for P1")
            pks.remove(self.p1activate_key)
        if self.p2activate_key in pks:
            # print("P pressed to send power up by P2")
            if power_up_type == 4:
                p2_activated = 1
                last_power_up = time.time() #pedro added 2023
            # else: 
                # print("... but there's none active for P2")
            pks.remove(self.p2activate_key)
        if self.level_1_key in pks:
            level = 1
            self.ball_speed = self.speed
            pks.remove(self.level_1_key)
            if (client_1 != None):
                client_1.send_message("/level", 1)
            if (client_2 != None):
                client_2.send_message("/level", 1)
        if self.level_2_key in pks:
            level = 2
            self.ball_speed = self.speed*1.2
            pks.remove(self.level_2_key)
            if (client_1 != None):
                client_1.send_message("/level", 2)
            if (client_2 != None):
                client_2.send_message("/level", 2)
        if self.level_3_key in pks:
            level = 3
            self.ball_speed = self.speed*2
            pks.remove(self.level_3_key)
            if (client_1 != None):
                client_1.send_message("/level", 3)
            if (client_2 != None):
                client_2.send_message("/level", 3)
        if pyglet.window.key.R in pks and debug:
            self.reset_ball(1)
        if pyglet.window.key.F in pks and debug:
            self.reset_ball("debug")

        if not self.paused:
            p1 = self.players[0]
            if power_up_type == 1:
                pass
            else: 
                if (paddle_1 != 0):
                    p1.y = paddle_1
                    paddle_1 = 0
                if p1.up_key in pks and p1.down_key not in pks: 
                    p1.y -= self.speed
                elif p1.up_key not in pks and p1.down_key in pks: 
                    p1.y += self.speed
               
            p2 = self.players[1]
            if power_up_type == 2:
                pass
            else: 
                if (paddle_2 != 0):
                    p2.y = paddle_2
                    paddle_2 = 0
                if p2.up_key in pks and p2.down_key not in pks:
                    p2.y -= self.speed
                elif p2.up_key not in pks and p2.down_key in pks:
                    p2.y += self.speed

            if (client_1 != None):
                client_1.send_message("/paddle", [p1.y, p2.y])
            if (client_2 != None):
                client_2.send_message("/paddle", [p1.y, p2.y])

            self.update_ball()

class Controller(object):

    def __init__(self, model):
        self.m = model

    def on_key_press(self, symbol, modifiers):
        # `a |= b`: mathematical or. add to set a if in set a or b.
        # equivalent to `a = a | b`.
        # p0 holds down both keys => p1 controls break  # PYGLET!? D:
        self.m.pressed_keys |= set([symbol])

    def on_key_release(self, symbol, modifiers):
        if symbol in self.m.pressed_keys:
            self.m.pressed_keys.remove(symbol)

    def update(self):
        self.m.update()


class View(object):

    def __init__(self, window, model):
        self.w = window
        self.m = model
        # ------------------ IMAGES --------------------#
        # "white_square.png" is a 10x10 white image
        lplayer = pyglet.resource.image("white_square.png")
        self.player_spr = pyglet.sprite.Sprite(lplayer)

    def redraw_game(self):
        # ------------------ PLAYERS --------------------#
        TO_SIDE = self.m.ball.TO_SIDE
        idx = 0
        for p in self.m.players:
                idx = idx + 1                       
                self.player_spr.x = p.x//1 - TO_SIDE
                # oh god! pyglet's (0, 0) is bottom right! madness.
                self.player_spr.y = self.w.height - (p.y//1 + TO_SIDE)
                self.player_spr.draw()  # these 3 lines: pretend-paddle
                self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                self.player_spr.y += 4*TO_SIDE; self.player_spr.draw()
                # print ("----")
                # print (p1_activated)
                # print (p2_activated)
                # print(power_up_type)
                if idx == 2 and p2_activated == 1 and power_up_type == 4:
                    self.player_spr.y += 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y += 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y += 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y += 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y += 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y += 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y += 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 14*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()

# do the same for p1
                if idx == 1 and p1_activated == 1 and power_up_type == 3:
                    self.player_spr.y += 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y += 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y += 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y += 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y += 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y += 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y += 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 14*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
                    self.player_spr.y -= 2*TO_SIDE; self.player_spr.draw()
 
                
        # ------------------ BALL --------------------#
        self.player_spr.x = self.m.ball.x//1 - TO_SIDE
        self.player_spr.y = self.w.height - (self.m.ball.y//1 + TO_SIDE)
        self.player_spr.draw()
        

    def redraw_menu(self):
        global level
        self.m.level = level
        if (level == 1):
            self.m.ball_speed = self.m.speed
        elif (level == 2):
            self.m.ball_speed = self.m.speed*1.2
        elif (level == 3):
            self.m.ball_speed = self.m.speed*2
        self.start_label = pyglet.text.Label("press space to start", font_name=None, font_size=36, x=self.w.width//2, y=self.w.height//2, anchor_x='center', anchor_y='center')
        self.level_label = pyglet.text.Label("easy | hard | insane", font_name=None, font_size=24, x=self.w.width//2, y=self.w.height//2+100, anchor_x='center', anchor_y='center')
        if (self.m.level == 1):
            self.level_indicator_label = pyglet.text.Label("------", font_name=None, font_size=24, x=self.w.width//2-105, y=self.w.height//2+80, anchor_x='center', anchor_y='center')
        elif (self.m.level == 2):
            self.level_indicator_label = pyglet.text.Label("------", font_name=None, font_size=24, x=self.w.width//2-12, y=self.w.height//2+80, anchor_x='center', anchor_y='center')
        elif (self.m.level == 3):
            self.level_indicator_label = pyglet.text.Label("---------", font_name=None, font_size=24, x=self.w.width//2+92, y=self.w.height//2+80, anchor_x='center', anchor_y='center')
        self.start_label.draw()
        self.level_label.draw()
        self.level_indicator_label.draw()

class Window(pyglet.window.Window):

    def __init__(self, *args, **kwargs):
        DIM = (800, 450)  # DIMENSIONS
        super(Window, self).__init__(width=DIM[0], height=DIM[1],
                                     *args, **kwargs)
        # ------------------ MVC --------------------#
        the_window = self
        self.model = Model(DIM)
        self.view2 = View(the_window, self.model)
        self.controller = Controller(self.model)
        # ------------------ CLOCK --------------------#
        fps = 60.0
        pyglet.clock.schedule_interval(self.update, 1.0/fps)
        #pyglet.clock.set_fps_limit(fps)

        self.score_label = pyglet.text.Label(str(p1_score)+':'+str(p2_score), font_name=None, font_size=36, x=self.width//2, y=self.height//2, anchor_x='center', anchor_y='center')
        self.powerup_status_label = pyglet.text.Label("status: ", font_name=None, font_size=16, x=self.width//2, y=self.height//8, anchor_x='center', anchor_y='center')

    def on_key_release(self, symbol, modifiers):
        self.controller.on_key_release(symbol, modifiers)

    def on_key_press(self, symbol, modifiers):
        self.controller.on_key_press(symbol, modifiers)

    def update(self, *args, **kwargs):
        global last_power_up
        global power_up_duration
        global power_up_type
        global p1_activated
        global p2_activated
        # make more efficient (save last position, draw black square
        # over that and the new square, don't redraw _entire_ frame.)
        self.clear()
        self.controller.update()
        
        self.model.menu = game_start

        if (game_start == 1):
            self.model.paused = False
        else:
            self.model.paused = True

        if (self.model.menu == 1):
            self.view2.redraw_game()
            self.score_label.draw()
        else:
            self.view2.redraw_menu()

        if (game_start == 1):
            if (time.time() > last_power_up + random.randint(20,32)):
                last_power_up = time.time()
                power_up_type = random.randint(1,4)
                # print("new powerup: " + str(power_up_type))
                # 1 - freeze p1
                # 2 - freeze p2
                # 3 - adds a big paddle to p1, not use
                # 4 - adds a big paddle to p2, not use

                if (client_1 != None):
                    # fix power up you / oppenent fre
                    client_1.send_message("/powerup", power_up_type)
                if (client_2 != None):
                    client_2.send_message("/powerup", power_up_type)

            if (power_up_type != 0 and time.time() > last_power_up + power_up_duration):
                # print("reset powerup")
                power_up_type = 0
                p1_activated = 0
                p2_activated = 0
                if (client_1 != None):
                    client_1.send_message("/powerup", 0)
                if (client_2 != None):
                    client_2.send_message("/powerup", 0)

            self.score_label.text = str(p1_score)+':'+str(p2_score)
            if power_up_type == 1:
                power_up_status_add = " P1 is frozen!"
            elif power_up_type == 2:
                power_up_status_add = " P2 is frozen!"
            elif power_up_type == 3:
                power_up_status_add = " P1 could use big-paddle now!"
            elif power_up_type == 4:
                power_up_status_add = " P2 could use big-paddle now!"
            else:
                power_up_status_add = " no active power ups" 
            self.powerup_status_label.text = "powerup status: " + power_up_status_add 
            self.powerup_status_label.draw()  


# OSC thread
# -------------------------------------#
server_1 = osc_server.ThreadingOSCUDPServer((host_ip, host_port_1), dispatcher_1)
server_1_thread = threading.Thread(target=server_1.serve_forever)
server_1_thread.daemon = True
server_1_thread.start()
server_2 = osc_server.ThreadingOSCUDPServer((host_ip, host_port_2), dispatcher_2)
server_2_thread = threading.Thread(target=server_2.serve_forever)
server_2_thread.daemon = True
server_2_thread.start()
print("> server opens at ip: "+host_ip)
print("> instruction: player 1 connects to "+str(host_port_1) + ", listen at "+str(player_1_port))
print("> instruction: player 2 connects to "+str(host_port_2) + ", listen at "+str(player_2_port))
# -------------------------------------#

# Host: pygame starts

window = Window()
pyglet.app.run()