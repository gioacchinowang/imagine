import numpy as np
import logging as log
import os
import pymultinest
from mpi4py import MPI
from imagine.pipelines.pipeline import Pipeline
from imagine.tools.icy_decorator import icy

comm = MPI.COMM_WORLD
mpisize = comm.Get_size()
mpirank = comm.Get_rank()


@icy
class MultinestPipeline(Pipeline):

    def __init__(self, simulator, factory_list, likelihood, prior, ensemble_size=1):
        """
        """
        super(MultinestPipeline, self).__init__(simulator, factory_list, likelihood, prior, ensemble_size)

    def __call__(self):
        """

        :return: pyMultinest sampling results
        """
        # create dir for storing pymultinest output
        path = os.path.join(os.getcwd(),'chains')
        if not os.path.isdir(path):
            try: os.mkdir(path)
            except OSError: pass
        assert (os.path.isdir(path))
        # run pymultinest
        results = pymultinest.solve(LogLikelihood=self._mpi_likelihood,
                                    Prior=self.prior,
                                    n_dims=len(self._active_parameters),
                                    outputfiles_basename='chains/imagine_',
                                    **self._sampling_controllers)
        return results

    def _mpi_likelihood(self, cube):
        """
        mpi log-likelihood calculator
        PyMultinest supports execution with MPI
        where sampler on each node follows different journey in parameter space
        but keep in communication
        so we need to register parameter position on each node
        and calculate log-likelihood value of each node with joint force of all nodes
        in this way, ensemble size is multiplied by the number of working nodes
        :param cube: list of variable values
        :return: log-likelihood value
        """
        # gather cubes from all nodes
        cube_local_size = cube.size
        cube_pool = np.empty(cube_local_size*mpisize, dtype=np.float64)
        comm.Allgather([cube, MPI.DOUBLE], [cube_pool, MPI.DOUBLE])
        # calculate log-likelihood for each node
        loglike_pool = np.empty(mpisize, dtype=np.float64)
        for i in range(mpisize):  # loop through nodes
            cube_local = cube_pool[i*cube_local_size : (i+1)*cube_local_size]
            loglike_pool[i] = self._core_likelihood(cube_local)
        # scatter log-likelihood to each node
        loglike_local = np.empty(1, dtype=np.float64)
        comm.Scatter([loglike_pool, MPI.DOUBLE], [loglike_local, MPI.DOUBLE], root=0)
        return loglike_local

    def _core_likelihood(self, cube):
        """
        core log-likelihood calculator
        cube has been 'broadcasted' in the 2nd step in _mpi_likelihood
        now self._simulator will work on each node and provide multiple ensemble size
        """
        # security boundary check
        if np.any(cube > 1.) or np.any(cube < 0.):
            log.debug('cube %s requested. returned most negative possible number' % str(instant_cube))
            return np.nan_to_num(-np.inf)
        # return active variables from pymultinest cube to factories
        # and then generate new field objects
        head_idx = int(0)
        tail_idx = int(0)
        field_list = tuple()
        # random seeds manipulation
        self._randomness()
        # the ordering in factory list and variable list is vital
        for factory in self._factory_list:
            variable_dict = dict()
            tail_idx = head_idx + len(factory.active_parameters)
            factory_cube = cube[head_idx:tail_idx]
            for i, av in enumerate(factory.active_parameters):
                variable_dict[av] = factory_cube[i]
            field_list += (factory.generate(variables=variable_dict,
                                            ensemble_size=self._ensemble_size,
                                            ensemble_seeds=self._ensemble_seeds),)
            log.debug('create '+factory.name+' field')
            head_idx = tail_idx
        assert(head_idx == len(self._active_parameters))
        observables = self._simulator(field_list)
        # apply mask
        observables.apply_mask(self.likelihood.mask_dict)
        # add up individual log-likelihood terms
        current_likelihood = self.likelihood(observables)
        # check likelihood value until negative (or no larger than given threshold)
        if self._check_threshold and current_likelihood > self._likelihood_threshold:
            raise ValueError('log-likelihood beyond threashould')
        return current_likelihood * self.likelihood_rescaler
