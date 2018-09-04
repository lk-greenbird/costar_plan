#!/usr/local/bin/python
"""
A simple widget for visualizing hyperparameter rankings generated by hyperopt_rank.py in the dataset.

Rank the results of hyperparameter optimization.

How to run:

    bokeh serve --show hyperopt_plot.py --args --rank_csv /path/to/hyperopt_rank.csv

Apache License 2.0 https://www.apache.org/licenses/LICENSE-2.0

"""
import sys
import os
import traceback
import tensorflow as tf
import pandas
import json
import keras
from tensorflow.python.platform import flags
import numpy as np
import holoviews as hv
import os
import glob

import h5py
import bokeh
from bokeh.io import curdoc
from bokeh.layouts import layout
from bokeh.models import Slider
from bokeh.models import Button
from bokeh.models.widgets import TextInput

import numpy as np
import io
from PIL import Image
import argparse
from functools import partial

# progress bars https://github.com/tqdm/tqdm
# import tqdm without enforcing it as a dependency
try:
    from tqdm import tqdm
except ImportError:

    def tqdm(*args, **kwargs):
        if args:
            return args[0]
        return kwargs.get('iterable', None)

flags.DEFINE_string(
    'log_dir',
    '',
    """Directory for tensorboard, model layout, model weight, csv, and hyperparam files
    """
)

flags.DEFINE_string(
    'rank_csv',
    'hyperopt_rank.csv',
    """Sorted csv ranking models on which to perform full runs after hyperparameter optimization.

    See cornell_hyperopt.py to perform hyperparameter optimization,
    and then hyperopt_rank.py to generate the ranking csv file.
    The file is expected to be in the directory specified by the log_dir flag.

    Example file path:
        hyperopt_logs_costar_grasp_regression/hyperopt_rank.csv
        hyperopt_logs_costar_translation_regression/hyperopt_rank.csv
        hyperopt_logs_costar_block_stacking_train_ranked_regression/hyperopt_rank.csv
    """
)

flags.DEFINE_boolean(
    'filter_epoch',
    False,
    'Filter results, dropping everything except a single specific epoch specified by --epoch'
)

flags.DEFINE_integer(
    'epoch',
    0,
    'Results should only belong to this epoch if --filter_epoch=True'
)

flags.DEFINE_integer(
    'verbose',
    0,
    'print extra debug stuff'
)

flags.DEFINE_integer(
    'max_epoch',
    None,
    'Results should only belong to this epoch or lower, not enabled by default.'
)

flags.DEFINE_string(
    'save_dir',
    None,
    'Where to save the csv, defaults to log_dir'
)

flags.DEFINE_string(
    'save_csv',
    'hyperopt_plot.csv',
    'Where to save the sorted output csv file with the results'
)

flags.DEFINE_string(
    'problem_type',
    'semantic_translation_regression',
    'Options are semantic_translation_regression and semantic_rotation_regression,'
)

flags.DEFINE_string(
    'sort_by',
    None,
    'Options are semantic_translation_regression and semantic_rotation_regression,'
)

flags.DEFINE_boolean(
    'ascending',
    None,
    'Sort in ascending (1 to 100) or descending (100 to 1) order, '
    'Defaults to True unless acc is in sort_by, then defaults to False.'
)


FLAGS = flags.FLAGS
FLAGS(sys.argv)


problem_type = FLAGS.problem_type
sort_by = FLAGS.sort_by
ascending = FLAGS.ascending
if FLAGS.log_dir:
    csv_file = os.path.join(os.path.expanduser(FLAGS.log_dir), FLAGS.rank_csv)
else:
    csv_file = os.path.expanduser(FLAGS.rank_csv)
