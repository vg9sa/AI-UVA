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
import reflex

EntityInfo = namedtuple('EntityInfo', 'x, y, z, name')

# Create one agent host for parsing:
agent_hosts = [MalmoPython.AgentHost()]

# Parse the command-line options:
agent_hosts[0].addOptionalFlag( "debug,d", "Display debug information.")
agent_hosts[0].addOptionalIntArgument("agents,n", "Number of agents to use, including observer.", 2)
agent_hosts[0].addOptionalStringArgument("map,m", "Name of map to be used", "openClassic")

try:
    agent_hosts[0].parse( sys.argv )
except RuntimeError as e:
    print('ERROR:',e)
    print(agent_hosts[0].getUsage())
    exit(1)
if agent_hosts[0].receivedArgument("help"):
    print(agent_hosts[0].getUsage())
    exit(0)

DEBUG = agent_hosts[0].receivedArgument("debug")
INTEGRATION_TEST_MODE = agent_hosts[0].receivedArgument("test")
agents_requested = agent_hosts[0].getIntArgument("agents")
NUM_AGENTS = max(1, agents_requested) # Will be NUM_AGENTS robots running around, plus one static observer.
map_requested = agent_hosts[0].getStringArgument("map")
# Create the rest of the agent hosts - one for each robot, plus one to give a bird's-eye view:
agent_hosts += [MalmoPython.AgentHost() for x in range(1, NUM_AGENTS) ]

# Set up debug output:
for ah in agent_hosts:
    ah.setDebugOutput(DEBUG)    # Turn client-pool connection messages on/off.

if sys.version_info[0] == 2:
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)  # flush print output immediately
else:
    import functools
    print = functools.partial(print, flush=True)


def safeStartMission(agent_host, my_mission, my_client_pool, my_mission_record, role, expId):
    used_attempts = 0
    max_attempts = 5
    print("Calling startMission for role", role)
    while True:
        try:
            # Attempt start:
            agent_host.startMission(my_mission, my_client_pool, my_mission_record, role, expId)
            break
        except MalmoPython.MissionException as e:
            errorCode = e.details.errorCode
            if errorCode == MalmoPython.MissionErrorCode.MISSION_SERVER_WARMING_UP:
                print("Server not quite ready yet - waiting...")
                time.sleep(2)
            elif errorCode == MalmoPython.MissionErrorCode.MISSION_INSUFFICIENT_CLIENTS_AVAILABLE:
                print("Not enough available Minecraft instances running.")
                used_attempts += 1
                if used_attempts < max_attempts:
                    print("Will wait in case they are starting up.", max_attempts - used_attempts, "attempts left.")
                    time.sleep(2)
            elif errorCode == MalmoPython.MissionErrorCode.MISSION_SERVER_NOT_FOUND:
                print("Server not found - has the mission with role 0 been started yet?")
                used_attempts += 1
                if used_attempts < max_attempts:
                    print("Will wait and retry.", max_attempts - used_attempts, "attempts left.")
                    time.sleep(2)
            else:
                print("Other error:", e.message)
                print("Waiting will not help here - bailing immediately.")
                exit(1)
        if used_attempts == max_attempts:
            print("All chances used up - bailing now.")
            exit(1)
    print("startMission called okay.")

def safeWaitForStart(agent_hosts):
    print("Waiting for the mission to start", end=' ')
    start_flags = [False for a in agent_hosts]
    start_time = time.time()
    time_out = 120  # Allow a two minute timeout.
    while not all(start_flags) and time.time() - start_time < time_out:
        states = [a.peekWorldState() for a in agent_hosts]
        start_flags = [w.has_mission_begun for w in states]
        errors = [e for w in states for e in w.errors]
        if len(errors) > 0:
            print("Errors waiting for mission start:")
            for e in errors:
                print(e.text)
            print("Bailing now.")
            exit(1)
        time.sleep(0.1)
        print(".", end=' ')
    if time.time() - start_time >= time_out:
        print("Timed out while waiting for mission to start - bailing.")
        exit(1)
    print()
    print("Mission has started.")


def getLayout(name):
    matrix = tryToLoad("layouts/" + name)
    return matrix

def tryToLoad(fullname):
    if (not os.path.exists(fullname)): return None
    f = open(fullname)
    Matrix = [line.strip() for line in f]
    f.close()
    return Matrix

