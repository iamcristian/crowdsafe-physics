"""Paired seed experiments and scalar calibration against imported observations."""
import math
import numpy as np
from scipy.stats import t

METRICS = ('t90', 'restricted_mean_evacuation_time', 'peak_pressure', 'mean_flow_rate', 'exposure_agent_seconds')


def validate_horizons(horizons):
    """Censored RMET comparisons require the same observation horizon."""
    if len(set(horizons)) > 1:
        raise ValueError('All candidates must use the same observation horizon (duration) for RMET and Pareto comparisons.')


def pareto_front(summaries):
    """Nondominated sampled designs: minimize RMET, peak load and exposure.

    This ranks measured candidate means, not confidence bounds. It does not
    establish optimality beyond the supplied candidate set.
    """
    keys = ('restricted_mean_evacuation_time', 'peak_pressure', 'exposure_agent_seconds')
    points = np.asarray([[s['metrics'][key]['mean'] for key in keys] for s in summaries])
    return [i for i, point in enumerate(points) if not any(np.all(other <= point) and np.any(other < point) for other in points)]


def statistics(values):
    values = [v for v in values if v is not None]
    n = len(values)
    if not n:
        return dict(n=0, mean=None, sd=None, ci95=None)
    mean = float(np.mean(values))
    sd = float(np.std(values, ddof=1)) if n > 1 else None
    half = float(t.ppf(.975, n-1)*sd/math.sqrt(n)) if n > 1 else None
    return dict(n=n, mean=mean, sd=sd, ci95=[mean-half, mean+half] if half is not None else None)


def run_study(request, build_engine, progress, cancelled):
    """Run candidates with common seeds; exclude unobserved T90 explicitly."""
    seeds = request['seeds']
    candidates = request['candidates']
    rows = []
    horizons = set()
    total = len(seeds)*len(candidates)
    for index, controls in enumerate(candidates):
        for seed in seeds:
            if cancelled():
                return dict(cancelled=True, runs=rows)
            engine, _ = build_engine(dict(controls, seed=seed))
            horizons.add(engine.config.duration)
            validate_horizons(horizons)
            while not engine.done:
                if cancelled():
                    return dict(cancelled=True, runs=rows)
                for _ in range(100):
                    engine.step()
                    if engine.done:
                        break
            rows.append(dict(candidate=index, seed=seed, config=engine.config.to_dict(), metrics=engine.result().metrics))
            progress(len(rows), total)
    summaries = []
    for index in range(len(candidates)):
        group = [r for r in rows if r['candidate'] == index]
        summaries.append(dict(candidate=index, censored=sum(r['metrics']['censored'] for r in group),
                              metrics={key: statistics([r['metrics'][key] for r in group]) for key in METRICS}))
    paired = []
    for index in range(1, len(candidates)):
        base = [r for r in rows if r['candidate'] == 0]
        group = [r for r in rows if r['candidate'] == index]
        paired.append(dict(candidate=index, delta_vs_A={key: statistics([
            b['metrics'][key]-a['metrics'][key] if a['metrics'][key] is not None and b['metrics'][key] is not None else None
            for a,b in zip(base,group)]) for key in METRICS}))
    return dict(schema_version=1, model_revision='population-grid-v3', runs=rows, summaries=summaries,
                paired=paired, pareto_candidates=pareto_front(summaries),
                objectives=['min RMET', 'min peak pair load', 'min threshold exposure'],
                interval_method='Student t, 95% confidence interval of seed mean; null times excluded with n reported')


def calibrate(request, build_engine, progress, cancelled):
    """Grid fit of desired speed using RMET observations; holdout never selects parameters."""
    observations = request['observations']
    train = [r for r in observations if r['split'] == 'train']
    holdout = [r for r in observations if r['split'] == 'validation']
    if not train or not holdout or set(r['seed'] for r in train) & set(r['seed'] for r in holdout):
        raise ValueError('Provide train and validation observations with disjoint seeds.')
    history = []
    def evaluate(speed, records):
        errors = []
        predictions = []
        for record in records:
            if cancelled():
                raise ValueError('Calibration cancelled.')
            engine, _ = build_engine(dict(request['controls'], speed=speed, seed=record['seed']))
            while not engine.done:
                if cancelled():
                    raise ValueError('Calibration cancelled.')
                engine.step()
            predicted = engine.result().metrics['restricted_mean_evacuation_time']
            errors.append((predicted-record['rmet'])**2)
            predictions.append(dict(seed=record['seed'], observed=record['rmet'], predicted=predicted))
        return dict(rmse=math.sqrt(sum(errors)/len(errors)), predictions=predictions)
    for i, speed in enumerate(request['speeds']):
        history.append(dict(speed=speed, training=evaluate(speed,train)))
        progress(i+1,len(request['speeds'])+1)
    best = min(history,key=lambda row:row['training']['rmse'])
    validation = evaluate(best['speed'],holdout)
    progress(len(request['speeds'])+1,len(request['speeds'])+1)
    return dict(schema_version=1, model_revision='population-grid-v3', fitted_parameter='desired_speed',
                selected_speed=best['speed'], history=history, validation=validation,
                controls=request['controls'], observations=observations,
                note='Scalar fit to imported RMET observations. Validation RMSE is limited to these held-out observations.')
