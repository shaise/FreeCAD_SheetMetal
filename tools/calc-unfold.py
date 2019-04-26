#!/usr/bin/python
# Tool for manually calculating the unfolded geometry 
# See terminology.png for terminology. 

import math

r = inner_radius = 1.64
T = thickness = 2.0
ML = mold_line_distance = 50
K = k_factor = 0.38
bend_angle = 90.0

t = thickness * k_factor
BA = bend_allowance = 2.0 * math.pi * (r + t) * (bend_angle / 360.0)
leg_length = ML - BA / 2.0 
ossb = r + T
flange_diff = ossb - BA / 2.0
flange_length = ossb + leg_length

print "Inputs: r, T, Kf, ML, angle"
print "---------------------------------"
print "Effective inner radius: %.2f mm" % inner_radius
print "Effective outer radius: %.2f mm" % (r + T)
print "Flange length: %.2f mm" % flange_length
print "* Flange diff (FD = FL - ML): %.2f mm" % flange_diff
print "Bend allowance: %.2f mm" % BA
print "Leg length: %.2f mm" % leg_length
