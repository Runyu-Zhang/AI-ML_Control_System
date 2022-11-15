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
from copy import deepcopy
from typing import Callable, Dict, List, NoReturn, Optional, Union

import numpy as np
import optuna
from optuna.trial import Trial

from aps.ai.autoalignment.beamline28IDB.optimization import common, configs

# from matplotlib import pyplot as plt
from aps.ai.autoalignment.beamline28IDB.optimization.custom_botorch_integration import (
    BoTorchSampler,
    qehvi_candidates_func,
    qei_candidates_func,
    qnehvi_candidates_func,
    qnei_candidates_func,
)


class OptunaOptimizer(common.OptimizationCommon):
    opt_platform = "optuna"
    acquisition_functions = {
        "qei": qei_candidates_func,
        "qnei": qnei_candidates_func,
        "qehvi": qehvi_candidates_func,
        "qnehvi": qnehvi_candidates_func,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.best_params = None
        self.motor_ranges = None
        self.study = None
        self._constraints = None
        self._raise_prune_exception = None
        self._base_sampler = None
        self._sum_intensity_threshold = None
        self._loss_fn_this = None
        self._use_discrete_space = None

    def set_optimizer_options(
        self,
        motor_ranges: list = None,
        base_sampler: optuna.samplers.BaseSampler = None,
        directions: Dict = None,
        sum_intensity_threshold: float = 1e2,
        raise_prune_exception: bool = True,
        acquisition_function: Union[Callable, str] = None,
        moo_thresholds: Dict = None,
        botorch_seed: int = None,
        use_discrete_space: bool = True,
        constraints: Dict = None,
        n_startup_trials: Optional[int] = None,
        botorch_model_mean_module: Optional[object] = None,
        botorch_model_covar_module: Optional[object] = None,
    ):

        self.motor_ranges = self._get_guess_ranges(motor_ranges)

        directions_list = self._check_directions(directions)
        # Creating the acquisition function
        if acquisition_function is None:
            if self._multi_objective_optimization:

                def acquisition_function(*args, **kwargs):
                    thresholds_list = self._check_thresholds(moo_thresholds, directions_list)
                    return self.acquisition_functions["qnehvi"](*args, ref_point=thresholds_list, **kwargs)

            else:
                acquisition_function = self.acquisition_functions["qnei"]

        elif isinstance(acquisition_function, str):
            if acquisition_function not in self.acquisition_functions:
                raise ValueError
            acquisition_function = self.acquisition_functions[acquisition_function]

        # Setting up the constraints
        self._constraints = OptunaOptimizer._check_constraints(constraints)

        # Initializing the sampler
        seed = self.random_seed if botorch_seed is None else botorch_seed
        if base_sampler is None:
            sampler_extra_options = {}
            if self._constraints is not None:
                sampler_extra_options["constraints_func"] = self._constraints_func
            if n_startup_trials is not None:
                sampler_extra_options["n_startup_trials"] = n_startup_trials
            sampler_extra_options["model_mean_module"] = botorch_model_mean_module
            sampler_extra_options["model_covar_module"] = botorch_model_covar_module
            base_sampler = BoTorchSampler(candidates_func=acquisition_function, seed=seed, **sampler_extra_options)
        self._base_sampler = base_sampler
        self._raise_prune_exception = raise_prune_exception

        self.study = optuna.create_study(sampler=self._base_sampler, directions=directions_list)
        self.study.enqueue_trial({mt: 0.0 for mt in self.motor_types})

        loss_fn_obj = self.TrialInstanceLossFunction(self, verbose=False)
        self._loss_fn_this = loss_fn_obj.loss
        self._sum_intensity_threshold = sum_intensity_threshold
        self._use_discrete_space = use_discrete_space

        self.best_params = {k: 0.0 for k in self.motor_types}

    def _check_directions(self, directions: Dict) -> List:

        if directions is None:
            return ["minimize" for k in self.loss_parameters]
        directions_list = []
        for k in self.loss_parameters:
            if k not in directions:
                raise ValueError
            if directions[k] not in ["minimize", "maximize"]:
                raise ValueError
            directions_list.append(directions[k])
        return directions_list

    def _check_thresholds(self, thresholds: Dict, directions_list: List) -> Union[List, None]:
        if thresholds is None:
            return None

        thresholds_list = []
        for i, k in enumerate(self.loss_parameters):
            if k not in thresholds:
                raise ValueError
            v = np.abs(thresholds[k])
            if directions_list[i] == "minimize":
                v *= -1
            thresholds_list.append(v)
        return thresholds_list

    @staticmethod
    def _check_constraints(constraints: Dict):
        if constraints is None:
            return None
        for constraint in constraints:
            if constraint not in configs.DEFAULT_CONSTRAINT_OPTIONS:
                raise ValueError
        return constraints

    def _constraints_func(self, trial):
        constraint_vals = []
        for constraint_type in self._constraints:
            constraint_vals.append(trial.user_attrs[f"{constraint_type}_constraint"])
        return constraint_vals

    def _set_trial_constraints(self, trial: Trial) -> NoReturn:
        if self._constraints is None:
            return
        minimize_constraint_fns = {
            "centroid": self.get_centroid_distance,
            "sigma": self.get_sigma,
            "fwhm": self.get_fwhm,
        }
        maximize_constraint_fns = {
            "sum_intensity": self.get_sum_intensity,
            "peak_intensity": self.get_peak_intensity,
        }
        for constraint, threshold in self._constraints.items():
            if constraint in minimize_constraint_fns:
                x = minimize_constraint_fns[constraint]()
                value = -2 * (x < threshold) + 1
            else:
                x = maximize_constraint_fns[constraint]()
                value = -2 * (x > threshold) + 1
            trial.set_user_attr(f"{constraint}_constraint", value)
        return

    def _prune_trial(self, params):
        print("Pruning trial with parameters", params)
        raise optuna.TrialPruned

    def _objective(self, trial: Trial, step_scale: float = 1):

        current_params = []
        for mot, r in zip(self.motor_types, self.motor_ranges):
            if self._use_discrete_space:
                resolution = np.round(configs.DEFAULT_MOTOR_RESOLUTIONS[mot], 5)
                r_low = np.round(r[0], 5)
                r_high = ((r[1] - r[0]) // resolution) * resolution + r_low
                current_params.append(trial.suggest_float(mot, r_low, r_high, step=resolution * step_scale))
            else:
                current_params.append(trial.suggest_float(mot, r[0], r[1]))

        loss = self._loss_fn_this(current_params)

        self._set_trial_constraints(trial)
        if self._multi_objective_optimization:
            if np.nan in np.atleast_1d(loss):
                if self._raise_prune_exception:
                    self._prune_trial(current_params)
                loss[np.isnan(loss)] = 1e4

            if self._sum_intensity_threshold is not None:
                if self.beam_state.hist.data_2D.sum() < self._sum_intensity_threshold:
                    if self._raise_prune_exception:
                        self._prune_trial(current_params)
                    else:
                        return [1e4] * len(self._loss_function_list)

            for k in ["sigma", "fwhm"]:
                if k in self.loss_parameters:
                    width_idx = self.loss_parameters.index(k)
                    if loss[width_idx] == 0:
                        loss[width_idx] = 1e4
            loss = list(loss)
        else:
            if np.isnan(loss):
                if self._raise_prune_exception:
                    self._prune_trial(current_params)
                loss = 1e4

            if self._sum_intensity_threshold is not None:
                if self.beam_state.hist.data_2D.sum() < self._sum_intensity_threshold:
                    if self._raise_prune_exception:
                        self._prune_trial(current_params)
                    else:
                        return 1e4

            for k in ["sigma", "fwhm"]:
                if k in self.loss_parameters:
                    if loss == 0:
                        loss = 1e4

        # plt.pcolormesh(self.beam_state.hist.hh, self.beam_state.hist.vv, self.beam_state.hist.data_2D)
        # plt.title(str(self.beam_state.hist.data_2D.sum()))
        # plt.show()
        trial.set_user_attr("dw", deepcopy(self.beam_state.dw))

        return loss

    def trials(self, n_trials: int, trial_motor_types: list = None, step_scale: float = 1):

        obj_this = lambda t: self._objective(t, step_scale=step_scale)

        if trial_motor_types is None:
            self.study.optimize(obj_this, n_trials)
        else:
            fixed_params = {k: self.best_params[k] for k in self.best_params if k not in trial_motor_types}
            partial_sampler = optuna.samplers.PartialFixedSampler(fixed_params, self._base_sampler)

            self.study.sampler = partial_sampler
            self.study.optimize(obj_this, n_trials=n_trials)

            self.study.sampler = self._base_sampler

        self.best_params.update(self.study.best_trials[0].params)

    def select_best_trial_params(self, trials):
        rms_metrics = []
        for t in trials:
            vals = t.values
            rms_metrics.append(np.sum(np.array(vals) ** 2) ** 0.5)
        idx = np.argmin(rms_metrics)
        return trials[idx].params, trials[idx].values

    # def trials(self, n_guesses = 1, verbose: bool = False, accept_all_solutions: bool = False):
    #    pass

    def _optimize(self) -> NoReturn:
        pass

    # def set_optimizer_options(self):
    #    pass