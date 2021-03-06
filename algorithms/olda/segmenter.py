#!/usr/bin/env python
# CREATED:2013-08-22 12:20:01 by Brian McFee <brm2132@columbia.edu>
'''Music segmentation using timbre, pitch, repetition and time.

If run as a program, usage is:

    ./segmenter.py AUDIO.mp3 OUTPUT.lab

'''


import argparse
import logging
import sys

import numpy as np
import scipy.signal
import scipy.linalg

import librosa
import msaf

from msaf.algorithms.interface import SegmenterInterface

HOP_LENGTH = 512
REP_WIDTH = 3
REP_FILTER = 7
N_MFCC = 32
N_CHROMA = 12
N_REP = 32

# mfcc, chroma, repetitions for each, and 4 time features
__DIMENSION = N_MFCC + N_CHROMA + 2 * N_REP + 4


def features(audio_path, annot_beats=False):
    '''Feature-extraction for audio segmentation
    Arguments:
        audio_path -- str
        path to the input song in the Segmentation dataset

    Returns:
        - X -- ndarray

            beat-synchronous feature matrix:
            MFCC (mean-aggregated)
            Chroma (median-aggregated)
            Latent timbre repetition
            Latent chroma repetition
            Time index
            Beat index

        - beat_times -- array
            mapping of beat index => timestamp
            includes start and end markers (0, dur)

        - dur -- float
            duration of the track in seconds

    '''
    def compress_data(X, k):
        Xtemp = X.dot(X.T)
        if len(Xtemp) == 0:
            return None
        e_vals, e_vecs = np.linalg.eig(Xtemp)

        e_vals = np.maximum(0.0, np.real(e_vals))
        e_vecs = np.real(e_vecs)

        idx = np.argsort(e_vals)[::-1]

        e_vals = e_vals[idx]
        e_vecs = e_vecs[:, idx]

        # Truncate to k dimensions
        if k < len(e_vals):
            e_vals = e_vals[:k]
            e_vecs = e_vecs[:, :k]

        # Normalize by the leading singular value of X
        Z = np.sqrt(e_vals.max())

        if Z > 0:
            e_vecs = e_vecs / Z

        return e_vecs.T.dot(X)

    # Latent factor repetition features
    def repetition(X, metric='seuclidean'):
        R = librosa.segment.recurrence_matrix(X,
                                            k=2 * int(np.ceil(np.sqrt(X.shape[1]))),
                                            width=REP_WIDTH,
                                            metric=metric,
                                            sym=False).astype(np.float32)

        P = scipy.signal.medfilt2d(librosa.segment.structure_feature(R), [1, REP_FILTER])

        # Discard empty rows.
        # This should give an equivalent SVD, but resolves some numerical instabilities.
        P = P[P.any(axis=1)]

        return compress_data(P, N_REP)

    #########
    print '\tloading annotations and features of ', audio_path
    chroma, mfcc, tonnetz, beats, dur, anal = msaf.io.get_features(audio_path, annot_beats)

    # Sampling Rate
    sr = 11025

    ##########
    print '\treading beats'
    B = beats
    beat_frames = librosa.time_to_frames(B, sr=sr, hop_length=HOP_LENGTH)
    #print beat_frames, len(beat_frames), uidx

    #########
    M = mfcc.T
    #plt.imshow(M, interpolation="nearest", aspect="auto"); plt.show()

    #########
    # Get the beat-sync chroma
    C = chroma.T
    C += C.min() + 0.1
    C = C / C.max(axis=0)
    C = 80 * np.log10(C)  # Normalize from -80 to 0
    #plt.imshow(C, interpolation="nearest", aspect="auto"); plt.show()

    # Time-stamp features
    N = np.arange(float(len(beat_frames)))

    #########
    # Beat-synchronous repetition features
    print '\tgenerating structure features'

    R_timbre = repetition(librosa.feature.stack_memory(M))
    R_chroma = repetition(librosa.feature.stack_memory(C))
    if R_timbre is None or R_chroma is None:
        return None, None, dur

    R_timbre += R_timbre.min()
    R_timbre /= R_timbre.max()
    R_chroma += R_chroma.min()
    R_chroma /= R_chroma.max()
    #plt.imshow(R_chroma, interpolation="nearest", aspect="auto"); plt.show()

    # Stack it all up
    #print M.shape, C.shape, len(B), len(N)
    X = np.vstack([M, C, R_timbre, R_chroma, B, B / dur, N, N / len(beat_frames)])

    #plt.imshow(X, interpolation="nearest", aspect="auto"); plt.show()

    # Add on the end-of-track timestamp
    B = np.concatenate([B, [dur]])

    return X, B, dur


