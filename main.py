import pygame
import socket

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

    joystick = Connecting_Controller()
    winch_selection = {"camera": False, "cameraCommand": 0, "dart": False, "dartCommand": 0}
    angle = {"current_angle": 90, "new_angle": 90, "mode": False}
    while True:
        thrust = read_thrust_ps4(joystick)
        pygame.time.wait(100)
        if thrust == 1500: 
            angle = change_servo_angle(angle)
            update_winch_selection(joystick, winch_selection)
            get_winch_command(joystick, winch_selection)
        else:
            pygame.event.clear()  

        packet = build_packet(thrust, winch_selection, angle)
        send_packet(packet)
        


main()

