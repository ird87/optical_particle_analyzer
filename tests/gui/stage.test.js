const fs=require('fs');const vm=require('vm');const assert=require('assert');
const calls=[];let stopped=0;let job={id:'j1',kind:'scan',active:true,status:'running',completed:0,total:2};
const profile={id:'p',name:'Scale',points:[{z:100,width:480,height:360,coefficient:40,division_um:10,calibration_id:1}]};
const context={window:{},setTimeout:()=>1,clearTimeout:()=>{},api:{
 getStageState:async()=>({ok:true,settings:{mode:'simulator',board:'nano',driver:'a4988',travel_steps:[10000,10000,10000],steps_per_mm:[200,200,200]},stage:{connected:true,homed:true,pos:[0,0,0]},connected_microscope:'М002',profiles:[profile],job:JSON.parse(JSON.stringify(job))}),
 startStageJob:async(...args)=>{calls.push(args);return {ok:true,job};},
 stopStage:async()=>{stopped++;return {ok:true};},
}};
vm.runInNewContext(fs.readFileSync('gui/components/StagePanel.js','utf8'),context);
const def=context.window.StagePanel;
function component(){const c={...def.data(),microscope:{name:'М002',type:'AUTOMATIC'},active:true,mode:'scan',disabled:false,$root:{stageBusy:false,divisionPrices:[{name:'10 мкм',value:10}]},$emit:(...v)=>calls.push(v)};
 for(const [key,fn] of Object.entries(def.methods))c[key]=fn.bind(c);
 for(const [key,fn] of Object.entries(def.computed))Object.defineProperty(c,key,{get:()=>fn.call(c)});
 return c;}
(async()=>{
 const c=component();await c.refresh();assert.strictEqual(c.settings.board,'nano');assert(c.$root.stageBusy);
 c.profileId='p';c.z=100;c.grid={x:0,y:0,columns:2,rows:1,dx:1000,dy:1000};
 assert(c.fieldOfView.includes('120'));
 c.job.active=false;c.$root.stageBusy=false;await c.start('scan');assert.strictEqual(calls[0][1],'scan');assert.strictEqual(calls[0][2].z,100);
 assert(c.$root.stageBusy);await c.stop();assert.strictEqual(stopped,1);
 job={id:'j1',kind:'scan',active:false,status:'cancelled',completed:1,total:2,calibration_id:1,revision:1};
 await c.refresh();assert(!c.$root.stageBusy);assert(calls.some(v=>v[0]==='scan-updated'));
 const oldCount=calls.length;await c.refresh();assert.strictEqual(calls.length,oldCount,'Completion event only once');
 c.active=false;await c.start('home');assert.strictEqual(calls.length,oldCount,'Hidden panel cannot start motion');
 console.log('stage GUI tests passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
