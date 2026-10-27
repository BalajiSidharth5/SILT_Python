import os
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"  # keep joystick events when the Qt window has focus

import sys
import pygame
import socket
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from ui import PilotWindow

# Constants

LT = 4
RT = 5
DPAD_UP = 11
DPAD_LEFT = 13
DPAD_RIGHT = 14
CIRCLE = 1
SQUARE = 2
LB = 9
RB = 10

# Change to PI's Address and port

IPADDRESS = "127.0.0.1"
PORT = 5005

# Connecting Controller

pygame.init()
pygame.joystick.init()

def Connecting_Controller():

    while(pygame.joystick.get_count() == 0):
        print("Controller not Connected....")
        pygame.event.pump()
        pygame.time.wait(500)

    joystick = pygame.joystick.Joystick(0)
    joystick.init()

    print(joystick.get_name(), "is Connected. \n ")
    return joystick

def get_controller():
    # Non-blocking version of Connecting_Controller. Returns a joystick, or None when nothing is plugged in.
    pygame.event.pump()
    if pygame.joystick.get_count() == 0:
        return None
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    return joystick

def get_dpad_presses():
  hat = pygame.event.get()
  dpadPresses = []
  for event in hat:
    if (event.type == pygame.JOYBUTTONDOWN):
        if (event.button == DPAD_RIGHT):
            dpadPresses.append("right")
        elif (event.button == DPAD_UP):
            dpadPresses.append("up")
        elif (event.button == DPAD_LEFT):
            dpadPresses.append("left")
  return dpadPresses

def angle_to_pwm(angle):
    angle = max(0, min(180, angle)) 
    pwm = int((angle / 180) * 2000 + 500)
    return pwm

def read_thrust_ps4(joystick):
    pygame.event.pump()
    rt = joystick.get_axis(RT)
    lt = joystick.get_axis(LT)
    out01 = round((rt + 1) / 2 *100) - round((lt + 1) / 2 *100)
    out =  out01 * 5 + 1500
    return out

def change_servo_angle(angle):
    for dpad in get_dpad_presses():
        if dpad == "up":
           if angle["current_angle"] == angle["new_angle"]:
            angle["mode"] = not angle["mode"]
            return angle
        if angle["mode"]:
            if dpad == "left":
                angle["new_angle"] = max(0, angle["new_angle"] - 5)
            elif dpad == "right":
                angle["new_angle"] = min(180, angle["new_angle"] + 5)
            elif dpad == "up":
                angle["current_angle"] = angle["new_angle"]    
                angle["mode"] = not angle["mode"] 
    return angle

def update_winch_selection(joystick, winch_selection):

    pygame.event.pump()
    if joystick.get_button(LB):
        winch_selection["camera"] = True
        winch_selection["dart"] = False
    elif joystick.get_button(RB):
        winch_selection["dart"] = True
        winch_selection["camera"] = False
    return winch_selection


def get_winch_command(joystick, winch_selection):
    pygame.event.pump()
    if winch_selection["camera"] == True:
        winch_selection["dartCommand"] = 0
        if joystick.get_button(CIRCLE):
            winch_selection["cameraCommand"] = 1
        elif joystick.get_button(SQUARE):
            winch_selection["cameraCommand"] = 2
        elif not joystick.get_button(CIRCLE) and not joystick.get_button(SQUARE):
            winch_selection["cameraCommand"] = 0
    if winch_selection["dart"] == True:
        winch_selection["cameraCommand"] = 0
        if joystick.get_button(CIRCLE):
            winch_selection["dartCommand"] = 1
        else:
            winch_selection["dartCommand"] = 0
    return winch_selection

def checksum_calc(data):
    checksum = 0
    startBytePassed = False
    for byte in data:
        if byte == '$':
            startBytePassed = True
            continue
        elif byte == '*':
            break
        elif startBytePassed:
            checksum ^= ord(byte)
    return checksum
        
def build_packet(thrust, winch_selection, angle):
    packet = f"${thrust},{thrust},{angle_to_pwm(angle["current_angle"])},{winch_selection["cameraCommand"]},{winch_selection["dartCommand"]}*"
    checksum_value = checksum_calc(packet)
    packet += f"{checksum_value:02X}"
    packet += "\n"
    return packet

def send_packet(packet): # Transfers using UDP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(packet.encode("ascii"), (IPADDRESS, PORT))


def main():

    joystick = None   # stays None until a controller is plugged in
    winch_selection = {"camera": False, "cameraCommand": 0, "dart": False, "dartCommand": 0}
    angle = {"current_angle": 90, "new_angle": 90, "mode": False}

    app = QApplication(sys.argv)
    window = PilotWindow()
    window.show()

    def control_pass():
        # One pass of your old while loop. Runs every 50 ms (20 Hz).
        nonlocal joystick

        # Unplugged since the last pass
        if joystick is not None and pygame.joystick.get_count() == 0:
            joystick = None
            window.set_controller(None)

        # Look for a controller until one appears
        if joystick is None:
            joystick = get_controller()
            if joystick is not None:
                pygame.event.clear()   # drop button presses queued before the connection
                window.set_controller(joystick.get_name())

        if joystick is None:
            # No controller: send a neutral packet and ignore all input
            thrust = 1500
            winch_selection["cameraCommand"] = 0
            winch_selection["dartCommand"] = 0
        else:
            thrust = read_thrust_ps4(joystick)
            if thrust == 1500:
                change_servo_angle(angle)
                update_winch_selection(joystick, winch_selection)
                get_winch_command(joystick, winch_selection)
            else:
                pygame.event.clear()
                winch_selection["cameraCommand"] = 0
                winch_selection["dartCommand"] = 0

        packet = build_packet(thrust, winch_selection, angle)
        send_packet(packet)
        window.set_state(thrust, angle, winch_selection)

    timer = QTimer()
    timer.timeout.connect(control_pass)
    timer.start(50)

    sys.exit(app.exec())


main()