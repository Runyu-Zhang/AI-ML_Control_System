#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------- #
# Copyright (c) 2021, UChicago Argonne, LLC. All rights reserved.         #
#                                                                         #
# Copyright 2021. UChicago Argonne, LLC. This software was produced       #
# under U.S. Government contract DE-AC02-06CH11357 for Argonne National   #
# Laboratory (ANL), which is operated by UChicago Argonne, LLC for the    #
# U.S. Department of Energy. The U.S. Government has rights to use,       #
# reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR    #
# UChicago Argonne, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR        #
# ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is     #
# modified to produce derivative works, such modified software should     #
# be clearly marked, so as not to confuse it with the version available   #
# from ANL.                                                               #
#                                                                         #
# Additionally, redistribution and use in source and binary forms, with   #
# or without modification, are permitted provided that the following      #
# conditions are met:                                                     #
#                                                                         #
#     * Redistributions of source code must retain the above copyright    #
#       notice, this list of conditions and the following disclaimer.     #
#                                                                         #
#     * Redistributions in binary form must reproduce the above copyright #
#       notice, this list of conditions and the following disclaimer in   #
#       the documentation and/or other materials provided with the        #
#       distribution.                                                     #
#                                                                         #
#     * Neither the name of UChicago Argonne, LLC, Argonne National       #
#       Laboratory, ANL, the U.S. Government, nor the names of its        #
#       contributors may be used to endorse or promote products derived   #
#       from this software without specific prior written permission.     #
#                                                                         #
# THIS SOFTWARE IS PROVIDED BY UChicago Argonne, LLC AND CONTRIBUTORS     #
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT       #
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS       #
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL UChicago     #
# Argonne, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,        #
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,    #
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;        #
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER        #
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT      #
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN       #
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         #
# POSSIBILITY OF SUCH DAMAGE.                                             #
# ----------------------------------------------------------------------- #
import numpy

from beamline34IDC.facade.focusing_optics_interface import Movement, DistanceUnits, AngularUnits, MotorResolution
from beamline34IDC.simulation.facade.focusing_optics_interface import AbstractSimulatedFocusingOptics, get_default_input_features
from beamline34IDC.util.srw.common import write_dabam_file, plot_srw_wavefront_spatial_distribution

from syned.beamline.element_coordinates import ElementCoordinates
from syned.beamline.beamline_element import BeamlineElement
from syned.beamline.shape import Rectangle

from wofry.propagator.propagator import PropagationManager, PropagationParameters, PropagationElements

from wofrysrw.beamline.srw_beamline import SRWBeamline, Where
from wofrysrw.propagator.wavefront2D.srw_wavefront import WavefrontPropagationParameters
from wofrysrw.propagator.propagators2D.srw_fresnel_native import FresnelSRWNative, SRW_APPLICATION
from wofrysrw.propagator.propagators2D.srw_propagation_mode import SRWPropagationMode

from wofrysrw.beamline.optical_elements.srw_optical_element import SRWOpticalElementDisplacement
from wofrysrw.beamline.optical_elements.absorbers.srw_aperture import SRWAperture
from wofrysrw.beamline.optical_elements.mirrors.srw_mirror import Orientation
from wofrysrw.beamline.optical_elements.mirrors.srw_elliptical_mirror import SRWEllipticalMirror

def srw_focusing_optics_factory_method(**kwargs):
    try:
        if kwargs["bender"] == True: return __BendableFocusingOptics()
        else:                        return __IdealFocusingOptics()
    except: return __IdealFocusingOptics()

