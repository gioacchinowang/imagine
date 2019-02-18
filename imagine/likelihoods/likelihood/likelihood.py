from keepers import Loggable
from nifty import FieldArray

'''
Likelihood class defines likelihood posterior function
to be used in Bayesian analysis

members:
._strip_data
    -- works trivially on list/tuple

input argument of __call__ should have form
{observable_name: [observable_data]}

observable name/unit convention:
* 'fd'
    -- Faraday depth (in unit 
* 'dm'
    -- dispersion measure (in unit
* 'sync'+'freq'+X
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
        
'''
class Likelihood(Loggable, object):
    
    def __call__(self, observable_names):
        raise NotImplementedError

    # applies to NIFTy.Field input
    # acts trivially on normal input
    def _strip_data(self, data):
        # if the first element in the domain tuple is a FieldArray
        # we must extract the data
        if hasattr(data, 'domain'):
            return data.val.get_full_data()
        else:
            return data