#!/bin/bash -l

set -e
set -x
set -u

for lr in 0.001 0.0002 0.0001
do
  # just use the adam optimizer
  for opt in adam
  do
    for loss in mae logcosh
    do
    # what do we do about skip connections?
    for skip in 0 # 1
    do
      # Noise: add extra ones with no noise at all
      for noise_dim in 0 # 1 8 32
      do
        hd=true
        for dr in 0. 0.1 0.2 0.3 0.4 0.5
        do
		MODELDIR="$HOME/.costar/stack_$learning_rate$optimizer$dropout$noise_dim$loss"
		rm $MODELDIR/debug/*.png
	done
      done
    done
    done
  done
done

 
