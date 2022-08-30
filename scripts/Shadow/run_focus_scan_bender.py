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
import os, numpy
import sys

from beamline34IDC.simulation.facade import Implementors
from beamline34IDC.facade.focusing_optics_factory import focusing_optics_factory_method, ExecutionMode
from beamline34IDC.facade.focusing_optics_interface import Movement, DistanceUnits
from beamline34IDC.simulation.facade.focusing_optics_interface import get_default_input_features

from beamline34IDC.util.shadow.common import get_shadow_beam_spatial_distribution, plot_shadow_beam_spatial_distribution, load_shadow_beam, PreProcessorFiles
from beamline34IDC.util import clean_up
from beamline34IDC.util.wrappers import PlotMode

from matplotlib import cm
from matplotlib import pyplot as plt

def plot_3D(xx, yy, zz, label):

    figure = plt.figure(figsize=(10, 7))
    figure.patch.set_facecolor('white')

    axis = figure.add_subplot(111, projection='3d')
    axis.set_zlabel(label + " [mm]")
    axis.set_xlabel("Abs pos up [mm]")
    axis.set_ylabel("Abs pos down [mm]")

    x_to_plot, y_to_plot = numpy.meshgrid(xx, yy)

    axis.plot_surface(x_to_plot, y_to_plot, zz, rstride=1, cstride=1, cmap=cm.autumn, linewidth=0.5, antialiased=True)
    plt.show()


