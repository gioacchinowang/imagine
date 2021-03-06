"""
for convenience we define dictionary of Observable objects as
ObservableDict and inherit from which,
we define Measurements, Covariances, Simulations and Masks
for storing
    -- observational data sets
    -- observational covariances
    -- simulated ensemble sets
    -- HEALPix mask maps
separately

by HEALPix convention,
masked erea associated with pixel value 0,
unmasked area with pixel value 1

notice covariance matrix should not have Observable structure,
instead, it can be a single domain NIFTy5 Field or numpy ndarray,
nevertheless, we make ObservableDict flexible enough

observable name/unit convention:
* ('fd','nan',str(size/Nside),'nan')
    -- Faraday depth (in unit
* ('dm','nan',str(pix),'nan')
    -- dispersion measure (in unit
* ('sync',str(freq),str(pix),X)
    -- synchrotron emission
    X stands for:
    * 'I'
        -- total intensity (in unit K-cmb)
    * 'Q'
        -- Stokes Q (in unit K-cmb, IAU convention)
    * 'U'
        -- Stokes U (in unit K-cmb, IAU convention)
    * 'PI'
        -- polarisation intensity (in unit K-cmb)
    * 'PA'
        -- polarisation angle (in unit rad, IAU convention)

remarks on observable name:
    -- str(freq), polarisation-related-flag are redundant for Faraday depth and dispersion measure
    so we put 'nan' instead
    -- str(pix/nside) stores either Healpix Nisde, or just number of pixels/points
    we do this for flexibility, in case users have non-HEALPix based in/output

mask method:
    -- mask only applies to observables/covariances
    observable after masking will be re-recorded as plain data type

distribution with MPI
    -- Measurements is non-distributed (precsely speaking, distributed in NIFTy style)
    -- Masks, Simulations and Covariances are distributed
    -- Masks has Observable object with shape (mpisize, data_size)
    -- Covariances has Field object with shape "around" (data_size//mpisize, data_size)
    "around" means to distribute matrix correctly
    -- Simulations has Observable object with shape (N*mpisize, data_size)
    -- Measurements has Observable object with shape (1, data_size),
    the shape of local_data on slave nodes are (0, data_size)
"""

import numpy as np
import logging as log

import mpi4py

from nifty5 import Field, RGSpace, HPSpace, DomainTuple

from imagine.observables.observable import Observable
from imagine.tools.masker import mask_obs, mask_cov
from imagine.tools.icy_decorator import icy

comm = mpi4py.MPI.COMM_WORLD
mpisize = comm.Get_size()
mpirank = comm.Get_rank()


@icy
class ObservableDict(object):
    """
    add/update name and data with function .append
    """
    def __init__(self):
        self._archive = dict()

    @property
    def archive(self):
        return self._archive

    def keys(self):
        return self._archive.keys()
    
    def __getitem__(self, key):
        return self._archive[key]

    def append(self, name, data, plain=False):
        """

        :param name: str tuple
        notice: name should follow convention
        (data-name,str(data-freq),str(data-Nside/size),str(pol))
        if data is independent from frequency, set 'nan'
        pol should be either 'I','Q','U','PI','PA' or 'nan'

        :param data: distributed ndarray/Field/Observable

        :param plain: if True, means unstructured data
        if False(default), means healpix structured sky map

        :return:
        """
        pass

    def apply_mask(self, mask_dict):
        """
        apply mask maps
        :param mask_dict: Masks object
        """
        pass


@icy
class Masks(ObservableDict):

    def __init__(self):
        super(Masks, self).__init__()

    def append(self, name, data, plain=False):
        """
        
        :param name:
        :param data: distributed
        :param plain:
        :return:
        """
        assert (len(name) == 4)
        if isinstance(data, Observable):
            assert (data.shape[0] == mpisize)
            raw_data = data.local_data
            for i in raw_data[0]:
                assert (i == float(0) or i == float(1))
            self._archive.update({name: data})
        elif isinstance(data, Field):
            assert (data.shape[0] == mpisize)
            raw_data = data.local_data
            for i in raw_data[0]:
                assert (i == float(0) or i == float(1))
            self._archive.update({name: Observable(data.domain, data.local_data)})
        elif isinstance(data, np.ndarray):
            assert (data.shape[0] == 1)
            for i in data[0]:
                assert (i == float(0) or i == float(1))
            if plain:
                assert (data.shape[1] == int(name[2]))
                domain = DomainTuple.make((RGSpace(mpisize), RGSpace(data.shape[1])))
            else:
                assert (data.shape[1] == 12*int(name[2])*int(name[2]))              
                domain = DomainTuple.make((RGSpace(mpisize), HPSpace(nside=int(name[2]))))
            self._archive.update({name: Observable(domain, data)})
        else:
            raise TypeError('unsupported data type')
        log.debug('mask-dict appends data %s' % str(name))


