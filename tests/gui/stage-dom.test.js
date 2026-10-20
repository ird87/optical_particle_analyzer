// NODE_PATH=<jsdom node_modules> node tests/gui/stage-dom.test.js
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const {JSDOM}=require('jsdom');const dom=new JSDOM('<div id="app"></div>',{runScripts:'outside-only'});const w=dom.window;
const errors=[];w.console.error=(...args)=>errors.push(args.join(' '));w.addEventListener('error',e=>errors.push(e.error));
const state={settings:{mode:'serial',port:'',board:'nano',driver:'a4988',travel_steps:[10000,10000,10000],steps_per_mm:[200,200,200],settle_ms:300,move_timeout_s:90,mechanics_confirmed:false},stage:{connected:false},profiles:[],job:{active:false,status:'idle'}};
let seq=0,stops=0;const events=[];
const profile={id:'p',name:'Шкала Z',simulated:true,points:[{z:100,width:480,height:360,coefficient:40,division_um:10,calibration_id:7}]};
const ok=v=>({ok:true,...v});
const methods={get_stage_state:()=>ok({...state,connected_microscope:'М002'}),
 save_stage_settings:(name,s)=>{state.settings=s;return ok({settings:s});},
 start_stage_job:(name,kind,params)=>{assert.strictEqual(name,'М002');state.job={id:String(++seq),kind,active:true,status:'running',completed:0,total:kind==='scan'?2:0};state.params=params;return ok({job:state.job});},
 stop_stage:()=>{stops++;state.stage.homed=false;state.job={...state.job,active:false,status:'cancelled'};return ok({});},
 get_stage_profile_image:()=>ok({data:'data:image/jpeg;base64,c2NhbGU='}),
};
w.pywebview={api:new Proxy({},{get:(_,name)=>async(...args)=>{assert(methods[name],name);return JSON.parse(JSON.stringify(methods[name](...args)));}})};
for(const file of ['js/vue.global.prod.js','api.js','components/StagePanel.js'])vm.runInContext(fs.readFileSync('gui/'+file,'utf8'),dom.getInternalVMContext());
vm.runInContext(`window.root = Vue.createApp({data:()=>({mode:'settings',active:true,stageBusy:false,divisionPrices:[{name:'10 мкм',value:10}],microscope:{name:'М002',type:'AUTOMATIC'}}),template:'<stage-panel ref="panel" :mode="mode" :active="active" :microscope="microscope" :disabled="stageBusy" @scan-updated="onScan"/>',methods:{onScan(job){window.onScan(job)}}}).component('StagePanel',window.StagePanel).mount('#app')`,dom.getInternalVMContext());
w.onScan=job=>events.push(job);
const tick=async()=>{for(let i=0;i<8;i++){await Promise.resolve();await w.Vue.nextTick();}};
function done(result={}){state.job={...state.job,active:false,status:'done',result};}
function button(label){return [...w.document.querySelectorAll('button')].find(b=>b.textContent.trim()===label);}
(async()=>{try{
 await tick();const root=w.root,p=root.$refs.panel;
 assert(w.document.body.textContent.includes('Arduino Nano'));assert(button('Найти ноль Z → X → Y').disabled);
 p.settings.mode='simulator';await p.saveSettings();await p.start('connect');await tick();assert(root.stageBusy);assert(!button('СТОП').disabled);
 state.stage={connected:true,homed:false,configured:true,board:'nano',mode:'simulator',pos:[0,0,0],limits:[0,0,0]};done();await p.refresh();await tick();
 assert(!root.stageBusy);assert(!button('Найти ноль Z → X → Y').disabled);
 await p.start('home');root.active=false;await tick();assert(stops===1,'Leaving originating tab must stop an active job');
 root.active=true;await tick();await p.start('home');state.stage.homed=true;done();await p.refresh();await tick();
 root.mode='profile';p.profileName='Шкала Z';p.positions='100';p.divisionPrice='10 мкм';await tick();await p.start('profile');
 assert.strictEqual(state.params.positions[0],100);state.profiles=[profile];done({profile});await p.refresh();await tick();assert.strictEqual(p.z,100);
 await p.loadScaleImage();await tick();assert(w.document.querySelector('img[alt="Последний кадр автоматической съёмки или шкала Z"]'));
 root.mode='scan';await tick();p.grid.rows=1;await p.start('scan');assert.strictEqual(state.params.z,100);assert(button('Найти ноль Z → X → Y').disabled);
 state.job.completed=2;done({calibration_id:7,revision:2});await p.refresh();await tick();assert.strictEqual(events.length,1);assert.strictEqual(events[0].result.calibration_id,7);assert(!root.stageBusy);
 assert.deepStrictEqual(errors,[]);console.log('Stage DOM passed: settings → connect → STOP on leave → home → Z profile → scan');
}finally{const instance=w.document.getElementById('app')._vnode?.appContext.app;if(instance)instance.unmount();w.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
