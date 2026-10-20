// Optional DOM integration check: NODE_PATH=<jsdom node_modules> node ...
const fs = require('fs');
const assert = require('assert');
const vm = require('vm');
const {JSDOM} = require('jsdom');
const html = fs.readFileSync('gui/index.html', 'utf8');
const dom = new JSDOM(html,{runScripts:'outside-only',url:'http://localhost/'});
const w = dom.window;
const errors=[];
w.addEventListener('error',event=>errors.push(event.error));
w.console.error=(...args)=>errors.push(args.join(' '));
const state={microscopes:[{name:'По умолчанию',type:'DEFAULT',custom:false,camera_index:null},
                         {name:'М001',type:'MANUAL',custom:false,camera_index:null},
                         {name:'М002',type:'AUTOMATIC',custom:false,camera_index:null}],
             calibrations:[],researchRevision:0,calibrationRevision:0,files:[],calFiles:[],owner:null,saved:null};
let videoFrames=0;
const contour={contour_number:1,perimeter:10,area:20,width:2,length:3,dek:5};
const averages={perimeter:10,area:20,width:2,length:3,dek:5};
const ok=data=>({ok:true,...data});
const methods={
  get_microscopes:()=>ok({microscopes:state.microscopes}),
  get_division_prices:()=>ok({division_prices:[{name:'1 мкм',value:1}]}),
  get_calibrations:()=>ok({calibrations:state.calibrations}),
  get_researches:()=>ok({researches:state.saved?[state.saved]:[]}),
  get_session_state:ctx=>ok({revision:state[ctx+'Revision']}),
  list_images:ctx=>ok({revision:state[ctx+'Revision'],files:ctx==='research'?state.files:state.calFiles}),
  get_image:()=>ok({data:'data:image/jpeg;base64,/9j/'}),
  save_custom_microscope:data=>{state.microscopes.push({...data,id:1,custom:true,type_localized:'Ручной'});return ok({id:1});},
  bind_microscope:(name,index)=>{state.microscopes.find(m=>m.name===name).camera_index=index;return ok({});},
  connect_microscope:(name,ctx)=>{state.owner=ctx;return ok({connection_id:ctx,revision:state[ctx+'Revision']||0});},
  scan_cameras:()=>ok({cameras:[{index:0,label:'Камера 0'}]}),
  connect_camera:index=>{assert(Number.isInteger(index));state.testCameraIndex=index;state.owner='test';return ok({connection_id:'test'});},
  capture_test_frame:token=>{assert.strictEqual(token,state.owner);assert(['test','settings'].includes(token));return ok({data:'data:image/jpeg;base64,c25hcHNob3Q=',width:1600,height:1000});},
  disconnect_camera:token=>{if(state.owner===token)state.owner=null;return ok({});},
  get_camera_frame:()=>ok({data:'data:image/jpeg;base64,'+Buffer.from('frame-'+(++videoFrames)).toString('base64')}),
  capture_image:(token,ctx,revision)=>{
    assert.strictEqual(token,ctx);assert.strictEqual(revision,state[ctx+'Revision']);
    const filename=ctx==='research'?(state.files.length+1)+'.jpg':'sources.jpg';
    if(ctx==='research')state.files.push(filename);else state.calFiles=[filename];
    return ok({filename,revision:++state[ctx+'Revision']});
  },
  new_calibration:()=>{state.calFiles=[];return ok({revision:++state.calibrationRevision});},
  execute_calibration:()=>ok({coefficient:20,marks_count:4,orientation:'horizontal',revision:state.calibrationRevision}),
  save_calibration:data=>{assert.strictEqual(data.revision,state.calibrationRevision);state.calibrations=[{...data,id:1}];return ok({id:1});},
  invalidate_research:revision=>{assert.strictEqual(revision,state.researchRevision);return ok({revision:++state.researchRevision});},
  execute_research:cal=>{assert.strictEqual(cal,1);return ok({contours:[contour],averages,revision:state.researchRevision});},
  save_research:data=>{assert.strictEqual(data.revision,state.researchRevision);state.saved={...data,id:1,date:'2026-10-19T10:00:00'};return ok({id:1});},
  load_research:()=>ok({research:state.saved,files:state.files,revision:++state.researchRevision}),
  delete_research:()=>{state.saved=null;return ok({active:true,revision:++state.researchRevision});},
};
w.pywebview={api:new Proxy({}, {get:(_,name)=>async(...args)=>{
  assert(methods[name], 'Unexpected bridge method: '+name);
  return JSON.parse(JSON.stringify(methods[name](...args)));
}})};
w.confirm=()=>true;
function find(vnode,type){
  if(!vnode)return null;
  if(vnode.component){if(vnode.component.type===type)return vnode.component.proxy;const found=find(vnode.component.subTree,type);if(found)return found;}
  for(const child of Array.isArray(vnode.children)?vnode.children:[]){const found=find(child,type);if(found)return found;}
  return null;
}
const settle=async()=>{for(let i=0;i<8;i++){await Promise.resolve();await w.Vue.nextTick();}};
(async()=>{
  try {
    for(const match of html.matchAll(/<script src="([^"]+)"><\/script>/g)){
      if(match[1].includes('bootstrap')||match[1].includes('chart.umd'))continue;
      vm.runInContext(fs.readFileSync('gui/'+match[1],'utf8'),dom.getInternalVMContext(),{filename:match[1]});
    }
    vm.runInContext([...html.matchAll(/<script>([\s\S]*?)<\/script>/g)][0][1],dom.getInternalVMContext());
    w.dispatchEvent(new w.Event('pywebviewready'));
    await settle();
    const root=w.document.getElementById('app')._vnode.component.proxy;
    const component=name=>find(root.$.subTree,w[name]);
    const calibration=component('CalibrationView');
    const calibrationUpload=calibration.$el.querySelector('input[type="file"]');
    assert(calibrationUpload,'Default microscope must retain image upload');
    assert(!find(calibration.$.subTree,w.CameraPanel),'Default microscope must not require a camera');
    calibration.calibSelectedMicroscope=root.microscopes.find(m=>m.name==='М001');
    await settle();
    const calibrationCamera=find(calibration.$.subTree,w.CameraPanel);
    const cameraColumn=calibrationCamera.$el.closest('[class*="col-md-"]');
    const previewColumn=calibration.$el.querySelector('.img-thumbnail').closest('[class*="col-md-"]');
    assert.notStrictEqual(cameraColumn,previewColumn,'Calibration camera must have its own column beside the image preview');
    assert.strictEqual(cameraColumn.parentElement,previewColumn.parentElement,'Calibration camera and image preview must occupy sibling columns');
    assert(!calibration.$el.querySelector('input[type="file"]'),'Camera mode must show live capture');
    calibration.sourceMode='file';await settle();
    assert(calibration.$el.querySelector('input[type="file"]'),'A camera microscope must also accept an image from disk');
    calibration.sourceMode='camera';await settle();
    calibration.calibSelectedMicroscope=root.microscopes.find(m=>m.name==='М002');await settle();
    assert.strictEqual(find(calibration.$.subTree,w.CameraPanel).microscope.type,'AUTOMATIC','Automatic microscope must retain live calibration capture');
    calibration.calibSelectedMicroscope=root.microscopes.find(m=>m.name==='М001');
    root.currentTab='settings';
    const settings=component('SettingsView');
    await settings.configureMicroscope(root.microscopes.find(m=>m.name==='М001'));
    settings.bindingIndex=2;await settings.bindCamera();await settle();
    root.currentTab='calibration';await settle();
    assert.strictEqual(calibration.calibSelectedMicroscope.camera_index,2);
    root.currentTab='settings';
    await settings.beginAddMicroscope();
    await settings.scanCameras();await settings.selectCamera(settings.cameras[0]);await settle();
    let testPanel=find(settings.$.subTree,w.CameraPanel);
    assert(testPanel,'Discovered cameras must use the continuous preview panel');
    await testPanel.connect();await settle();
    const video=w.document.querySelector('img[alt="Видеопредпросмотр камеры"]');
    assert(video,'Live video must be visible before taking a snapshot');
    const frameBefore=video.src;
    const snapshotButton=[...testPanel.$el.querySelectorAll('button')].find(b=>b.textContent.trim()==='Снимок');
    assert(snapshotButton && !snapshotButton.disabled,'Settings must have a separate snapshot button');
    snapshotButton.click();await settle();
    const snapshot=w.document.querySelector('img[alt="Тестовый снимок"]');
    assert(snapshot,'Snapshot must appear separately from the live image');
    const snapshotBefore=snapshot.src;
    await testPanel.poll(testPanel.generation);await settle();
    assert.notStrictEqual(video.src,frameBefore);
    assert.strictEqual(snapshot.src,snapshotBefore);
    assert.strictEqual(state.files.length,0);
    assert.strictEqual(state.researchRevision,0);
    assert.strictEqual(state.calibrationRevision,0);
    root.currentTab='calibration';await settle();assert.strictEqual(state.owner,null);
    root.currentTab='settings';await settle();
    settings.newName='USB';settings.selectedCamera={index:0,label:'Камера 0'};
    await settings.addMicroscope();await settle();
    assert(root.microscopes.some(m=>m.name==='USB'));
    settings.bindingIndex=2;await settings.bindCamera();await settle();
    assert.strictEqual(root.microscopes.find(m=>m.name==='USB').camera_index,2);
    let panel=find(settings.$.subTree,w.CameraPanel);
    await panel.connect();await settle();
    assert(w.document.body.textContent.includes('Подключено'));
    await panel.capture();await settle();assert(panel.testSnapshot);
    await panel.stop();

    root.currentTab='calibration';
    calibration.calibSelectedMicroscope=root.microscopes.find(m=>m.name==='USB');
    calibration.calibSelectedDivisionPrice=root.divisionPrices[0];calibration.calibName='Scale';
    await settle();panel=find(calibration.$.subTree,w.CameraPanel);
    await panel.connect();await settle();assert.strictEqual(panel.disabled,false);await panel.capture();await settle();
    assert(calibration.calibFileExists['sources.jpg']);
    await calibration.runCalibration();await calibration.saveCalibration();await settle();
    assert.strictEqual(calibration.calibId,1);
    assert(calibration.$el.querySelector('.calibration-detection').textContent.includes('4'));
    assert(calibration.$el.textContent.includes('мкм/пикс'));
    assert(calibration.$el.textContent.includes('Калибровка сохранена'));
    assert(calibration.$el.querySelector('#calibration-coefficient').disabled,'Automatic coefficient must be protected from accidental editing');

    root.currentTab='analyze';const analyze=component('AnalyzeView');
    await analyze.fetchCalibrations();
    analyze.selectedMicroscope=root.microscopes.find(m=>m.name==='USB');
    await analyze.onMicroscopeChange();root.analyzeSelectedCalibration=analyze.calibrations[0];
    await analyze.onCalibrationChange();await settle();
    panel=find(analyze.$.subTree,w.CameraPanel);
    await panel.connect();await settle();assert.strictEqual(panel.disabled,false);await panel.capture();await settle();await panel.capture();await settle();
    assert.strictEqual(analyze.files.length,2);
    assert.strictEqual(analyze.isSaveButtonDisabled,true);
    analyze.name='Experiment';analyze.employee='User';
    await analyze.analyzeAllFiles();await settle();
    assert.strictEqual(analyze.files.length,2);
    assert.strictEqual(root.results.length,1);
    assert.strictEqual(analyze.isSaveButtonDisabled,false);
    await analyze.saveResearch();assert.strictEqual(analyze.researchId,1);
    await component('HomeView').loadResearch(1);await settle();
    assert.strictEqual(root.currentTab,'results');
    assert.strictEqual(root.results[0].area,20);
    assert.strictEqual(analyze.files.length,2);
    assert.strictEqual(state.owner,null);
    await component('HomeView').deleteResearch(1);await settle();
    assert.strictEqual(analyze.researchId,0);
    assert.strictEqual(root.results.length,0);
    assert.strictEqual(analyze.files.length,2);
    await analyze.analyzeAllFiles();await analyze.saveResearch();
    assert.strictEqual(analyze.researchId,1);
    root.currentTab='calibration';await settle();
    const microscopeSelect=calibration.$el.querySelector('#calibration-microscope');
    microscopeSelect.selectedIndex=2;microscopeSelect.dispatchEvent(new w.Event('change'));await settle();
    assert.strictEqual(calibration.calibCoefficient,'','Switching microscope must invalidate the previous scale');
    assert.strictEqual(calibration.isSaveDisabled,true);
    assert.strictEqual(calibration.calibFileExists['sources.jpg'],false);
    assert.deepStrictEqual(errors,[]);
    console.log('DOM flow passed: settings → calibration → capture series → analyze → save → load');
  } catch(error) { console.error(error.stack);for(const item of errors)console.error(String(item));process.exitCode=1; }
  finally { dom.window.close(); }
})();
