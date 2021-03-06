from __future__ import print_function

import keras.backend as K
import keras.losses as losses
import keras.optimizers as optimizers
import numpy as np

from matplotlib import pyplot as plt

from keras.layers.advanced_activations import LeakyReLU
from keras.layers import Input, RepeatVector, Reshape
from keras.layers import UpSampling2D, Conv2DTranspose
from keras.layers import BatchNormalization, Dropout
from keras.layers import Dense, Conv2D, Activation, Flatten
from keras.layers.merge import Concatenate
from keras.losses import binary_crossentropy
from keras.models import Model, Sequential
from keras.optimizers import Adam
from keras.utils.np_utils import to_categorical

from .multi_hierarchical import RobotMultiHierarchical
from .husky import *
from .multi import *

class RobotPolicy(RobotMultiHierarchical):

    '''
    This class learns one policy at a time
    '''

    def __init__(self, taskdef, *args, **kwargs):
        super(RobotPolicy, self).__init__(taskdef, *args, **kwargs)

        if self.option_num is None:
            raise RuntimeError("Policy model requires an 'option' argument")
        if self.option_num >= self.null_option:
            raise RuntimeError("Policy model requires an option between 0 and " +str(self.null_option)) 

        # add option to self.name, for saving
        self.name += "_opt" + str(self.option_num)


    def _makeModel(self, features, arm, gripper, arm_cmd, gripper_cmd, *args, **kwargs):
        '''
        Set up all models necessary to create actions
        '''
        img_shape, image_size, arm_size, gripper_size = self._sizes(
                features,
                arm,
                gripper)
        encoder = self._makeImageEncoder(img_shape)

        # Note: we must load weights for this version of the model. There's no
        # alternative, because we're expecting to train many different models
        # here.
        encoder.load_weights(self.makeName(
            "pretrain_image_encoder",
            #"pretrain_image_gan_model",
            "image_encoder"))
        encoder.trainable = False

        # Make end-to-end conditional actor
        self.model = MakeMultiPolicy(self, 
                encoder, features, arm, gripper,
                arm_cmd, gripper_cmd, option=self.option_num)
        self.model.summary()


    def _getData(self, *args, **kwargs):
        '''
        Filter out the data not relevant to the current option
        '''
        features, targets = GetAllMultiData(self.num_options, *args, **kwargs)
        [Iorig, _, _, _, label, _, _,] = features
        labels = label[:]
        # find the matches for filtering
        idx = labels == self.option_num
        if np.count_nonzero(idx) > 0:
            [I, q, g, _, _, _, _,] = [f[idx] for f in features]
            I0 = Iorig[0,:,:,:]
            length = I.shape[0]
            I0 = np.tile(np.expand_dims(I0,axis=0),[length,1,1,1]) 
            [_, _, _, qa, ga, _] = [t[idx] for t in targets]
            return [I0, I, q, g], [qa[:,0,:], ga[:,0,:]]
        else:
            return [], []

class HuskyPolicy(RobotPolicy):
    def __init__(self, taskdef, *args, **kwargs):
        self.options = HuskyNumOptions()
        self.null_option = HuskyNullOption()
        super(HuskyPolicy, self).__init__(taskdef, *args, **kwargs)

    def _makeModel(self, image, pose, action, *args, **kwargs):
        '''
        Set up all models necessary to create actions
        '''
        
        img_shape = image.shape[1:]

        # Note: we must load weights for this version of the model. There's no
        # alternative, because we're expecting to train many different models
        # here.
        encoder = self._makeImageEncoder(img_shape)
        encoder.load_weights(self._makeName(
            "pretrain_image_encoder_model_husky",
            #"pretrain_image_gan_model_husky",
            "image_encoder.h5f"))
        encoder.trainable = False

        # Make end-to-end conditional actor
        self.model = MakeHuskyPolicy(self, 
                encoder, image, pose, action, option=self.option_num)



    def _getData(self, *args, **kwargs):
        '''
        Filter out the data not relevant to the current option
        '''
        return GetPolicyHuskyData(self.num_options, self.option_num, *args,
                **kwargs)
