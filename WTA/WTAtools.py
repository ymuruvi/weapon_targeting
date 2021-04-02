import WTAOR
import WTAGA
import numpy as np
import json
import secrets
import os
import time
import csv
import argparse

TOKEN_LENGTH = 5


def log(string):
    print(f"[{time.asctime()}] {string}")


def save_problem(problem, filename):
    to_file = {}
    for key in problem.keys():
        to_file[key] = np.asarray(problem[key]).tolist()
    with open(filename, 'w') as file:
        json.dump(to_file, file)


def load_problem(filename):
    problem = {}
    with open(filename, 'r') as file:
        from_file = json.load(file)
    for key in from_file.keys():
        problem[key] = np.asarray(from_file[key])
    return problem


def new_problem(weapons=5, targets=5):
    p = np.random.uniform(0.6, 0.9, (weapons, targets))  # uniform between 0.6 and 0.9
    values = np.random.randint(25, 100, targets, dtype=int).tolist()  # uniform between 25 and 100
    return {"values": values, "p": p}


def safe_filename(size_str, json_prefix):
    # TODO: Check that the number has been used or not; provide filename with prepended zeros
    return json_prefix + "-" + secrets.token_urlsafe(TOKEN_LENGTH) + size_str + ".json"


def generate_dataset(weapons=5, targets=5, quantity=100, solve_problems=True, csv_filename=time.time(),
                     json_prefix="train", json_name_offset=0):
    solvers = [{'name': "Genetic Algorithm", 'function': WTAGA.wta_ga_solver, 'solve': True},
               {'name': "OR-Tools", 'function': WTAOR.wta_or_solver, 'solve': True}]

    size_str = f"{weapons}x{targets}"
    try:
        os.mkdir(size_str)
    except:
        pass
    csv_content = []
    csv_row = ["filename", "total reward"]
    for solver in solvers:
        if solver['solve']:
            csv_row.append(solver['name'])
            csv_row.append("solution")
    csv_content.append(csv_row)
    for i in range(quantity):
        try:
            problem = new_problem(weapons, targets)
            filename = safe_filename(size_str, json_prefix)
            save_problem(problem, os.path.join(size_str, filename))

            rewards_available = sum(problem['values'])

            if solve_problems:
                csv_row = [filename, rewards_available]
                start_time = time.time()
                for solver in solvers:
                    if solver['solve']:
                        g, solution = solver['function'](problem['values'], problem['p'])
                        csv_row.append(g)
                        csv_row.append(solution)
                end_time = time.time()
                csv_content.append(csv_row)
                log(f"Solved {i + 1}/{quantity}: {filename} in: {end_time - start_time:.6f}s")
        except KeyboardInterrupt:
            input("Press Enter to attempt again, or ctrl+c to quit.")
    print()
    if solve_problems:
        csv_filename = os.path.join(size_str, f'{csv_filename}.csv')
        with open(csv_filename, 'wb') as f:
            writer = csv.writer(f)
            writer.writerows(csv_content)
        log(f"solutions exported to {csv_filename}")


def grid_search(num_problems=25, num_attempts=5, numbering_offset=0, sizes=None):
    if sizes is None:
        sizes = [3, 4, 5, 7, 10]
    problem_sizes = []
    for size in sizes:
        problem_sizes.append((size, size))
    population_sizes = [40, 60, 80]  # , 100]
    crossover_probabilities = [0.1, 0.3, 0.5]  # , 0.7]
    mutation_probabilities = [0.1, 0.25, 0.4]
    generations_qtys = [500, 1000, 2000]  # , 5000]  # , 10000]
    tournament_fractions = [2, 5, 10]
    mutation_fractions = [4, 6, 10]
    evaluations_per_problem = np.product([len(mutation_fractions), len(generations_qtys), len(mutation_probabilities),
                                          len(crossover_probabilities), len(population_sizes)])
    for problem_size in problem_sizes:
        log(f"Testing dataset for problems of size {problem_size}")
        problem_set_results = []
        header = ['']
        for population_size in population_sizes:
            for crossover_probability in crossover_probabilities:
                for mutation_probability in mutation_probabilities:
                    for generations_qty in generations_qtys:
                        for mutation_fraction in mutation_fractions:
                            header.append(f"{population_size}-{crossover_probability}-{mutation_probability}-"
                                          f"{generations_qty}-{mutation_fraction}")
        problem_set_results.append(header)
        for i in range(numbering_offset, num_problems + numbering_offset):
            problem = new_problem(*problem_size)
            g, solution = WTAOR.wta_or_solver(problem['values'], problem['p'])
            g = sum(problem['values']) - g
            problem_results = [g]
            specific_values = [[g]]
            identifier = f"{problem_size[0]}x{problem_size[1]}-{i:04d}"
            save_problem(problem, os.path.join("problems", identifier + ".json"))
            log(f"{g} -- Problem: {i - numbering_offset} / {num_problems}")
            completed = 0
            for population_size in population_sizes:
                for crossover_probability in crossover_probabilities:
                    for mutation_probability in mutation_probabilities:
                        for generations_qty in generations_qtys:
                            for mutation_fraction in mutation_fractions:
                                gs = []
                                for attempt in range(num_attempts):
                                    g, solution = WTAGA.wta_ga_solver(problem['values'], problem['p'],
                                                                      population_size=population_size,
                                                                      crossover_probability=crossover_probability,
                                                                      mutation_probability=mutation_probability,
                                                                      generations_qty=generations_qty,
                                                                      mutation_fraction=mutation_fraction)
                                    gs.append(g)
                                    # print(f"{g}, ", end="")
                                specific_values.append(gs)
                                problem_results.append(sum(gs) / num_attempts)
                                completed += 1
                                print(f"{completed} / {evaluations_per_problem}", end="\r")
                                # print(f"\b\b: {sum(gs)/num_attempts}")
            print()
            csv_filename = os.path.join("problems", f'{identifier}.csv')
            with open(csv_filename, 'w') as f:
                writer = csv.writer(f)
                writer.writerows(problem_set_results)
            problem_set_results.append(problem_results)

        csv_filename = f'{problem_size}.csv'
        with open(csv_filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerows(problem_set_results)
        log(f"solutions exported to {csv_filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--quantity', type=int, help="The number of problems of each size", default=25, required=False)
    parser.add_argument('--sizes', type=int, nargs='*', help="The problem sizes (problems are all squares)",
                        default=[3, 4, 5, 7, 10], required=False)
    parser.add_argument('--offset', type=int, help="Numbering offset for scenarios", default=0, required=False)
    args = parser.parse_args()
    grid_search(num_problems=args.quantity, numbering_offset=args.offset, sizes=args.sizes)
