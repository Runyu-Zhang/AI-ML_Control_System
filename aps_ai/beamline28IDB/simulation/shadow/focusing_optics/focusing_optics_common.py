#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------- #
# Copyright (c) 2022, UChicago Argonne, LLC. All rights reserved.         #
#                                                                         #
# Copyright 2022. UChicago Argonne, LLC. This software was produced       #
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
import Shadow
import numpy

from orangecontrib.shadow.util.shadow_objects import ShadowOpticalElement
from orangecontrib.shadow.util.shadow_util import ShadowPhysics

from aps_ai.common.util.shadow.common import TTYInibitor, PreProcessorFiles, write_reflectivity_file, plot_shadow_beam_spatial_distribution
from aps_ai.common.simulation.shadow.focusing_optics import ShadowFocusingOptics
from aps_ai.beamline28IDB.simulation.facade.focusing_optics_interface import AbstractSimulatedFocusingOptics, get_default_input_features

class FocusingOpticsCommon(ShadowFocusingOptics, AbstractSimulatedFocusingOptics):
    def __init__(self):
        super(FocusingOpticsCommon, self).__init__()

        self._h_bendable_mirror_beam = None
        self._v_bimorph_mirror_beam = None
        self._coded_mask_beam = None
        self._h_bendable_mirror = None
        self._v_bimoprh_mirror = None
        self._coded_mask = None

    def initialize(self,
                   input_photon_beam,
                   input_features=get_default_input_features(),
                   **kwargs):

        super(FocusingOpticsCommon, self).initialize(input_photon_beam, input_features, **kwargs)

        try:    rewrite_preprocessor_files = kwargs["rewrite_preprocessor_files"]
        except: rewrite_preprocessor_files = PreProcessorFiles.YES_SOURCE_RANGE


        energies     = ShadowPhysics.getEnergyFromShadowK(self._input_beam._beam.rays[:, 10])
        energy_range = [numpy.min(energies), numpy.max(energies)]

        if rewrite_preprocessor_files   == PreProcessorFiles.YES_FULL_RANGE:     reflectivity_file = write_reflectivity_file()
        elif rewrite_preprocessor_files == PreProcessorFiles.YES_SOURCE_RANGE: reflectivity_file = write_reflectivity_file(energy_range=energy_range)
        elif rewrite_preprocessor_files == PreProcessorFiles.NO:               reflectivity_file = "Pt.dat"

        h_bendable_mirror_error_profile_file = "H-Bendable-Mirror_shadow.dat"

        self._initialize_mirrors(input_features, reflectivity_file, h_bendable_mirror_error_profile_file)

        coded_mask = Shadow.OE()
        coded_mask.DUMMY = 0.1
        coded_mask.FWRITE = 3
        coded_mask.F_REFRAC = 2
        coded_mask.F_SCREEN = 1
        coded_mask.I_SLIT = numpy.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        coded_mask.N_SCREEN = 1
        coded_mask.RX_SLIT = numpy.array([0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        coded_mask.RZ_SLIT = numpy.array([0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        coded_mask.T_IMAGE      = 500.0
        coded_mask.T_INCIDENCE  = 0.0
        coded_mask.T_REFLECTION = 180.0
        coded_mask.T_SOURCE     = 2500.0

        self._coded_mask = ShadowOpticalElement(coded_mask)

        self._modified_elements = [self._h_bendable_mirror, self._v_bimoprh_mirror, self._coded_mask]

        #####################################################################################
        # This methods represent the run-time interface, to interact with the optical system
        # in real time, like in the real beamline

    #####################################################################################
    # Run the simulation

    def get_photon_beam(self, near_field_calculation=False, remove_lost_rays=True, **kwargs):
        try:    verbose = kwargs["verbose"]
        except: verbose = False
        try:    debug_mode = kwargs["debug_mode"]
        except: debug_mode = False
        try:    random_seed = kwargs["random_seed"]
        except: random_seed = None

        if self._input_beam is None: raise ValueError("Focusing Optical System is not initialized")

        self._input_beam = self._check_beam(self._input_beam, "Primary Optical System", remove_lost_rays)

        if not verbose:
            fortran_suppressor = TTYInibitor()
            fortran_suppressor.start()

        output_beam = None

        try:
            run_all = self._modified_elements == [] or len(self._modified_elements) == 3

            if run_all or self._h_bendable_mirror in self._modified_elements:
                self._h_bendable_mirror_beam = self._trace_h_bendable_mirror(random_seed, remove_lost_rays, verbose)
                output_beam    = self._h_bendable_mirror_beam

                if debug_mode: plot_shadow_beam_spatial_distribution(self._h_bendable_mirror_beam, title="H-Bendable-Mirror", xrange=None, yrange=None)

            if run_all or self._v_bimoprh_mirror in self._modified_elements:
                self._v_bimorph_mirror_beam = self._trace_v_bimoprh_mirror(random_seed, remove_lost_rays, verbose)
                output_beam    = self._v_bimorph_mirror_beam

                if debug_mode: plot_shadow_beam_spatial_distribution(self._v_bimorph_mirror_beam, title="V-Bimorph-Mirror", xrange=None, yrange=None)

            if run_all or self._coded_mask in self._modified_elements:
                self._coded_mask_beam = self._trace_oe(self._v_bimorph_mirror_beam,
                                                       self._coded_mask,
                                                       "Screen-Slits",
                                                       "Coded-Mask",
                                                       remove_lost_rays,
                                                       history=False)
                output_beam    = self._coded_mask_beam

                if debug_mode: plot_shadow_beam_spatial_distribution(self._v_bimorph_mirror_beam, title="V-Bimorph-Mirror", xrange=None, yrange=None)

            # after every run, the list of modified elements must be empty
            self._modified_elements = []

        except Exception as e:
            if not verbose:
                try:    fortran_suppressor.stop()
                except: pass

            raise e
        else:
            if not verbose:
                try:    fortran_suppressor.stop()
                except: pass

        return output_beam.duplicate(history=False)

    def _trace_h_bendable_mirror(self, random_seed, remove_lost_rays, verbose): raise NotImplementedError()
    def _trace_v_bimoprh_mirror(self,  random_seed, remove_lost_rays, verbose): raise NotImplementedError()
    def _initialize_mirrors(self, input_features, reflectivity_file, h_bendable_mirror_error_profile_file): raise NotImplementedError()
