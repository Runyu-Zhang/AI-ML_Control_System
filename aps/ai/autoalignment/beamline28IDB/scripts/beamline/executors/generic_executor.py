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
import time

from aps.common.scripts.abstract_script import AbstractScript
from aps.common.traffic_light import get_registered_traffic_light_instance

from aps.ai.autoalignment.beamline28IDB.scripts.beamline import AA_28ID_BEAMLINE_SCRIPTS

class GenericScript(AbstractScript):

    def __init__(self, root_directory, energy, period, n_cycles, mocking_mode):
        self._root_directory = root_directory
        self._energy         = energy
        self.__mocking_mode   = mocking_mode
        self.__period        = period * 60.0 # in seconds
        self.__n_cycles      = n_cycles

        self.__initialize_traffic_light()

    def execute_script(self, **kwargs):
        cycles = 0

        try:
            while(cycles < self.__n_cycles):
                cycles += 1
                self.__traffic_light.request_red_light()

                print("Running " + self._get_script_name() + " #" + str(cycles))

                if self.__mocking_mode:
                    print("Mocking Mode: do nothing and wait 5 second")
                    time.sleep(5)
                else:
                    self._execute_script_inner(**kwargs)

                self.__traffic_light.set_green_light()

                print(self._get_script_name() + " #" + str(cycles) + " completed.\n"
                      "Pausing for " + str(self.__period) + " seconds.")

                time.sleep(self.__period)
        except Exception as e:
            try:    self.__traffic_light.set_green_light()
            except: pass

            print("Script interrupted by the following exception:\n" + str(e))

    def manage_keyboard_interrupt(self):
        print("\n" + self._get_script_name() + " interrupted by user")

        try:    self.__traffic_light.set_green_light()
        except: pass

    def __initialize_traffic_light(self):
        self.__traffic_light = get_registered_traffic_light_instance(application_name=AA_28ID_BEAMLINE_SCRIPTS)

    def _execute_script_inner(self, **kwargs): raise NotImplementedError()
    def _get_script_name(self): raise NotImplementedError()