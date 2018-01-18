from __future__ import print_function

import keras.backend as K
import keras.losses as losses
import keras.optimizers as optimizers
import numpy as np
import tensorflow as tf

from keras.constraints import maxnorm
from keras.layers.advanced_activations import LeakyReLU
from keras.layers import Input, RepeatVector, Reshape
from keras.layers import UpSampling2D, Conv2DTranspose
from keras.layers import BatchNormalization, Dropout
from keras.layers import Dense, Conv2D, Activation, Flatten
from keras.layers import Lambda
from keras.layers.merge import Add, Multiply
from keras.layers.merge import Concatenate
from keras.losses import binary_crossentropy
from keras.models import Model, Sequential
from keras.optimizers import Adam
from keras.constraints import max_norm

from .data_utils import *

'''
Contains tools to make the sub-models for the "multi" application
'''

def _makeTrainTarget(I_target, q_target, g_target, o_target):
    if I_target is not None:
        length = I_target.shape[0]
        image_shape = I_target.shape[1:]
        image_size = 1
        for dim in image_shape:
            image_size *= dim
        image_size = int(image_size)
        Itrain = np.reshape(I_target,(length, image_size))
        return np.concatenate([Itrain, q_target,g_target,o_target],axis=-1)
    else:
        length = q_target.shape[0]
        return np.concatenate([q_target,g_target,o_target],axis=-1)

def GetAllMultiData(num_options, features, arm, gripper, arm_cmd, gripper_cmd, label,
            prev_label, goal_features, goal_arm, goal_gripper, value, *args, **kwargs):
        I = np.array(features) / 255. # normalize the images
        q = np.array(arm)
        g = np.array(gripper) * -1
        qa = np.array(arm_cmd)
        ga = np.array(gripper_cmd) * -1
        oin = np.array(prev_label)
        I_target = np.array(goal_features) / 255.
        q_target = np.array(goal_arm)
        g_target = np.array(goal_gripper) * -1
        o_target = np.array(label)

        # Preprocess values
        value_target = np.array(np.array(value) > 1.,dtype=float)
        #if value_target[-1] == 0:
        #    value_target = np.ones_like(value) - np.array(label == label[-1], dtype=float)
        q[:,3:] = q[:,3:] / np.pi
        q_target[:,3:] = np.array(q_target[:,3:]) / np.pi
        qa /= np.pi

        o_target_1h = np.squeeze(ToOneHot2D(o_target, num_options))
        train_target = _makeTrainTarget(
                I_target,
                q_target,
                g_target,
                o_target_1h)

        return [I, q, g, oin, label, q_target, g_target,], [
                np.expand_dims(train_target, axis=1),
                o_target,
                value_target,
                np.expand_dims(qa, axis=1),
                np.expand_dims(ga, axis=1),
                I_target]
