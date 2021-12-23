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
import Shadow

from orangecontrib.shadow.util.shadow_objects import ShadowBeam, ShadowOpticalElement
from orangecontrib.shadow.util.shadow_util import ShadowPhysics
from orangecontrib.shadow.widgets.special_elements.bl import hybrid_control
from beamline34IDC.util.common import write_bragg_file, write_reflectivity_file, write_dabam_file, \
    rotate_axis_system, get_hybrid_input_parameters

class PreProcessorFiles:
    NO = 0
    YES_FULL_RANGE = 1
    YES_SOURCE_RANGE = 2

class FocusingOpticsSystem():
    def __init__(self):
        self.__input_beam = None
        self.__coherence_slits = None
        self.__vkb = None
        self.__hkb = None

    def initialize(self,
                   input_beam,
                   input_features,
                   rewrite_preprocessor_files=PreProcessorFiles.YES_SOURCE_RANGE,
                   rewrite_height_error_profile_files=False,
                   **kwargs):
        self.__input_beam = input_beam

        energies = ShadowPhysics.getEnergyFromShadowK(self.__input_beam._beam.rays[:, 10])

        central_energy = numpy.average(energies)
        energy_range = [numpy.min(energies), numpy.max(energies)]

        if rewrite_preprocessor_files==PreProcessorFiles.YES_FULL_RANGE:
            reflectivity_file = write_reflectivity_file()
        elif rewrite_preprocessor_files==PreProcessorFiles.YES_SOURCE_RANGE:
            reflectivity_file = write_reflectivity_file(energy_range=energy_range)
        elif rewrite_preprocessor_files==PreProcessorFiles.NO:
            reflectivity_file = "Pt.dat"

        if rewrite_height_error_profile_files==True:
            vkb_error_profile_file = write_dabam_file(dabam_entry_number=20, heigth_profile_file_name="VKB.dat", seed=8787)
            hkb_error_profile_file = write_dabam_file(dabam_entry_number=62, heigth_profile_file_name="HKB.dat", seed=2345345)
        else:
            vkb_error_profile_file = "VKB.dat"
            hkb_error_profile_file = "HKB.dat"

        coherence_slits = Shadow.OE()

        # COHERENCE SLITS
        coherence_slits.DUMMY = 0.1
        coherence_slits.FWRITE = 3
        coherence_slits.F_REFRAC = 2
        coherence_slits.F_SCREEN = 1
        coherence_slits.I_SLIT = numpy.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        coherence_slits.N_SCREEN = 1
        coherence_slits.CX_SLIT = numpy.array([input_features.get_parameter("coh_slits_h_center"), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        coherence_slits.CZ_SLIT = numpy.array([input_features.get_parameter("coh_slits_v_center"), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        coherence_slits.RX_SLIT = numpy.array([input_features.get_parameter("coh_slits_h_aperture"), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        coherence_slits.RZ_SLIT = numpy.array([input_features.get_parameter("coh_slits_v_aperture"), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        coherence_slits.T_IMAGE = 0.0
        coherence_slits.T_INCIDENCE = 0.0
        coherence_slits.T_REFLECTION = 180.0
        coherence_slits.T_SOURCE = 0.0

        # V-KB
        vkb = Shadow.OE()

        vkb_motor_3_pitch_angle = input_features.get_parameter("vkb_motor_3_pitch_angle")
        vkb_pitch_angle_shadow  = 90 - numpy.degrees(vkb_motor_3_pitch_angle)
        vkb_motor_4_translation = input_features.get_parameter("vkb_motor_4_translation")

        vkb.ALPHA = 180.0
        vkb.DUMMY = 0.1
        vkb.FCYL = 1
        vkb.FHIT_C = 1
        vkb.FILE_REFL = reflectivity_file.encode()
        vkb.FILE_RIP = vkb_error_profile_file.encode()
        vkb.FMIRR = 2
        vkb.FWRITE = 1
        vkb.F_DEFAULT = 0
        vkb.F_G_S = 2
        vkb.F_REFLEC = 1
        vkb.F_RIPPLE = 1
        vkb.RLEN1 = 50.0
        vkb.RLEN2 = 50.0
        vkb.RWIDX1 = 10.0
        vkb.RWIDX2 = 10.0
        vkb.SIMAG = input_features.get_parameter("vkb_p_distance")
        vkb.SSOUR = 50667.983
        vkb.THETA = vkb_pitch_angle_shadow
        vkb.T_IMAGE = 101.0
        vkb.T_INCIDENCE = vkb_pitch_angle_shadow
        vkb.T_REFLECTION = vkb_pitch_angle_shadow
        vkb.T_SOURCE = 150.0
        # DISPLACEMENT
        vkb.F_MOVE = 1
        vkb.OFFY = vkb_motor_4_translation*numpy.sin(vkb_motor_3_pitch_angle)
        vkb.OFFZ = vkb_motor_4_translation*numpy.cos(vkb_motor_3_pitch_angle)
        vkb.X_ROT = input_features.get_parameter("vkb_motor_3_delta_pitch_angle")

        # H-KB
        hkb = Shadow.OE()

        hkb_motor_3_pitch_angle = input_features.get_parameter("hkb_motor_3_pitch_angle")
        hkb_pitch_angle_shadow  = 90 - numpy.degrees(hkb_motor_3_pitch_angle)
        hkb_motor_4_translation = input_features.get_parameter("hkb_motor_4_translation")

        hkb.ALPHA = 90.0
        hkb.DUMMY = 0.1
        hkb.FCYL = 1
        hkb.FHIT_C = 1
        hkb.FILE_REFL = reflectivity_file.encode()
        hkb.FILE_RIP = hkb_error_profile_file.encode()
        hkb.FMIRR = 2
        hkb.FWRITE = 1
        hkb.F_DEFAULT = 0
        hkb.F_G_S = 2
        hkb.F_REFLEC = 1
        hkb.F_RIPPLE = 1
        hkb.RLEN1 = 50.0
        hkb.RLEN2 = 50.0
        hkb.RWIDX1 = 10.0
        hkb.RWIDX2 = 10.0
        hkb.SIMAG = input_features.get_parameter("hkb_p_distance")
        hkb.SSOUR = 50768.983
        hkb.THETA = hkb_pitch_angle_shadow
        hkb.T_IMAGE = 120.0
        hkb.T_INCIDENCE = hkb_pitch_angle_shadow
        hkb.T_REFLECTION = hkb_pitch_angle_shadow
        hkb.T_SOURCE = 0.0
        # DISPLACEMENT
        hkb.F_MOVE = 1
        hkb.OFFY = hkb_motor_4_translation*numpy.sin(hkb_motor_3_pitch_angle)
        hkb.OFFZ = hkb_motor_4_translation*numpy.cos(hkb_motor_3_pitch_angle)
        hkb.X_ROT = input_features.get_parameter("hkb_motor_3_delta_pitch_angle")

        self.__coherence_slits = ShadowOpticalElement(coherence_slits)
        self.__vkb             =  ShadowOpticalElement(vkb)
        self.__hkb             =  ShadowOpticalElement(hkb)

    def get_beam(self, verbose=False, **kwargs):
        if self.__input_beam is None: raise ValueError("Focusing Optical System is not initialized")

        input_beam = self.__input_beam.duplicate()

        # HYBRID CORRECTION TO CONSIDER DIFFRACTION FROM SLITS
        output_beam = ShadowBeam.traceFromOE(input_beam, self.__coherence_slits, widget_class_name="ScreenSlits")
        output_beam = hybrid_control.hy_run(get_hybrid_input_parameters(output_beam,
                                                                        diffraction_plane=4,  # BOTH 1D+1D (3 is 2D)
                                                                        calcType=1,  # Diffraction by Simple Aperture
                                                                        verbose=verbose)).ff_beam

        output_beam = ShadowBeam.traceFromOE(output_beam.duplicate(), self.__vkb, widget_class_name="EllypticalMirror")
        output_beam = hybrid_control.hy_run(get_hybrid_input_parameters(output_beam,
                                                                        diffraction_plane=1,  # Tangential
                                                                        calcType=3,  # Diffraction by Mirror Size + Errors
                                                                        nf=1,
                                                                        verbose=verbose)).nf_beam

        output_beam = ShadowBeam.traceFromOE(output_beam.duplicate(), self.__hkb, widget_class_name="EllypticalMirror")
        output_beam = hybrid_control.hy_run(get_hybrid_input_parameters(output_beam,
                                                                        diffraction_plane=1,  # Tangential
                                                                        calcType=3,  # Diffraction by Mirror Size + Errors
                                                                        nf=1,
                                                                        verbose=verbose)).nf_beam

        return output_beam


from beamline34IDC.simulation.source import  GaussianUndulatorSource, StorageRing
from beamline34IDC.simulation.primary_optics_system import PrimaryOpticsSystem, PreProcessorFiles
from beamline34IDC.util.common import plot_shadow_beam_spatial_distribution
from orangecontrib.ml.util.data_structures import DictionaryWrapper

if __name__ == "__main__":
    source = GaussianUndulatorSource()
    source.initialize(n_rays=500000, random_seed=3245345, storage_ring=StorageRing.APS)
    source.set_angular_acceptance_from_aperture(aperture=[0.03, 0.07], distance=50500)
    source.set_energy(energy_range=[5000], photon_energy_distribution=GaussianUndulatorSource.PhotonEnergyDistributions.SINGLE_LINE)

    primary_system = PrimaryOpticsSystem()
    primary_system.initialize(source.get_source_beam(), rewrite_preprocessor_files=PreProcessorFiles.NO)

    input_beam = primary_system.get_beam()

    input_features = DictionaryWrapper(coh_slits_h_aperture=0.03,
                                       coh_slits_h_center=0.0,
                                       coh_slits_v_aperture=0.07,
                                       coh_slits_v_center=0.0,
                                       vkb_p_distance=221,
                                       vkb_motor_4_translation=0.0,
                                       vkb_motor_3_pitch_angle=0.003,
                                       vkb_motor_3_delta_pitch_angle=0.0,
                                       hkb_p_distance=120,
                                       hkb_motor_4_translation=0.0,
                                       hkb_motor_3_pitch_angle=0.003,
                                       hkb_motor_3_delta_pitch_angle=0.0)

    focusing_system = FocusingOpticsSystem()
    focusing_system.initialize(input_beam=input_beam, input_features=input_features,
                               rewrite_preprocessor_files=PreProcessorFiles.NO, rewrite_height_error_profile_files=False)

    output_beam = focusing_system.get_beam(verbose=True)

    plot_shadow_beam_spatial_distribution(output_beam, xrange=None, yrange=None)