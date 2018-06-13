'''
-----------------------
``xarray_filters.reshape``
~~~~~~~~~~~~~~~~~~~~~~~
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from collections import namedtuple, OrderedDict
from copy import deepcopy

import numpy as np
import pandas as pd
import xarray as xr

from xarray_filters.constants import (FEATURES_LAYER_DIMS,
                                      FEATURES_LAYER, YNAME)
from xarray_filters.multi_index import create_multi_index, multi_index_to_coords
from xarray_filters.pipe_utils import for_each_array

__all__ = ['has_features',
           'concat_ml_features',
           'from_features',
           'to_features',
           'to_xy_arrays']


RAVEL_ORDER = 'C'

def has_features(dset, raise_err=True, features_layer=None):
    '''Check if an MLDataset has a DataArray called "features"
    with dimensions (space, layer)

    Parameters
    ----------

    dset: an MLDataset
    raise_err: raise or not

    Returns
    -------

    features_layer (str), ``False`` or, if ``raise_err`` raises ``ValueError``

    Examples
    --------

    >>> import pandas as pd
    >>> import numpy as np
    >>> import xarray as xr
    >>> from xarray_filters import (from_features, to_features,
    ...                             MLDataset, has_features)
    >>> index = pd.MultiIndex.from_product((np.arange(2), np.arange(2, 4)), names=('x', 'y'))
    >>> arr1 = xr.DataArray(np.random.uniform(0,1, (4, 1)), coords=[('space', index), ('layer', ['pressure'])], dims=('space', 'layer'), name='features')
    >>> dset1 = from_features(arr1)
    >>> assert isinstance(dset1, MLDataset) and tuple(dset1.data_vars) == ('pressure',)
    >>> dset2 = to_features(dset1)
    >>> assert ('features',) == tuple(dset2.data_vars)
    >>> assert np.all(dset2.features == arr1)
    >>> dset2  # doctest: +SKIP
    <xarray.MLDataset>
    Dimensions:   (layer: 1, space: 4)
    Coordinates:
      * space     (space) MultiIndex
      - x         (space) int64 0 0 1 1
      - y         (space) int64 2 3 2 3
      * layer     (layer) object 'pressure'
    Data variables:
        ...
    >>> has_features(dset2) == 'features'
    True
    >>> has_features(dset1, raise_err=False)
    '''
    if features_layer is None:
        features_layer = FEATURES_LAYER
    if features_layer not in dset.data_vars:
        if raise_err:
            raise ValueError('{} DataArray is not in dset (found {})'.format(features_layer, dset.data_vars.keys()))
        return None
    arr = dset[features_layer]
    return features_layer


def to_features(dset, layers=None, row_dim=None,
                col_dim=None, trans_dims=None,
                features_layer=None, keep_attrs=False,
                astype=None):
    '''
    From an xarray.Dataset or MLDataset instance return a
    2-D xarray.DataArray or numpy.array for input as a
    feature matrix in tools like scikit-learn (calling
    .ravel() on N-D DataArray's to become columns)

    Parameters
    ----------

    dset: xarray.Dataset or xarray_filters.MLDataset
        We assume each xarray.DataArray in dset
        has the same coords/dims.
    row_dim: Name of the row dimension created by flattening the
             coordinate arrays of each xarray.DataArray in dset.
             The row dimension has a pandas.MultiIndex, e.g. if
             xarray.DataArrays in dset have dims ('x', 'y')
             then the pandas.MultiIndex has index names of ('x', 'y')
             If None, row_dim becomes 'space'
    trans_dims: transpose to trans_dims
                (becomes a pandas.MultiIndex)
                if trans_dims is not None
    col_dim: Becomes column dimension name - 'layer' by default
    features_layer: Name of single 2-D DataArray
                    in the returned MLDataset instance.
                    ('features' by default)
    keep_attrs: If True, keep attributes
    # TODO: Gui - make astype consistent with PR 2
            (see comment at top of module)
    astype: MLDataset instance by default or one of:
            ('DataFrame', 'numpy', 'DataArray', 'Dataset')

    Returns
    -------

    new_dset: xarray_filters.MLDataset instance with a single
              2-D DataArray variable named by 'features_layer'
              keyword argument
    Examples
    --------

    >>> import pandas as pd
    >>> import numpy as np
    >>> import xarray as xr
    >>> from xarray_filters import from_features, MLDataset
    >>> index = pd.MultiIndex.from_product((np.arange(2), np.arange(2, 4)), names=('x', 'y'))
    >>> arr1 = xr.DataArray(np.random.uniform(0,1, (4, 1)), coords=[('space', index), ('layer', ['pressure'])], dims=('space', 'layer'), name='features')
    >>> dset = from_features(arr1)
    >>> assert isinstance(dset, MLDataset) and tuple(dset.data_vars) == ('pressure',)
    >>> arr2 = to_features(dset)
    >>> assert np.all(arr1 == arr2.features)
    >>> arr2  # doctest: +SKIP
    <xarray.MLDataset>
    Dimensions:   (layer: 1, space: 4)
    Coordinates:
      * space     (space) MultiIndex
      - x         (space) int64 0 0 1 1
      - y         (space) int64 2 3 2 3
      * layer     (layer) object 'pressure'
    Data variables:
        ...

    '''
    from xarray_filters.mldataset import MLDataset
    arrs = []
    if has_features(dset, raise_err=False, features_layer=features_layer):
        return dset
    if features_layer is None:
        features_layer = FEATURES_LAYER
    if row_dim is None:
        row_dim = FEATURES_LAYER_DIMS[0]
    if col_dim is None:
        col_dim = FEATURES_LAYER_DIMS[1]
    if layers is None:
        layers = tuple(dset.data_vars)
    for layer in layers:
        if not layer in dset.data_vars:
            raise ValueError('TODO - message')
        arr = dset[layer]
        coords, dims, val, attrs = arr.coords, arr.dims, arr.values, arr.attrs
        if trans_dims is not None:
            if tuple(trans_dims) != tuple(arr.dims):
                arr = arr.transpose(*trans_dims)
                coords, dims, val, attrs = arr.coords, arr.dims, arr.values, arr.attrs
                attrs = arr.attrs
        attrs = deepcopy(attrs)
        if len(dims) == 1:
            row_dim = dims[0]
            index = getattr(arr, row_dim)
        else:
            index = create_multi_index(arr)
        val = val.ravel(order=RAVEL_ORDER)[:, np.newaxis]
        coords = OrderedDict([(row_dim, index),
                              (col_dim, [layer])])
        new_dims = (row_dim, col_dim)
        arr = xr.DataArray(val, coords=coords,
                           dims=new_dims, attrs=attrs)
        arrs.append(arr)
    dims, siz = _same_size_dims_arrs(*arrs)
    if not all(col_dim in arr.dims for arr in arrs):
        raise ValueError('TODO - document how one ends up here {}'.format(layers))
    new_arr = xr.concat(arrs, dim=col_dim)
    if not keep_attrs:
        attrs = OrderedDict()
    new_dset = MLDataset(OrderedDict([(features_layer, new_arr)]), attrs=attrs)
    if astype is not None:
        return new_dset.astype(to_type=astype)
    return new_dset


def from_features(arr, axis=0):
    '''
    From a 2-D xarray.DataArray with a pandas.MultiIndex
    on axis (axis=0 by default), return a MLDataset
    with DataArrays of dimensions from MultiIndex

    Parameters
    ----------

        arr: 2-D xr.DataArray with
        axis: Axis with pandas.MultiIndex (default=0)

    Returns
    -------

        MLDataset instance

    Examples
    --------

    >>> import pandas as pd
    >>> import numpy as np
    >>> import xarray as xr
    >>> from xarray_filters import from_features, to_features, MLDataset
    >>> index = pd.MultiIndex.from_product((np.arange(2), np.arange(2, 4)), names=('x', 'y'))
    >>> arr1 = xr.DataArray(np.random.uniform(0,1, (4, 1)), coords=[('space', index), ('layer', ['pressure'])], dims=('space', 'layer'), name='features')
    >>> dset1 = from_features(arr1)
    >>> assert isinstance(dset1, MLDataset) and tuple(dset1.data_vars) == ('pressure',)
    >>> dset2 = to_features(dset1)
    >>> assert ('features',) == tuple(dset2.data_vars)
    >>> assert np.all(dset2.features == arr1)
    >>> dset2  # doctest: +SKIP
    <xarray.MLDataset>
    Dimensions:   (layer: 1, space: 4)
    Coordinates:
      * space     (space) MultiIndex
      - x         (space) int64 0 0 1 1
      - y         (space) int64 2 3 2 3
      * layer     (layer) object 'pressure'
    Data variables:
      ...
    '''
    from xarray_filters.mldataset import MLDataset
    coords, dims = multi_index_to_coords(arr, axis=axis)
    simple_axis = 0 if axis == 1 else 1
    simple_dim = arr.dims[simple_axis]
    simple_np_arr = getattr(arr, simple_dim).values
    shp = tuple(coords[dim].size for dim in dims)
    dset = OrderedDict()
    n_elts_needed = np.prod(shp)
    for j in range(simple_np_arr.size):
        arr_val = arr[:, j].values
        n_arr_vals = len(arr_val)
        assert n_arr_vals <= n_elts_needed, 'Data array falls outside of domain for destination coordinates'
        if n_arr_vals < n_elts_needed:
            val = np.full(shp, np.nan)
            feature_idx = arr.indexes[arr.dims[0]]
            dim_coord_pairs = feature_idx.tolist()
            row, col = coords[dims[0]], coords[dims[1]]
            for idx, dim_coord_pair in enumerate(dim_coord_pairs):
                val[(dim_coord_pair[0] == row), (dim_coord_pair[1] == col)] = arr_val[idx]
        else:
            val = arr_val.reshape(shp, order=RAVEL_ORDER)
        layer = simple_np_arr[j]
        dset[layer] = xr.DataArray(val, coords=coords, dims=dims)
    return MLDataset(dset)


def to_xy_arrays(dset=None, y=None, features_layer=None,
                 yname=YNAME, y1d=True, as_np=True):

    from xarray_filters.mldataset import MLDataset
    orig_kw = dict(features_layer=features_layer, yname=yname,
                   y1d=y1d, as_np=as_np)
    if isinstance(y, xr.Dataset):
        y = MLDataset(y)
    if isinstance(y, MLDataset):
        y = y.to_features(features_layer=features_layer)
        orig_kw['dset'] = y
        y, _ = to_xy_arrays(**orig_kw)
        orig_kw['dset'] = dset
        dset, _ = to_xy_arrays(**orig_kw)
        return dset, y
    if not isinstance(dset, (xr.Dataset, MLDataset)):
        return dset, y
    if dset is None:
        y, _ = to_xy_arrays(dset=y, **orig_kw)
        return None, y
    dset = to_features(dset, features_layer=features_layer)
    arr = dset[features_layer or FEATURES_LAYER]
    col_dim = arr.dims[1]
    col_labels = getattr(arr, col_dim)
    idxes = [col for col, item in enumerate(col_labels)
             if col != yname]
    xkw = {col_dim: idxes}
    ykw = {col_dim: yname}
    X = arr.isel(**xkw)
    if y is None:
        col_names = getattr(arr, arr.dims[-1])
        if yname in col_names.values:
            y = arr.isel(**ykw)
            if as_np:
                y = y.values
    if as_np and y1d and y is not None and y.ndim == 2 and y.shape[1] == 1:
        y = y.squeeze()
    if as_np:
        X = X.values
        return X, y
    else:
        return X.to_dataframe(), y.to_dataframe()


def _same_size_dims_arrs(*arrs, **kwargs):
    '''Check if all DataArrays in arrs have same size and same dims

    Parameters:
        :raise_err: If True, raise ValueError if dims/sizes differ
                    else return True/False
    '''
    raise_err = kwargs.get('raise_err', True)
    siz = None
    dims = None
    for arr in arrs:
        if siz is not None and siz != arr.size:
            if raise_err:
                raise ValueError('Expected arrays of same size but found {} and {}'.format(siz, arr.size))
            return False
        if dims is not None and tuple(arr.dims) != dims:
            if raise_err:
                raise ValueError('Expected arrays of same dims but found {} and {}'.format(dims, arr.dims))
            return False
    return dims, siz


def concat_ml_features(*dsets, **kwargs):
    '''Concatenate MLDataset / Dataset (dsets) along concat_dim
    (by default the column dimension, typically called "layer")

    Parameters:
        :dsets: Any number of MLDataset / Dataset objects that are
                2D
        :features_layer: Typically "layer", the column dimension
        :concat_dim: If None, the column dimension is guessed
        :keep_attrs: If True, keep the attrs of the first dset in *dsets
    TODO - Gui: This could use the astype logic discussed elsewhere?

    '''
    features_layer = kwargs.get('features_layer', FEATURES_LAYER)
    concat_dim = kwargs.get('concat_dim', None)
    keep_attrs = kwargs.get('keep_attrs', False) # TODO True or False (convention?)

    from xarray_filters.mldataset import MLDataset
    if not dsets:
        raise ValueError('No MLDataset / Dataset arguments passed.  Expected >= 1')
    if keep_attrs:
        attrs = deepcopy(dsets[0].attrs)
    else:
        attrs = OrderedDict()
    concat_dim = concat_dim or FEATURES_LAYER_DIMS[1]
    data_arrs = []
    for dset in dsets:
        if not isinstance(dset, (MLDataset, xr.Dataset)):
            raise ValueError('TODO -error message here')
        data_arr = dset.data_vars.get(features_layer, None)
        if data_arr is None:
            raise ValueError('TODO -error message here')
        data_arrs.append(data_arr)
    data_arr = xr.concat(data_arrs, dim=concat_dim)
    return MLDataset(OrderedDict([(features_layer, data_arr)]), attrs=attrs)

