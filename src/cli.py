r"""Command-line entry points for simulation, experiments, figures and the server.

All numerical arguments use SI units. JSON room files expose geometric inputs;
strict validation turns unsupported states into readable parser errors. Artifact
paths are explicit so every benchmark can be archived independently.
"""
import argparse
import json
from pathlib import Path
from src.config import SimulationConfig, room_from_dict
from src.simulation import simulate


def parser():
    r"""Build self-documenting subcommands without importing plotting/server code.

    Shared run arguments mirror SimulationConfig exactly. Optimization budgets
    count differential-evolution generations and population multiplier (3*pop).
    """
    root = argparse.ArgumentParser(description="CrowdSafe-Physics: reproducible SI crowd dynamics")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("simulate", "benchmark", "optimize"):
        item = commands.add_parser(name, help=f"Run the {name} workflow")
        item.add_argument("--agents", type=int, default=60, help="Initial pedestrian count")
        item.add_argument("--speed", type=float, default=5.0, help="Desired speed (m/s); benchmark sweeps prescribed speeds")
        item.add_argument("--dt", type=float, default=0.0015, help="Physics timestep (s)")
        item.add_argument("--duration", type=float, default=90.0, help="Observation horizon (s)")
        item.add_argument("--seed", type=int, default=7)
        item.add_argument("--method", choices=("euler", "verlet"), default="euler")
        item.add_argument("--room", type=Path, help="Custom room JSON")
        item.add_argument("--output", type=Path, default=Path("outputs"))
        if name != "simulate":
            item.add_argument("--iterations", type=int, default=3)
            item.add_argument("--population", type=int, default=4)
            item.add_argument("--train-seeds", type=int, nargs="+", default=[7, 11])
        if name == "benchmark":
            item.add_argument("--seeds", type=int, nargs="+", default=[19, 23, 31])
    plots = commands.add_parser("plots", help="Render four 300-DPI benchmark figures")
    plots.add_argument("--output", type=Path, default=Path("outputs"))
    serve = commands.add_parser("serve", help="Launch the interactive local Canvas laboratory")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    return root


def main(argv=None):
    r"""Dispatch a reproducible command and print actual metrics as strict JSON.

    Simulation and optimization save measurements before printing success.
    Benchmark also produces plots; the independent plots command regenerates
    them solely from stored artifacts without rerunning expensive physics.
    """
    command_parser = parser()
    args = command_parser.parse_args(argv)
    try:
        if args.command == "serve":
            import uvicorn
            uvicorn.run("src.visualization.web_app:app", host=args.host, port=args.port)
            return
        if args.command == "plots":
            from src.visualization.scientific_plots import generate_plots
            print("\n".join(generate_plots(args.output)))
            return
        parameters = dict(n_agents=args.agents, desired_speed=args.speed, dt=args.dt,
                          duration=args.duration, seed=args.seed, method=args.method)
        if args.room:
            parameters["room"] = room_from_dict(json.loads(args.room.read_text()))
        config = SimulationConfig(**parameters)
        if args.command == "simulate":
            result = simulate(config)
            result.save(args.output / "data", "simulation")
            print(json.dumps(result.metrics, indent=2, allow_nan=False))
        elif args.command == "optimize":
            from src.optimization.pillar_evolver import optimize_pillar
            result = optimize_pillar(config, args.train_seeds, args.iterations, args.population)
            directory = args.output / "data"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "optimization.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
            print(json.dumps({key: value for key, value in result.items() if key not in ("history", "baseline_metrics")}, indent=2))
        else:
            from src.experiments import run_benchmark
            from src.visualization.scientific_plots import generate_plots
            run_benchmark(config, args.output, args.seeds, args.train_seeds, args.iterations, args.population)
            print("\n".join(generate_plots(args.output)))
    except (ValueError, OSError) as error:
        command_parser.error(str(error))


if __name__ == "__main__":
    main()
