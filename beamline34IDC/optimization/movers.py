import numpy as np
from beamline34IDC.simulation.facade.focusing_optics_interface import Movement

def getMovement(movement):
    movement_types = {'relative': Movement.RELATIVE,
                      'absolute': Movement.ABSOLUTE}
    if movement in movement_types:
        return movement_types[movement]
    if movement in movement_types.values():
        return movement
    raise ValueError

def getMotorMoveFn(focusing_system, motor):
    motor_move_fns = {'hkb_4': focusing_system.move_hkb_motor_4_translation,
                      'hkb_3': focusing_system.move_hkb_motor_3_pitch,
                      'hkb_q': focusing_system.change_hkb_shape,
                      'vkb_4': focusing_system.move_vkb_motor_4_translation,
                      'vkb_3': focusing_system.move_vkb_motor_3_pitch,
                      'vkb_q': focusing_system.change_vkb_shape}
    if motor in motor_move_fns:
        return motor_move_fns[motor]
    if motor in motor_move_fns.values():
        return motor
    raise ValueError

def moveMotors(focusing_system, motors, translations, movement='relative'):
    movement = getMovement(movement)
    if np.ndim(motors) == 0:
        motors = [motors]
    if np.ndim(translations) == 0:
        translations = [translations]
    for motor, trans in zip(motors, translations):
        motor_move_fn = getMotorMoveFn(focusing_system, motor)
        motor_move_fn(trans, movement=movement)
    return focusing_system
