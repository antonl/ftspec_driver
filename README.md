# FT two-photon measurement

## Description

This project mashes up code I wrote in the @antonl/notebooks and  @antonl/pyDAQmx repos to do an actual time-domain FT measurement.

The idea is this: 
- start motor driver and start moving it very slowly
- capture the output of photodiodes for fringe tracking as the motor moves
- use ellipse-fitting code to determine the gains/offsets 
- massage the raw data and use unwrap to obtain time-delays
- fourier transform the data to reconstruct the spectrum

## Possible improvements

- make sure that continuous measurements are not missing samples. a relatively simple check is to store a bunch of frames and then take a derivative of each trace. if the derivatives are huge at periodic intervals, it is likely that I'm doing something wrong
- make the motor driver code easier to use. Make it use the slave library I found

