/* Draft geometry stays separate from the running experiment until Apply. */
const editorPanel=document.createElement('section');
editorPanel.className='panel workspace';
editorPanel.innerHTML=`<h2>Visual scenario editor</h2><p>Click twice to draw a wall or spawn rectangle. With Exit, click a clear boundary to add an exit or click an existing opening to resize it. Exits snap inside their wall; conflicting exits are rejected. Select an object, then drag to move it. Coordinates snap to 0.1 m. Apply validates geometry and starts a new paused run.</p><div class="buttons" style="display:flex;flex-wrap:wrap"><select id="edit-tool" style="width:auto"><option value="select">Select / move</option><option value="wall">Wall</option><option value="pillar">Pillar</option><option value="exit">Exit</option><option value="spawn">Spawn area</option></select><label>Radius / exit width (m)<input id="edit-size" type="number" min="0.1" step="0.1" value="1.2"></label><button id="edit-delete">Delete selected</button><button id="edit-undo">Undo</button><button id="edit-redo">Redo</button><button id="edit-load">Load current run</button><button id="edit-apply" class="primary">Apply scenario</button></div><canvas id="editor-canvas" width="1000" height="650" style="width:100%;max-height:650px;object-fit:contain;background:#f7fafc;touch-action:none"></canvas><p id="edit-info">Draft: 8 × 8 m. Green segments are exits; blue rectangle is the spawn area.</p>`;
document.querySelector('main').after(editorPanel);
let draft={width:8,height:8,exit_width:1.2,pillars:[],interior_segments:[],exits:[{side:'right',center:4,width:1.2}],spawn:[.1,.1,4.8,7.8]},selected=null,anchor=null,dragStart=null,undoStack=[],redoStack=[];
const editCanvas=byId('editor-canvas');
function saveDraft(){undoStack.push(JSON.stringify(draft));redoStack=[];}
function transform(canvas,room){const scale=Math.min((canvas.width-100)/room.width,(canvas.height-100)/room.height);return {scale,point:(x,y)=>[50+x*scale,canvas.height-50-y*scale]};}
function exitEnds(e,r){const lo=e.center-e.width/2,hi=e.center+e.width/2;return e.side==='left'?[[0,lo],[0,hi]]:e.side==='right'?[[r.width,lo],[r.width,hi]]:e.side==='top'?[[lo,r.height],[hi,r.height]]:[[lo,0],[hi,0]];}
function renderGeometry(canvas,r,agents=null){const ctx=canvas.getContext('2d'),{scale,point}=transform(canvas,r);ctx.clearRect(0,0,canvas.width,canvas.height);ctx.strokeStyle=agents?'#294258':'#dce5eb';ctx.lineWidth=1;for(let x=0;x<=r.width;x++){ctx.beginPath();ctx.moveTo(...point(x,0));ctx.lineTo(...point(x,r.height));ctx.stroke();}for(let y=0;y<=r.height;y++){ctx.beginPath();ctx.moveTo(...point(0,y));ctx.lineTo(...point(r.width,y));ctx.stroke();}ctx.lineWidth=4;ctx.strokeStyle=agents?'#b7cad8':'#354e64';const segments=agents?.wall_segments??[[[0,0],[r.width,0]],[[0,r.height],[r.width,r.height]],[[0,0],[0,r.height]],[[r.width,0],[r.width,r.height]],...r.interior_segments];for(const s of segments){ctx.beginPath();ctx.moveTo(...point(...s[0]));ctx.lineTo(...point(...s[1]));ctx.stroke();}for(const e of (r.exits?.length?r.exits:[{side:'right',center:r.height/2,width:r.exit_width}])){const s=exitEnds(e,r);ctx.strokeStyle='#10b997';ctx.lineWidth=7;ctx.beginPath();ctx.moveTo(...point(...s[0]));ctx.lineTo(...point(...s[1]));ctx.stroke();}for(const p of r.pillars){ctx.fillStyle='#7794aa';ctx.beginPath();ctx.arc(...point(p.x,p.y),p.radius*scale,0,Math.PI*2);ctx.fill();}if(!agents&&r.spawn){const [x,y,w,h]=r.spawn;ctx.fillStyle='#2685bf22';ctx.fillRect(...point(x,y+h),w*scale,h*scale);ctx.strokeStyle='#2685bf';ctx.lineWidth=2;ctx.strokeRect(...point(x,y+h),w*scale,h*scale);}if(agents){agents.positions.forEach((p,i)=>{ctx.fillStyle=color(agents.pressure[i]);ctx.beginPath();ctx.arc(...point(...p),agents.radii[i]*scale,0,Math.PI*2);ctx.fill();});}else if(selected){ctx.fillStyle='#bb5c19';ctx.font='16px system-ui';ctx.fillText('Selected: '+selected.kind+' '+(selected.index??''),15,22);}}
draw=state=>renderGeometry(byId('room'),state.room,state);
function paintDraft(){
  renderGeometry(editCanvas,draft);
  const exit=selected?.kind==='exits'?draft.exits[selected.index]:null;
  byId('edit-info').textContent=`Draft: ${draft.width} × ${draft.height} m · ${draft.exits.length} exits · ${draft.interior_segments.length} walls. `+(exit?`Exit ${selected.index+1}: ${exit.side} wall · width ${exit.width} m · span ${(exit.center-exit.width/2).toFixed(2)}–${(exit.center+exit.width/2).toFixed(2)} m.`:anchor?'Click the second point.':'Apply to validate and simulate.');
  const properties=byId('exit-properties');
  if(properties){properties.hidden=!exit;if(exit){byId('selected-exit-side').value=exit.side;byId('selected-exit-center').value=exit.center;byId('selected-exit-width').value=exit.width;}}
}
function position(event){const rect=editCanvas.getBoundingClientRect(),{scale}=transform(editCanvas,draft);return [Math.round(((event.clientX-rect.left)*editCanvas.width/rect.width-50)/scale*10)/10,Math.round((editCanvas.height-50-(event.clientY-rect.top)*editCanvas.height/rect.height)/scale*10)/10];}
function nearest(p){
  let best=null,d=.5;
  function consider(kind,index,q){const distance=Math.hypot(p[0]-q[0],p[1]-q[1]);if(distance<d){d=distance;best={kind,index};}}
  draft.pillars.forEach((o,i)=>consider('pillars',i,[o.x,o.y]));
  draft.interior_segments.forEach((s,i)=>consider('interior_segments',i,[(s[0][0]+s[1][0])/2,(s[0][1]+s[1][1])/2]));
  draft.exits.forEach((e,i)=>{const s=exitEnds(e,draft),vertical=e.side==='left'||e.side==='right';consider('exits',i,vertical?[s[0][0],Math.max(s[0][1],Math.min(s[1][1],p[1]))]:[Math.max(s[0][0],Math.min(s[1][0],p[0])),s[0][1]]);});
  if(!best&&draft.spawn){const [x,y,w,h]=draft.spawn;if(p[0]>=x&&p[0]<=x+w&&p[1]>=y&&p[1]<=y+h)best={kind:'spawn'};}
  return best;
}
editCanvas.onpointerdown=event=>{
  const p=position(event),tool=byId('edit-tool').value,size=+byId('edit-size').value;
  if(tool==='select'){selected=nearest(p);dragStart=p;paintDraft();return;}
  if(tool==='exit'){
    const [side,distance]=[['left',Math.abs(p[0])],['right',Math.abs(draft.width-p[0])],['bottom',Math.abs(p[1])],['top',Math.abs(draft.height-p[1])]].sort((a,b)=>a[1]-b[1])[0];
    if(distance>.5){byId('edit-info').textContent='Click within 0.5 m of a room boundary to place or resize an exit.';return;}
    try{
      const result=exitGeometry.place(draft,draft.exits,side,side==='left'||side==='right'?p[1]:p[0],size);
      saveDraft();draft.exits=result.exits;selected={kind:'exits',index:result.index};paintDraft();
    }catch(error){byId('edit-info').textContent=error.message;}
    return;
  }
  if(tool==='wall'||tool==='spawn'){
    if(!anchor){anchor=p;paintDraft();return;}
    saveDraft();if(tool==='wall')draft.interior_segments.push([anchor,p]);else draft.spawn=[Math.min(anchor[0],p[0]),Math.min(anchor[1],p[1]),Math.abs(anchor[0]-p[0]),Math.abs(anchor[1]-p[1])];anchor=null;
  }else{saveDraft();draft.pillars.push({x:p[0],y:p[1],radius:size});}
  paintDraft();
};
editCanvas.onpointerup=event=>{
  if(!dragStart||!selected)return;
  const p=position(event),dx=p[0]-dragStart[0],dy=p[1]-dragStart[1];dragStart=null;if(!dx&&!dy)return;
  if(selected.kind==='exits'){
    try{const exit=draft.exits[selected.index],delta=exit.side==='left'||exit.side==='right'?dy:dx;
      const result=exitGeometry.update(draft,draft.exits,selected.index,{...exit,center:exit.center+delta});
      saveDraft();draft.exits=result.exits;paintDraft();
    }catch(error){byId('edit-info').textContent=error.message;}
    return;
  }
  saveDraft();if(selected.kind==='spawn'){draft.spawn[0]+=dx;draft.spawn[1]+=dy;}else{const o=draft[selected.kind][selected.index];if(selected.kind==='pillars'){o.x+=dx;o.y+=dy;}else o.forEach(q=>{q[0]+=dx;q[1]+=dy;});}paintDraft();
};
byId('edit-tool').onchange=()=>{anchor=null;selected=null;paintDraft();};
byId('edit-delete').onclick=()=>{if(!selected)return;saveDraft();if(selected.kind==='spawn')draft.spawn=null;else draft[selected.kind].splice(selected.index,1);selected=null;paintDraft();};
byId('edit-undo').onclick=()=>{if(!undoStack.length)return;redoStack.push(JSON.stringify(draft));draft=JSON.parse(undoStack.pop());selected=null;paintDraft();};
byId('edit-redo').onclick=()=>{if(!redoStack.length)return;undoStack.push(JSON.stringify(draft));draft=JSON.parse(redoStack.pop());selected=null;paintDraft();};
byId('edit-load').onclick=()=>{if(!lastState)return;saveDraft();draft=structuredClone(lastState.room);draft.exits=draft.exits?.length?draft.exits:[{side:'right',center:draft.height/2,width:draft.exit_width}];selected=null;paintDraft();};
byId('edit-apply').onclick=()=>{if(!draft.exits.length){byId('edit-info').textContent='Add at least one exit before applying.';return;}try{exitGeometry.validate(draft,draft.exits);}catch(error){byId('edit-info').textContent=error.message;return;}customRoom=structuredClone(draft);populateRoom(customRoom);send('reset');};
document.querySelector('.workspace-grid .helper').textContent='Numeric editor for basic geometry. Use the visual editor for multiple exits and spawn areas. Global routes use a 0.25 m clearance grid; narrow passages may be rejected.';
paintDraft();
const inspector=document.createElement('div');
inspector.innerHTML='<div id="exit-properties" hidden><h3>Selected exit</h3><label>Wall<select id="selected-exit-side"><option>left</option><option>right</option><option>top</option><option>bottom</option></select></label><label>Center along wall (m)<input id="selected-exit-center" type="number" step="0.1"></label><label>Exit width (m)<input id="selected-exit-width" type="number" min="0.1" step="0.1"></label><button id="selected-exit-apply">Update exit</button></div><label>Selected object / room JSON (meters)<textarea id="object-json" style="min-height:90px"></textarea></label><button id="object-read">Inspect selected / room</button><button id="object-apply">Update draft object</button>';
editCanvas.after(inspector);
byId('object-read').onclick=()=>{byId('object-json').value=JSON.stringify(selected?(selected.kind==='spawn'?draft.spawn:draft[selected.kind][selected.index]):draft,null,2);};
byId('object-apply').onclick=()=>{try{const value=JSON.parse(byId('object-json').value),candidate=structuredClone(draft);if(selected){if(selected.kind==='spawn')candidate.spawn=value;else candidate[selected.kind][selected.index]=value;}else{if(!value.width||!value.height||!Array.isArray(value.exits)||!Array.isArray(value.pillars)||!Array.isArray(value.interior_segments))throw Error('Room requires dimensions and exits, pillars, interior_segments arrays.');Object.assign(candidate,value);}exitGeometry.validate(candidate,candidate.exits);saveDraft();draft=candidate;paintDraft();}catch(e){byId('edit-info').textContent=e.message;}};
byId('selected-exit-apply').onclick=()=>{if(selected?.kind!=='exits')return;try{const result=exitGeometry.update(draft,draft.exits,selected.index,{side:byId('selected-exit-side').value,center:+byId('selected-exit-center').value,width:+byId('selected-exit-width').value});saveDraft();draft.exits=result.exits;paintDraft();}catch(error){byId('edit-info').textContent=error.message;}};
