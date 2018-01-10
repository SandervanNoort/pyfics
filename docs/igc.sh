#!/bin/sh

# ssh results@influenzanet.eu -L 5000:fics2.freechess.org:23 -N -n -f
ssh results@influenzanet.eu -L 5000:freechess.org:5000 -N -n -f
PYTHONPATH=. bin/pyfics
killall ssh
