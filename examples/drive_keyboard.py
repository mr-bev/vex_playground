# Phase 3 demo. Drive the robot by keyboard via the Controller API.
#
# Run with the pygame window:
#     uv run python -m vex_sim run examples/drive_keyboard.py --render
#
# Keys (also shown in the HUD):
#   W / S   -> forward / reverse  (axis2, right-stick Y)
#   A / D   -> turn left / right  (axis1, right-stick X)
#   space   -> pause / unpause
#   →       -> single-step one frame
#   1/2/3   -> 0.5x / 1x / 2x sim speed
#   esc     -> quit
#
# Headless mode (no --render) leaves every controller axis at 0, so the
# robot sits still until the run hits --max-time. This matches the
# headless-determinism contract: nothing about the human's keyboard
# leaks into the JSON result.

from vex import *

brain = Brain()
controller = Controller()
left_drive = Motor(Ports.PORT6, False)
right_drive = Motor(Ports.PORT10, True)
drivetrain = DriveTrain(left_drive, right_drive, 259.34, 320, 40, MM, 1)

drivetrain.set_drive_velocity(60, PERCENT)
drivetrain.set_turn_velocity(60, PERCENT)

brain.screen.print("Drive with W/A/S/D")

while True:
    forward = controller.axis2.position()  # -100..100
    turn = controller.axis1.position()  # -100..100

    if forward > 10:
        drivetrain.drive(FORWARD, abs(forward))
    elif forward < -10:
        drivetrain.drive(REVERSE, abs(forward))
    elif turn > 10:
        drivetrain.turn(RIGHT, abs(turn))
    elif turn < -10:
        drivetrain.turn(LEFT, abs(turn))
    else:
        drivetrain.stop()

    wait(20, MSEC)