# load the hyperparameter optimization ranking csv file created by hyperopt_rank.py
dataframe = pandas.read_csv(csv_file, index_col=None, header=0)
if problem_type == 'semantic_rotation_regression':
    # sort by val_angle_error from low to high
    dataframe = dataframe.sort_values('val_angle_error', ascending=True)
    if sort_by is None:
        sort_by = 'val_angle_error'

    if sort_by is not None and ascending is None:
        ascending = True
        if 'acc' in sort_by:
            ascending = False
    dataframe = dataframe.sort_values(sort_by, ascending=ascending)
    # sort_by = 'val_grasp_acc'
    # dataframe = dataframe.sort_values(sort_by, ascending=False)
    value_dimension_tuples_mm = [
        ('grasp_acc_5mm_7_5deg', 7.5),
        ('grasp_acc_1cm_15deg', 15),
        ('grasp_acc_2cm_30deg', 30),
        ('grasp_acc_4cm_60deg', 60),
        ('grasp_acc_8cm_120deg', 120),
        ('grasp_acc_16cm_240deg', 240),
        ('grasp_acc_32cm_360deg', 360),
    ]
    units = '°'
elif problem_type == 'semantic_translation_regression':
    dataframe = dataframe.sort_values('val_cart_error', ascending=True)
    if sort_by is None:
        sort_by = 'val_cart_error'

    if sort_by is not None and ascending is None:
        ascending = True
        if 'acc' in sort_by:
            ascending = False
    dataframe = dataframe.sort_values(sort_by, ascending=ascending)
    # # sort by grasp accuracy within 4 cm and 60 degrees
    # sort_by = 'val_grasp_acc_4cm_60deg'
    # dataframe = dataframe.sort_values(sort_by, ascending=False)
    # sort_by = 'val_grasp_acc'
    # dataframe = dataframe.sort_values(sort_by, ascending=False)
    value_dimension_tuples_mm = [
        ('grasp_acc_5mm_7_5deg', 5),
        ('grasp_acc_1cm_15deg', 10),
        ('grasp_acc_2cm_30deg', 20),
        ('grasp_acc_4cm_60deg', 40),
        ('grasp_acc_8cm_120deg', 80),
        ('grasp_acc_16cm_240deg', 160),
        ('grasp_acc_32cm_360deg', 320),
        ('grasp_acc_256cm_360deg', 2560),
        ('grasp_acc_512cm_360deg', 5120),
    ]
    units = 'mm'
elif problem_type == 'semantic_grasp_regression':
    dataframe = dataframe.sort_values('val_grasp_acc', ascending=False)
    sort_by = 'val_grasp_acc'
    # we don't have plotting set up for full pose estimation yet
    raise NotImplementedError
else:
    raise ValueError('hyperopt_plot.py: '
                     'unsupported problem type: ' + str(problem_type) + ' '
                     'Options are semantic_translation_regression and '
                     'semantic_rotation_regression.')

# epoch to filter, or None if we should just take the best performing value ever
filter_epoch = FLAGS.filter_epoch

# don't give really long runs an unfair advantage
if FLAGS.max_epoch is not None:
    dataframe = dataframe.loc[dataframe['epoch'] <= FLAGS.max_epoch]
# filter only the specified epoch so we don't redo longer runs
if filter_epoch is not None and filter_epoch is True:
    dataframe = dataframe.loc[dataframe['epoch'] == FLAGS.epoch]
    # TODO(ahundt) we are really looking for "is this a hyperopt result?" not "checkpoint"
    # hyperopt search results don't have checkpoints, but full training runs do
    dataframe = dataframe.loc[dataframe['checkpoint'] == False]

renderer = hv.renderer('bokeh')

# key_dimensions = [('basename', 'Model')]
# value_dimension_tuples = [
#     ('grasp_acc_5mm_7_5deg', '5mm'),
#     ('grasp_acc_1cm_15deg', '10mm'),
#     ('grasp_acc_2cm_30deg', '20mm'),
#     ('grasp_acc_4cm_60deg', '40mm'),
#     ('grasp_acc_8cm_120deg', '80mm'),
#     ('grasp_acc_16cm_240deg', '160mm'),
#     ('grasp_acc_32cm_360deg', '320mm'),
#     ('grasp_acc_256cm_360deg', '2560mm'),
#     ('grasp_acc_512cm_360deg', '5120mm'),
# ]