class _FocusingOpticsCommon(AbstractSimulatedFocusingOptics):
    def __init__(self):
        self._input_wavefront = None

        self._slits_wavefront = None
        self._vkb_wavefront = None
        self._hkb_wavefront = None

        self._coherence_slits_propagation_parameters = None
        self._vkb_propagation_parameters = None
        self._hkb_propagation_parameters = None

        self._coherence_slits = None
        self._vkb = None
        self._hkb = None
        self._modified_elements = None

    def initialize(self, input_photon_beam, input_features=get_default_input_features(), **kwargs):
        try:    rewrite_height_error_profile_files = kwargs["rewrite_height_error_profile_files"]
        except: rewrite_height_error_profile_files = False

        self._input_wavefront          = input_photon_beam.duplicate()
        self.__initial_input_wavefront = input_photon_beam.duplicate()

        if rewrite_height_error_profile_files == True:
            vkb_error_profile_file = write_dabam_file(dabam_entry_number=92, heigth_profile_file_name="VKB-LTP_srw.dat", seed=8787)
            hkb_error_profile_file = write_dabam_file(dabam_entry_number=93, heigth_profile_file_name="HKB-LTP_srw.dat", seed=2345345)
        else:
            vkb_error_profile_file = "VKB-LTP_srw.dat"
            hkb_error_profile_file = "HKB-LTP_srw.dat"

        self._beamline = SRWBeamline()

        # Coherence Slits
        width    = input_features.get_parameter("coh_slits_h_aperture") * 1e-3 # m
        height   = input_features.get_parameter("coh_slits_v_aperture") * 1e-3
        h_center = input_features.get_parameter("coh_slits_h_center") * 1e-3
        v_center = input_features.get_parameter("coh_slits_v_center") * 1e-3

        self._coherence_slits = SRWAperture(boundary_shape=Rectangle(x_left=-0.5 * width + h_center,
                                                                     x_right=0.5 * width + h_center,
                                                                     y_bottom=-0.5 * height + v_center,
                                                                     y_top=0.5 * height + v_center))

        propagation_elements = PropagationElements()
        propagation_elements.add_beamline_element(BeamlineElement(optical_element=self._coherence_slits, 
                                                                  coordinates=ElementCoordinates(q=0.15)))

        self._coherence_slits_propagation_parameters = PropagationParameters(wavefront=self._input_wavefront, 
                                                                             propagation_elements=propagation_elements)

        self._coherence_slits_propagation_parameters.set_additional_parameters("srw_oe_wavefront_propagation_parameters",
                                                                               WavefrontPropagationParameters(
                                                                                   allow_semianalytical_treatment_of_quadratic_phase_term = 0,  # Standard
                                                                                   horizontal_range_modification_factor_at_resizing       = 0.1,
                                                                                   horizontal_resolution_modification_factor_at_resizing  = 5.0,
                                                                                   vertical_range_modification_factor_at_resizing         = 0.1,
                                                                                   vertical_resolution_modification_factor_at_resizing    = 5.0
                                                                               ))
        
        self._coherence_slits_propagation_parameters.set_additional_parameters("srw_drift_after_wavefront_propagation_parameters",
                                                                               WavefrontPropagationParameters(
                                                                                   allow_semianalytical_treatment_of_quadratic_phase_term = 2,  # QTS
                                                                                   horizontal_range_modification_factor_at_resizing       = 1.0,
                                                                                   horizontal_resolution_modification_factor_at_resizing  = 2.0,
                                                                                   vertical_range_modification_factor_at_resizing         = 1.0,
                                                                                   vertical_resolution_modification_factor_at_resizing    = 2.0
                                                                               ))

        self._initialize_kb(input_features, vkb_error_profile_file, hkb_error_profile_file)

        self._modified_elements = [self._coherence_slits, self._vkb, self._hkb]

    def perturbate_input_photon_beam(self, shift_h=None, shift_v=None, rotation_h=None, rotation_v=None): pass
    def restore_input_photon_beam(self): pass

    def modify_coherence_slits(self, coh_slits_h_center=None, coh_slits_v_center=None, coh_slits_h_aperture=None, coh_slits_v_aperture=None, units=DistanceUnits.MICRON):
        boundaries = self._coherence_slits._boundary_shape.get_boundaries()

        if units==DistanceUnits.MILLIMETERS: factor = 1e-3
        elif units==DistanceUnits.MICRON:    factor = 1e-6
        else: ValueError("Units not recognized")

        round_digit = MotorResolution.getInstance().get_coh_slits_motors_resolution(units=DistanceUnits.MILLIMETERS) + 3 # m

        coh_slits_h_center   = round(abs(boundaries[1]-boundaries[0]) if coh_slits_h_center is None else factor*coh_slits_h_center, round_digit)
        coh_slits_v_center   = round(abs(boundaries[3]-boundaries[2]) if coh_slits_v_center is None else factor*coh_slits_v_center, round_digit)
        coh_slits_h_aperture = round(0.5*(boundaries[1]+boundaries[0]) if coh_slits_h_aperture is None else factor*coh_slits_h_aperture, round_digit)
        coh_slits_v_aperture = round(0.5*(boundaries[3]+boundaries[2]) if coh_slits_v_aperture is None else factor*coh_slits_v_aperture, round_digit)

        self._coherence_slits._boundary_shape=Rectangle(x_left=-0.5 * coh_slits_h_aperture + coh_slits_h_center,
                                                        x_right=0.5 * coh_slits_h_aperture + coh_slits_h_center,
                                                        y_bottom=-0.5 * coh_slits_v_aperture + coh_slits_v_center,
                                                        y_top=0.5 * coh_slits_v_aperture + coh_slits_v_center)

    def get_coherence_slits_parameters(self, units=DistanceUnits.MICRON):  # center x, center z, aperture x, aperture z
        boundaries = self._coherence_slits._boundary_shape.get_boundaries()

        if units == DistanceUnits.MILLIMETERS: factor = 1e3
        elif units == DistanceUnits.MICRON:    factor = 1e6
        else: ValueError("Units not recognized")

        coh_slits_h_center   = factor * abs(boundaries[1] - boundaries[0])
        coh_slits_v_center   = factor * abs(boundaries[3] - boundaries[2])
        coh_slits_h_aperture = factor * 0.5 * (boundaries[1] + boundaries[0])
        coh_slits_v_aperture = factor * 0.5 * (boundaries[3] + boundaries[2])

        return coh_slits_h_center, coh_slits_v_center, coh_slits_h_aperture, coh_slits_v_aperture


    # PROTECTED GENERIC MOTOR METHODS
    @classmethod
    def _move_motor_3_pitch(cls, element, angle, movement=Movement.ABSOLUTE, units=AngularUnits.MILLIRADIANS, round_digit=4):
        if element is None: raise ValueError("Initialize Focusing Optics System first")

        if units == AngularUnits.MILLIRADIANS: angle = angle * 1e-3
        elif units == AngularUnits.DEGREES:    angle = numpy.radians(angle)
        elif units == AngularUnits.RADIANS:    pass
        else: raise ValueError("Angular units not recognized")

        if movement == Movement.ABSOLUTE:
            if element.orientation_of_reflection_plane == Orientation.LEFT or \
                    element.orientation_of_reflection_plane == Orientation.RIGHT:
                element.displacement = SRWOpticalElementDisplacement(shift_x=element.displacement.shift_x,
                                                                     shift_y=element.displacement.shift_y,
                                                                     rotation_x=round(angle, round_digit),
                                                                     rotation_y=element.displacement.rotation_y)
            else:
                element.displacement = SRWOpticalElementDisplacement(shift_x=element.displacement.shift_x,
                                                                     shift_y=element.displacement.shift_y,
                                                                     rotation_x=element.displacement.rotation_x,
                                                                     rotation_y=round(angle, round_digit))
        elif movement == Movement.RELATIVE:
            if element.orientation_of_reflection_plane == Orientation.LEFT or \
                    element.orientation_of_reflection_plane == Orientation.RIGHT:
                element.displacement = SRWOpticalElementDisplacement(shift_x=element.displacement.shift_x,
                                                                     shift_y=element.displacement.shift_y,
                                                                     rotation_x=element.displacement.rotation_x + round(angle, round_digit),
                                                                     rotation_y=element.displacement.rotation_y)
            else:
                element.displacement = SRWOpticalElementDisplacement(shift_x=element.displacement.shift_x,
                                                                     shift_y=element.displacement.shift_y,
                                                                     rotation_x=element.displacement.rotation_x,
                                                                     rotation_y=element.displacement.rotation_y + round(angle, round_digit))
        else:  raise ValueError("Movement not recognized")

    @classmethod
    def _move_motor_4_transation(cls, element, translation, movement=Movement.ABSOLUTE, units=DistanceUnits.MICRON, round_digit=3):
        if element is None: raise ValueError("Initialize Focusing Optics System first")

        if units == DistanceUnits.MICRON:        translation *= 1e-6
        elif units == DistanceUnits.MILLIMETERS: translation *= 1e-3
        else: raise ValueError("Distance units not recognized")

        if movement == Movement.ABSOLUTE:
            if element.orientation_of_reflection_plane == Orientation.UP or \
                    element.orientation_of_reflection_plane == Orientation.DOWN:
                element.displacement = SRWOpticalElementDisplacement(shift_x=element.displacement.shift_x,
                                                                     shift_y=round(translation, round_digit),
                                                                     rotation_x=element.displacement.rotation_x,
                                                                     rotation_y=element.displacement.rotation_y)
            else:
                element.displacement = SRWOpticalElementDisplacement(shift_x=round(translation, round_digit),
                                                                     shift_y=element.displacement.shift_y,
                                                                     rotation_x=element.displacement.rotation_x,
                                                                     rotation_y=element.displacement.rotation_y)
        elif movement == Movement.RELATIVE:
            if element.orientation_of_reflection_plane == Orientation.UP or \
                    element.orientation_of_reflection_plane == Orientation.DOWN:
                element.displacement = SRWOpticalElementDisplacement(shift_x=element.displacement.shift_x,
                                                                     shift_y=element.displacement.shift_y + round(translation, round_digit),
                                                                     rotation_x=element.displacement.rotation_x,
                                                                     rotation_y=element.displacement.rotation_y)
            else:
                element.displacement = SRWOpticalElementDisplacement(shift_x=element.displacement.shift_x + round(translation, round_digit),
                                                                     shift_y=element.displacement.shift_y,
                                                                     rotation_x=element.displacement.rotation_x,
                                                                     rotation_y=element.displacement.rotation_y)
        else:  raise ValueError("Movement not recognized")

    @classmethod
    def _get_motor_3_pitch(cls, element, units=AngularUnits.MILLIRADIANS):
        if element is None: raise ValueError("Initialize Focusing Optics System first")

        if element.orientation_of_reflection_plane == Orientation.UP or \
                element.orientation_of_reflection_plane == Orientation.DOWN: pitch_angle = element._angle_radial - element.displacement.rotation_x
        else:                                                                pitch_angle = element._angle_radial - element.displacement.rotation_y

        if units == AngularUnits.MILLIRADIANS:  return 1000 * pitch_angle
        elif units == AngularUnits.DEGREES:     return numpy.degrees(pitch_angle)
        elif units == AngularUnits.RADIANS:     return pitch_angle
        else: raise ValueError("Angular units not recognized")

    @classmethod
    def _get_motor_4_translation(cls, element, units=DistanceUnits.MICRON):
        if element is None: raise ValueError("Initialize Focusing Optics System first")

        if element.orientation_of_reflection_plane == Orientation.UP or \
                element.orientation_of_reflection_plane == Orientation.DOWN: translation = element.displacement.shift_y
        else:                                                                translation = element.displacement.shift_x

        if units == DistanceUnits.MICRON:        return translation*1e6
        elif units == DistanceUnits.MILLIMETERS: return translation*1e3
        else: raise ValueError("Distance units not recognized")

    @classmethod
    def _get_q_distance(cls, element):
        if element is None: raise ValueError("Initialize Focusing Optics System first")

        _, q = element.get_surface_shape().get_p_q(element.grazing_angle)

        return q

    #####################################################################################
    # Run the simulation

    def get_photon_beam(self, **kwargs):
        try:
            verbose = kwargs["verbose"]
        except:
            verbose = False
        try:
            debug_mode = kwargs["debug_mode"]
        except:
            debug_mode = False

        if self._input_wavefront is None: raise ValueError("Focusing Optical System is not initialized")

        PropagationManager.Instance().set_propagation_mode(SRW_APPLICATION, SRWPropagationMode.STEP_BY_STEP)

        output_wavefront = None

        try:
            run_all = self._modified_elements == [] or len(self._modified_elements) == 3

            if run_all or self._coherence_slits in self._modified_elements:
                self._slits_wavefront = self._propagate_coherence_slits(verbose)
                output_wavefront = self._slits_wavefront

                if debug_mode: plot_srw_wavefront_spatial_distribution(self._slits_wavefront, title="Coherence Slits", xrange=None, yrange=None)

            if run_all or self._vkb in self._modified_elements:
                self._vkb_wavefront = self._propagate_vkb(verbose)
                output_wavefront = self._vkb_wavefront

                if debug_mode: plot_srw_wavefront_spatial_distribution(self._vkb_wavefront, title="VKB", xrange=None, yrange=None)

            if run_all or self._hkb in self._modified_elements:
                self._hkb_wavefront = self._propagate_hkb(verbose)
                output_wavefront = self._hkb_wavefront

                if debug_mode: plot_srw_wavefront_spatial_distribution(self._hkb_wavefront, title="HKB", xrange=None, yrange=None)

            # after every run, the list of modified elements must be empty
            self._modified_elements = []

        except Exception as e:
            raise e

        return output_wavefront

    def _propagate_coherence_slits(self, verbose):
        self._coherence_slits_propagation_parameters._wavefront = self._input_wavefront.duplicate()

        return PropagationManager.Instance().do_propagation(propagation_parameters=self._coherence_slits_propagation_parameters,
                                                            handler_name=FresnelSRWNative.HANDLER_NAME)

    def _propagate_vkb(self, verbose): raise NotImplementedError()
    def _propagate_hkb(self, verbose): raise NotImplementedError()

