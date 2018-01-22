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

from .abstract import *
from .callbacks import *
from .robot_multi_models import *
from .split import *
from .mhp_loss import *
from .loss import *
from .sampler2 import *

from .conditional_image import ConditionalImage
from .dvrk import *

class ConditionalImageJigsaws(ConditionalImage):

    def __init__(self, *args, **kwargs):

        super(ConditionalImageJigsaws, self).__init__(*args, **kwargs)

        self.num_options = SuturingNumOptions()

    def _makeModel(self, image, *args, **kwargs):

        img_shape = image.shape[1:]

        img0_in = Input(img_shape, name="predictor_img0_in")
        img_in = Input(img_shape, name="predictor_img_in")
        prev_option_in = Input((1,), name="predictor_prev_option_in")
        ins = [img0_in, img_in]

        if self.skip_connections:
            encoder = self._makeImageEncoder2(img_shape)
            decoder = self._makeImageDecoder2(self.hidden_shape)
        else:
            encoder = MakeJigsawsImageEncoder(self, img_shape)
            decoder = MakeJigsawsImageDecoder(self, self.hidden_shape)

        # load encoder/decoder weights if found
        try:
            encoder.load_weights(self._makeName(
                #"pretrain_image_encoder_model_jigsaws",
                "pretrain_image_gan_model_jigsaws",
                "image_encoder.h5f"))
            encoder.trainable = self.retrain
            decoder.load_weights(self._makeName(
                #"pretrain_image_encoder_model_jigsaws",
                "pretrain_image_gan_model_jigsaws",
                "image_decoder.h5f"))
            decoder.trainable = self.retrain
        except Exception as e:
            if not self.retrain:
                raise e


        # =====================================================================
        # Load the discriminator
        image_discriminator = MakeJigsawsImageClassifier(self, img_shape)
        #image_discriminator.load_weights("discriminator_model_classifier.h5f")
        image_discriminator.load_weights(
                self._makeName("goal_discriminator_model_jigsaws", "predictor_weights.h5f"))
        image_discriminator.trainable = False

        # =====================================================================
        # Create encoded state
        if self.skip_connections:
            h, s32, s16, s8 = encoder([img0_in, img_in])
        else:
            h = encoder(img_in)
            h0 = encoder(img0_in)

        # Create model for predicting label
        next_model = GetJigsawsNextModel(h, self.num_options, 128,
                self.decoder_dropout_rate)
        next_model.compile(loss="mae", optimizer=self.getOptimizer())
        next_option_out = next_model([h0, h, prev_option_in])
        self.next_model = next_model

        # create input for controlling noise output if that's what we decide
        # that we want to do
        if self.use_noise:
            z = Input((self.num_hypotheses, self.noise_dim))
            ins += [z]

        option_in = Input((1,), name="option_in")
        option_in2 = Input((1,), name="option_in2")
        ins += [option_in, option_in2]

        # Image model
        y = Flatten()(OneHot(self.num_options)(option_in))
        y2 = Flatten()(OneHot(self.num_options)(option_in2))
        x = h
        #tform = self._makeTransform(h_dim=(12,16))
        tform = self._makeTransform(h_dim=(6,8))
        x = tform([h0, h, y])
        x2 = tform([h0, x, y2])
        image_out, image_out2 = decoder([x]), decoder([x2])
        disc_out2 = image_discriminator(image_out2)

        lfn = self.loss
        lfn2 = "logcosh"

        # =====================================================================
        # Create models to train
        predictor = Model(ins + [prev_option_in],
                [image_out, image_out2, next_option_out])
        predictor.compile(
                loss=[lfn, lfn, "binary_crossentropy"],
                loss_weights=[1., 1., 0.1],
                optimizer=self.getOptimizer())
        model = Model(ins + [prev_option_in],
                [image_out, image_out2, next_option_out, disc_out2])
        model.compile(
                loss=[lfn, lfn, "binary_crossentropy", "categorical_crossentropy"],
                loss_weights=[1., 1., 0.1, 1e-4],
                optimizer=self.getOptimizer())

        self.predictor = predictor
        self.model = model

    def _getData(self, image, label, goal_image, goal_label,
            prev_label, *args, **kwargs):

        image = np.array(image) / 255.
        goal_image = np.array(goal_image) / 255.

        goal_image2, label2 = GetNextGoal(goal_image, label)

        # Extend image_0 to full length of sequence
        image0 = image[0,:,:,:]
        length = image.shape[0]
        image0 = np.tile(np.expand_dims(image0,axis=0),[length,1,1,1])

        label_1h = np.squeeze(ToOneHot2D(label, self.num_options))
        label2_1h = np.squeeze(ToOneHot2D(label2, self.num_options))
        return [image0, image, label, goal_label, prev_label], [goal_image, goal_image2, label_1h, label2_1h]
