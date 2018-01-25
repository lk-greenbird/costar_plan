from __future__ import print_function

import keras.backend as K
import keras.losses as losses
import keras.optimizers as optimizers
import numpy as np

from keras.callbacks import ModelCheckpoint
from keras.layers.advanced_activations import LeakyReLU
from keras.layers import Input, RepeatVector, Reshape
from keras.layers.embeddings import Embedding
from keras.layers.merge import Concatenate, Multiply
from keras.losses import binary_crossentropy
from keras.models import Model, Sequential
from keras.optimizers import Adam
from matplotlib import pyplot as plt

from .callbacks import *
from .pretrain_image_gan import *
from .planner import *

class ConditionalImageGan(PretrainImageGan):
    '''
    Version of the sampler that only produces results conditioned on a
    particular action; this version does not bother trying to learn a separate
    distribution for each possible state.

    This one generates:
      - image
      - arm command
      - gripper command
    '''

    def __init__(self, *args, **kwargs):
        '''
        As in the other models, we call super() to parse arguments from the
        command line and set things like our optimizer and learning rate.

        Parameters:
        -----------
        taskdef: definition of the problem used to create a task model
        '''
        super(ConditionalImageGan, self).__init__(*args, **kwargs)
        self.PredictorCb = ImageWithFirstCb
        self.rep_size = 256
        self.num_transforms = 3
        self.do_all = True
        self.skip_connections = False
        self.num_generator_files = 1
 
    def _makePredictor(self, features):
        # =====================================================================
        # Create many different image decoders
        (images, arm, gripper) = features
        img_shape, image_size, arm_size, gripper_size = self._sizes(
                images,
                arm,
                gripper)

        # =====================================================================
        # Load the image decoders
        img_in = Input(img_shape,name="predictor_img_in")
        img0_in = Input(img_shape,name="predictor_img0_in")
        arm_in = Input((arm_size,))
        gripper_in = Input((gripper_size,))
        arm_gripper = Concatenate()([arm_in, gripper_in])
        label_in = Input((1,))
        next_option_in = Input((1,), name="next_option_in")
        next_option2_in = Input((1,), name="next_option2_in")
        ins = [img0_in, img_in, next_option_in, next_option2_in]

        if self.skip_connections:
            encoder = self._makeImageEncoder2(img_shape)
            decoder = self._makeImageDecoder2(self.hidden_shape)
        else:
            encoder = self._makeImageEncoder(img_shape)
            decoder = self._makeImageDecoder(self.hidden_shape)

        LoadEncoderWeights(self, encoder, decoder)

        # create input for controlling noise output if that's what we decide
        # that we want to do
        if self.use_noise:
            z = Input((self.num_hypotheses, self.noise_dim))
            ins += [z]

        if self.skip_connections:
            h, s32, s16, s8 = encoder([img0_in, img_in])
        else:
            h = encoder([img_in])
            h0 = encoder(img0_in)

        # =====================================================================
        # Actually get the right outputs
        y = OneHot(self.num_options)(next_option_in)
        y = Flatten()(y)
        y2 = OneHot(self.num_options)(next_option2_in)
        y2 = Flatten()(y2)
        x = h
        tform = self._makeTransform()
        x = tform([h0,h,y])
        x2 = tform([h0,x,y2])
        image_out = decoder([x])
        image_out2 = decoder([x2])

        # =====================================================================
        # Save
        self.transform_model = tform

        # =====================================================================
        # Make the discriminator
        image_discriminator = self._makeImageDiscriminator(img_shape)
        self.discriminator = image_discriminator

        image_discriminator.trainable = False
        is_fake = image_discriminator([
            img0_in, img_in,
            next_option_in, 
            next_option2_in,
            image_out,
            image_out2])

        # =====================================================================
        # Create generator model to train
        lfn = self.loss
        predictor = Model(ins,
                [image_out, image_out2])
        predictor.compile(
                loss=[lfn, lfn],
                optimizer=self.getOptimizer())
        self.generator = predictor

        # =====================================================================
        # And adversarial model 
        model = Model(ins, [image_out, image_out2, is_fake])
        model.compile(
                loss=["mae"]*2 + ["binary_crossentropy"],
                loss_weights=[100., 100., 1.],
                optimizer=self.getOptimizer())
        self.model = model

        return predictor, model, model, ins, h

    def _getData(self, *args, **kwargs):
        features, targets = GetAllMultiData(self.num_options, *args, **kwargs)
        [I, q, g, oin, label, q_target, g_target,] = features
        tt, o1, v, qa, ga, I_target = targets

        # Create the next image including input image
        I0 = I[0,:,:,:]
        length = I.shape[0]
        I0 = np.tile(np.expand_dims(I0,axis=0),[length,1,1,1]) 

        # Extract the next goal
        I_target2, o2 = GetNextGoal(I_target, o1)
        return [I0, I, o1, o2], [ I_target, I_target2 ]

    def _makeImageDiscriminator(self, img_shape):
        '''
        create image-only encoder to extract keypoints from the scene.
        
        Params:
        -------
        img_shape: shape of the image to encode
        '''
        img0 = Input(img_shape,name="img0_encoder_in")
        img = Input(img_shape,name="img_encoder_in")
        img_goal = Input(img_shape,name="goal_encoder_in")
        img_goal2 = Input(img_shape,name="goal2_encoder_in")
        option = Input((1,),name="disc_options")
        option2 = Input((1,),name="disc2_options")
        ins = [img0, img, option, option2, img_goal, img_goal2]
        dr = self.dropout_rate
        dr = 0

        x0 = AddConv2D(img0, 64, [4,4], 1, dr, "same", lrelu=True, bn=False)
        xobs = AddConv2D(img, 64, [4,4], 1, dr, "same", lrelu=True, bn=False)
        xg1 = AddConv2D(img_goal, 64, [4,4], 1, dr, "same", lrelu=True, bn=False)
        xg2 = AddConv2D(img_goal2, 64, [4,4], 1, dr, "same", lrelu=True, bn=False)

        #x1 = Add()([x0, xobs, xg1])
        #x2 = Add()([x0, xg1, xg2])
        x1 = Add()([xobs, xg1])
        x2 = Add()([xg1, xg2])
        
        # -------------------------------------------------------------
        y = OneHot(self.num_options)(option)
        y = AddDense(y, 64, "lrelu", dr)
        x1 = TileOnto(x1, y, 64, (64,64), add=True)
        x1 = AddConv2D(x1, 64, [4,4], 2, dr, "same", lrelu=True, bn=False)

        # -------------------------------------------------------------
        y = OneHot(self.num_options)(option2)
        y = AddDense(y, 64, "lrelu", dr)
        x2 = TileOnto(x2, y, 64, (64,64), add=True)
        x2 = AddConv2D(x2, 64, [4,4], 2, dr, "same", lrelu=True, bn=False)

        #x = Concatenate()([x1, x2])
        x = x2
        x = AddConv2D(x, 128, [4,4], 2, dr, "same", lrelu=True)
        x= AddConv2D(x, 256, [4,4], 2, dr, "same", lrelu=True)
        x = AddConv2D(x, 1, [1,1], 1, 0., "same", activation="sigmoid",
                bn=False)

        #x = MaxPooling2D(pool_size=(8,8))(x)
        x = AveragePooling2D(pool_size=(8,8))(x)
        x = Flatten()(x)
        discrim = Model(ins, x, name="image_discriminator")
        self.lr *= 2.
        loss = wasserstein_loss if self.use_wasserstein else "binary_crossentropy"
        discrim.compile(loss=loss, loss_weights=[1.],
                optimizer=self.getOptimizer())
        self.lr *= 0.5
        self.image_discriminator = discrim
        return discrim


