import pygame

# Constants

LT = 4
RT = 5

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
    print(joystick.get_numhats(), joystick.get_numbuttons()) 
    return joystick

def get_dpad_presses():
  hat = pygame.event.get()
  dpadPresses = []
  for event in hat:
    if (event.type == pygame.JOYBUTTONDOWN):
        if (event.button == 14):
            dpadPresses.append("right")
        elif (event.button == 11):
            dpadPresses.append("up")
        elif (event.button == 13):
            dpadPresses.append("left")
  return dpadPresses

def read_thrust_ps4(joystick):
    pygame.event.pump()
    rt = joystick.get_axis(RT)
    lt = joystick.get_axis(LT)
    out01 = round((rt + 1) / 2 *100) - round((lt + 1) / 2 *100)
    out =  out01 * 5 + 1500
    return out

def main():
    joystick = Connecting_Controller()
    while True:
       # thrust = read_thrust_ps4(joystick)
       # print("Thrust: ", thrust)
        pygame.time.wait(100)
        for press in get_dpad_presses():
            print("Dpad Pressed: ", press)

main()