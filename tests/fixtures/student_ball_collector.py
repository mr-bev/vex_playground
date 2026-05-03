# region VEXcode Generated Robot Configuration
from vex import *
import urandom
import math

# Brain should be defined by default
brain = Brain()

# Robot configuration code
brain_inertial = Inertial()
left_drive_smart = Motor(Ports.PORT6, False)
right_drive_smart = Motor(Ports.PORT10, True)
drivetrain = SmartDrive(
    left_drive_smart, right_drive_smart, brain_inertial, 259.34, 320, 40, MM, 1
)
bumper_d = Bumper(brain.three_wire_port.d)
bumper_f = Bumper(brain.three_wire_port.f)
distance_1 = Distance(Ports.PORT1)
optical_7 = Optical(Ports.PORT7)
motor_3clawarm = Motor(Ports.PORT3, False)
motor_4clawhand = Motor(Ports.PORT4, False)


# Wait for sensor(s) to fully initialize
wait(100, MSEC)


# generating and setting random seed
def initializeRandomSeed():
    wait(100, MSEC)
    xaxis = brain_inertial.acceleration(XAXIS) * 1000
    yaxis = brain_inertial.acceleration(YAXIS) * 1000
    zaxis = brain_inertial.acceleration(ZAXIS) * 1000
    systemTime = brain.timer.system() * 100
    urandom.seed(int(xaxis + yaxis + zaxis + systemTime))


# Initialize random seed
initializeRandomSeed()


# Color to String Helper
def convert_color_to_string(col):
    if col == Color.RED:
        return "red"
    if col == Color.GREEN:
        return "green"
    if col == Color.BLUE:
        return "blue"
    if col == Color.WHITE:
        return "white"
    if col == Color.YELLOW:
        return "yellow"
    if col == Color.ORANGE:
        return "orange"
    if col == Color.PURPLE:
        return "purple"
    if col == Color.CYAN:
        return "cyan"
    if col == Color.BLACK:
        return "black"
    if col == Color.TRANSPARENT:
        return "transparent"
    return ""


vexcode_initial_drivetrain_calibration_completed = False


def calibrate_drivetrain():
    # Calibrate the Drivetrain Inertial
    global vexcode_initial_drivetrain_calibration_completed
    sleep(200, MSEC)
    brain.screen.print("Calibrating")
    brain.screen.next_row()
    brain.screen.print("Inertial")
    brain_inertial.calibrate()
    while brain_inertial.is_calibrating():
        sleep(25, MSEC)
    vexcode_initial_drivetrain_calibration_completed = True
    brain.screen.clear_screen()
    brain.screen.set_cursor(1, 1)


# Calibrate the Drivetrain
calibrate_drivetrain()


# Library imports
from vex import *

# Begin project code
drivetrain.set_drive_velocity(20, PERCENT)
motor_3clawarm.set_velocity(10, PERCENT)
motor_4clawhand.set_velocity(10, PERCENT)

motor_3clawarm.spin_to_position(180, DEGREES)

ball_in_hand = False

while True:

    if optical_7.color() == Color.RED and ball_in_hand == False:

        drivetrain.stop()

        drivetrain.drive_for(REVERSE, 120, MM)
        motor_3clawarm.spin_to_position(0, DEGREES)
        drivetrain.drive_for(FORWARD, 130, MM)
        motor_4clawhand.spin_for(FORWARD, 70, DEGREES)
        wait(200, MSEC)

        ball_in_hand = True
        motor_3clawarm.spin_to_position(180, DEGREES)

    elif bumper_d.pressing() or bumper_f.pressing():

        brain.screen.print("Bumper")
        brain.screen.clear_screen()

        drivetrain.drive_for(REVERSE, 80, MM)

        if ball_in_hand == False:
            drivetrain.turn_for(LEFT, 90, DEGREES)
        else:
            drivetrain.turn_for(RIGHT, 90, DEGREES)

    elif distance_1.object_distance(MM) < 100:

        drivetrain.stop()

        if ball_in_hand == False:
            drivetrain.turn_for(LEFT, 90, DEGREES)
        else:
            drivetrain.turn_for(RIGHT, 90, DEGREES)

    elif optical_7.color() == Color.GREEN and ball_in_hand == True:

        drivetrain.stop()
        motor_3clawarm.spin_to_position(0, DEGREES)
        motor_4clawhand.spin_for(REVERSE, 90, DEGREES)
        motor_3clawarm.spin_to_position(180, DEGREES)
        drivetrain.turn_for(RIGHT, 180, DEGREES)

        ball_in_hand = False

    elif optical_7.color() == Color.RED and ball_in_hand == True:

        drivetrain.turn_for(RIGHT, 180, DEGREES)

    else:
        print("forward")

        drivetrain.drive(FORWARD)

    wait(50, MSEC)
