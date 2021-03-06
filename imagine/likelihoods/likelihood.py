"""
Likelihood class defines likelihood posterior function
to be used in Bayesian analysis

members:
__init__
    -- initialisation requires
    Measurements object
    Covariances object
    Masks object
__call__
    -- running LOG-likelihood calculation requires
    ObservableDict object
"""

import logging as log

from imagine.observables.observable import Observable
from imagine.observables.observable_dict import Measurements, Simulations, Covariances, Masks
from imagine.tools.icy_decorator import icy


@icy
class Likelihood(object):

    def __init__(self, measurement_dict, covariance_dict=None, mask_dict=None):
        self.mask_dict = mask_dict
        self.measurement_dict = measurement_dict
        self.covariance_dict = covariance_dict

    @property
    def mask_dict(self):
        return self._mask_dict

    @mask_dict.setter
    def mask_dict(self, mask_dict):
        if mask_dict is not None:
            assert isinstance(mask_dict, Masks)
        self._mask_dict = mask_dict

    @property
    def measurement_dict(self):
        return self._measurement_dict

    @measurement_dict.setter
    def measurement_dict(self, measurement_dict):
        assert isinstance(measurement_dict, Measurements)
        self._measurement_dict = measurement_dict
        if self._mask_dict is not None:  # apply mask
            self._measurement_dict.apply_mask(self._mask_dict)

    @property
    def covariance_dict(self):
        return self._covariance_dict

    @covariance_dict.setter
    def covariance_dict(self, covariance_dict):
        if covariance_dict is not None:
            assert isinstance(covariance_dict, Covariances)
        self._covariance_dict = covariance_dict
        if self._mask_dict is not None:  # apply mask
            self._covariance_dict.apply_mask(self._mask_dict)
    
    def __call__(self, observable_dict, variables):
        raise NotImplementedError
