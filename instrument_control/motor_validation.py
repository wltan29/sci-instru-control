"""Validation a motor stage over EPICS following refurbishment of motion
controllers: speed, acceleration, accuracy, repeatability.

Select a stage by editing ``motor_pv`` and choose tests with CLI flags
(``--speed --accl --accuracy --repeat``). The accuracy and repeatability tests
compare commanded vs readback vs encoder position against an in-position
tolerance band and stream the errors to a live-updating matplotlib plot; a
summary of worst-case errors is printed at the end.

Requires a live beamline: EPICS ``caput``/``caget`` access to a real motor
controller. Included as a code sample -- it does nothing off the beamline
network.
"""

from time import sleep
import random
import numpy as np
import matplotlib.pyplot as plt

from epics import caput, caget

import argparse

TIMEOUT = 5    # seconds
plot_live = True

# motor_pv = "SR10BM01LIN100:X"
# motor_pv = "SR10BM01SLM02:YT"
# motor_pv = "SR10BM01SLM02:YB"
# motor_pv = "SR10BM01SLM02:XI"
# motor_pv = "SR10BM01SLM02:XO"
# motor_pv = "SR10BM01MCS03:VSIZE"
# motor_pv = "SR10BM01MCS03:VCENTRE"
# motor_pv = "SR10BM01MCS03:HSIZE"
# motor_pv = "SR10BM01MCS03:HCENTRE"
# motor_pv = "SR10BM01STG01:X"
# motor_pv = "SR10BM01STG01:Y"
# motor_pv = "SR10BM01TBL01:Y"
# motor_pv = "SR10BM01TBL01:X"
# motor_pv = "SR10BM01LIN300:Z"
# motor_pv = "SR10BM01DIF01:Y"
# motor_pv = "SR10BM01DIF01:C"
motor_pv = "SR10BM01LIN100N:Z"
# motor_pv = "SR10BM01STG02:TRANSZ"
# motor_pv = "SR10BM01STG02:TILTZ"
# motor_pv = "SR10BM01HUBER02:TILT"
# motor_pv = "SR10BM01BAT01:ROT01"
# motor_pv = "SR10BM01FLATROT01:ROT01"
# motor_pv = "SR10BM01HUBER01:Z"
# motor_pv = "SR10BM01SLM03:XI"
# motor_pv = "SR10BM01SLM03:XO"
# motor_pv = "SR10BM01SLM03:YT"
# motor_pv = "SR10BM01SLM03:YB"
# motor_pv = "SR10BM01MCS06:HSIZE"
# motor_pv = "SR10BM01MCS06:HCENTRE"
# motor_pv = "SR10BM01MCS06:VSIZE"
# motor_pv = "SR10BM01MCS06:VCENTRE"


motor_value_pv = motor_pv + ".VAL"
motor_rbv_pv = motor_pv + ".RBV"
motor_speed_pv = motor_pv + ".VELO"
motor_speed_max_pv = motor_pv + ".VMAX"
motor_accl_pv = motor_pv + ".ACCL"
motor_off_pv = motor_pv + ".OFF"
motor_powerbrick_rbv_pv = motor_pv + ":POSITION"
motor_powerbrick_enc_pv = motor_pv + ":RefPos" # For open loop with encoder + EPICS retry

# Sleep parameters
short_sleep = 0.1
long_sleep = 1

# Test toggling using args
parser = argparse.ArgumentParser(description="Motor Test Script")
parser.add_argument("--speed", action="store_true", help="Run speed test")
parser.add_argument("--accl", action="store_true", help="Run acceleration test")
parser.add_argument("--accuracy", action="store_true", help="Run accuracy test")
parser.add_argument("--repeat", action="store_true", help="Run repeatability test")

args = parser.parse_args()

speed_test = args.speed
accl_test = args.accl
accuracy_test = args.accuracy
repeat_test = args.repeat

# Stage parameters
motor_unit = "mm"
in_position_band = 0.001 # Powerbrick parameter for closed loop, use resolution requirement/2 for open loop, use retry deadband for EPICS closed loop.
max_speed = caget(motor_speed_max_pv)
max_speed = 17
max_accel = 0.1
travel_range = [0, 100]
speed_range = [max_speed, max_speed/2]

