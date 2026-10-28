"""Bounded research jobs: sampled Pareto search and Saltelli sensitivity."""
import numpy as np
from src.analytics.studies import run_study, METRICS, statistics


def sobol_indices(a,b,ab):
    a,b,ab=np.asarray(a),np.asarray(b),np.asarray(ab)
    variance=float(np.var(np.r_[a,b],ddof=1))
    if variance<1e-15:
        return dict(variance=variance,first_order=None,total_order=None)
    return dict(variance=variance,
        first_order=(np.mean(b[None,:]*(ab-a[None,:]),axis=1)/variance).tolist(),
        total_order=(np.mean((a[None,:]-ab)**2,axis=1)/(2*variance)).tolist())


def sensitivity(request,build,progress,cancelled):
    rng=np.random.default_rng(request.get('search_seed',2026))
    fields=list(request['bounds']);n=request.get('samples',8)
    bounds=np.asarray([request['bounds'][field] for field in fields])
    a=rng.uniform(bounds[:,0],bounds[:,1],size=(n,len(fields)))
    b=rng.uniform(bounds[:,0],bounds[:,1],size=(n,len(fields)))
    arrays=[a,b]
    for column in range(len(fields)):
        hybrid=a.copy();hybrid[:,column]=b[:,column];arrays.append(hybrid)
    candidates=[dict(request['controls'],**dict(zip(fields,row.tolist()))) for matrix in arrays for row in matrix]
    result=run_study(dict(candidates=candidates,seeds=request['seeds']),build,progress,cancelled)
    if result.get('cancelled'):
        return result
    estimates={}
    for metric in ('restricted_mean_evacuation_time','peak_pressure','exposure_agent_seconds'):
        values=np.array([s['metrics'][metric]['mean'] for s in result['summaries']]).reshape(len(fields)+2,n)
        estimates[metric]=sobol_indices(values[0],values[1],values[2:])
    result.update(kind='sobol',fields=fields,bounds=request['bounds'],samples=n,indices=estimates,
        note='Saltelli first-order and Jansen total-order Monte Carlo estimates. Small budgets can yield negative or >1 estimates; convergence must be checked. Seeds are common across sample points.')
    return result


def design_search(request,build,progress,cancelled):
    base=request['controls'];seeds=request['seeds'];holdout=request['validation_seeds']
    if set(seeds)&set(holdout):
        raise ValueError('Training and validation seeds must be disjoint.')
    engine,_=build(base);room=engine.config.to_dict()['room']
    if room['pillars']:
        raise ValueError('Start geometry search from a room without pillars.')
    rng=np.random.default_rng(request.get('search_seed',2026));budget=request.get('budget',6)
    candidates=[dict(base,room=room)]
    rejected=[]
    for _ in range(budget*10):
        if cancelled():
            return dict(cancelled=True)
        if len(candidates)>=budget:
            break
        radius=float(rng.uniform(.18,.5))
        pillar=dict(x=float(rng.uniform(room['width']*.65,room['width']*.85)),y=float(rng.uniform(radius+.1,room['height']-radius-.1)),radius=radius)
        candidate=dict(base,room=dict(room,pillars=[pillar]))
        try:
            for seed in seeds+holdout:
                build(dict(candidate,seed=seed))
        except (ValueError,TypeError) as error:
            rejected.append(dict(pillar=pillar,error=str(error)));continue
        candidates.append(candidate)
    if len(candidates)<2:
        raise ValueError('No feasible pillar candidates sampled. Revise the spawn region or geometry.')
    training=run_study(dict(candidates=candidates,seeds=seeds),build,progress,cancelled)
    if training.get('cancelled'):
        return training
    selected=training['pareto_candidates']
    evaluation=run_study(dict(candidates=[candidates[i] for i in selected],seeds=holdout),build,progress,cancelled)
    return dict(kind='geometry_search',model_revision='population-grid-v3',search_seed=request.get('search_seed',2026),
        training=training,selected_training_candidates=selected,validation=evaluation,candidates=candidates,rejected=rejected,
        note='Seeded random single-pillar search with nondominated selection on training means; held-out seeds evaluated after selection. Not a global optimum or code-compliance assessment.')


def monte_carlo(request,build,progress,cancelled):
    rows=[];trace=[];minimum=request.get('minimum',4);tolerance=request.get('half_width',.5)
    for i,seed in enumerate(request['seeds']):
        result=run_study(dict(candidates=[request['controls']],seeds=[seed]),build,lambda *args:None,cancelled)
        if result.get('cancelled'):return dict(cancelled=True,runs=rows)
        rows.extend(result['runs'])
        stats=statistics([r['metrics']['restricted_mean_evacuation_time'] for r in rows])
        half=(stats['ci95'][1]-stats['ci95'][0])/2 if stats['ci95'] else None
        trace.append(dict(n=i+1,rmet=stats))
        progress(i+1,len(request['seeds']))
        if i+1>=minimum and half is not None and half<=tolerance and not any(r['metrics']['censored'] for r in rows):
            break
    return dict(kind='monte_carlo',model_revision='population-grid-v3',runs=rows,trace=trace,
        precision_reached=len(rows)>=minimum and half is not None and half<=tolerance and not any(r['metrics']['censored'] for r in rows),
        note='Exploratory sequential Student-t precision stopping on mean RMET; repeated checking does not provide fixed 95% simultaneous coverage. Censored runs prevent early stopping.')
