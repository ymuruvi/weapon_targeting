#!/usr/bin/env python3

from http.client import responses
import simulator as sim
import problem_generators as pg
import features as jf
import solvers as js
import numpy as np
import json
import urllib
import copy
import time
import configparser

from flask import Flask, request, jsonify
from flask_cors import CORS
from simulator import print_grid

config = configparser.ConfigParser()
config.read('config.ini')

PORT = int(config['MCNANO']['port'])
server_cert = config['MCNANO']['cert']
server_key = config['MCNANO']['priv_key']

app = Flask(__name__)
CORS(app)
pythonState = False
env = sim.Simulation(sim.mergeState)

appEnv = None
app_problem = None
originalAppProblem = None
total_reward = 0
sequence_num = 0

rewards = []


MULTIPLE = True

COMMANDS = {"step": 1, "restart": 2}


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

    # return jsonify({'a':1,'b':2})
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


@app.route('/app', methods=['POST'])
def get_app_command():
    global app_problem
    global appEnv
    global sequence_num
    global rewards
    decodedData = request.data.decode("UTF-8")
    #print(f"{request = }\n{decodedData = }")
    json_string = urllib.parse.unquote(request.data.decode("UTF-8"))
    # print(json_string)
    command = json.loads(json_string)
    print(command)
    # return jsonify("Response String")
    instruction = command['instruction']
    #print(f"Instruction: {instruction = }")
    response = None
    shape = [1]

    if(instruction == 'new'):
        sequence_num = 0
        data = command['args']
        app_problem = pg.network_validation(data['effectors'], data['targets'])

        appEnv = sim.Simulation(sim.mergeState, problem=app_problem)
        np_state = appEnv.getState()

        state_list = np_state.tolist()
        state_shape = (list(np_state.shape))
        state_shape.insert(0, 1)
        #j_list = json.dumps(state_list)

        response = {'state': state_list, 'reward': 0,
                    'terminal': False, 'time': time.time(), 'shape': state_shape, 'valid': True}

    elif(instruction == 'reset'):
        sequence_num = 0
        #state = appEnv.reset()
        np_state = appEnv.getState()
        state_list = np_state.tolist()
        state_shape = (list(np_state.shape))
        state_shape.insert(0, 1)
        response = {'state': state_list, 'reward': 0, 'terminal': False,
                    'time': time.time(), 'shape': state_shape, 'valid': True}

        for r in rewards:
            print(r)

    elif(instruction == 'step'):
        valid = True
        sequence_num += 1
        action_obj = command['action']
        action = action_obj['effector'], action_obj['task']
        reward = 0
        terminal = False
        try:
            np_state, reward, terminal = appEnv.update(action)
            if reward == 0:
                terminal = True
        except Exception as e:
            np_state = appEnv.getState()
            valid = False
        state_list = np_state.tolist()
        state_shape = (list(np_state.shape))
        state_shape.insert(0, 1)
        response = {'state': state_list,  'reward': reward,
                    'terminal': terminal, 'time': 0, 'shape': state_shape, 'valid': valid}
    elif(instruction == 'test'):
        server_state = {'time': time.time(), 'status': 'working'}
        response = {'server_state': server_state}

    js_str = json.dumps(response)
    with open('json_state.json', 'w') as outfile:
        outfile.write(js_str)
        #print("WRITING TO FILE")

    js_response = jsonify(response)

    #print(f"({len(js_str)=}): {response}")
    return js_response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, ssl_context=(server_cert, server_key))

