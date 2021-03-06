"""This script contains methods to plot multiple aspects of the results
of MSAF.
"""

__author__      = "Oriol Nieto"
__copyright__   = "Copyright 2014, Music and Audio Research Lab (MARL)"
__license__     = "GPL"
__version__     = "1.0"
__email__       = "oriol@nyu.edu"

import logging
import mir_eval
import numpy as np
import os
import pylab as plt

# Local stuff
import msaf
from msaf import io
from msaf import utils
from msaf import jams2

translate_ids = {
    "2dfmc" : "2D-FMC",
    "cnmf3" : "C-NMF",
    "foote" : "Ckboard",
    "levy"  : "CC",
    "cc"    : "CC",
    "olda"  : "OLDA",
    "serra" : "SF",
    "sf"    : "SF",
    "siplca": "SI-PLCA"
}


def _plot_formatting(title, est_file, algo_ids, last_bound, N, output_file):
    """Formats the plot with the correct axis labels, title, ticks, and
    so on."""
    if title is None:
        title = os.path.basename(est_file).split(".")[0]
    plt.title(title)
    plt.yticks(np.arange(0, 1, 1 / float(N)) + 1 / (float(N) * 2))
    plt.gcf().subplots_adjust(bottom=0.22)
    plt.gca().set_yticklabels(algo_ids)
    plt.xlabel("Time (seconds)")
    plt.xlim((0, last_bound))
    plt.tight_layout()
    if output_file is not None:
        plt.savefig(output_file)
    plt.show()


def plot_boundaries(all_boundaries, est_file, algo_ids=None, title=None,
                    output_file=None):
    """Plots all the boundaries.

    Parameters
    ----------
    all_boundaries: list
        A list of np.arrays containing the times of the boundaries, one array
        for each algorithm.
    est_file: str
        Path to the estimated file (JSON file)
    algo_ids : list
        List of algorithm ids to to read boundaries from.
        If None, all algorithm ids are read.
    title : str
        Title of the plot. If None, the name of the file is printed instead.
    """
    N = len(all_boundaries)  # Number of lists of boundaries
    if algo_ids is None:
        algo_ids = io.get_algo_ids(est_file)

    # Translate ids
    for i, algo_id in enumerate(algo_ids):
        algo_ids[i] = translate_ids[algo_id]
    algo_ids = ["GT"] + algo_ids

    figsize = (6, 4)
    plt.figure(1, figsize=figsize, dpi=120, facecolor='w', edgecolor='k')
    for i, boundaries in enumerate(all_boundaries):
        color = "b"
        if i == 0:
            color = "g"
        for b in boundaries:
            plt.axvline(b, i / float(N), (i + 1) / float(N), color=color)
        plt.axhline(i / float(N), color="k", linewidth=1)

    # Format plot
    _plot_formatting(title, est_file, algo_ids, all_boundaries[0][-1], N,
                     output_file)


def plot_labels(all_labels, gt_times, est_file, algo_ids=None, title=None,
                output_file=None):
    """Plots all the labels.

    Parameters
    ----------
    all_labels: list
        A list of np.arrays containing the labels of the boundaries, one array
        for each algorithm.
    gt_times: np.array
        Array with the ground truth boundaries.
    est_file: str
        Path to the estimated file (JSON file)
    algo_ids : list
        List of algorithm ids to to read boundaries from.
        If None, all algorithm ids are read.
    title : str
        Title of the plot. If None, the name of the file is printed instead.
    """
    N = len(all_labels)  # Number of lists of labels
    if algo_ids is None:
        algo_ids = io.get_algo_ids(est_file)

    # Translate ids
    for i, algo_id in enumerate(algo_ids):
        algo_ids[i] = translate_ids[algo_id]
    algo_ids = ["GT"] + algo_ids

    # Index the labels to normalize them
    for i, labels in enumerate(all_labels):
        all_labels[i] = mir_eval.util.index_labels(labels)[0]

    # Get color map
    cm = plt.get_cmap('gist_rainbow')
    max_label = max(max(labels) for labels in all_labels)

    # To intervals
    gt_inters = utils.times_to_intervals(gt_times)

    # Plot labels
    figsize = (6, 4)
    plt.figure(1, figsize=figsize, dpi=120, facecolor='w', edgecolor='k')
    for i, labels in enumerate(all_labels):
        for label, inter in zip(labels, gt_inters):
            plt.axvspan(inter[0], inter[1], ymin=i / float(N),
                        ymax=(i + 1) / float(N), alpha=0.6,
                        color=cm(label / float(max_label)))
        plt.axhline(i / float(N), color="k", linewidth=1)

    # Draw the boundary lines
    for bound in gt_times:
        plt.axvline(bound, color="g")

    # Format plot
    _plot_formatting(title, est_file, algo_ids, gt_times[-1], N,
                     output_file)


def plot_one_track(in_path, est_times, est_labels, boundaries_id, labels_id,
                   title=None):
    """Plots the results of one track, with ground truth if it exists."""
    try:
        # Get the ds_prefix
        ds_prefix = os.path.basename(in_path).split("_")[0]

        # Get reference file
        ref_file = in_path.replace(msaf.Dataset.audio_dir,
                                msaf.Dataset.references_dir)
        ref_file = ref_file[:-4] + msaf.Dataset.references_ext
        print ref_file

        # Read file
        ref_inter, ref_labels = jams2.converters.load_jams_range(
            ref_file, "sections", annotator=0,
            context=msaf.prefix_dict[ds_prefix])

        # To times
        ref_times = utils.intervals_to_times(ref_inter)
        all_boundaries = [ref_times, est_times]
        all_labels = [ref_labels, est_labels]
    except:
        logging.warning("No references found in %s. Not plotting groundtruth"
                        % ref_file)
        all_boundaries = [est_times]
        all_labels = [est_labels]

    N = len(all_boundaries)

    # Index the labels to normalize them
    for i, labels in enumerate(all_labels):
        all_labels[i] = mir_eval.util.index_labels(labels)[0]

    # Get color map
    cm = plt.get_cmap('gist_rainbow')
    max_label = max(max(labels) for labels in all_labels)

    figsize = (8, 4)
    plt.figure(1, figsize=figsize, dpi=120, facecolor='w', edgecolor='k')
    for i, boundaries in enumerate(all_boundaries):
        color = "b"
        if i == 0:
            color = "g"
        for b in boundaries:
            plt.axvline(b, i / float(N), (i + 1) / float(N), color=color)
        if labels_id is not None:
            labels = all_labels[i]
            inters = utils.times_to_intervals(boundaries)
            for label, inter in zip(labels, inters):
                plt.axvspan(inter[0], inter[1], ymin=i / float(N),
                            ymax=(i + 1) / float(N), alpha=0.6,
                            color=cm(label / float(max_label)))
        plt.axhline(i / float(N), color="k", linewidth=1)

    # Format plot
    bid_lid = boundaries_id
    algo_ids = [bid_lid]
    if labels_id is not None:
        bid_lid += " + " + labels_id
        algo_ids = ["GT"] + [bid_lid]
    _plot_formatting(title, in_path, algo_ids, all_boundaries[0][-1], N,
                     None)
