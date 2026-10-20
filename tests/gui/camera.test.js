const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
let passed = 0;
const failures = [];
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return {promise, resolve}; };
const tick = () => new Promise(r => setImmediate(r));

function load(file, api = {}, extra = {}) {
  const context = { window: {}, api, console, setTimeout, clearTimeout, ...extra };
  vm.runInNewContext(fs.readFileSync(file, 'utf8'), context, {filename:file});
  return context;
}
function instance(definition, props = {}) {
  const state = Object.assign({}, definition.data ? definition.data() : {}, props);
  state.$emit = (event, payload) => state.events.push([event, payload]);
  state.events = [];
  state.$nextTick = fn => Promise.resolve().then(fn);
  for (const [name, method] of Object.entries(definition.methods || {})) state[name] = method.bind(state);
  for (const [name, getter] of Object.entries(definition.computed || {})) Object.defineProperty(state,name,{get:()=>getter.call(state)});
  return state;
}
async function test(name, run) {
  try { await run(); passed++; }
  catch (error) { failures.push(name + ': ' + error.stack); }
}

(async () => {
  await test('settings test continuously refreshes video and takes a separate snapshot', async () => {
    const timers=[];let reads=0;let openedIndex=null;
    const context=load('gui/components/CameraPanel.js',{
      connectCamera:async index=>{openedIndex=index;return {ok:true,connection_id:'test'};},
      getCameraFrame:async()=>({ok:true,data:'video-'+(++reads)}),
      captureTestFrame:async token=>({ok:token==='test',data:'full-snapshot',width:1600,height:1000}),
      disconnectCamera:async()=>({ok:true}),
    },{setTimeout:fn=>{timers.push(fn);return timers.length;},clearTimeout:()=>{}});
    const state=instance(context.window.CameraPanel,{active:true,context:'settings',cameraIndex:0});
    await state.connect();await tick();
    assert.strictEqual(openedIndex,0);
    assert.strictEqual(state.preview,'video-1');
    await state.capture();
    assert.strictEqual(state.testSnapshot,'full-snapshot');
    assert.strictEqual(state.preview,'video-1');
    timers.shift()();await tick();
    assert.strictEqual(state.preview,'video-2');
    assert.strictEqual(state.testSnapshot,'full-snapshot');
    await state.stop();
  });
  await test('late test snapshot is ignored after leaving settings', async () => {
    const pending=deferred();
    const context=load('gui/components/CameraPanel.js',{
      captureTestFrame:()=>pending.promise,disconnectCamera:async()=>({ok:true}),
    });
    const state=instance(context.window.CameraPanel,{active:true,context:'settings',connectionId:'test'});
    const capturing=state.capture();state.active=false;await state.stop();
    pending.resolve({ok:true,data:'old-snapshot',width:100,height:80});await capturing;
    assert.strictEqual(state.testSnapshot,'');
    assert(!state.events.some(event=>event[0]==='captured'));
  });
  await test('switching test cameras closes preview and clears the previous snapshot', async () => {
    let disconnected='';
    const context=load('gui/components/CameraPanel.js',{
      disconnectCamera:async token=>{disconnected=token;return {ok:true};},
    });
    const definition=context.window.CameraPanel;
    const state=instance(definition,{active:true,context:'settings',cameraIndex:0,connectionId:'test'});
    state.testSnapshot='old-snapshot';
    await definition.watch.cameraIndex.call(state,1);
    assert.strictEqual(disconnected,'test');
    assert.strictEqual(state.testSnapshot,'');
    assert.strictEqual(state.connectionId,'');
  });
  await test('stale frame is ignored and only one preview request is active', async () => {
    const pending = deferred(); let reads = 0;
    const context = load('gui/components/CameraPanel.js', {
      connectMicroscope:async()=>({ok:true,connection_id:'a',revision:0}),
      getCameraFrame:()=>{ reads++; return pending.promise; }, disconnectCamera:async()=>({ok:true})
    });
    const component = context.window.CameraPanel;
    const state = instance(component,{active:true,context:'research',revision:0,microscope:{name:'USB',camera_index:0}});
    await state.connect();
    await state.poll(state.generation);
    assert.strictEqual(reads,1);
    await state.stop();
    pending.resolve({ok:true,data:'old-frame'});
    await tick();
    assert.strictEqual(state.preview,'');
    assert.strictEqual(state.connectionId,'');
  });
  await test('capture emits full source identity and revision', async () => {
    const context = load('gui/components/CameraPanel.js', {
      captureImage:async(token,ctx,revision)=>({ok:token==='a' && ctx==='research' && revision===3,filename:'4.jpg',revision:4}),
      disconnectCamera:async()=>({ok:true})
    });
    const state = instance(context.window.CameraPanel,{active:true,context:'research',revision:3,connectionId:'a'});
    await state.capture();
    assert.strictEqual(state.events[0][0],'captured');
    assert.strictEqual(state.events[0][1].filename,'4.jpg');
    assert.strictEqual(state.events[0][1].revision,4);
    await state.stop();
  });
  await test('failed preview releases the connection', async () => {
    let disconnected = false;
    const context = load('gui/components/CameraPanel.js', {
      getCameraFrame:async()=>({ok:false,error:'USB disconnected'}),
      disconnectCamera:async()=>{disconnected=true;return {ok:true};}
    });
    const state = instance(context.window.CameraPanel,{active:true,context:'research',connectionId:'a'});
    await state.poll(state.generation);
    assert.strictEqual(state.connectionId,'');
    assert.strictEqual(disconnected,true);
    assert(state.cameraError.includes('USB'));
  });
  await test('stop during opening closes late connection', async () => {
    const pending = deferred(); let closed = '';
    const context = load('gui/components/CameraPanel.js', {
      connectMicroscope:()=>pending.promise,
      disconnectCamera:async token=>{closed=token;return {ok:true};}
    });
    const state = instance(context.window.CameraPanel,{active:true,context:'research',revision:0,microscope:{name:'USB',camera_index:0}});
    const opening = state.connect();
    await state.stop();
    pending.resolve({ok:true,connection_id:'late'});
    await opening;
    assert.strictEqual(closed,'late');
    assert.strictEqual(state.connectionId,'');
  });
  await test('new captured source invalidates analysis and clears derived cache', async () => {
    const context = load('gui/views/AnalyzeView.js');
    const root = {researchRevision:2,results:[{area:20}],averages:{area:20}};
    const state = instance(context.window.AnalyzeView,{$root:root});
    state.loadImage = async()=>{};
    state.imageCache = {'1.jpg':{analyzed:'old'}};
    await state.onCaptured({filename:'2.jpg',revision:3});
    assert.strictEqual(root.results.length,0);
    assert.strictEqual(root.researchRevision,3);
    assert.strictEqual(state.files[0].name,'2.jpg');
    assert.strictEqual(state.isSaveButtonDisabled,true);
    assert.strictEqual(Object.keys(state.imageCache).length,0);
  });
  await test('new calibration source resets coefficient and processed images', async () => {
    const context = load('gui/views/CalibrationView.js');
    const root = {calibrationRevision:1};
    const state = instance(context.window.CalibrationView,{$root:root});
    state._loadImage = async()=>{};
    state.calibCoefficient = 50;
    state.calibDetection = {count:4,orientation:'horizontal'};
    await state.onCaptured({filename:'sources.jpg',revision:2});
    assert.strictEqual(state.calibCoefficient,'');
    assert.strictEqual(state.calibDetection,null);
    assert.strictEqual(state.calibFileExists['calibrated.jpg'],false);
    assert.strictEqual(root.calibrationRevision,2);
  });
  await test('application waits for pywebview bridge readiness', async () => {
    const html = fs.readFileSync('gui/index.html','utf8');
    const inline = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)][0][1];
    let mounted = 0; const timers = []; const listeners = {};
    const app = {component:()=>{},mount:()=>{mounted++;}};
    const window = {addEventListener:(name,fn)=>{listeners[name]=fn;}};
    vm.runInNewContext(inline,{window,Vue:{createApp:()=>app},setTimeout:fn=>{timers.push(fn);}});
    timers.shift()();
    assert.strictEqual(mounted,0);
    window.pywebview = {api:{}};
    listeners.pywebviewready();
    assert.strictEqual(mounted,1);
    listeners.pywebviewready();
    assert.strictEqual(mounted,1);
  });
  await test('late image response cannot replace a newly selected source', async () => {
    const pending=deferred();
    const context=load('gui/views/AnalyzeView.js',{getImage:()=>pending.promise});
    const state=instance(context.window.AnalyzeView,{$root:{results:[]}});
    state.currentFile={name:'1.jpg'};
    const loading=state.loadImage('1.jpg','sources');
    state.currentFile={name:'2.jpg'};
    state.currentImage='new-source';
    pending.resolve({ok:true,data:'old-source'});
    await loading;
    assert.strictEqual(state.currentImage,'new-source');
  });
  await test('late session file list cannot roll back the session revision', async () => {
    const pending=deferred();
    const context=load('gui/views/AnalyzeView.js',{listImages:()=>pending.promise});
    const root={researchRevision:2,microscopes:[],results:[]};
    const state=instance(context.window.AnalyzeView,{$root:root});
    const loading=state.syncFromRoot(null);
    root.researchRevision=3;
    pending.resolve({ok:true,revision:2,files:[]});
    await loading;
    assert.strictEqual(root.researchRevision,3);
  });
  await test('successful capture after tab stop still reconciles the committed mutation', async () => {
    const pending=deferred();
    const context=load('gui/components/CameraPanel.js',{
      captureImage:()=>pending.promise,disconnectCamera:async()=>({ok:true})
    });
    const state=instance(context.window.CameraPanel,{active:true,context:'research',revision:3,connectionId:'a'});
    const capturing=state.capture();
    state.active=false;
    await state.stop();
    pending.resolve({ok:true,filename:'4.jpg',revision:4});
    await capturing;
    assert(state.events.some(event=>event[0]==='captured' && event[1].revision===4));
  });
  await test('returning to acquisition reconciles a committed but unseen source', async () => {
    const context=load('gui/views/AnalyzeView.js',{
      listImages:async()=>({ok:true,revision:4,files:['1.jpg','2.jpg']})
    });
    const root={researchRevision:3,results:[{area:99}],averages:{area:99}};
    const state=instance(context.window.AnalyzeView,{$root:root});
    state.loadImage=async()=>{};
    state.files=[{name:'1.jpg'}];
    await state.refreshSession();
    assert.strictEqual(root.researchRevision,4);
    assert.strictEqual(state.files.length,2);
    assert.strictEqual(root.results.length,0);
  });
  await test('analysis waits until session reconciliation finishes', async () => {
    const context=load('gui/views/AnalyzeView.js');
    const root={researchPending:false,analyzeSelectedCalibration:{id:1},results:[]};
    const state=instance(context.window.AnalyzeView,{$root:root});
    state.selectedMicroscope={name:'USB',type:'MANUAL'};state.files=[{name:'1.jpg'}];
    state.sessionSyncing=true;
    assert.strictEqual(state.isAnalyzeButtonDisabled,true);
  });
  await test('deleted loaded calibration resets its save identifier', async () => {
    const context=load('gui/views/CalibrationView.js',{
      deleteCalibration:async()=>({ok:true,active:true,revision:2})
    },{confirm:()=>true});
    const root={calibrationRevision:1};
    const state=instance(context.window.CalibrationView,{$root:root});
    state.calibId=1;state.selectedRow={id:1};state.calibrations=[{id:1}];
    await state.deleteCalibration();
    assert.strictEqual(state.calibId,0);
    assert.strictEqual(root.calibrationRevision,2);
  });
  console.log(`${passed} GUI behavior checks passed; ${failures.length} failed`);
  for (const failure of failures) console.error(failure);
  if (failures.length) process.exitCode=1;
})();
