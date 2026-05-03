# Phase 4 demo. Drives diagonally across the empty room into the
# top-right goal zone using only dead reckoning.
#
# Pass the empty_room playground:
#     uv run python -m vex_sim run examples/reach_goal.py
#         --playground empty_room
# Or render it:
#     uv run python -m vex_sim run examples/reach_goal.py
#         --playground empty_room --render

from vex import *

brain = Brain()
left_drive = Motor(Ports.PORT6, False)
right_drive = Motor(Ports.PORT10, True)
drivetrain = DriveTrain(left_drive, right_drive, 259.34, 320, 40, MM, 1)

# Start: (1500, 1500, theta=pi/2 facing +y).
# Goal:  (2400..2800, 2400..2800).
drivetrain.set_drive_velocity(50, PERCENT)
drivetrain.set_turn_velocity(50, PERCENT)

drivetrain.drive_for(FORWARD, 1100, MM)
drivetrain.turn_for(RIGHT, 90, DEGREES)
drivetrain.drive_for(FORWARD, 1100, MM)
drivetrain.stop()