def create_data_comparison_table(value_dimension_tuples_mm, units, problem_type):
    dataset_names_prefix = [
        ('train', ''),
        ('val', 'val_'),
        ('test', 'test_')
    ]

    value_dimension_strs = [vt[0] for vt in value_dimension_tuples_mm]
    value_dimension_ints = [vt[1] for vt in value_dimension_tuples_mm]
    value_dimension_int_as_str = [str(vt[1]) for vt in value_dimension_tuples_mm]
    accuracy_range_limits = []
    prev_acc_int = 0
    for name, acc_int in value_dimension_tuples_mm:
        acc_range = str(prev_acc_int) + '-' + str(acc_int) + ' ' + units
        prev_acc_int = acc_int
        accuracy_range_limits = accuracy_range_limits + [acc_range]
    value_dimension_range_tuples_mm = [(vdt[0], vdt[1], ar) for vdt, ar in zip(value_dimension_tuples_mm, accuracy_range_limits)]
    print('accuracy_range_limits: ' + str(accuracy_range_limits))

    # first 20 characters of model name are the time, full names are too long
    number_of_time_characters = 19
    # loop over the ranked models
    row_progress = tqdm(dataframe.iterrows(), ncols=240)
    max_models_to_show = 5
    names = []
    acc_limits = []
    acc_range_limits = []
    values = []
    split_values = []
    tvts = []
    for index, row in row_progress:
        if index < max_models_to_show:
            # train, val, test datasets
            for tvt, tvt_prefix in dataset_names_prefix:
                prev_val = 0.0
                # accuracy values & splits
                for name, acc_limit, acc_range in value_dimension_range_tuples_mm:
                    val = row[tvt_prefix + name]
                    # split of accuracies within a range
                    split_val = val - prev_val
                    # print('split_val: ' + str(split_val))
                    prev_val = val
                    # vals.append((acc_int, split_val))
                    values = values + [val]
                    split_values = split_values + [split_val]
                    names = names + [row['basename'][:number_of_time_characters]]
                    acc_range_limits = acc_range_limits + [acc_range]
                    acc_limits = acc_limits + [acc_limit]
                    tvts = tvts + [tvt]

    dictionary = {'name': names,
                  'accuracy_range_limits': acc_range_limits,
                  'accuracy_range_value': split_values,
                  'train_val_test': tvts,
                  'accuracy_value': values,
                  'accuracy_value_limit': acc_limits}

    rdf = pandas.DataFrame(dictionary)
    # for i, name in enumerate(value_dimension_int_as_str):
    #     rdf = rdf.rename(index={i : name})
    if FLAGS.verbose > 0:
        print('rdf:')
        print(rdf)

    if FLAGS.save_dir is None:
        FLAGS.save_dir = FLAGS.log_dir
    output_filename = os.path.join(FLAGS.save_dir, FLAGS.save_csv)
    rdf.to_csv(output_filename)
    print('Plotting CSV saved to: ' + output_filename)
    return rdf

rdf = create_data_comparison_table(value_dimension_tuples_mm, units, problem_type)

# key_dimensions = [('name', 'Model'), ('accuracy_range_limits', 'Accuracy Range'), ('train_val_test', 'Train Val Test')]
key_dimensions = [('name', 'Model'), ('accuracy_range_limits', 'Accuracy Range')]
key_dimension_display_strs = [vt[1] for vt in key_dimensions]

table = hv.Table(rdf, key_dimensions, 'accuracy_range_value')
print('1.0 table created')
table_bars = table.to.bars(key_dimension_display_strs, 'accuracy_range_value', ['train_val_test'])
table_bars = table_bars.options(stack_index=1, width=1920, height=1080, xrotation=90, tools=['hover'])
print('2.0 table bars')
table_plot = renderer.get_plot(table_bars)
print('3.0 table plot')
plot_list = [[table_plot.state]]
print('3.0 plot list')
# layout_child = layout(plot_list, sizing_mode='fixed')
layout_child = layout(plot_list)
curdoc().clear()
curdoc().add_root(layout_child)

