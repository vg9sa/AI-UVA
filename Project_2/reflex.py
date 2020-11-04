# Created by Minbiao Han and Roman Sharykin
# AI fall 2018

from __future__ import print_function
from __future__ import division

from builtins import range
from past.utils import old_div
import MalmoPython
import json
import logging
import math
import os
import random
import sys
import time
import re
import uuid
from collections import namedtuple
from operator import add
from random import *
import numpy as np

### You should define your evaluation function here
# Inputs: pos - tuple (position of player), enemy_pos - tuple, food - array
# Output: your evaluation score
def evalfuncReflex(pos, enemy_pos, dest_blocks):
    ### YOUR CODE HERE ###
    return

### Implement a way for the agent to decide which way to move
# Inputs: pos - tuple (position of player), world_state, enemy_pos - tuple, food - array
# Output: direction in which to move (can be a string, int, or whatever way you want to implement it)
def chooseAction(pos, wstate, dest_blocks, enemy_pos):
    ### YOUR CODE HERE ###
    return

### Move the agent here
# Output: void (should just call the correct movement function)
def reflexAgentMove(agent, pos, wstate, dest_blocks, enemy_pos):
    ### YOUR CODE HERE ###
    return

### Helper methods for you to use ###

# Simple movement functions
# Hint: if you want your execution to run faster you can decrease time.sleep
def moveRight(ah):
    ah.sendCommand("strafe 1")
    time.sleep(0.1)


def moveLeft(ah):
    ah.sendCommand("strafe -1")
    time.sleep(0.1)


def moveStraight(ah):
    ah.sendCommand("move 1")
    time.sleep(0.1)


def moveBack(ah):
    ah.sendCommand("move -1")
    time.sleep(0.1)

# Used to find which movements will result in the player walking into a wall
### Input: current world state
### Output: An array directional strings
def illegalMoves(world_state):
    blocks = []
    if world_state.number_of_observations_since_last_state > 0:
        msg = world_state.observations[-1].text
        observations = json.loads(msg)
        grid = observations.get(u'floor3x3W', 0)
        if grid[3] == u'diamond_block':
            blocks.append("right")
        if grid[1] == u'diamond_block':
            blocks.append("back")
        if grid[5] == u'diamond_block':
            blocks.append("left")
        if grid[7] == u'diamond_block':
            blocks.append("forward")

        return blocks

# Used to find the Manhattan distance between two tuples
def manhattan_distance(start, end):
    sx, sy = start
    ex, ey = end
    return abs(ex - sx) + abs(ey - sy)

# Do not modify!
###
###
# This functions moves the enemy agent randomly #
def enemyAgentMoveRand(agent, ws):
    time.sleep(0.1)
    illegalgrid = illegalMoves(ws)
    legalLST = ["right", "left", "forward", "back"]
    for x in illegalgrid:
        if x in legalLST:
            legalLST.remove(x)
    y = randint(0,len(legalLST)-1)
    togo = legalLST[y]
    if togo == "right":
        moveRight(agent)

    elif togo == "left":
        moveLeft(agent)

    elif togo == "forward":
        moveStraight(agent)

    elif togo == "back":
        moveBack(agent)
