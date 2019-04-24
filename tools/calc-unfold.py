#!/usr/bin/python
# Tool for manually calculating the unfolded geometry 
# See terminology.png for terminology. 

import math

r = inner_radius = 1.64
T = thickness = 2.0
ML = mold_line_distance = 50.0
K = k_factor = 0.38
bend_angle = 90.0

t = thickness * k_factor
BA = bend_allowance = 2.0 * math.pi * (r + t) * (bend_angle / 360.0)
leg_length = ML - BA / 2.0 
ossb = r + T 

print "Effective inner radius: ", round(inner_radius, 2), "mm"
print "Effective outer radius:", round((r + T), 2), "mm"
print "Flange length: ", round((ossb + leg_length), 2), "mm"
print "Bend allowance: ", round(BA, 2), "mm"
print "Leg length: ", round(leg_length, 2), "mm"
