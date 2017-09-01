
from .util import GetModels

import argparse
import sys

_desc = """
Start the model learning tool. This should be independent of the actual
simulation capabilities we are using.
"""
_epilog = """
"""

def GetAvailableFeatures():
    '''
    List all the possible sets of features we might recognize when constructing
    a model using the tool.
    '''
    return ['empty',
            'null',
            'depth', # depth channel only
            'rgb', # RGB channels only
            'joint_state', # robot joints only
            'multi', # RGB+joints+gripper
            'pose', #object poses + joints + gripper
            'grasp_segmentation',]

def GetModelParser():
    '''
    Get the set of arguments for models and learning.
    '''
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-L', '--lr', '--learning_rate',
                        help="Learning rate to be used in algorithm.",
                        type=float,
                        default=1e-3)
    parser.add_argument('--model_directory',
                        help="models directory",
                        default = "~/.costar/models"),
    parser.add_argument('-i', '--iter',
                        help='Number of iterations to run',
                        default=100,
                        type=int)
    parser.add_argument('-b','--batch_size',
                        help='Batch size to use in the model',
                        default=32,
                        type=int)
    parser.add_argument('-e','--epochs',
                        help="Number of epochs",
                        type=int,
                        default=1000,)
    parser.add_argument('--data_file', '--file',
                        help="File name for data archive.",
                        default='data.npz')
    parser.add_argument('--model_descriptor',
                        help="model description for use with save/load file",
                        default="model")
    parser.add_argument('-m', '--model',
                        help="Name of NN model to learn.",
                        default=None,
                        choices=GetModels())
    parser.add_argument("--optimizer","--opt",
                        help="optimizer to use with learning",
                        default="adam")
    parser.add_argument("-z", "--zdim", "--noise_dim",
                        help="size of action parameterization",
                        default=16)
    parser.add_argument("-D", "--debug_model", "--dm", "--debug",
                        help="Run a short script to debug the current model.",
                        action="store_true")
    parser.add_argument("--clipnorm",
                        help="Clip norm of gradients to this value to " + \
                              "prevent exploding gradients.",
                        default=100)
    parser.add_argument("--load_model", "--lm",
                        help="Load model from file for tests.",
                        #type=argparse.FileType('r'))#,
                        action="store_true")
    parser.add_argument("--show_iter", "--si",
                        help="Show output images from model training" + \
                             " every N iterations.",
                        default=0,
                        type=int)
    parser.add_argument("--pretrain_iter", "--pi",
                        help="Number of iterations of pretraining to run" + \
                              ", in particular for training GAN" + \
                              " discriminators.",
                        default=0,
                        type=int)
    parser.add_argument("--cpu",
                        help="Run in CPU-only mode, even if GPUs are" + \
                             " available.",
                        action="store_true",)
    parser.add_argument('--window_length',
                        help="Window length used for data collection.",
                        type=int,
                        default=10)
    parser.add_argument('--seed',
                        help="Seed used for running experiments.",
                        type=int)
    parser.add_argument('--profile',
                        help='Run cProfile on agent',
                        action="store_true")
    parser.add_argument('--features',
                        help="Specify feature function",
                        default="null",
                        choices=GetAvailableFeatures())
    return parser

def ParseModelArgs():
    parser = argparse.ArgumentParser(add_help=True,
                                     parents=[GetModelParser()],
                                     description=_desc, epilog=_epilog)
    return vars(parser.parse_args())