@icy
class Measurements(ObservableDict):

    def __init__(self):
        super(Measurements, self).__init__()

    def append(self, name, data, plain=False):
        """
        
        :param name:
        :param data: distributed
        :param plain:
        :return:
        """
        assert (len(name) == 4)
        if isinstance(data, Observable):
            assert (data.shape[0] == 1)
            self._archive.update({name: data})  # rw
        elif isinstance(data, Field):
            assert (data.shape[0] == 1)
            self._archive.update({name: Observable(data.domain, data.local_data)})  # rw
        # reading from numpy array takes information only on master node
        elif isinstance(data, np.ndarray):
            assert (data.shape[0] == 1)
            if plain:
                assert (data.shape[1] == int(name[2]))
                domain = DomainTuple.make((RGSpace(int(1)), RGSpace(data.shape[1])))
            else:
                assert (data.shape[1] == 12*int(name[2])*int(name[2]))
                domain = DomainTuple.make((RGSpace(int(1)), HPSpace(nside=int(name[2]))))
            self._archive.update({name: Observable(domain, data)})  # rw
        else:
            raise TypeError('unsupported data type')
        log.debug('measurements-dict appends data %s' % str(name))

    def apply_mask(self, mask_dict):
        if mask_dict is None:
            pass
        else:
            assert isinstance(mask_dict, Masks)
            for name, msk in mask_dict._archive.items():
                if name in self._archive.keys():
                    masked = mask_obs(self._archive[name].to_global_data(), msk.local_data)
                    new_name = (name[0], name[1], str(masked.shape[1]), name[3])
                    self._archive.pop(name, None)  # pop out obsolete
                    self.append(new_name, masked, plain=True)  # append new as plain data


@icy
class Simulations(ObservableDict):

    def __init__(self):
        super(Simulations, self).__init__()

    def append(self, name, data, plain=False):
        """
        
        :param name:
        :param data: distributed
        :param plain:
        :return:
        """
        assert (len(name) == 4)
        if name in self._archive.keys():  # app
            self._archive[name].append(data)
        else:  # new
            if isinstance(data, Observable):
                self._archive.update({name: data})
            elif isinstance(data, Field):
                self._archive.update({name: Observable(data.domain, data.local_data)})
            elif isinstance(data, np.ndarray):  # distributed data
                if plain:
                    assert (data.shape[1] == int(name[2]))
                    domain = DomainTuple.make((RGSpace(data.shape[0]*mpisize), RGSpace(data.shape[1])))
                else:
                    assert (data.shape[1] == 12*int(name[2])*int(name[2]))
                    domain = DomainTuple.make((RGSpace(data.shape[0]*mpisize), HPSpace(nside=int(name[2]))))
                self._archive.update({name: Observable(domain, data)})
            else:
                raise TypeError('unsupported data type')
        log.debug('observable-dict appends data %s' % str(name))

    def apply_mask(self, mask_dict):
        if mask_dict is None:
            pass
        else:
            assert isinstance(mask_dict, Masks)
            for name, msk in mask_dict._archive.items():
                if name in self._archive.keys():
                    masked = mask_obs(self._archive[name].local_data, msk.local_data)
                    new_name = (name[0], name[1], str(masked.shape[1]), name[3])
                    self._archive.pop(name, None)  # pop out obsolete
                    self.append(new_name, masked, plain=True)  # append new as plain data


@icy
class Covariances(ObservableDict):

    def __init__(self):
        super(Covariances, self).__init__()

    def append(self, name, data, plain=False):
        """
        matrix coming in, numpy.matrix is not recommended
        matrix must be distributed
        :param name:
        :param data: distributed
        :param plain:
        :return:
        """
        assert (len(name) == 4)
        if plain:
            assert (data.shape[1] == int(name[2]))
        else:
            assert (data.shape[1] == 12*int(name[2])*int(name[2]))
        if isinstance(data, Field):
            assert (data.shape[0] == data.shape[1])
            assert (len(data.domain) == 1)  # single domain
            self._archive.update({name: data})  # rw
        elif isinstance(data, np.ndarray):
            if data.shape[0] < data.shape[1]//mpisize +int(2):  # distributed
                domain = DomainTuple.make(RGSpace(shape=(data.shape[1], data.shape[1])))
                self._archive.update({name: Field.from_local_data(domain, data)})  # rw
            elif data.shape[0] == data.shape[1]:  # non-distributed
                domain = DomainTuple.make(RGSpace(shape=data.shape))
                self._archive.update({name: Field.from_global_data(domain, data)})  # rw
            else:
                raise ValueError('unsupported data shape')
        else:
            raise TypeError('unsupported data type')
        log.debug('covariances-dict appends data %s' % str(name))

    def apply_mask(self, mask_dict):
        if mask_dict is None:
            pass
        else:
            assert isinstance(mask_dict, Masks)
            for name, msk in mask_dict._archive.items():
                if name in self._archive.keys():
                    masked = mask_cov(self._archive[name].local_data, msk.local_data)
                    remain = msk.local_data.sum()
                    # assemble masked pieces
                    if mpirank == 0:
                        for i in range(1, mpisize):
                            req = comm.irecv(source=i)
                            newslice = req.wait()
                            masked = np.vstack([masked, newslice])
                    else:
                        comm.isend(masked, dest=0)
                        masked = np.zeros((remain, remain))
                    comm.Bcast(masked, root=0)
                    new_name = (name[0], name[1], str(remain), name[3])
                    self._archive.pop(name, None)  # pop out obsolete
                    domain = DomainTuple.make(RGSpace(shape=(remain, remain)))
                    self._archive.update({new_name: Field.from_global_data(domain, masked)})
