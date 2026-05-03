# Phase 4 demo. Visits the start (green), pickup (red), and dropoff
# (blue) zones in pickup_and_dropoff in order, using the optical sensor
# to confirm arrival at each one.
#
#     uv run python -m vex_sim run examples/colour_walker.py \
#         --playground pickup_and_dropoff --render

from vex import *

brain = Brain()
left_drive = Motor(Ports.PORT6, False)
right_drive = Motor(Ports.PORT10, True)
drivetrain = DriveTrain(left_drive, right_drive, 259.34, 320, 40, MM, 1)
optical = Optical(Ports.PORT7)

drivetrain.set_drive_velocity(70, PERCENT)
drivetrain.set_turn_velocity(70, PERCENT)


def drive_until_color(target_color, max_steps=50, step_mm=80):
    """Drive forward in fixed-size steps, stopping as soon as the optical
    sensor reads the target colour. Returns True on success."""
    for _ in range(max_steps):
        drivetrain.drive_for(FORWARD, step_mm, MM)
        if optical.color() == target_color:
            drivetrain.stop()
            return True
    drivetrain.stop()
    return False


# Start zone (green) is right under us at spawn -- log it for fun.
brain.screen.print("starting on:", optical.color())
brain.screen.next_row()

# Aim diagonally toward the red pickup zone in the upper-right.
# Start pose is (400, 400, theta=0); pickup centre ~ (2500, 1500),
# which is about 28 deg above the +x axis. Turning LEFT increases
# theta; close enough.
drivetrain.turn_for(LEFT, 28, DEGREES)
drive_until_color("red")
brain.screen.print("reached pickup")
brain.screen.next_row()

# Now turn ~120 deg left (heading goes from ~28 to ~148) and drive to
# the blue dropoff in the lower-left.
drivetrain.turn_for(LEFT, 120, DEGREES)
drive_until_color("blue")
brain.screen.print("reached dropoff")