# Functions definition
def fail_warn(message):
    warning_message = f"\033[91m[FAILED]\033[0m {message}"
    return warning_message
    
def motion_error_analysis(motor_value_pv, motor_rbv_pv, motor_powerbrick_rbv_pv, motor_off_pv, in_position_band, cmd_rbv_error_list, cmd_enc_error_list, rbv_enc_error_list):
    # Get rbv, cal, pos enc
    motor_cmd_val = caget(motor_value_pv)
    motor_rbv_val = caget(motor_rbv_pv)
    motor_pos_enc_abs_val = caget(motor_powerbrick_rbv_pv) + caget(motor_off_pv)
    # motor_pos_enc_abs_val = caget(motor_powerbrick_enc_pv) + caget(motor_off_pv) # For stages with Open Loop + EPICS retry
    # motor_pos_enc_abs_val = -(caget(motor_powerbrick_rbv_pv) - caget(motor_off_pv)) # For stage with Neg drive direction

    # Compute error
    cmd_rbv_error = motor_cmd_val - motor_rbv_val
    cmd_enc_error = motor_cmd_val - motor_pos_enc_abs_val
    rbv_enc_error = motor_rbv_val - motor_pos_enc_abs_val
    
    
    cmd_rbv_error_list.append(cmd_rbv_error)
    cmd_enc_error_list.append(cmd_enc_error)
    rbv_enc_error_list.append(rbv_enc_error)
    
    # Output error message
    message = f"cmd_rbv_err: {cmd_rbv_error:.5f}, cmd_enc_err: {cmd_enc_error:.5f}, rbv/enc absolute error: {rbv_enc_error:.5f}"
    
    if np.abs(cmd_rbv_error) > in_position_band or np.abs(cmd_enc_error) > in_position_band:
        print(fail_warn(f"!!! {message}"))
    else:
        print(f"--- {message}")
    
    return(cmd_rbv_error, cmd_enc_error, rbv_enc_error, cmd_rbv_error_list, cmd_enc_error_list, rbv_enc_error_list)





print(f"""
-----------------------------------
Testing stage {motor_pv}
-----------------------------------
""")

# Tests
if speed_test == True:
    # ------------
    # Speed test
    # Input parameters
    
    speed_range = speed_range
    travel_range = travel_range

    # Move to start position
    print(f"\nStarting Speed test\n")
    print(f"Testing speed: {speed_range} {motor_unit}/s")
    print(f"Travel range: {travel_range} {motor_unit}\n")
    print(f"[+] Moving to start position: {travel_range[0]} {motor_unit}")
    caput(motor_speed_pv, max_speed)
    caput(motor_accl_pv, max_accel)
    sleep(short_sleep)
    caput(motor_value_pv, travel_range[0], wait=True)

    # Do the test
    for speed in speed_range:
        caput(motor_speed_pv, speed)
        print(f"[+] Testing speed = {speed} {motor_unit}/s")
        sleep(short_sleep)
        caput(motor_value_pv, travel_range[1], wait=True)
        sleep(long_sleep)
        caput(motor_value_pv, travel_range[0], wait=True)
        sleep(2)
    
    print(f"Finished Speed Test\n")


if accl_test == True:
    # ------------
    # Acceleration test
    # Input parameters

    accel_range = [0.1, 5]
    travel_range = travel_range

    # Move to start position
    print(f"\nStarting Acceleration Test\n")
    print(f"Testing accl: {accel_range} s")
    print(f"Travel range: {travel_range} {motor_unit}\n")
    print(f"[+] Moving to start position: {travel_range[0]} {motor_unit}")
    caput(motor_accl_pv, max_accel)
    caput(motor_speed_pv, max_speed)
    sleep(short_sleep)
    caput(motor_value_pv, travel_range[0], wait=True)

    # Do the test
    for accel in accel_range:
        caput(motor_accl_pv, accel)
        print(f"[+] Testing acceleration = {accel} s")
        sleep(short_sleep)
        caput(motor_value_pv, travel_range[1], wait=True)
        sleep(2)
        caput(motor_value_pv, travel_range[0], wait=True)
        sleep(5)

    print(f"Finished Acceleration Test\n")

