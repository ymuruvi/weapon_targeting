#!/usr/bin/env python3

from PGTest import printProblem
import simulator as sim
import problem_generators as pg
import features as jf
import solvers as js
import numpy as np
import json
import urllib
import copy
from flask import Flask, request, jsonify
from flask_cors import CORS
from simulator import print_grid

app = Flask(__name__)
CORS(app)
pythonState = False
env = sim.Simulation(sim.mergeState)

appEnv = None
appProblem = None
total_reward = 0
# Used to step through
MULTIPLE = True

COMMANDS = {"step":1,"restart":2}


def get_action_from_solver(state):
    _, solution = js.greedy(state)  # AStar(state)
    return solution[0]


def get_actions_from_solver(state):
    _, solution = js.greedy(state)
    return solution


def compare_results(python_state, unity_state):
    pad = 0  # len(JF.EffectorFeatures) + len(JF.TaskFeatures)
    print(
        f"U-Energy cost: {unity_state[:, 0, pad + jf.EffectorFeatures.ENERGYLEFT]}")
    print(
        f"P-Energy cost: {python_state[:, 0, pad + jf.EffectorFeatures.ENERGYLEFT]}")
    print(
        f"U-Time cost: {unity_state[:, 0, pad + jf.EffectorFeatures.TIMELEFT]}")
    print(
        f"P-Time cost: {python_state[:, 0, pad + jf.EffectorFeatures.TIMELEFT]}")


@app.route('/', methods=['GET'])
def test_connection():
    return jsonify('The connection to the server was successful')


@app.route('/', methods=['POST'])
def get_action():
    global pythonState
    json_string = urllib.parse.unquote(request.data.decode("UTF-8"))
    problem = json.loads(json_string)
    for key in problem.keys():
        problem[key] = np.asarray(problem[key])
    pg.correct_effector_data(problem)
    state = sim.mergeState(
        problem['Effectors'], problem['Targets'], problem['Opportunities'])

    #return jsonify({'a':1,'b':2})
    if type(pythonState) == np.ndarray:
        compare_results(pythonState, state)
    if MULTIPLE:
        actions = get_actions_from_solver(copy.deepcopy(problem))
        print(f"Selected actions: {actions}")
        assets = {'assets': []}
        for action in actions:
            assets['assets'].append([int(action[0]), int(action[1])])
        return jsonify(assets)
    else:
        action = get_action_from_solver(copy.deepcopy(problem))
        print(f"Selected action: {action = }")
        pythonState, _, _ = env.update_state(
            (action[0], action[1]), state.copy())
        return jsonify({'assets': [int(action[0]), int(action[1])]})


@app.route('/app', methods=['POST', 'GET'])
def get_app_command():
    global appProblem
    global appEnv
    print(f"{request = }")
    json_string = urllib.parse.unquote(request.data.decode("UTF-8"))
    command = json.loads(json_string)
    print(command)
    #return jsonify("Response String")
    instruction = command['instruction']
    print(f"Instruction: {instruction = }")
    response = None

    if(instruction == 'new'):
        total_reward = 0
        data = command['args']
        appProblem = pg.network_validation(data['effectors'], data['targets'])
        appEnv = sim.Simulation(sim.mergeState, problem=appProblem)
        np_state = appEnv.getState()
        
        list_state = np_state.tolist()
        print(np_state.shape)
        j_list = json.dumps(list_state)

        response = {'state': list_state, 'reward': None, 'terminal':None, 'time': 0}

    elif(instruction == 'reset'):
        total_reward = 0
        print("Resetting Scenario with same problem")
        state = appEnv.reset()
        np_state = appEnv.getState()
        list_state = np_state.tolist()

        response = {'state': list_state, 'reward': None, 'time': 0}

    elif(instruction == 'step'):
        print("Stepping")
        print(f"CMD: {command}")
        action_obj = command['action']
        print(f"Doing Action: {action_obj=}")
        action = action_obj['effector'], action_obj['task']
        valid_action = True
        reward = 0
        terminal = False
        valid_action = True
        try:
            new_state, reward, terminal = appEnv.update(action)
        except:
            new_state = appEnv.getState()
        state_list = new_state.tolist()
        #print(f"{new_state}")
        #print_grid
        print(f"{new_state.shape=}")
        response = {'state': state_list,'valid': valid_action,  'reward': reward, 'terminal':terminal, 'time': 0}

    js_response = jsonify(response)
    print(f"{js_response}")
    return js_response


app.run(host="0.0.0.0")
