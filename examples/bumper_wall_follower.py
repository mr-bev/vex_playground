# Phase 4 demo. A bumper-only wall follower for the low_wall_maze
# playground. The interior walls are LOW (30 mm) so a default-mounted
# distance sensor cannot see them; we rely entirely on the bumpers.
#
# Run:
#     uv run python -m vex_sim run examples/bumper_wall_follower.py \
#         --playground low_wall_maze --render

from vex import *

brain = Brain()
left_drive = Motor(Ports.PORT6, False)
right_drive = Motor(Ports.PORT10, True)
drivetrain = DriveTrain(left_drive, right_drive, 259.34, 320, 40, MM, 1)

front_bumper = Bumper(brain.three_wire_port.a)

drivetrain.set_drive_velocity(35, PERCENT)
drivetrain.set_turn_velocity(40, PERCENT)

# Drive forward until something stops us, back off a bit, turn, repeat.
# A real solution would track heading and stop at the goal; this is a
# minimal demonstration of using the bumper to navigate when the
# distance sensor is blind to LOW walls.
deadline = brain.timer.system() + 50_000  # 50 s wall budget
while brain.timer.system() < deadline:
    drivetrain.drive(FORWARD)
    while front_bumper.pressing() == 0 and brain.timer.system() < deadline:
        wait(20, MSEC)
    drivetrain.stop()
    drivetrain.drive_for(REVERSE, 80, MM)
    drivetrain.turn_for(LEFT, 90, DEGREES)
