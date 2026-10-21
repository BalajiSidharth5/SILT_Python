import pygame

# Connecting Controller

pygame.init()
pygame.joystick.init()

while(pygame.joystick.get_count() == 0):
    print("Controller not Connected....")
    pygame.event.pump()
    pygame.time.wait(500)

joysticks = pygame.joystick.Joystick(0)
joysticks.init()

print(joysticks.get_name(), "is Connected. \n ")



while True:
    pygame.time.wait(100)
    pygame.event.pump()
    print("\n\n\n\n\n\n")
    rt = joysticks.get_axis(5)
    lt = joysticks.get_axis(4)
    rt01 = round((rt + 1) / 2) *100
    lt01 = round((lt + 1) / 2) *100
    out01 = rt01-lt01
    out =  round(out01) * 5 + 1500

    print("Trigger Output: ", out)