def gaussian_cost(X):
    '''Return the average log-likelihood of data under a standard normal
    '''

    d, n = X.shape

    if n < 2:
        return 0

    sigma = np.var(X, axis=1, ddof=1)

    cost = -0.5 * d * n * np.log(2. * np.pi) - 0.5 * (n - 1.) * np.sum(sigma)
    return cost


def clustering_cost(X, boundaries):

    # Boundaries include beginning and end frames, so k is one less
    k = len(boundaries) - 1

    d, n = map(float, X.shape)

    # Compute the average log-likelihood of each cluster
    cost = [gaussian_cost(X[:, start:end]) for
            (start, end) in zip(boundaries[:-1], boundaries[1:])]

    cost = - 2 * np.sum(cost) / n + 2 * (d * k)

    return cost


def get_k_segments(X, k):

    # Step 1: run ward
    boundaries = librosa.segment.agglomerative(X, k)

    boundaries = np.unique(np.concatenate(([0], boundaries, [X.shape[1]])))

    # Step 2: compute cost
    cost = clustering_cost(X, boundaries)

    return boundaries, cost


def get_segments(X, kmin=8, kmax=32):

    cost_min = np.inf
    S_best = []
    for k in range(kmax, kmin, -1):
        S, cost = get_k_segments(X, k)
        if cost < cost_min:
            cost_min = cost
            S_best = S
        else:
            break

    return S_best


def save_segments(outfile, S, beats):

    times = beats[S]
    with open(outfile, 'w') as f:
        for idx, (start, end) in enumerate(zip(times[:-1], times[1:]), 1):
            f.write('%.3f\t%.3f\tSeg#%03d\n' % (start, end, idx))

    pass


def process_arguments():
    parser = argparse.ArgumentParser(description='Music segmentation')

    parser.add_argument('-t',
                        '--transform',
                        dest='transform',
                        required=False,
                        type=str,
                        help='npy file containing the linear projection',
                        default=None)

    parser.add_argument('input_song',
                        action='store',
                        help='path to input audio data')

    parser.add_argument('output_file',
                        action='store',
                        help='path to output segment file')

    return vars(parser.parse_args(sys.argv[1:]))


def load_transform(transform_file):

    if transform_file is None:
        W = np.eye(__DIMENSION)
    else:
        W = np.load(transform_file)

    return W


def get_num_segs(duration, MIN_SEG=10.0, MAX_SEG=45.0):
    kmin = max(1, np.floor(duration / MAX_SEG).astype(int))
    kmax = max(2, np.ceil(duration / MIN_SEG).astype(int))

    return kmin, kmax


class Segmenter(SegmenterInterface):
    def process(self):
        """Main process.
        Returns
        -------
        est_times : np.array(N)
            Estimated times for the segment boundaries in seconds.
        est_labels : np.array(N-1)
            Estimated labels for the segments.
        """
        # Preprocess to obtain features, times, and input boundary indeces
        F, frame_times, dur = features(self.audio_file, self.annot_beats)

        try:
            # Load and apply transform
            W = load_transform(self.config["transform"])
            F = W.dot(F)

            # Get Segments
            kmin, kmax = get_num_segs(frame_times[-1])
            segments = get_segments(F, kmin=kmin, kmax=kmax)
            est_times = frame_times[segments]
        except:
            # The audio file is too short, only beginning and end
            logging.warning("Audio file too short! "
                            "Only start and end boundaries.")
            est_times = [0, dur]

        # Empty labels
        est_labels = np.ones(len(est_times) - 1) * -1

        # Post process estimations
        est_times, est_labels = self._postprocess(est_times, est_labels)

        # Concatenate last boundary
        logging.info("Estimated times: %s" % est_times)

        return est_times, est_labels
