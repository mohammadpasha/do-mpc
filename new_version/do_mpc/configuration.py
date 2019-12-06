#
#   This file is part of do-mpc
#
#   do-mpc: An environment for the easy, modular and efficient implementation of
#        robust nonlinear model predictive control
#
#   Copyright (c) 2014-2019 Sergio Lucia, Alexandru Tatulea-Codrean
#                        TU Dortmund. All rights reserved
#
#   do-mpc is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Lesser General Public License as
#   published by the Free Software Foundation, either version 3
#   of the License, or (at your option) any later version.
#
#   do-mpc is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Lesser General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with do-mpc.  If not, see <http://www.gnu.org/licenses/>.

import numpy as np
from casadi import *
from casadi.tools import *
import pdb
import do_mpc
import matplotlib.pyplot as plt

class configuration:
    def __init__(self, simulator, optimizer, estimator, x0=None):
        self.simulator = simulator
        self.optimizer = optimizer
        self.estimator = estimator

        self.graphics = do_mpc.backend_graphics()

        if x0 is not None:
            # Set global intial condition.
            self.simulator.set_initial_state(x0)
            self.optimizer.set_initial_state(x0)
            self.estimator.set_initial_state(x0)

        #self.store_initial_state()

    def set_initial_state(self, x0, reset_history=False):
        """Triggers the set_initial_state method for

        * simulator

        * optimizer

        * estimator

        to reset the intial state for all objects to the same value.
        Optionally resets the history of all objects.
        Note that if the intial state was not chosen explicitly for the individual objects (simulator, optimizer, estimator),
        it defaults to zero and this value was written to the history upon creating the configuration object.

        :param x0: Initial state of the configuration
        :type x0: numpy array
        :param reset_history: Resets the history of the configuration objects, defaults to False
        :type reset_history: bool (,optional)

        :return: None
        :rtype: None
        """
        self.simulator.set_initial_state(x0, reset_history=reset_history)
        self.optimizer.set_initial_state(x0, reset_history=reset_history)
        self.estimator.set_initial_state(x0, reset_history=reset_history)


    def make_step_optimizer(self):
        x0 = self.optimizer._x0
        u_prev = self.optimizer._u0
        tvp0 = self.optimizer.tvp_fun(self.optimizer._t0)
        p0 = self.optimizer.p_fun(self.optimizer._t0)
        t0 = self.optimizer._t0

        self.optimizer.opt_p_num['_x0'] = x0
        self.optimizer.opt_p_num['_u_prev'] = u_prev
        self.optimizer.opt_p_num['_tvp'] = tvp0['_tvp']
        self.optimizer.opt_p_num['_p'] = p0['_p']
        self.optimizer.solve()

        u0 = self.optimizer._u0 = self.optimizer.opt_x_num['_u', 0, 0]
        z0 = self.optimizer._z0 = self.optimizer.opt_x_num['_z', 0, 0, 0]

        self.optimizer.data.update(_x = x0)
        self.optimizer.data.update(_u = u0)
        self.optimizer.data.update(_z = z0)
        # self.optimizer.data.update(_tvp = tvp0)
        # self.optimizer.data.update(_p = p0)
        self.optimizer.data.update(_time = t0)

        if self.optimizer.store_full_solution == True:
            opt_x_num = self.optimizer.opt_x_num
            self.optimizer.data.update(_opt_x_num = opt_x_num)

        self.optimizer._t0 = self.optimizer._t0 + self.optimizer.t_step


    def make_step_simulator(self):
        tvp0 = self.simulator.tvp_fun(self.simulator._t0)
        p0 = self.simulator.p_fun(self.simulator._t0)
        x0 = self.simulator._x0
        u0 = self.optimizer._u0
        z0 = self.optimizer._z0 # This is just an initial guess.
        t0 = self.simulator._t0

        self.simulator.sim_x_num['_x'] = x0
        self.simulator.sim_x_num['_z'] = z0
        self.simulator.sim_p_num['_u'] = u0
        self.simulator.sim_p_num['_p'] = p0
        self.simulator.sim_p_num['_tvp'] = tvp0

        self.simulator.simulate()

        x_next = self.simulator.sim_x_num['_x']
        z0 = self.simulator.sim_x_num['_z']

        self.simulator.data.update(_x = x0)
        self.simulator.data.update(_u = u0)
        self.simulator.data.update(_z = z0)
        self.simulator.data.update(_tvp = tvp0)
        self.simulator.data.update(_p = p0)
        self.simulator.data.update(_time = t0)

        self.simulator._x0 = x_next
        self.simulator._t0 = self.simulator._t0 + self.simulator.t_step

    def make_step_estimator(self):
        # Should we not call the estimator prior to the optimization and simulator?
        # Usually a more complex mapping:
        self.estimator._x0 = self.simulator._x0

        self.optimizer._x0 = self.estimator._x0

        # t0 = self.estimator._t0 = self.estimator._t0 + self.estimator.t_step
        # self.estimator.data.update(_time = t0)

    def setup_graphic(self, _x=[], _u=[], _z=[]):
        """High Level API to create a graphic straight from the configuration.
        """
        assert isinstance(_x, list), 'param _x must be type list. You have: {}'.format(type(_x))
        assert isinstance(_u, list), 'param _u must be type list. You have: {}'.format(type(_u))
        assert isinstance(_z, list), 'param _z must be type list. You have: {}'.format(type(_z))

        # Check if variables were selected for plotting and if they exist in the model.
        # By default: Choose all states and inputs for plotting.
        if not _x:
            _x = self.optimizer.model._x.keys()
        elif not set(_x).issubset(set(self.optimizer.model._x.keys())):
            raise Exception('The given list for _x contains elements that were not defined in the model.')
        if not _u:
            _u = self.optimizer.model._u.keys()
            # Remove "default" element.
            _u.pop(0)
        elif not set(_u).issubset(set(self.optimizer.model._u.keys())):
            raise Exception('The given list for _u contains elements that were not defined in the model.')
        if not _z:
            #by default _z is not plotted.
            pass
        elif not set(_z).issubset(set(self.optimizer.model._z.keys())):
            raise Exception('The given list for _z contains elements that were not defined in the model.')

        n_plt_x = len(_x)
        n_plt_u = len(_u)
        n_plt_z = len(_z)
        n_plt_tot = n_plt_x + n_plt_u + n_plt_z

        fig, ax = plt.subplots(n_plt_tot, sharex=True)

        for i, _x_i in enumerate(_x):
            self.graphics.add_line(var_type='_x', var_name=_x_i, axis=ax[i])
            ax[i].set_ylabel(_x_i)
        for i, _u_i in enumerate(_u, n_plt_x):
            self.graphics.add_line(var_type='_u', var_name=_u_i, axis=ax[i])
            ax[i].set_ylabel(_u_i)
        for i, _z_i in enumerate(_z, n_plt_x+n_plt_u):
            self.graphics.add_line(var_type='_z', var_name=_z_i, axis=ax[i])
            ax[i].set_ylabel(_z_i)

        ax[-1].set_xlabel('time')

        self.graphics.fig = fig
        plt.ion()

        return fig, ax

    def plot_animation(self):
        self.graphics.reset_axes()
        self.graphics.plot_results(self.optimizer.data)
        self.graphics.plot_predictions(self.optimizer.data, linestyle='--')
        self.graphics.fig.align_ylabels()
        self.graphics.fig.show()
        input('Press enter to continue the loop. Press Ctrl-C followed by enter to stop.')

    def plot_results(self):
        self.graphics.plot_results(self.optimizer.data)
        self.graphics.fig.align_ylabels()
        self.graphics.fig.show()
