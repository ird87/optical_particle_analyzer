const fs=require('fs'),vm=require('vm'),assert=require('assert');
let passed=0;const failures=[];
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};};
function rootState(){return {researchRevision:1,researchPending:false,results:[],averages:{},microscopes:[{name:'A',type:'MANUAL'},{name:'B',type:'MANUAL'}],analyzeSelectedCalibration:null,researchContext:null,researchState:{},resetResearch(result){this.researchRevision=result.revision;this.selectedResearch=null;this.results=[];this.averages={};this.analyzeSelectedCalibration=null;},async invalidateResearch(){this.researchRevision++;this.results=[];this.averages={};}};}
function load(file,api={},root=rootState(),extra={}){const c={window:{},api,console,setTimeout,clearTimeout,confirm:()=>true,...extra};vm.runInNewContext(fs.readFileSync(file,'utf8'),c);const d=Object.values(c.window)[0];const s={...d.data(),$root:root,$nextTick:fn=>Promise.resolve().then(fn)};for(const [k,f]of Object.entries(d.methods||{}))s[k]=f.bind(s);for(const [k,f]of Object.entries(d.computed||{}))Object.defineProperty(s,k,{get:()=>f.call(s)});return s;}
const editor=(api={},root=rootState(),extra={})=>load('gui/views/AnalyzeView.js',api,root,extra);
async function test(name,fn){try{await fn();passed++;}catch(e){failures.push(name+': '+e.stack);}}
(async()=>{
 await test('switching microscope starts a fresh series and drops the previous saved id',async()=>{
  const root=rootState(),s=editor({newResearch:async()=>({ok:true,revision:2})},root);
  s.activeMicroscopeName='A';s.sourceMicroscopeName='A';s.files=[{name:'1.jpg'}];s.researchId=7;s.name='Sample';s.selectedMicroscope=root.microscopes[1];
  await s.onMicroscopeChange();assert.strictEqual(s.files.length,0);assert.strictEqual(s.researchId,0);assert.strictEqual(s.name,'Sample');assert.strictEqual(root.researchRevision,2);
 });
 await test('declining a microscope change restores the previous instrument and frames',async()=>{
  let resets=0;const root=rootState(),s=editor({newResearch:async()=>{resets++;return {ok:true,revision:2};}},root,{confirm:()=>false});
  s.activeMicroscopeName='A';s.sourceMicroscopeName='A';s.files=[{name:'1.jpg'}];s.selectedMicroscope=root.microscopes[1];
  await s.onMicroscopeChange();assert.strictEqual(resets,0);assert.strictEqual(s.selectedMicroscope.name,'A');assert.strictEqual(s.files.length,1);
 });
 await test('first pending capture is invalidated when changing microscope',async()=>{
  const root=rootState(),s=editor({newResearch:async()=>({ok:true,revision:3})},root);
  s.activeMicroscopeName='A';s.selectedMicroscope=root.microscopes[1];await s.onMicroscopeChange();s.loadImage=async()=>{};
  await s.onCaptured({microscope:'A',filename:'1.jpg',revision:2});assert.strictEqual(s.files.length,0);
 });
 await test('calibration change removes the old overlay and selects the source',async()=>{
  const root=rootState(),s=editor({},root);root.results=[{area:1}];s.files=[{name:'1.jpg'}];s.currentFile=s.files[0];s.currentImage='old-overlay';s.selectedFolder='analyzed';
  s.loadImage=async(name,folder)=>{s.currentImage=folder;};await s.onCalibrationChange();
  assert.strictEqual(s.selectedFolder,'sources');assert.strictEqual(s.currentImage,'sources');assert.strictEqual(root.results.length,0);
 });
 await test('a frame from another instrument cannot enable analysis',async()=>{
  const root=rootState(),s=editor({},root);s.selectedMicroscope=root.microscopes[1];root.analyzeSelectedCalibration={id:2,microscope:'B'};
  s.files=[{name:'1.jpg'}];s.sourceMicroscopeName='A';assert.strictEqual(s.isAnalyzeButtonDisabled,true);
 });
 await test('deleting a frame uses the requested identity when selection changes',async()=>{
  const pending=deferred(),s=editor({deleteImage:()=>pending.promise});s.files=[{name:'1.jpg'},{name:'2.jpg'}];s.currentFile=s.files[0];s.loadImage=async()=>{};
  const deleting=s.deleteCurrentFile();s.currentFile=s.files[1];pending.resolve({ok:true,revision:2});await deleting;
  assert.strictEqual(s.files.length,1);assert.strictEqual(s.files[0].name,'2.jpg');
 });
 await test('saving is single flight and updates the result metadata and saved state',async()=>{
  const pending=deferred();let writes=0;const root=rootState();root.results=[{area:20}];root.selectedResearch={id:0,name:'Old',employee:'Old'};
  root.analyzeSelectedCalibration={id:1,microscope:'A'};
  const s=editor({saveResearch:()=>{writes++;return pending.promise;}},root);s.selectedMicroscope=root.microscopes[0];s.sourceMicroscopeName='A';s.name='New name';s.employee='New employee';
  const first=s.saveResearch(),second=s.saveResearch();pending.resolve({ok:true,id:7});await Promise.all([first,second]);
  assert.strictEqual(writes,1);assert.strictEqual(root.selectedResearch.name,'New name');assert.strictEqual(root.selectedResearch.employee,'New employee');assert.strictEqual(s.hasUnsavedChanges,false);assert(s.successMsg.includes('сохранено'));
  s.name='Edited';assert.strictEqual(s.hasUnsavedChanges,true);
 });
 await test('new research honours cancellation of unsaved work',async()=>{
  let resets=0;const s=editor({newResearch:async()=>{resets++;return {ok:true,revision:2};}},rootState(),{confirm:()=>false});s.files=[{name:'1.jpg'}];
  await s.createNewResearch();assert.strictEqual(resets,0);assert.strictEqual(s.files.length,1);
 });
 await test('pending research load blocks new work and cannot roll back a revision',async()=>{
  const pending=deferred();let resets=0;const root=rootState();const s=editor({loadResearch:()=>pending.promise,newResearch:async()=>{resets++;return {ok:true,revision:4};}},root);
  const loading=s.doLoadResearch({id:7});const working=s.working;await s.createNewResearch();root.researchRevision=3;
  pending.resolve({ok:true,revision:2,research:{id:7,name:'Old',contours:[]}});await loading;
  assert.strictEqual(working,true);assert.strictEqual(resets,0);assert.strictEqual(root.researchRevision,3);assert.strictEqual(s.researchId,0);
 });
 await test('file upload keeps the instrument and blocks concurrent session reset',async()=>{
  const pending=deferred();let resets=0;const root=rootState(),s=editor({uploadImage:()=>pending.promise,newResearch:async()=>{resets++;return {ok:true,revision:3};}},root);
  s.selectedMicroscope=root.microscopes[0];s._readAsBase64=async()=> 'image';s.loadImage=async()=>{};
  const upload=s.handleFileSelect({target:{files:[{name:'source.png'}],value:'source.png'}});await Promise.resolve();await s.createNewResearch();
  pending.resolve({ok:true,filename:'1.jpg',revision:2});await upload;
  assert.strictEqual(resets,0);assert.strictEqual(s.sourceMicroscopeName,'A');assert.strictEqual(s.files.length,1);
 });
 await test('opening another saved research does not invalidate it using the previous calibration',async()=>{
  let invalidations=0;const root=rootState();root.analyzeSelectedCalibration={id:1,name:'Old',microscope:'A',coefficient:20,division_price:'1 мкм'};
  root.invalidateResearch=async()=>{invalidations++;root.results=[];root.researchRevision++;};
  const s=editor({loadResearch:async()=>({ok:true,revision:2,research:{id:8,name:'Saved B',microscope:'B',calibration_id:2,contours:[{contour_number:1,area:20}]}}),
   getCalibrations:async()=>({ok:true,calibrations:[{id:2,name:'B scale',microscope:'B',coefficient:30,division_price:'1 мкм'}]}),
   listImages:async()=>({ok:true,revision:2,files:[]})},root);
  await s.doLoadResearch({id:8});assert.strictEqual(invalidations,0);assert.strictEqual(root.results.length,1);assert.strictEqual(root.analyzeSelectedCalibration.id,2);
 });
 await test('reanalysis of unchanged saved inputs is unsaved until saved again',async()=>{
  let resets=0;const root=rootState();root.results=[{area:1}];root.analyzeSelectedCalibration={id:1,microscope:'A',coefficient:10};
  const s=editor({executeResearch:async()=>({ok:true,revision:1,contours:[{area:999}],averages:{area:999}}),newResearch:async()=>{resets++;return {ok:true,revision:2};}},root,{confirm:()=>false});
  s.selectedMicroscope=root.microscopes[0];s.sourceMicroscopeName='A';s.files=[{name:'1.jpg'}];s.name='Saved';s.researchId=7;s.savedFingerprint=s.fingerprint;
  await s.analyzeAllFiles();assert.strictEqual(root.results[0].area,999);assert.strictEqual(s.hasUnsavedChanges,true);assert.strictEqual(s.editorStatus.saved,false);
  await s.createNewResearch();assert.strictEqual(resets,0);
 });
 await test('loaded measurements do not claim the current calibration scale as historical',async()=>{
  const root=rootState();root.results=[{area:1}];root.divisionPrices=[{name:'1 мкм',value:1}];root.analyzeSelectedCalibration={id:1,microscope:'A',coefficient:50,division_price:'1 мкм'};
  root.researchContext={calibration:{id:1,name:'Saved scale'}};
  const s=editor({},root);assert(!s.calibrationScale.includes('0,02'));assert(s.calibrationScale.includes('сохранённого'));
 });
 await test('calibration refresh blocks analysis and saving until the latest settings arrive',async()=>{
  const pending=deferred();let runs=0;const root=rootState();root.analyzeSelectedCalibration={id:1,microscope:'A',coefficient:10,division_price:'1 мкм'};root.results=[{area:1}];
  const s=editor({getCalibrations:()=>pending.promise,executeResearch:async()=>{runs++;return {ok:true,revision:1,contours:[{area:99}],averages:{area:99}};}},root);
  s.name='Sample';s.selectedMicroscope=root.microscopes[0];s.sourceMicroscopeName='A';s.files=[{name:'1.jpg'}];
  const refresh=s.fetchCalibrations();const blocked=s.isAnalyzeButtonDisabled && s.isSaveButtonDisabled;await s.analyzeAllFiles();
  pending.resolve({ok:true,calibrations:[{id:1,microscope:'A',coefficient:50,division_price:'1 мкм'}]});await refresh;
  assert.strictEqual(blocked,true);assert.strictEqual(runs,0);assert.strictEqual(root.analyzeSelectedCalibration.coefficient,50);
 });
 await test('analysis cannot accept a result after its calibration context changes',async()=>{
  const pending=deferred(),root=rootState();root.analyzeSelectedCalibration={id:1,microscope:'A',coefficient:10,division_price:'1 мкм'};
  const s=editor({executeResearch:()=>pending.promise},root);s.selectedMicroscope=root.microscopes[0];s.sourceMicroscopeName='A';s.files=[{name:'1.jpg'}];
  const run=s.analyzeAllFiles();root.analyzeSelectedCalibration={id:1,microscope:'A',coefficient:50,division_price:'1 мкм'};
  pending.resolve({ok:true,revision:1,contours:[{area:99}],averages:{area:99}});await run;
  assert.strictEqual(root.results.length,0);assert.strictEqual(root.researchContext,null);
 });
 await test('failed calibration refresh cannot leave analysis enabled with unverified settings',async()=>{
  const root=rootState();root.analyzeSelectedCalibration={id:1,microscope:'A',coefficient:10};root.results=[{area:1}];
  const s=editor({getCalibrations:async()=>({ok:false,error:'Device settings unavailable'})},root);s.selectedMicroscope=root.microscopes[0];s.sourceMicroscopeName='A';s.files=[{name:'1.jpg'}];s.name='Sample';
  await s.fetchCalibrations();assert.strictEqual(s.isAnalyzeButtonDisabled,true);assert.strictEqual(s.isSaveButtonDisabled,true);
 });
 await test('older calibration response cannot replace a newer list',async()=>{
  const first=deferred(),second=deferred();let calls=0;const root=rootState();root.analyzeSelectedCalibration={id:1,microscope:'A',coefficient:10};
  const s=editor({getCalibrations:()=>++calls===1?first.promise:second.promise},root);
  const a=s.fetchCalibrations(),b=s.fetchCalibrations();second.resolve({ok:true,calibrations:[{id:1,microscope:'A',coefficient:50}]});await b;
  first.resolve({ok:true,calibrations:[{id:1,microscope:'A',coefficient:10}]});await a;assert.strictEqual(root.analyzeSelectedCalibration.coefficient,50);
 });
 await test('changing particle settings clears old measurements and returns to the source',async()=>{
  const root=rootState();root.results=[{area:1}];const s=editor({},root);s.files=[{name:'1.jpg'}];s.currentFile=s.files[0];s.selectedFolder='analyzed';s.currentImage='old-overlay';s.loadImage=async(_,folder)=>{s.currentImage=folder;};
  s.analysisOptions={mode:'light',min_area_px:50,split_touching:false};await s.onAnalysisOptionsChange();
  assert.strictEqual(root.results.length,0);assert.strictEqual(s.currentImage,'sources');assert.strictEqual(s.needsAnalysis,true);
 });
 await test('analysis sends particle settings and rejects late results for different settings',async()=>{
  let sent;const pending=deferred(),root=rootState();root.analyzeSelectedCalibration={id:1,microscope:'A',coefficient:10};
  const s=editor({executeResearch:(id,options)=>{sent=options;return pending.promise;}},root);s.selectedMicroscope=root.microscopes[0];s.sourceMicroscopeName='A';s.files=[{name:'1.jpg'}];
  s.analysisOptions={mode:'color',min_area_px:40,split_touching:false};const run=s.analyzeAllFiles();s.analysisOptions.mode='dark';
  pending.resolve({ok:true,revision:1,contours:[{area:5}],averages:{area:5}});await run;
  assert.strictEqual(sent.mode,'color');assert.strictEqual(root.results.length,0);
 });
 await test('invalid minimum particle area prevents analysis and saving',async()=>{
  const root=rootState();root.analyzeSelectedCalibration={id:1,microscope:'A'};root.results=[{area:1}];const s=editor({},root);s.selectedMicroscope=root.microscopes[0];s.sourceMicroscopeName='A';s.files=[{name:'1.jpg'}];s.name='Sample';s.analysisOptions={mode:'auto',min_area_px:'',split_touching:false};
  assert.strictEqual(s.isAnalyzeButtonDisabled,true);assert.strictEqual(s.isSaveButtonDisabled,true);
 });
 for(const value of [0,'',2.5,101,-1])await test('histogram rejects invalid bin count '+JSON.stringify(value),async()=>{
  const s=load('gui/views/ResultsView.js');assert.throws(()=>s.createBins(1,10,value));
 });
 await test('histogram includes extrema and constant measurements',async()=>{
  const s=load('gui/views/ResultsView.js');const bins=s.createBins(1,10,3);const counts=s.distributeToBins([1,4,7,10],bins);assert.strictEqual(counts.reduce((a,b)=>a+b,0),4);
  assert.strictEqual(s.distributeToBins([5,5,5],s.createBins(5,5,20))[0],3);
 });
 console.log(`${passed} research workflow checks passed; ${failures.length} failed`);for(const f of failures)console.error(f);if(failures.length)process.exitCode=1;
})();