if __name__ == "__main__":
    verbose = False

    os.chdir("../../work_directory")

    clean_up()

    input_beam = load_shadow_beam("primary_optics_system_beam.dat")

    # Focusing Optics System -------------------------

    focusing_system = focusing_optics_factory_method(execution_mode=ExecutionMode.SIMULATION, implementor=Implementors.SHADOW, bender=2)

    input_features = get_default_input_features()
    input_features.set_parameter("coh_slits_h_aperture", 0.03)
    input_features.set_parameter("coh_slits_v_aperture", 0.07)
    input_features.set_parameter("vkb_motor_1_bender_position", 138.0)
    input_features.set_parameter("vkb_motor_2_bender_position", 243.5)
    input_features.set_parameter("hkb_motor_1_bender_position", 215.5)
    input_features.set_parameter("hkb_motor_2_bender_position", 110.5)

    focusing_system.initialize(input_photon_beam=input_beam,
                               input_features=input_features,
                               rewrite_preprocessor_files=PreProcessorFiles.NO,
                               rewrite_height_error_profile_files=False)

    print("Initial V-KB bender positions and q (up, down) ",
          focusing_system.get_vkb_motor_1_bender(units=DistanceUnits.MICRON),
          focusing_system.get_vkb_motor_2_bender(units=DistanceUnits.MICRON),
          focusing_system.get_vkb_q_distance())
    print("Initial H-KB bender positions and q (up, down)",
          focusing_system.get_hkb_motor_1_bender(units=DistanceUnits.MICRON),
          focusing_system.get_hkb_motor_2_bender(units=DistanceUnits.MICRON),
          focusing_system.get_hkb_q_distance())

    random_seed = 2120 # for repeatability

    output_beam = focusing_system.get_photon_beam(verbose=verbose, near_field_calculation=True, debug_mode=False, random_seed=random_seed)

    v_pos_up   = focusing_system.get_vkb_motor_1_bender(units=DistanceUnits.MICRON)
    v_pos_down = focusing_system.get_vkb_motor_2_bender(units=DistanceUnits.MICRON)
    h_pos_up   = focusing_system.get_hkb_motor_1_bender(units=DistanceUnits.MICRON)
    h_pos_down = focusing_system.get_hkb_motor_2_bender(units=DistanceUnits.MICRON)

    n_points = 31
    rel_pos = [-15, 15]

    v_abs_pos_up   = numpy.linspace(rel_pos[0], rel_pos[1], n_points) + v_pos_up
    v_abs_pos_down = numpy.linspace(rel_pos[0], rel_pos[1], n_points) + v_pos_down
    h_abs_pos_up   = numpy.linspace(rel_pos[0], rel_pos[1], n_points) + h_pos_up
    h_abs_pos_down = numpy.linspace(rel_pos[0], rel_pos[1], n_points) + h_pos_down

    sigma_v = numpy.zeros((len(v_abs_pos_up), len(v_abs_pos_down)))
    fwhm_v  = numpy.zeros((len(v_abs_pos_up), len(v_abs_pos_down)))
    sigma_h = numpy.zeros((len(h_abs_pos_up), len(h_abs_pos_down)))
    fwhm_h  = numpy.zeros((len(h_abs_pos_up), len(h_abs_pos_down)))

    positions_v = numpy.zeros((2, n_points))
    positions_v[0, :] = v_abs_pos_up
    positions_v[1, :] = v_abs_pos_down
    positions_h = numpy.zeros((2, n_points))
    positions_h[0, :] = h_abs_pos_up
    positions_h[1, :] = h_abs_pos_down
    with open("positions_v.npy", 'wb') as f: numpy.save(f, positions_v, allow_pickle=False)
    with open("positions_h.npy", 'wb') as f: numpy.save(f, positions_h, allow_pickle=False)

    for i in range(n_points):
        focusing_system.move_vkb_motor_1_bender(pos_upstream=v_abs_pos_up[i],
                                                movement=Movement.ABSOLUTE,
                                                units=DistanceUnits.MICRON)
        focusing_system.move_hkb_motor_1_bender(pos_upstream=h_abs_pos_up[i],
                                                movement=Movement.ABSOLUTE,
                                                units=DistanceUnits.MICRON)

        for j in range(n_points):
            focusing_system.move_vkb_motor_2_bender(pos_downstream=v_abs_pos_down[j],
                                                    movement=Movement.ABSOLUTE,
                                                    units=DistanceUnits.MICRON)
            focusing_system.move_hkb_motor_2_bender(pos_downstream=h_abs_pos_down[j],
                                                    movement=Movement.ABSOLUTE,
                                                    units=DistanceUnits.MICRON)

            try:
                _, dict = get_shadow_beam_spatial_distribution(focusing_system.get_photon_beam(verbose=verbose,
                                                                                               near_field_calculation=True,
                                                                                               debug_mode=False,
                                                                                               random_seed=random_seed),
                                                               nbins=201, xrange=[-0.01, 0.01], yrange=[-0.01, 0.01])

                sigma_v[i, j] = dict.get_parameter("v_sigma")
                fwhm_v[i, j]  = dict.get_parameter("v_fwhm")
                sigma_h[i, j] = dict.get_parameter("h_sigma")
                fwhm_h[i, j]  = dict.get_parameter("h_fwhm")
            except:
                pass

            #print("V-KB absolute movement (U,D): " + str(abs_pos_up[i]) + "," + str(abs_pos_down[j]),
            #      focusing_system.get_vkb_q_distance())

        print("Percentage completed: " + str(round(100*(1+i)*n_points / n_points**2, 2)))

    with open("sigma_v.npy", 'wb') as f: numpy.save(f, sigma_v, allow_pickle=False)
    with open("fwhm_v.npy", 'wb')  as f: numpy.save(f, fwhm_v, allow_pickle=False)
    with open("sigma_h.npy", 'wb') as f: numpy.save(f, sigma_h, allow_pickle=False)
    with open("fwhm_h.npy", 'wb')  as f: numpy.save(f, fwhm_h, allow_pickle=False)

    plot_3D(v_abs_pos_up, v_abs_pos_down, sigma_v, "Sigma (V)")
    plot_3D(h_abs_pos_up, h_abs_pos_down, sigma_h, "Sigma (H)")
    plot_3D(v_abs_pos_up, v_abs_pos_down, fwhm_v, "FWHM (V)")
    plot_3D(h_abs_pos_up, h_abs_pos_down, fwhm_h, "FWHM (H)")

    clean_up()
