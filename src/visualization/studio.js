/* Application shell. Move the existing controls, never clone their state. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const shell = document.querySelector('.shell');
  const header = shell.querySelector('header');
  const simulation = shell.querySelector('main');
  const stage = simulation.querySelector('.stage');
  const telemetry = simulation.querySelector('.results');
  const runControls = simulation.querySelector('.controls');
  const views = new Map();
  const savedScroll = new Map();
  const tabs = new Map();
  let current = 'simulation';
  let returnFocus = null;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function button(label, action, className = '') {
    const node = element('button', className, label);
    node.type = 'button'; node.addEventListener('click', action);
    return node;
  }
  function card(title) {
    const node = element('section', 'tool-card');
    if (title) node.append(element('h3', '', title));
    return node;
  }
  function groupChildren(parent) {
    const groups = [];
    let active;
    for (const node of [...parent.children]) {
      if (node.tagName === 'H3' || !active) {
        active = card(); groups.push(active); parent.append(active);
      }
      active.append(node);
    }
    return groups;
  }
  function fold(node, title, open = false) {
    const details = element('details', 'disclosure');
    details.open = open;
    details.append(element('summary', '', title), node);
    return details;
  }
  function explain(root) {
    for (const note of root.querySelectorAll('p.helper, .model-note')) {
      if (note.closest('details')) continue;
      const details = element('details', 'context-help');
      details.append(element('summary', '', note.id === 'design' ? 'Scenario notes' : 'Method & assumptions'));
      note.replaceWith(details); details.append(note);
    }
  }
  const viewDefinitions = [
    ['simulation', 'Simulation', 'Live crowd dynamics', 'M3 16V8m6 8V4m6 12v-6m6 6V2'],
    ['scenario', 'Scenario', 'Geometry & exits', 'M3 3h18v18H3z M9 3v10h12'],
    ['analysis', 'Analysis', 'Replay & compare', 'M4 19V5m0 14h17 M7 14l4-5 4 3 5-8'],
    ['experiments', 'Experiments', 'Studies & optimization', 'M9 3h6 M10 3v7l-6 10h16l-6-10V3 M8 15h8'],
    ['evidence', 'Evidence', 'Data & calibration', 'M5 3h11l4 4v14H5z M9 11h7 M9 15h7 M15 3v5h5'],
    ['building', 'Building', 'Floors & networks', 'M4 21V3h12v18 M16 9h4v12 M8 7h4 M8 11h4 M8 15h4']
  ];
  function icon(path) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('aria-hidden', 'true');
    const line = document.createElementNS(svg.namespaceURI, 'path');
    line.setAttribute('d', path); svg.append(line); return svg;
  }

  document.body.classList.add('studio');
  const sidebar = element('aside', 'studio-sidebar'); sidebar.id = 'studio-sidebar';
  const identity = element('div', 'studio-identity');
  const identityName = element('div', 'nav-copy');
  identityName.append(element('strong', '', 'CrowdSafe'), element('span', '', 'Research studio'));
  identity.append(element('div', 'studio-monogram', 'CS'), identityName);
  sidebar.append(identity);
  const navigation = element('nav', 'studio-nav'); navigation.setAttribute('aria-label', 'Workspaces');
  navigation.append(element('div', 'nav-caption', 'WORKSPACES'));
  for (const [id, name, description, path] of viewDefinitions) {
    const link = element('a', 'nav-item'); link.href = '#' + id; link.dataset.view = id;
    link.title = name; link.setAttribute('aria-label', name);
    const text = element('span', 'nav-copy'); text.append(element('strong', '', name), element('small', '', description));
    link.append(icon(path), text); navigation.append(link);
  }
  sidebar.append(navigation);
  const navBottom = element('div', 'nav-bottom');
  navBottom.append(element('span', 'nav-copy model-label', 'Local research environment'));
  navBottom.append(button('Help & shortcuts', () => helpDialog.showModal(), 'nav-help'));
  sidebar.append(navBottom); document.body.prepend(sidebar);
  const scrim = button('Close navigation', () => setNavigation(false), 'navigation-scrim');
  scrim.tabIndex = -1; scrim.setAttribute('aria-hidden', 'true'); document.body.append(scrim);
  const oldBrand = header.querySelector('.brand'); oldBrand.remove();
  const headerStart = element('div', 'header-start');
  const menuButton = button('☰', () => setNavigation(!navIsExpanded()), 'menu-button');
  menuButton.id = 'nav-toggle'; menuButton.setAttribute('aria-label', 'Toggle workspace navigation');
  menuButton.setAttribute('aria-controls', sidebar.id);
  const breadcrumb = element('div', 'studio-breadcrumb');
  breadcrumb.append(element('span', '', 'Workspace'), element('span', '', '/'));
  const title = element('h1', '', 'Simulation'); title.id = 'workspace-title'; breadcrumb.append(title);
  headerStart.append(menuButton, breadcrumb); header.prepend(headerStart);
  const headerActions = element('div', 'header-actions');
  const finderButton = button('Find a tool', () => openFinder(), 'finder-button');
  finderButton.setAttribute('aria-keyshortcuts', 'Control+k Meta+k'); finderButton.title = 'Find a tool (Ctrl+K)';
  const runToolbar = element('div', 'run-toolbar'); runToolbar.setAttribute('aria-label', 'Live simulation controls');
  for (const id of ['play', 'pause', 'reset']) runToolbar.append($(id));
  headerActions.append(finderButton, $('connection'), runToolbar); header.append(headerActions);
  header.classList.add('studio-header');
  const pages = element('div', 'studio-pages'); pages.id = 'studio-pages';
  pages.setAttribute('role','main'); simulation.setAttribute('role','region');
  pages.setAttribute('aria-labelledby', 'workspace-title'); shell.append(pages);
  const statusBar = element('div', 'studio-statusbar');
  const liveStatus = element('span', '', 'Waiting for physics engine'); liveStatus.id = 'studio-live-status';
  const statusJob = button('No active study', () => navigate('experiments', 'results'), 'job-indicator');
  statusJob.id = 'studio-job-status'; statusBar.append(liveStatus, statusJob); shell.append(statusBar);
  const footer = shell.querySelector('footer'); footer.remove();

  function makeView(id, description) {
    const view = id === 'simulation' ? simulation : element('section', '');
    view.classList.add('studio-view'); view.id = 'view-' + id;
    view.dataset.workspace = id; view.setAttribute('aria-label', viewDefinitions.find(v => v[0] === id)[1]);
    const intro = element('div', 'view-intro'); intro.append(element('p', '', description));
    view.prepend(intro); views.set(id, view); pages.append(view); return view;
  }
  const liveView = makeView('simulation', 'Run a scenario and watch its dynamics. Advanced settings live in the inspector.');
  const scenarioView = makeView('scenario', 'Build geometry, add exits and set the spawn area. Apply when your draft is ready.');
  const analysisView = makeView('analysis', 'Inspect live or recorded frames. Compare two captured runs on the same time axis.');
  const experimentsView = makeView('experiments', 'Compare designs, estimate sensitivity and explore uncertainty with reproducible seeds.');
  const evidenceView = makeView('evidence', 'Examine experimental performance and calibrate against imported observations.');
  const buildingView = makeView('building', 'Explore floors, stairs and visibility using the separate capacity network model.');

  // Split the former long document into cards, retaining original input nodes.
  const basicColumns = workspace.querySelector('.workspace-grid').children;
  const numericCard = basicColumns[0]; numericCard.classList.add('tool-card');
  const runGroups = groupChildren(basicColumns[1]);
  const runSettings = runGroups[0], diagnostics = runGroups[1];
  const fileControls = card('Scenario files');
  for (const id of ['export-run','export-scenario']) fileControls.append($(id));
  fileControls.append($('import-scenario').closest('label'));
  const populationColumns = advancedPanel.querySelector('.workspace-grid').children;
  const populationCard = populationColumns[0]; populationCard.classList.add('tool-card');
  const advancedGroups = groupChildren(populationColumns[1]);
  const sensitivityCard = advancedGroups[0], designCard = advancedGroups[1];
  archivePanel.classList.add('tool-card');
  const researchColumns = modulesPanel.querySelector('.workspace-grid').children;
  const researchGroups = groupChildren(researchColumns[0]);
  const behaviorCard = researchGroups[0], sobolCard = researchGroups[1], searchCard = researchGroups[2];
  const evidenceGroups = groupChildren(researchColumns[1]);
  const evidenceCard = evidenceGroups[0], networkCard = evidenceGroups[1];
  const studyColumns = studyPanel.querySelector('.workspace-grid').children;
  const compareCard = studyColumns[0]; compareCard.classList.add('tool-card');
  const calibrationCard = studyColumns[1]; calibrationCard.classList.add('tool-card');

  // One shared viewport and inspector travel between live and replay workspaces.
  const inspector = element('aside', 'studio-inspector'); inspector.id = 'studio-inspector';
  const inspectorHeader = element('div', 'inspector-header');
  inspectorHeader.append(element('strong', '', 'Inspector'));
  const closeInspector = button('×', () => setInspector(false), 'icon-button');
  closeInspector.setAttribute('aria-label', 'Close inspector'); inspectorHeader.append(closeInspector); inspector.append(inspectorHeader);
  const inspectorToggle = button('Inspector', () => setInspector(!inspectorIsExpanded()), 'inspector-toggle');
  inspectorToggle.id = 'inspector-toggle'; inspectorToggle.setAttribute('aria-controls', inspector.id);
  headerActions.prepend(inspectorToggle);
  const inspectAgent = card('Agent inspection');
  inspectAgent.append($('agent-probe'), $('agent-info'));
  runControls.querySelector('.buttons').remove();
  runControls.append(fold(runSettings, 'Timing & integrator'), fold(fileControls, 'Import & export'));
  inspectAgent.append(fold(diagnostics, 'Numerical diagnostics'));
  installTabs(inspector, 'inspector', [
    ['run', 'Run', runControls], ['population','Population',populationCard],
    ['model','Model',behaviorCard], ['inspect','Inspect',inspectAgent]
  ]);
  // The old wrappers are empty once all useful nodes have been moved.
  simulation.querySelector('.side').remove();
  const charts = telemetry.querySelector('.charts'); telemetry.append(fold(charts, 'Live time series'));
  const stageHead = stage.querySelector('.stage-head');
  const stageLink = button('Edit scenario ↗', () => navigate('scenario'), 'stage-edit'); stageHead.append(stageLink);
  const canvasHosts = new Map();
  for (const [id, view] of [['simulation',liveView],['analysis',analysisView]]) {
    const layout = element('div', 'canvas-workspace');
    const main = element('div', 'canvas-column');
    const host = element('div', 'viewport-host'); const summaryHost = element('div', 'summary-host');
    main.append(host, summaryHost); layout.append(main);
    const inspectorHost = element('div', 'inspector-host'); layout.append(inspectorHost); view.append(layout);
    canvasHosts.set(id, {host, summaryHost, inspectorHost});
  }
  // Keep shared controls attached even when a deep link opens a non-canvas
  // workspace first. Socket initialization still needs their input values.
  const initialHosts=canvasHosts.get('simulation');
  initialHosts.host.append(stage);initialHosts.summaryHost.append(telemetry);initialHosts.inspectorHost.append(inspector);

  const editorHeading = editorPanel.querySelector('h2'); editorHeading.remove();
  const editorHelp = editorPanel.querySelector('p');
  const helpPlaceholder = document.createComment('editor help'); editorHelp.replaceWith(helpPlaceholder);
  helpPlaceholder.replaceWith(fold(editorHelp, 'Drawing controls & keyboard workflow'));
  editorPanel.classList.add('scenario-surface');
  const editorInspector = $('object-json').closest('div'); editorInspector.classList.add('editor-properties');
  const editorBoard = element('div', 'editor-board');
  const canvasContainer = element('div', 'editor-canvas-host'); canvasContainer.append(editCanvas, $('edit-info'));
  editorBoard.append(canvasContainer, editorInspector); editorPanel.append(editorBoard);
  scenarioView.append(editorPanel, fold(numericCard, 'Advanced: basic room JSON editor'));
  const scenarioActions = element('div', 'scenario-actions');
  const exportScenario = button('Export scenario', () => $('export-scenario').click());
  const importScenario = button('Import scenario', () => $('import-scenario').click());
  scenarioActions.append(importScenario, exportScenario, button('Open simulation →', () => navigate('simulation'), 'primary'));
  scenarioView.querySelector('.view-intro').append(scenarioActions);

  // Keep the replay controls next to the viewport, not pages away from it.
  const replayControls = element('div', 'replay-controls');
  for (const id of ['replay-live','replay-back','replay-play','replay-next','layer','replay-export']) replayControls.append($(id));
  const timeline = element('div', 'replay-timeline'); timeline.append($('replay-time'), $('replay-info'));
  const recordingCard = card(); recordingCard.append(replayControls, timeline);
  analysisView.querySelector('.view-intro').after(recordingCard);
  const comparisonCard = card('Captured A/B runs');
  comparisonCard.append($('capture-a'), $('capture-b'));
  const comparisonCanvases = $('compare-a').parentElement.parentElement;
  comparisonCard.append(comparisonCanvases, $('compare-info'));
  analysisView.append(fold(comparisonCard, 'A/B replay comparison'));

  const experimentShared = card(); experimentShared.classList.add('experiment-shared');
  const seedLabel = $('study-seeds').closest('label'); experimentShared.append(seedLabel);
  const context = element('p', 'helper', 'Each tool uses the current run settings. Save A/B settings to compare two scenarios.');
  experimentShared.append(context); experimentsView.append(experimentShared);
  const sensitivityTools = element('div', 'tool-grid'); sensitivityTools.append(sensitivityCard, fold(sobolCard, 'Advanced: global Sobol analysis'));
  const geometryTools = element('div', 'tool-grid'); geometryTools.append(designCard, fold(searchCard, 'Automatic pillar search'));
  mcPanel.classList.add('tool-card');
  const resultsCard = card('Study results');
  const resultActions = element('div', 'result-actions'); resultActions.append($('cancel-study'), $('export-study'));
  resultsCard.append(resultActions, $('study-progress'));
  const emptyResults = element('div', 'empty-state', 'No results yet. Run an experiment or open a saved study.');
  emptyResults.id = 'studio-empty-results'; resultsCard.append(emptyResults, $('study-results'), fold(archivePanel, 'Saved study archive', true));
  installTabs(experimentsView, 'experiments', [
    ['compare','Compare & sweep',compareCard], ['sensitivity','Sensitivity',sensitivityTools],
    ['geometry','Design search',geometryTools], ['montecarlo','Monte Carlo',mcPanel], ['results','Results & archive',resultsCard]
  ]);
  installTabs(evidenceView, 'evidence', [['report','Experimental report',evidenceCard],['calibration','Calibration',calibrationCard]]);
  networkCard.classList.add('network-card'); buildingView.append(networkCard);
  // Remove the former document containers; every input remains in a workspace.
  for (const obsolete of [workspace, advancedPanel, modulesPanel, analysisPanel, studyPanel]) obsolete.remove();
  for (const view of views.values()) explain(view);
  explain(inspector);

  function installTabs(parent, namespace, definitions) {
    const list = element('div', 'studio-tabs'); list.setAttribute('role','tablist'); list.setAttribute('aria-label', namespace + ' tools');
    const panels = element('div', 'studio-tabpanels'); const items = new Map();
    for (const [key, label, content] of definitions) {
      const id = namespace + '-' + key;
      const tab = button(label, () => selectTab(namespace, key)); tab.id = 'tab-' + id;
      tab.setAttribute('role','tab'); tab.setAttribute('aria-controls','panel-' + id);
      const panel = element('div', 'studio-tabpanel'); panel.id = 'panel-' + id;
      panel.setAttribute('role','tabpanel'); panel.setAttribute('aria-labelledby',tab.id); panel.append(content);
      list.append(tab); panels.append(panel); items.set(key,{tab,panel});
      tab.addEventListener('keydown', event => {
        const allKeys = definitions.map(d => d[0]); const index = allKeys.indexOf(key);
        let next;
        if (event.key === 'ArrowRight') next = allKeys[(index+1)%allKeys.length];
        if (event.key === 'ArrowLeft') next = allKeys[(index-1+allKeys.length)%allKeys.length];
        if (event.key === 'Home') next = allKeys[0];
        if (event.key === 'End') next = allKeys.at(-1);
        if (next) { event.preventDefault(); selectTab(namespace,next); items.get(next).tab.focus(); }
      });
    }
    parent.append(list,panels); tabs.set(namespace,items); selectTab(namespace,definitions[0][0]);
  }
  function selectTab(namespace, key) {
    const items = tabs.get(namespace); if (!items?.has(key)) return;
    for (const [name,{tab,panel}] of items) {
      tab.setAttribute('aria-selected',String(name===key)); tab.tabIndex = name===key ? 0 : -1;
      panel.hidden = name!==key;
    }
  }
  function navIsExpanded() {
    return matchMedia('(max-width: 760px)').matches ? document.body.classList.contains('nav-open') : !document.body.classList.contains('nav-collapsed');
  }
  function setNavigation(expanded) {
    if (matchMedia('(max-width: 760px)').matches) {
      document.body.classList.toggle('nav-open',expanded);
      if (expanded) { returnFocus = document.activeElement; navigation.querySelector('[aria-current]')?.focus(); }
      else if (sidebar.contains(document.activeElement)) (returnFocus || menuButton).focus();
    } else {
      document.body.classList.toggle('nav-collapsed',!expanded);
      try { localStorage.setItem('crowdsafe.navCollapsed',String(!expanded)); } catch {}
    }
    menuButton.setAttribute('aria-expanded',String(expanded));
    sidebar.inert = matchMedia('(max-width: 760px)').matches && !expanded;
  }
  function inspectorIsExpanded() { return !document.body.classList.contains('inspector-collapsed'); }
  function setInspector(expanded) {
    document.body.classList.toggle('inspector-collapsed',!expanded);
    inspectorToggle.setAttribute('aria-expanded',String(expanded)); inspector.inert = !expanded;
    if (!expanded && inspector.contains(document.activeElement)) inspectorToggle.focus();
  }
  function navigate(id, tabKey) {
    if (!views.has(id)) id = 'simulation';
    const target = '#' + id + (tabKey ? '/' + tabKey : '');
    if (location.hash === target) applyRoute(); else location.hash = target;
  }
  function applyRoute() {
    const [requested, tabKey] = location.hash.slice(1).split('/');
    const id = views.has(requested) ? requested : 'simulation';
    savedScroll.set(current,pages.scrollTop); current = id;
    for (const [key,view] of views) view.hidden = key!==id;
    for (const link of navigation.querySelectorAll('a')) {
      if (link.dataset.view===id) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current');
    }
    title.textContent = viewDefinitions.find(v => v[0]===id)[1]; document.title = title.textContent + ' · CrowdSafe';
    document.body.dataset.workspace=id;
    inspectorToggle.hidden=!canvasHosts.has(id);
    if (canvasHosts.has(id)) {
      const {host,summaryHost,inspectorHost} = canvasHosts.get(id);
      host.append(stage); summaryHost.append(telemetry); inspectorHost.append(inspector);
      if (id==='analysis') selectTab('inspector','inspect');
    }
    if (tabKey) selectTab(id,tabKey);
    if (matchMedia('(max-width: 760px)').matches) setNavigation(false);
    pages.scrollTop=savedScroll.get(id)||0;
    // Repaint the same state; no socket messages or simulation resets.
    if (lastState && canvasHosts.has(id)) requestAnimationFrame(() => { if (displayFrame) displayAnalysis(displayFrame); });
  }
  window.addEventListener('hashchange',applyRoute);
  navigation.addEventListener('click', event => {
    const link=event.target.closest('a'); if (!link) return;
    event.preventDefault(); navigate(link.dataset.view);
  });

  const helpDialog = element('dialog','studio-dialog'); helpDialog.setAttribute('aria-labelledby','studio-help-title');
  helpDialog.innerHTML='<h2 id="studio-help-title">Your research workspace</h2><p>Use the sidebar to switch tasks. Navigation keeps your live run, geometry draft, recorded frames and results in memory.</p><ul><li><strong>Simulation:</strong> start, pause, reset and inspect a live run.</li><li><strong>Scenario:</strong> draw geometry and apply the draft to start a new paused run.</li><li><strong>Analysis:</strong> scrub recorded frames, change layers and capture A/B runs.</li><li><strong>Experiments:</strong> compare designs and review saved studies.</li><li><strong>Evidence:</strong> inspect real data and calibration.</li><li><strong>Building:</strong> run the separate floor and stair network.</li></ul><p>Ctrl+K finds tools. Escape closes dialogs and mobile navigation. Arrow keys switch tabs. Export scenarios and recordings before reloading the page.</p>';
  helpDialog.append(button('Close',()=>helpDialog.close(),'primary')); document.body.append(helpDialog);
  const finder=element('dialog','studio-dialog tool-finder'); finder.setAttribute('aria-labelledby','finder-title');
  finder.append(element('h2','','Find a tool')); finder.querySelector('h2').id='finder-title';
  const finderInput=element('input',''); finderInput.placeholder='Search scenarios, replay, calibration…'; finderInput.setAttribute('aria-label','Search tools');
  const finderList=element('div','finder-results'); finder.append(finderInput,finderList,button('Close',()=>finder.close())); document.body.append(finder);
  const toolDefinitions = [
    ['Live simulation','simulation'],['Draw walls, pillars & exits','scenario'],['Replay & spatial layers','analysis'],
    ['Run settings','simulation',null,'run'],['Population distributions','simulation',null,'population'],
    ['Movement model & groups','simulation',null,'model'],['Agent inspector & diagnostics','analysis',null,'inspect'],
    ['Compare A/B & speed sweep','experiments','compare'],['Sensitivity & Sobol','experiments','sensitivity'],
    ['Pareto & automatic design search','experiments','geometry'],['Monte Carlo','experiments','montecarlo'],
    ['Results & saved study archive','experiments','results'],['Experimental HERMES report','evidence','report'],
    ['Calibrate desired speed','evidence','calibration'],['Floors, stairs & visibility','building']
  ];
  function filterTools() {
    finderList.replaceChildren();
    const query=finderInput.value.toLowerCase().trim();
    for (const [label,view,tab,inspectorTab] of toolDefinitions.filter(tool=>tool[0].toLowerCase().includes(query))) {
      finderList.append(button(label,()=>{finder.close();navigate(view,tab);if(inspectorTab){setInspector(true);selectTab('inspector',inspectorTab);}},'finder-result'));
    }
    if (!finderList.children.length) finderList.append(element('p','','No matching tools. Try “replay”, “population” or “results”.'));
  }
  function openFinder() { finderInput.value=''; filterTools(); finder.showModal(); finderInput.focus(); }
  finderInput.addEventListener('input',filterTools);
  finderInput.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();finderList.querySelector('button')?.click();}});
  document.addEventListener('keydown',event=>{
    if ((event.ctrlKey||event.metaKey) && event.key.toLowerCase()==='k') {event.preventDefault();if(!finder.open)openFinder();}
    if (event.key==='Escape') {if(matchMedia('(max-width: 760px)').matches)setNavigation(false);if(matchMedia('(max-width: 1000px)').matches)setInspector(false);}
    if (event.key==='Tab' && document.body.classList.contains('nav-open')) {
      const focusable=[menuButton,...sidebar.querySelectorAll('a,button')];
      if(event.shiftKey&&document.activeElement===focusable[0]){event.preventDefault();focusable.at(-1).focus();}
      else if(!event.shiftKey&&document.activeElement===focusable.at(-1)){event.preventDefault();focusable[0].focus();}
    }
  });

  const toast=element('div','studio-toast'); toast.setAttribute('role','status'); toast.hidden=true;
  toast.append(element('span','', '')); const toastClose=button('×',()=>{toast.hidden=true;},'icon-button');toastClose.setAttribute('aria-label','Dismiss notification');toast.append(toastClose);document.body.append(toast);
  let toastTimer;
  function notify(message) {toast.firstElementChild.textContent=message.length>360?message.slice(0,360)+'…':message;toast.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>{toast.hidden=true;},6500);}
  for (const id of ['study-a','study-b','capture-a','capture-b']) $(id).addEventListener('click',()=>notify(id.startsWith('capture')?'Recorded run captured. Open A/B replay comparison to review it.':'Current settings saved as candidate '+(id.endsWith('a')?'A.':'B.')));
  const studyObserver=new MutationObserver(()=>{
    const message=$('study-progress').textContent.trim();statusJob.textContent=message||'No active study';statusJob.title=message||'Open experiment results';
  });studyObserver.observe($('study-progress'),{childList:true,characterData:true,subtree:true});
  const finalRender=renderStudy;
  renderStudy=result=>{
    finalRender(result);$('studio-empty-results').hidden=!!result;
    // Preserve full downloadable output, disclose verbose JSON on demand.
    for(const pre of [...$('study-results').children].filter(node=>node.tagName==='PRE')){
      const placeholder=document.createComment('numerical output');pre.replaceWith(placeholder);placeholder.replaceWith(fold(pre,'Detailed numerical output'));
    }
    if(result){if(current==='experiments')selectTab('experiments','results');else notify('Study results are ready. Open Experiments → Results & archive to review them.');}
  };
  const priorLaunch=launchStudy;
  launchStudy=async request=>{await priorLaunch(request);if($('study-progress').textContent.trim())navigate('experiments','results');};
  new MutationObserver(()=>{const message=$('workspace-error').textContent.trim();if(message)notify(message);}).observe($('workspace-error'),{childList:true,characterData:true,subtree:true});
  const priorReceive=receive;
  receive=event=>{
    priorReceive(event);let state;try{state=JSON.parse(event.data);}catch{return;}
    if(state.error){notify(state.error);return;}
    if(replayMode&&displayFrame)displayAnalysis(displayFrame);
    liveStatus.textContent=`${state.playing?'Running':state.done?'Finished':'Paused'} · ${state.time.toFixed(2)} s · ${state.evacuated}/${state.config.n_agents} evacuated · seed ${state.config.seed}`;
  };if(socket)socket.onmessage=receive;
  if(lastState)liveStatus.textContent=`Paused · ${lastState.time.toFixed(2)} s · seed ${lastState.config.seed}`;
  try { if(localStorage.getItem('crowdsafe.navCollapsed')==='true')document.body.classList.add('nav-collapsed'); } catch {}
  const mobile=matchMedia('(max-width: 760px)');
  mobile.addEventListener('change',()=>{document.body.classList.remove('nav-open');setNavigation(navIsExpanded());});
  const inspectorBreakpoint=matchMedia('(max-width: 1000px)');
  inspectorBreakpoint.addEventListener('change',()=>setInspector(!inspectorBreakpoint.matches));
  setNavigation(navIsExpanded());setInspector(!inspectorBreakpoint.matches);applyRoute();
})();
