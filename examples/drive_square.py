# Phase 2 demo. Drives the robot in a 1 m square, then stops.
#
# Run headless:
#     uv run python -m vex_sim run examples/drive_square.py
# Run with the pygame window:
#     uv run python -m vex_sim run examples/drive_square.py --render

from vex import *

brain = Brain()
left_drive = Motor(Ports.PORT6, False)
right_drive = Motor(Ports.PORT10, True)
drivetrain = DriveTrain(left_drive, right_drive, 259.34, 320, 40, MM, 1)

drivetrain.set_drive_velocity(60, PERCENT)
drivetrain.set_turn_velocity(60, PERCENT)

for _ in range(4):
    drivetrain.drive_for(FORWARD, 1000, MM)
    drivetrain.turn_for(RIGHT, 90, DEGREES)

drivetrain.stop()