level_mat = getLayout(map_requested + ".lay")

def drawItems(x, z):
    return  '<DrawItem x="' + str(x) + '" y="56" z="' + str(z) + '" type="apple"/>'


def GenBlock(x, y, z, blocktype):
    return '<DrawBlock x="' + str(x) + '" y="' + str(y) + '" z="' + str(z) + '" type="' + blocktype + '"/>'

def GenPlayerStart(x, z):
    return '<Placement x="' + str(x + 0.5) + '" y="56" z="' + str(z + 0.5) + '" yaw="0"/>'

def GenEnemyStart(x, z):
    return '<Placement x="' + str(x + 0.5) + '" y="56" z="' + str(z + 0.5) + '" yaw="0"/>'

pStart = {'x': 0, 'z': 0}
eStart = {'x': 0, 'z': 0}

pCurr = {'x': 0, 'z': 0}
eCurr = {'x': 0, 'z': 0}

food = []

def mazeCreator():
    genstring = ""
    genstring += GenBlock(0, 65, 0, "glass") + "\n"
    for i in range(len(level_mat)):
        for j in range(len(level_mat[0])):

            if level_mat[i][j] == "%":
                genstring += GenBlock(i, 54, j, "diamond_block") + "\n"
                genstring += GenBlock(i, 55, j, "diamond_block") + "\n"
                genstring += GenBlock(i, 56, j, "diamond_block") + "\n"

            elif level_mat[i][j] == "P":
                pStart['x'] = i
                pStart['z'] = j
                pCurr['x'] = i
                pCurr['z'] = j

            elif level_mat[i][j] == ".":
                genstring += GenBlock(i, 55, j, "glowstone") + "\n"
                food.append((i, j))

            elif level_mat[i][j] == "G":
                eStart['x'] = i
                eStart['z'] = j
                eCurr['x'] = i
                eCurr['z'] = j

    return genstring

def invMake():
    xml = ""
    for i in range(0, 39):
        xml += '<InventoryObject type="diamond_axe" slot="' + str(i) + '" quantity="1"/>'
    return(xml)

def getXML(reset):
    # Set up the Mission XML:
    xml = '''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
            <Mission xmlns="http://ProjectMalmo.microsoft.com" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
              <About>
                <Summary>Hello world!</Summary>
              </About>
              <ServerSection>
                <ServerHandlers>
                  <FlatWorldGenerator generatorString="3;7,44*49,73,35:1,159:4,95:13,35:13,159:11,95:10,159:14,159:6,35:6,95:6;12;"/>
                  <DrawingDecorator>
                    ''' + mazeCreator() + '''
                  </DrawingDecorator>
                  <ServerQuitFromTimeUp timeLimitMs="100000"/>
                  <ServerQuitWhenAnyAgentFinishes/>
                </ServerHandlers>
              </ServerSection>
              <AgentSection mode="Survival">
                <Name>Player</Name>
                <AgentStart> '''   + GenPlayerStart(pStart['x'], pStart['z']) +  ''' </AgentStart>
                <AgentHandlers>
                  <DiscreteMovementCommands/>
                  <ObservationFromFullStats/>
                  <ObservationFromGrid>
                      <Grid name="floor3x3W">
                        <min x="-1" y="0" z="-1"/>
                        <max x="1" y="0" z="1"/>
                      </Grid>
                      <Grid name="floor3x3F">
                        <min x="-1" y="-1" z="-1"/>
                        <max x="1" y="-1" z="1"/>
                      </Grid>
                  </ObservationFromGrid>
                </AgentHandlers>
              </AgentSection>
              <AgentSection mode="Survival">
                <Name>Enemy</Name>
                <AgentStart> 
                '''   + GenEnemyStart(eStart['x'], eStart['z']) +  ''' 
                <Inventory>''' + invMake() + '''</Inventory>
                </AgentStart>
                <AgentHandlers>
                  <DiscreteMovementCommands/>
                  <ObservationFromFullStats/>
                  <ObservationFromGrid>
                      <Grid name="floor3x3W">
                        <min x="-1" y="0" z="-1"/>
                        <max x="1" y="0" z="1"/>
                      </Grid>
                      <Grid name="floor3x3F">
                        <min x="-1" y="-1" z="-1"/>
                        <max x="1" y="-1" z="1"/>
                      </Grid>
                  </ObservationFromGrid>
                </AgentHandlers>
              </AgentSection>
            </Mission>'''

    return xml