if accuracy_test == True:
    # ------------
    # Accuracy test
    # Input parameters
    
    move_step_range = [1, 0.1, 0.01]
    # move_step_range = [0.1]
    # move_step_range = [0.005] # Use the resolution step if testing for resolution.
    num_move_step = 11 # Odd number only
    mid_pos = 50 # middle position of the motion
    
    speed_range = speed_range # Speed used to test motion accuracy
    # speed_range = [max_speed]
    
    # Do the test
    print(f"\nStarting Accuracy test\n")
    print(f"Move step range: {move_step_range} {motor_unit}")
    print(f"Num of steps: {num_move_step}")
    print(f"Speed tested: {speed_range} {motor_unit}/s")
    print(f"In position band: {in_position_band} {motor_unit}\n")
    
    cmd_rbv_error_list, cmd_enc_error_list, rbv_enc_error_list = [], [], []
    
    for speed in speed_range:

        print(f"\nTesting speed = {speed} {motor_unit}/s\n")

        for move_step in move_step_range:
            
            if plot_live:
                # Enable interactive mode
                plt.ion()

                # Create figure and axes
                fig, ax = plt.subplots(figsize=(10, 8))

                # Initialize empty data lists
                motor_positions = []
                cmd_rbv_errors = []
                cmd_enc_errors = []
                rbv_enc_errors = []
                in_position_band_plot_pos = []
                in_position_band_plot_neg = []

                # Create empty line objects for updating later
                line1, = ax.plot([], [], "o-", label="cmd - rbv error")
                line2, = ax.plot([], [], "o-", label="cmd - enc error")
                line3, = ax.plot([], [], "o-", label="rbv - enc error")
                line4, = ax.plot([], [], "r--", label=f"in-position band/retry deadband\n{in_position_band} {motor_unit}")
                line5, = ax.plot([], [], "r--")

                ax.set_xlabel(f"Motor Position ({motor_unit})")
                ax.set_ylabel(f"Error ({motor_unit})")
                ax.set_title(f"{motor_pv}\nMotion Errors vs Motor Position (speed: {speed} {motor_unit}/s, scan step: {move_step} {motor_unit})")
                ax.legend(loc="upper right")
                ax.grid(True)
                
            print(f"\nMove step = {move_step} {motor_unit}")
            motor_pos_list_inc = np.arange(mid_pos-move_step*(num_move_step//2)-move_step, mid_pos+move_step*(num_move_step//2+1), move_step) # Move in one direction
            motor_pos_list_dec = motor_pos_list_inc[:-1][::-1][:-1] # Move in the other direction
            motor_pos_list = np.concatenate((motor_pos_list_inc, motor_pos_list_dec))

            print(f">> Moving to start position: {motor_pos_list[0]} {motor_unit}")
            caput(motor_speed_pv, max_speed) # Move to start pos at max speed
            caput(motor_accl_pv, max_accel) # Use the max accl
            sleep(short_sleep)
            caput(motor_value_pv, motor_pos_list[0], wait=True)
            sleep(long_sleep)
            caput(motor_speed_pv, speed) # Set the speed back to test speed
            sleep(short_sleep)
            
            for i, motor_pos in enumerate(motor_pos_list[1:]):

                print(f"[+] Moving to test position {i}: {motor_pos:.5f} {motor_unit}")
                caput(motor_value_pv, motor_pos, wait=True)
                sleep(long_sleep)

                cmd_rbv_error, cmd_enc_error, rbv_enc_error, cmd_rbv_error_list, cmd_enc_error_list, rbv_enc_error_list = motion_error_analysis(motor_value_pv, motor_rbv_pv, motor_powerbrick_rbv_pv, motor_off_pv, in_position_band, cmd_rbv_error_list, cmd_enc_error_list, rbv_enc_error_list)
                
                if plot_live:
                    # Append to lists
                    motor_positions.append(motor_pos)
                    cmd_rbv_errors.append(cmd_rbv_error)
                    cmd_enc_errors.append(cmd_enc_error)
                    rbv_enc_errors.append(rbv_enc_error)
                    in_position_band_plot_pos.append(in_position_band)
                    in_position_band_plot_neg.append(-in_position_band)

                    # Update data in plots
                    line1.set_data(motor_positions, cmd_rbv_errors)
                    line2.set_data(motor_positions, cmd_enc_errors)
                    line3.set_data(motor_positions, rbv_enc_errors)
                    line4.set_data(motor_positions, in_position_band_plot_pos)
                    line5.set_data(motor_positions, in_position_band_plot_neg)

                    ax.relim()               # Recalculate limits
                    ax.autoscale_view()      # Autoscale view to fit new data
                    plt.draw()               # Redraw figure
                    plt.pause(0.1)           # Pause to update display
                
    
    print("\nAccuracy Analysis\n")
    print(f"In-position band = {in_position_band:.5f}")
    print(f"Max cmd_rbv_error = {max(abs(cmd_rbv_error) for cmd_rbv_error in cmd_rbv_error_list):.5f}")
    print(f"Max cmd_enc_error = {max(abs(cmd_enc_error) for cmd_enc_error in cmd_enc_error_list):.5f}")
    print(f"Max rbv_enc_error = {max(abs(rbv_enc_error) for rbv_enc_error in rbv_enc_error_list):.5f}")
    print(f"\nFinished Accuracy Test\n")
    
    if plot_live:
        # Optional: keep final plot open
        plt.ioff()
        plt.show()

if repeat_test == True:
    # ------------  
    # Repeatablity test
    # Input parameters
    
    travel_range = travel_range
    # travel_range = [-1, 20] # Slits size
    # travel_range = [-3, 3] # Slits centre
    num_cycle = 20
    speed_range = [max_speed]
    
    print(f"\nStarting Repeatiblity test\n")
    
    print(f"Speeds: {speed_range} {motor_unit}/s")
    print(f"Num of repeats: {num_cycle}")
    print(f"Travel range: {travel_range} {motor_unit}")
    

    
    for speed in speed_range:
        print(f"\nTesting speed = {speed} {motor_unit}/s\n")
        
        print(f">> Moving to start position: {travel_range[0]} {motor_unit}")
        caput(motor_speed_pv, max_speed) # Move to start pos at max speed
        caput(motor_accl_pv, max_accel) # Use the max accl
        sleep(short_sleep)
        caput(motor_value_pv, travel_range[0], wait=True)
        sleep(short_sleep)
        caput(motor_speed_pv, speed) # Set the speed back to test speed
        sleep(short_sleep)
        
        # Do the test
        cmd_rbv_error_list, cmd_enc_error_list, rbv_enc_error_list = [], [], []
    
        for i in np.arange(0,num_cycle):
            print(f"[+] Cycle {i+1}")
            caput(motor_value_pv, travel_range[1], wait=True)
            sleep(short_sleep)
            cmd_rbv_error, cmd_enc_error, rbv_enc_error, cmd_rbv_error_list, cmd_enc_error_list, rbv_enc_error_list = motion_error_analysis(motor_value_pv, motor_rbv_pv, motor_powerbrick_rbv_pv, motor_off_pv, in_position_band, cmd_rbv_error_list, cmd_enc_error_list, rbv_enc_error_list)
            caput(motor_value_pv, travel_range[0], wait=True)
            sleep(short_sleep)
            cmd_rbv_error, cmd_enc_error, rbv_enc_error, cmd_rbv_error_list, cmd_enc_error_list, rbv_enc_error_list = motion_error_analysis(motor_value_pv, motor_rbv_pv, motor_powerbrick_rbv_pv, motor_off_pv, in_position_band, cmd_rbv_error_list, cmd_enc_error_list, rbv_enc_error_list)

        sleep(long_sleep)
    
        print("\nMotor Drift Analysis\n")
        print(f"Max cmd_rbv_error = {max(abs(cmd_rbv_error) for cmd_rbv_error in cmd_rbv_error_list):.5f}")
        print(f"Max cmd_enc_error = {max(abs(cmd_enc_error) for cmd_enc_error in cmd_enc_error_list):.5f}")
        print(f"Max rbv_enc_error = {max(abs(rbv_enc_error) for rbv_enc_error in rbv_enc_error_list):.5f}")
    
    print(f"\nFinished Repeatiblity test\n")