class __IdealFocusingOptics(_FocusingOpticsCommon):
    def __init__(self):
        super().__init__()

    def _initialize_kb(self, input_features, vkb_error_profile_file, hkb_error_profile_file):
        vkb_motor_3_pitch_angle       = input_features.get_parameter("vkb_motor_3_pitch_angle")
        vkb_motor_3_delta_pitch_angle = input_features.get_parameter("vkb_motor_3_delta_pitch_angle")
        vkb_motor_4_translation       = input_features.get_parameter("vkb_motor_4_translation") * 1e-3

        self._vkb = SRWEllipticalMirror(tangential_size=0.1,
                                        sagittal_size=0.0419,
                                        grazing_angle=vkb_motor_3_pitch_angle,
                                        orientation_of_reflection_plane=Orientation.UP,
                                        invert_tangent_component=False,
                                        add_acceptance_slit=True,
                                        height_profile_data_file=vkb_error_profile_file,
                                        distance_from_first_focus_to_mirror_center=50.65,
                                        distance_from_mirror_center_to_second_focus=input_features.get_parameter("vkb_q_distance")*1e-3)

        self._vkb.displacement = SRWOpticalElementDisplacement(shift_y=vkb_motor_4_translation,
                                                               rotation_x=-vkb_motor_3_delta_pitch_angle)

        propagation_elements = PropagationElements()
        propagation_elements.add_beamline_element(BeamlineElement(optical_element=self._vkb,
                                                                  coordinates=ElementCoordinates(q=0.101,
                                                                                                 angle_radial=0.5*numpy.pi - (vkb_motor_3_pitch_angle - vkb_motor_3_delta_pitch_angle),
                                                                                                 angle_azimuthal=0.0)))

        self._vkb_propagation_parameters = PropagationParameters(propagation_elements=propagation_elements)

        self._vkb_propagation_parameters.set_additional_parameters("srw_oe_wavefront_propagation_parameters",          
                                                                   WavefrontPropagationParameters(
                                                                       allow_semianalytical_treatment_of_quadratic_phase_term = 0, # Standard
                                                                       horizontal_range_modification_factor_at_resizing       = 1.0,
                                                                       horizontal_resolution_modification_factor_at_resizing  = 1.0,
                                                                       vertical_range_modification_factor_at_resizing         = 1.0,
                                                                       vertical_resolution_modification_factor_at_resizing    = 1.0
                                                                   ))

        self._vkb_propagation_parameters.set_additional_parameters("srw_drift_after_wavefront_propagation_parameters",
                                                                   WavefrontPropagationParameters(
                                                                       allow_semianalytical_treatment_of_quadratic_phase_term = 2,  # QTS
                                                                       horizontal_range_modification_factor_at_resizing       = 1.0,
                                                                       horizontal_resolution_modification_factor_at_resizing  = 2.0,
                                                                       vertical_range_modification_factor_at_resizing         = 1.0,
                                                                       vertical_resolution_modification_factor_at_resizing    = 2.0
                                                                   ))

        hkb_motor_3_pitch_angle       = input_features.get_parameter("hkb_motor_3_pitch_angle")
        hkb_motor_3_delta_pitch_angle = input_features.get_parameter("hkb_motor_3_delta_pitch_angle")
        hkb_motor_4_translation       = input_features.get_parameter("hkb_motor_4_translation") * 1e-3

        self._hkb = SRWEllipticalMirror(tangential_size=0.1,
                                        sagittal_size=0.0495,
                                        grazing_angle=hkb_motor_3_pitch_angle,
                                        orientation_of_reflection_plane=Orientation.LEFT,
                                        invert_tangent_component=False,
                                        add_acceptance_slit=True,
                                        height_profile_data_file=hkb_error_profile_file,
                                        distance_from_first_focus_to_mirror_center=50.751,
                                        distance_from_mirror_center_to_second_focus=input_features.get_parameter("hkb_q_distance")*1e-3)

        self._hkb.displacement = SRWOpticalElementDisplacement(shift_x=hkb_motor_4_translation,
                                                               rotation_y=-hkb_motor_3_delta_pitch_angle)

        propagation_elements = PropagationElements()
        propagation_elements.add_beamline_element(BeamlineElement(optical_element=self._hkb,
                                                                  coordinates=ElementCoordinates(q=0.12,
                                                                                                 angle_radial=0.5*numpy.pi - (hkb_motor_3_pitch_angle - hkb_motor_3_delta_pitch_angle),
                                                                                                 angle_azimuthal=0.5*numpy.pi)))

        self._hkb_propagation_parameters = PropagationParameters(propagation_elements=propagation_elements)

        self._hkb_propagation_parameters.set_additional_parameters("srw_oe_wavefront_propagation_parameters",          
                                                                   WavefrontPropagationParameters(
                                                                       allow_semianalytical_treatment_of_quadratic_phase_term = 0, # Standard
                                                                       horizontal_range_modification_factor_at_resizing       = 1.0,
                                                                       horizontal_resolution_modification_factor_at_resizing  = 2.0,
                                                                       vertical_range_modification_factor_at_resizing         = 1.0,
                                                                       vertical_resolution_modification_factor_at_resizing    = 2.0
                                                                   ))

        self._hkb_propagation_parameters.set_additional_parameters("srw_drift_after_wavefront_propagation_parameters",
                                                                   WavefrontPropagationParameters(
                                                                       allow_semianalytical_treatment_of_quadratic_phase_term = 1,  # to waist
                                                                       horizontal_range_modification_factor_at_resizing       = 2.0,
                                                                       horizontal_resolution_modification_factor_at_resizing  = 1.0,
                                                                       vertical_range_modification_factor_at_resizing         = 2.0,
                                                                       vertical_resolution_modification_factor_at_resizing    = 1.0
                                                                   ))

    # V-KB -----------------------

    def move_vkb_motor_3_pitch(self, angle, movement=Movement.ABSOLUTE, units=AngularUnits.MILLIRADIANS):
        self._move_motor_3_pitch(self._vkb, angle, movement, units,
                                 round_digit=MotorResolution.getInstance().get_vkb_motor_3_pitch_resolution(units=AngularUnits.RADIANS)[1])

        if not self._vkb in self._modified_elements: self._modified_elements.append(self._vkb)
        if not self._hkb in self._modified_elements: self._modified_elements.append(self._hkb)

    def get_vkb_motor_3_pitch(self, units=AngularUnits.MILLIRADIANS):
        return self._get_motor_3_pitch(self._vkb, units)

    def move_vkb_motor_4_translation(self, translation, movement=Movement.ABSOLUTE, units=DistanceUnits.MICRON):
        self._move_motor_4_transation(self._vkb, translation, movement, units,
                                      round_digit=MotorResolution.getInstance().get_vkb_motor_4_translation_resolution(units=DistanceUnits.MILLIMETERS)[1] + 3)

        if not self._vkb in self._modified_elements: self._modified_elements.append(self._vkb)
        if not self._hkb in self._modified_elements: self._modified_elements.append(self._hkb)

    def get_vkb_motor_4_translation(self, units=DistanceUnits.MICRON):
        return self._get_motor_4_translation(self._vkb, units)

    def change_vkb_shape(self, q_distance, movement=Movement.ABSOLUTE):
        self.__change_shape(self._vkb, q_distance, movement)

        if not self._vkb in self._modified_elements: self._modified_elements.append(self._vkb)
        if not self._hkb in self._modified_elements: self._modified_elements.append(self._hkb)

    def get_vkb_q_distance(self):
        return self._get_q_distance(self._vkb)

    # H-KB -----------------------

    def move_hkb_motor_3_pitch(self, angle, movement=Movement.ABSOLUTE, units=AngularUnits.MILLIRADIANS):
        self._move_motor_3_pitch(self._hkb, angle, movement, units,
                                 round_digit=MotorResolution.getInstance().get_hkb_motor_3_pitch_resolution(units=AngularUnits.RADIANS)[1])

        if not self._hkb in self._modified_elements: self._modified_elements.append(self._hkb)

    def get_hkb_motor_3_pitch(self, units=AngularUnits.MILLIRADIANS):
        return self._get_motor_3_pitch(self._hkb, units)

    def move_hkb_motor_4_translation(self, translation, movement=Movement.ABSOLUTE, units=DistanceUnits.MICRON):
        self._move_motor_4_transation(self._hkb, translation, movement, units,
                                      round_digit=MotorResolution.getInstance().get_hkb_motor_4_translation_resolution(units=DistanceUnits.MILLIMETERS)[1] + 3)

        if not self._hkb in self._modified_elements: self._modified_elements.append(self._hkb)

    def get_hkb_motor_4_translation(self, units=DistanceUnits.MICRON):
        return self._get_motor_4_translation(self._hkb, units)

    def change_hkb_shape(self, q_distance, movement=Movement.ABSOLUTE):
        self.__change_shape(self._hkb, q_distance, movement)

        if not self._hkb in self._modified_elements: self._modified_elements.append(self._hkb)

    def get_hkb_q_distance(self):
        return self._get_q_distance(self._hkb)

    @classmethod
    def __change_shape(cls, element, q_distance, movement=Movement.ABSOLUTE):
        if element is None: raise ValueError("Initialize Focusing Optics System first")

        p, q = element.get_surface_shape().get_p_q(element.grazing_angle)

        if movement == Movement.ABSOLUTE:   q = q_distance * 1e-3
        elif movement == Movement.RELATIVE: q += q_distance * 1e-3
        else: raise ValueError("Movement not recognized")

        element.get_surface_shape().initialize_from_p_q(p, q, element.grazing_angle)

    # IMPLEMENTATION OF PROTECTED METHODS FROM SUPERCLASS

    def _propagate_vkb(self, verbose):
        self._vkb_propagation_parameters._wavefront = self._slits_wavefront.duplicate()

        return PropagationManager.Instance().do_propagation(propagation_parameters=self._vkb_propagation_parameters,
                                                            handler_name=FresnelSRWNative.HANDLER_NAME)

    def _propagate_hkb(self, verbose):
        self._hkb_propagation_parameters._wavefront = self._vkb_wavefront.duplicate()

        return PropagationManager.Instance().do_propagation(propagation_parameters=self._hkb_propagation_parameters,
                                                            handler_name=FresnelSRWNative.HANDLER_NAME)