client_pool = MalmoPython.ClientPool()
for x in range(10000, 10000 + NUM_AGENTS + 1):
    client_pool.add( MalmoPython.ClientInfo('127.0.0.1', x) )


print("Running mission")
# Create mission xml - use forcereset if this is the first mission.
my_mission = MalmoPython.MissionSpec(getXML("true"), True)

experimentID = str(uuid.uuid4())

for i in range(len(agent_hosts)):
    safeStartMission(agent_hosts[i], my_mission, client_pool, MalmoPython.MissionRecordSpec(), i, experimentID)

safeWaitForStart(agent_hosts)

time.sleep(1)
running = True

current_pos = [(0,0) for x in range(NUM_AGENTS)]
# When an agent is killed, it stops getting observations etc. Track this, so we know when to bail.

timed_out = False
g_score = 0

# Main mission loop
while not timed_out and food:
    print('global score:', g_score)

    for i in range(NUM_AGENTS):
        ah = agent_hosts[i]
        world_state = ah.getWorldState()
        if world_state.is_mission_running == False:
            timed_out = True
        if world_state.is_mission_running and world_state.number_of_observations_since_last_state > 0:
            msg = world_state.observations[-1].text
            ob = json.loads(msg)

            if "XPos" in ob and "ZPos" in ob:
                current_pos[i] = (ob[u'XPos'], ob[u'ZPos'])
                print("First pos ", current_pos[i])
                #print(current_pos[i])
            if ob['Name'] == 'Enemy':
                print('enemy moving:')
                reflex.enemyAgentMoveRand(ah, world_state)
                ah = agent_hosts[i]
                world_state = ah.getWorldState()
                if world_state.is_mission_running and world_state.number_of_observations_since_last_state > 0:
                    msg = world_state.observations[-1].text
                    ob = json.loads(msg)
                if "XPos" in ob and "ZPos" in ob:
                    current_pos[i] = (ob[u'XPos'], ob[u'ZPos'])
                    print("Second pos ", current_pos[i])
                eCurr['x'] = current_pos[i][0]
                eCurr['z'] = current_pos[i][1]
                if (current_pos[i] == (pCurr['x'], pCurr['z'])):
                    g_score -= 100
                    timed_out = True
                    break
                time.sleep(0.1)
            if ob['Name'] == 'Player':
                if (current_pos[i] == (eCurr['x'], eCurr['z'])):
                    g_score -= 100
                    timed_out = True
                    break

                print('agent moving')
                reflex.reflexAgentMove(ah, current_pos[i], world_state, food, (eCurr['x'], eCurr['z']))
                ah = agent_hosts[i]
                world_state = ah.getWorldState()
                if world_state.is_mission_running and world_state.number_of_observations_since_last_state > 0:
                    msg = world_state.observations[-1].text
                    ob = json.loads(msg)
                if "XPos" in ob and "ZPos" in ob:
                    current_pos[i] = (ob[u'XPos'], ob[u'ZPos'])
                    print("Second pos ", current_pos[i])
                if ((current_pos[i][0] - 0.5, current_pos[i][1] - 0.5) in food):
                    print("Food found!")
                    food.remove((current_pos[i][0] - 0.5, current_pos[i][1] - 0.5))
                    g_score += 10
                if (current_pos[i] == (eCurr['x'], eCurr['z'])):
                    g_score -= 100
                    timed_out = True
                    break
                #g_score -= 1
                pCurr['x'] = current_pos[i][0]
                pCurr['z'] = current_pos[i][1]

    time.sleep(0.05)
print(food)
print(g_score)

print("Waiting for mission to end ", end=' ')
# Mission should have ended already, but we want to wait until all the various agent hosts
# have had a chance to respond to their mission ended message.
hasEnded = True
while not hasEnded:
    hasEnded = True # assume all good
    print(".", end="")
    time.sleep(0.1)
    for ah in agent_hosts:
        world_state = ah.getWorldState()
        if world_state.is_mission_running:
            hasEnded = False # all not good


time.sleep(2)
