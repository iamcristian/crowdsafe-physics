"""HERMES open-data analysis and held-out local trajectory prediction.

Run python -m src.empirical. Raw files are preserved in their downloaded ZIP.
Evaluation conditions on measured neighbors; it is not free-running validation.
"""
import hashlib
import io
import json
from pathlib import Path
import zipfile
import numpy as np
from src.config import Room, Exit, Physics
from src.physics.forces import total_forces
from src.physics.integrator import semi_implicit_euler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'data/experimental/hermes'
DOI = 'https://doi.org/10.34735/ped.2009.6'


def load_runs():
    metadata = json.loads((DATA/'metadata.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(DATA/'trajectories.zip') as archive:
        for run in metadata['experiment']['run']:
            name = run['run_name']
            rows = np.loadtxt(io.BytesIO(archive.read(name+'.txt')))
            rows[:,2:5] /= 100  # archive coordinates are cm; model SI is m
            yield run, rows


def observed_crossings(rows, line_y=0., fps=16.):
    """First downstream crossing of y=0 for each observed track; interpolate."""
    times=[]
    for identity in np.unique(rows[:,0]):
        track=rows[rows[:,0]==identity]
        track=track[np.argsort(track[:,1])]
        for a,b in zip(track[:-1],track[1:]):
            if b[1]-a[1]==1 and a[3]>line_y>=b[3]:
                fraction=(a[3]-line_y)/(a[3]-b[3])
                times.append(float((a[1]+fraction)/fps))
                break
    return sorted(times)


def samples(rows, count=8, fps=16.):
    """Velocity ±4 frames, forecast +8 frames; require continuous IDs."""
    frames={int(f):{int(r[0]):r[2:4] for r in rows[rows[:,1]==f]} for f in np.unique(rows[:,1])}
    chosen=np.linspace(min(frames)+4,max(frames)-8,count,dtype=int)
    for frame in chosen:
        if any(frame+k not in frames for k in (-4,0,4,8)):
            continue
        ids=sorted(set(frames[frame-4])&set(frames[frame])&set(frames[frame+4])&set(frames[frame+8]))
        if len(ids)<3:
            continue
        pos=np.array([frames[frame][i] for i in ids])
        velocity=np.array([(frames[frame+4][i]-frames[frame-4][i])/(8/fps) for i in ids])
        future=np.array([frames[frame+8][i] for i in ids])
        # Only upstream approach, not image edges or downstream departures.
        valid=(pos[:,1]>.7)&(pos[:,1]<5)&(np.abs(pos[:,0])<2.5)
        if valid.any():
            yield pos,velocity,future,valid


def evaluate_run(run, rows, speed, tau):
    width=float(run['parameter']['b_Exit [m]'])
    # Left jamb is defined by metadata's second obstacle; use geometry, not filename.
    import re
    pairs=[tuple(map(float,p)) for p in re.findall(r'(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)',run['wkt_geometry'])]
    # Metadata has a rectangular outer ring then two rectangular obstacles.
    left=max(x for x,y in pairs[10:15])
    right=left+width
    walls=[]
    for ring in (pairs[5:10],pairs[10:15]):
        shifted=[(x+6,y+8) for x,y in ring]
        walls.extend(zip(shifted[:-1],shifted[1:]))
    room=Room(width=12,height=18,exit_width=2,exits=(Exit('bottom',6,12),),interior_segments=tuple(walls))
    errors=[];baseline=[];stationary=[];clamped=0
    physics=Physics(tau=tau,radius=.2,radius_spread=0)
    for positions,velocities,future,valid in samples(rows):
        target=np.column_stack((np.clip(positions[:,0],left+.22,right-.22),np.full(len(positions),-1.5)))
        direction=target-positions
        direction/=np.maximum(np.linalg.norm(direction,axis=1)[:,None],1e-12)
        prediction=positions+[6,8]
        predicted_velocity=velocities.copy()
        for _ in range(167):
            delta=target+[6,8]-prediction
            directions=delta/np.maximum(np.linalg.norm(delta,axis=1)[:,None],1e-12)
            force=total_forces(prediction,predicted_velocity,np.full(len(positions),.2),room,physics,speed,directions)
            prediction,predicted_velocity,caps=semi_implicit_euler(prediction,predicted_velocity,force.total,physics.mass,.5/167,physics.max_speed)
            clamped+=caps
        prediction=prediction-[6,8]
        errors.extend(np.sum((prediction[valid]-future[valid])**2,axis=1).tolist())
        baseline.extend(np.sum((positions[valid]+.5*velocities[valid]-future[valid])**2,axis=1).tolist())
        stationary.extend(np.sum((positions[valid]-future[valid])**2,axis=1).tolist())
    return dict(n_predictions=len(errors),clamped_updates=clamped,rmse_m=float(np.sqrt(np.mean(errors))) if errors else None,
                constant_velocity_rmse_m=float(np.sqrt(np.mean(baseline))) if baseline else None,
                stationary_rmse_m=float(np.sqrt(np.mean(stationary))) if stationary else None)


def main():
    runs=list(load_runs())
    summaries=[]
    for run,rows in runs:
        times=observed_crossings(rows)
        summaries.append(dict(run=run['run_name'],width_m=float(run['parameter']['b_Exit [m]']),
            observed_tracks=len(np.unique(rows[:,0])),samples=len(rows),observed_crossings=len(times),
            crossing_span_s=times[-1]-times[0] if len(times)>1 else None,
            observed_span_flow_per_s=(len(times)-1)/(times[-1]-times[0]) if len(times)>1 else None,
            split='train' if run['run_name'] in ('ao-240-400','ao-360-400','ao-500-400') else 'validation'))
    history=[]
    for speed in (1.,1.3,1.6):
        for tau in (.3,.5,.8):
            scores=[evaluate_run(r,rows,speed,tau) for r,rows in runs if r['run_name'] in ('ao-240-400','ao-360-400','ao-500-400')]
            history.append(dict(speed=speed,tau=tau,training_rmse_m=float(np.mean([s['rmse_m'] for s in scores]))))
    best=min(history,key=lambda r:r['training_rmse_m'])
    validation=[dict(run=r['run_name'],**evaluate_run(r,rows,best['speed'],best['tau'])) for r,rows in runs if r['run_name'] in ('ao-300-400','ao-440-400')]
    report=dict(source=DOI,license='CC BY 4.0',fps=16,coordinate_conversion='cm to m',
        zip_sha256=hashlib.sha256((DATA/'trajectories.zip').read_bytes()).hexdigest(),
        summaries=summaries,parameter_search=history,selected=best,validation=validation,
        method='0.5 s integrated local ensemble forecast, 167 Euler steps, measured initial neighbors, centered 0.5 s initial velocity; run-level mean RMSE',
        limitations=['Short local ensemble forecast from measured initial states, not full evacuation validation.',
                     'Camera window omits neighbors outside the observed region.',
                     'Assumed body radius 0.2 m; no contact forces measured.',
                     'Centered initial velocity uses future frames; this is retrospective evaluation, not causal online forecasting.',
                     'Forecast samples share tracked individuals and are statistically dependent.',
                     'Held-out widths are from the same experiment, not an independent population.'])
    output=ROOT/'outputs/empirical';output.mkdir(parents=True,exist_ok=True)
    (output/'hermes_report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    plot_report(report)
    print(json.dumps(dict(selected=best,validation=validation),indent=2))


def plot_report(report):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    results=report['validation'];x=np.arange(len(results));w=.25
    fig,ax=plt.subplots(figsize=(8,4.5))
    for j,(key,label,color) in enumerate((('rmse_m','HFV local forecast','#bd5939'),('constant_velocity_rmse_m','Constant velocity','#267d86'),('stationary_rmse_m','Stationary','#8493a2'))):
        ax.bar(x+(j-1)*w,[r[key] for r in results],w,label=label,color=color)
    ax.set_xticks(x,[r['run'] for r in results]);ax.set_ylabel('Position RMSE at 0.5 s (m)')
    ax.set_title('HERMES: held-out widths · retrospective local forecasts')
    ax.spines[['top','right']].set_visible(False);ax.legend(frameon=False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.text(.05,.01,'Source: doi:10.34735/ped.2009.6 · 16 Hz · no contact-force validation',fontsize=8)
    fig.tight_layout(rect=(0,.03,1,1));fig.savefig(ROOT/'outputs/empirical/hermes_validation.png',dpi=180);plt.close(fig)


if __name__=='__main__':
    main()
