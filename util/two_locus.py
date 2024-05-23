
import gzip
import numpy as np
from util import one_locus


"""
Read files
"""


def read_map_file(map_fname, map_col="Map(cM)"):

    if ".gz" in map_fname:
        open_fxn = gzip.open
    else:
        open_fxn = open
    file = open_fxn(map_fname, "rb")
    header = file.readline()
    file.close()
    header_fields = header.decode().strip('\n').split()
    if "Position(bp)" in header_fields:
        pos_idx = header_fields.index("Position(bp)")
    else:
        raise ValueError("There must be a 'Position(bp)' column!")
    if map_col in header_fields:
        map_idx = header_fields.index(map_col)
    else:
        raise ValueError(f"There must be a '{map_col}' column!")
    map_positions = []
    map_vals = []
    with open_fxn(map_fname, "rb") as file:
        for line_b in file:
            line = line_b.decode()
            fields = line.strip('\n').split('\t')
            if "Position(bp)" not in fields:
                map_positions.append(int(fields[pos_idx]))
                map_vals.append(float(fields[map_idx]))
    map_positions = np.array(map_positions)
    map_vals = np.array(map_vals)
    return map_positions, map_vals


def get_map_vals(map_fname, positions, map_col="Map(cM)"):

    map_pos, map_vals = read_map_file(map_fname, map_col=map_col)
    if np.any(positions < map_pos[0]):
        print("There are positions below map start")
    if np.any(positions > map_pos[-1]):
        print("There are positions beyond map end")
    vals = np.interp(
        positions, map_pos, map_vals, left=map_vals[0], right=map_vals[-1]
    )
    return vals


"""
Map transformations
"""


def map_function(r_vals):
    # r > d
    return -50 * np.log(1 - 2 * r_vals)


"""
Compute statistics
"""


def count_site_pairs(map_vals, r_bins, positions=None, window=None,
                     vectorized=False, bp_thresh=0, lim_right=False):
    if bp_thresh:
        if not np.any(positions):
            raise ValueError("You must provide positions to use bp_thresh!")
    d_bins = map_function(r_bins)
    if np.any(window):
        if not np.any(positions):
            raise ValueError("You must provide positions to use a window!")
        l_start, l_stop = one_locus.get_window_bounds(window, positions)
        if lim_right:
            r_stop = l_stop
        else:
            max_d = map_vals[l_stop - 1] + d_bins[-1]
            r_stop = np.searchsorted(map_vals, max_d)
        map_vals = map_vals[l_start:r_stop]
        if bp_thresh:
            positions = positions[l_start:r_stop]
    else:
        l_start = 0
        l_stop = len(map_vals)
    n_left_loci = l_stop - l_start
    cum_counts = np.zeros(len(d_bins), dtype=np.int64)
    if vectorized:
        edges = map_vals[:n_left_loci, np.newaxis] + d_bins[np.newaxis, :]
        counts = np.searchsorted(map_vals, edges)
        # correction
        cum_counts = counts.sum(0)
    else:
        for i in np.arange(n_left_loci):
            if bp_thresh > 0:
                j = np.searchsorted(positions, positions[i] + bp_thresh + 1)
            else:
                j = i + 1
            _bins = d_bins + map_vals[i]
            cum_counts += np.searchsorted(map_vals[j:], _bins)
            if i % 1e6 == 0:
                print(f"locus {i} of {n_left_loci} loci")
    pair_counts = np.diff(cum_counts)
    return pair_counts


def count_H2(genotypes, map_vals, r_bins, positions=None, window=None,
             vectorized=False, bp_thresh=0, lim_right=False):

    het_idx = one_locus.get_het_idx(genotypes)
    het_map_vals = map_vals[het_idx]
    if np.any(positions):
        het_positions = positions[het_idx]
    else:
        het_positions = None
    H2_counts = count_site_pairs(
        het_map_vals, r_bins, positions=het_positions, window=window,
        vectorized=vectorized, bp_thresh=bp_thresh, lim_right=lim_right
    )
    return H2_counts


def count_H2xy(genotypes_x, genotypes_y, map_vals, r_bins, positions=None,
               window=None, bp_thresh=0, lim_right=False):
    # unphased, of course
    if bp_thresh:
        if not np.any(positions):
            raise ValueError("You must provide positions to use bp_thresh!")
    d_bins = map_function(r_bins)
    if np.any(window):
        if not np.any(positions):
            raise ValueError("You must provide positions to use a window!")
        l_start, l_stop = one_locus.get_window_bounds(window, positions)
        if lim_right:
            r_stop = l_stop
        else:
            max_d = map_vals[l_stop - 1] + d_bins[-1]
            r_stop = np.searchsorted(map_vals, max_d)
        map_vals = map_vals[l_start:r_stop]
        genotypes_y = genotypes_y[l_start:r_stop]
        genotypes_x = genotypes_x[l_start:r_stop]
        if bp_thresh:
            positions = positions[l_start:r_stop]
    else:
        l_start = 0
        l_stop = len(map_vals)
    n_left_loci = l_stop - l_start
    right_lims = np.searchsorted(map_vals, map_vals + d_bins[-1])
    site_Hxy = new_one_locus.get_site_Hxy(genotypes_x, genotypes_y)
    allowed_Hxy = np.array([0.25, 0.5, 0.75, 1])
    precomputed_H2xy = np.cumsum(allowed_Hxy[:, np.newaxis] * site_Hxy, axis=1)
    cum_counts = np.zeros(len(d_bins), dtype=np.float64)
    for i in np.arange(n_left_loci):
        if bp_thresh > 0:
            j_min = np.searchsorted(positions, positions[i] + bp_thresh + 1)
        else:
            j_min = i + 1
        j_max = right_lims[i]
        left_Hxy = site_Hxy[i]
        if left_Hxy > 0:
            _bins = d_bins + map_vals[i]
            edges = np.searchsorted(map_vals[j_min:j_max], _bins)
            select = np.searchsorted(allowed_Hxy, left_Hxy)
            locus_H2xy = precomputed_H2xy[select, i:j_max]
            cum_counts += locus_H2xy[edges]
    H2xy_counts = np.diff(cum_counts)
    return H2xy_counts
