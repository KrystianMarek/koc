#!/usr/bin/env python

import curses
import os
import sys
import time

# from system_temperature import SystemTemperature
from BrickPi import BrickPiUpdateValues, BrickPiSetup, BrickPi, PORT_A, PORT_D, BrickPiSetupSensors, PORT_C, PORT_1, \
    TYPE_SENSOR_COLOR_FULL, TYPE_SENSOR_COLOR_GREEN, TYPE_SENSOR_COLOR_RED, TYPE_SENSOR_COLOR_BLUE, PORT_3, \
    TYPE_SENSOR_ULTRASONIC_CONT, PORT_4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.server.turret_guard import TurretGuard  # noqa: E402

_turret = {"guard": None, "speed": 0}


def update_values(brick):
    """Every exchange passes the turret through the cable envelope guard: the
    requested turret speed stays set in MotorSpeed across later exchanges."""
    if _turret["guard"] is None:
        _turret["guard"] = TurretGuard()
    guard = _turret["guard"]
    brick.MotorSpeed[PORT_C] = guard.limit(brick.Encoder[PORT_C], _turret["speed"])
    result = BrickPiUpdateValues()
    if result == 0:
        guard.observe(brick.Encoder[PORT_C])
    else:
        guard.mark_stale()
    return result


def update_window(window, power, key, temp, color):
    window.refresh()
    window.clear()
    window.addstr(1, 1, "a,z - power, arrows - steering, q|esc - exit")
    window.addstr(3, 1, "current power: " + str(power))
    window.addstr(5, 1, "color: " + str(color))


def increase_power(power, power_step):
    power = power + power_step
    if power > 250:
        power = 250

    return power


def decrease_power(power, power_step):
    power = power - power_step
    if power < 0:
        power = 0

    return power


def run_motors(brick, power_left, power_right):
    brick.MotorSpeed[PORT_D] = power_left
    brick.MotorSpeed[PORT_A] = power_right
    update_values(brick)


def rotate_turret(power, brick):
    _turret["speed"] = power
    update_values(brick)


def rotate_turret_cw(power, brick):
    rotate_turret(power, brick)


def rotate_turret_ccw(power, brick):
    rotate_turret(-power, brick)


def go_right(power, brick):
    run_motors(brick, power, power)


def go_left(power, brick):
    run_motors(brick, -power, -power)


def go_backward(power, brick):
    run_motors(brick, -power, power)


def go_forward(power, brick):
    run_motors(brick, power, -power)


def setup_color_sensor(brick):
    # brick.SensorType[PORT_1] = TYPE_SENSOR_COLOR_RED   #Set the type of sensor
    brick.SensorType[PORT_1] = TYPE_SENSOR_COLOR_BLUE   #Set the type of sensor


def setup_ultrasonic_sensor(brick):
    brick.SensorType[PORT_4] = TYPE_SENSOR_ULTRASONIC_CONT


def read_color_sensor(brick):
    col = [ None , "Black","Blue","Green","Yellow","Red","White" ]   #used for converting the color index to name

    result = update_values(brick)
    if not result:
        return brick.Sensor[PORT_1]     #BrickPi.Sensor[PORT] stores the value obtained from sensor

    return ""


def test_color_sensor():
    brick = setup_brick()
    setup_color_sensor(brick)

    while True:
        data = read_color_sensor(brick)
        print(data)
        time.sleep(1)


def test_ultrasonic_sensor():
    brick = setup_brick()
    setup_ultrasonic_sensor(brick)

    while True:
        result = update_values(brick)
        if not result:
            print(BrickPi.Sensor[PORT_4])     #BrickPi.Sensor[PORT] stores the value obtained from sensor
        # time.sleep(.01)     # sleep for 10 ms
        time.sleep(1)


def main_loop(window, brick):
    run = True
    power = 0
    power_step = 50
    key_pressed = 0

    key_esc = 27
    key_q = 113
    key_arrow_up = 259
    key_arrow_down = 258
    key_arrow_left = 260
    key_arrow_right = 261
    key_w = ord('w')
    key_e = ord('e')
    key_a = ord('a')
    key_z = ord('z')

    # st = 0 #SystemTemperature()
    setup_color_sensor(brick)

    while run:
        temp = 0 #st.get_temp()
        update_window(window, power, key_pressed, temp, read_color_sensor(brick))
        key_pressed = window.getch()

        if key_pressed == key_q or key_pressed == key_esc:
            run = False

        if key_pressed == key_a:
            power = increase_power(power, power_step)

        if key_pressed == key_z:
            power = decrease_power(power, power_step)

        if key_pressed == key_arrow_up:
            go_forward(power, brick)

        if key_pressed == key_arrow_down:
            go_backward(power, brick)

        if key_pressed == key_arrow_left:
            go_left(power, brick)

        if key_pressed == key_arrow_right:
            go_right(power, brick)

        if key_pressed == key_w:
            rotate_turret_ccw(power, brick)

        if key_pressed == key_e:
            rotate_turret_cw(power, brick)


def setup_brick():
    BrickPiSetup()
    BrickPi.MotorEnable[PORT_A] = 1
    BrickPi.MotorEnable[PORT_D] = 1
    BrickPi.MotorEnable[PORT_C] = 1
    BrickPiSetupSensors()

    return BrickPi


def main():
    window = curses.initscr()
    curses.noecho()
    curses.cbreak()
    window.keypad(1)
    window.border(1)

    brick = setup_brick()

    try:
        main_loop(window, brick)
    except Exception:
        raise
    finally:
        curses.endwin()


if __name__ == '__main__':
    # main()
    # test_sensor()
    test_ultrasonic_sensor()