class __BendableFocusingOptics(_FocusingOpticsCommon):
    def __init__(self):
        super().__init__()

    def _initialize_kb(self, input_features, vkb_error_profile_file, hkb_error_profile_file):
        pass


    # V-KB -----------------------

    def move_vkb_motor_1_bender(self, pos_upstream, movement=Movement.ABSOLUTE, units=DistanceUnits.MICRON): raise NotImplementedError()
    def get_vkb_motor_1_bender(self, units=DistanceUnits.MICRON): raise NotImplementedError()
    def move_vkb_motor_2_bender(self, pos_downstream, movement=Movement.ABSOLUTE, units=DistanceUnits.MICRON): raise NotImplementedError()
    def get_vkb_motor_2_bender(self, units=DistanceUnits.MICRON): raise NotImplementedError()
    def move_vkb_motor_3_pitch(self, angle, movement=Movement.ABSOLUTE, units=AngularUnits.MILLIRADIANS): pass
    def get_vkb_motor_3_pitch(self, units=AngularUnits.MILLIRADIANS): pass
    def move_vkb_motor_4_translation(self, translation, movement=Movement.ABSOLUTE, units=DistanceUnits.MICRON): pass
    def get_vkb_motor_4_translation(self, units=DistanceUnits.MICRON): pass

    # H-KB -----------------------

    def move_hkb_motor_1_bender(self, pos_upstream, movement=Movement.ABSOLUTE, units=DistanceUnits.MICRON): raise NotImplementedError()
    def get_hkb_motor_1_bender(self, units=DistanceUnits.MICRON): raise NotImplementedError()
    def move_hkb_motor_2_bender(self, pos_downstream, movement=Movement.ABSOLUTE, units=DistanceUnits.MICRON): raise NotImplementedError()
    def get_hkb_motor_2_bender(self, units=DistanceUnits.MICRON): raise NotImplementedError()
    def move_hkb_motor_3_pitch(self, angle, movement=Movement.ABSOLUTE, units=AngularUnits.MILLIRADIANS): pass
    def get_hkb_motor_3_pitch(self, units=AngularUnits.MILLIRADIANS): pass
    def move_hkb_motor_4_translation(self, translation, movement=Movement.ABSOLUTE, units=DistanceUnits.MICRON): pass
    def get_hkb_motor_4_translation(self, units=DistanceUnits.MICRON): pass

    def get_photon_beam(self, **kwargs): pass
