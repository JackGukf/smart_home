"""Cloud outages must not delay local dashboard rendering."""
import json
import shutil
import subprocess
from pathlib import Path
import pytest
from src.python.status_overview import connectivity_states


def test_connectivity_distinguishes_unreachable_and_auth_response():
    def runner(args):
        return "204" if "gstatic" in args[-1] else "401" if "govee" in args[-1] else "000"
    internet, govee, weather = connectivity_states(runner)
    assert internet["ok"] and govee["ok"] and not weather["ok"]
    assert "API health not checked" in govee["detail"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node required")
def test_local_renders_while_cloud_hangs_and_recovers(tmp_path):
    source = Path("src/python/web_static/app.js").resolve()
    harness = r"""
const fs = require('fs');
const source = fs.readFileSync(process.argv[2], 'utf8');
const start = source.indexOf('let dashboardRefreshInFlight');
const end = source.indexOf('/* ═════════════════ HOME', start);
let latestSwitchDevices=[],latestCameras=[],latestTuyaDevices=[],latestMatterDevices=[],latestThermostats=[],latestCameraPaths=[],latestAlarmData=null,areasDoc={};
const statusDot={classList:{add(){},toggle(){}}},apiStatus={};
let paint=0, weather=17, failures=true;
function renderDevices(){paint++;}
function renderWeather(data){weather=data.temperature;}
function noop(){}
const applyPendingCommands=noop,renderHomeView=noop,refreshActiveDynamicGroupPanel=noop,notifyDoorbellEvents=noop,renderCameras=noop,updatePathWatch=noop,updateMotionWatch=noop,renderTuyaDevices=noop,renderThermostats=noop,notifySeenNewHomeAssistantDevices=noop,renderHomeAssistant=noop,renderAlarmSection=noop,_updateMatterServerStatus=noop,_renderMatterDeviceList=noop;
const cacheSnapshotsInBackground=()=>Promise.resolve();
let releaseCloud;
function requestJson(url){
 if(url==='/api/weather') return failures ? new Promise(r=>releaseCloud=r) : Promise.resolve({temperature:20});
 return Promise.resolve({devices:[{id:'local'}],cameras:[],entities:[],thermostats:[]});
}
eval(source.slice(start,end)+`
(async()=>{
 const refresh=loadDevices();
 await new Promise(r=>setTimeout(r,20));
 if(!paint || latestSwitchDevices.length!==1) throw Error('Local blocked by cloud');
 releaseCloud({status:'error'}); await refresh;
 if(weather!==17 || !apiStatus.textContent.includes('last readings')) throw Error('Failed cloud erased readings');
 failures=false;await loadDevices();
 if(weather!==20 || apiStatus.textContent!=='Online') throw Error('Recovery failed');
 console.log('OFFLINE_TEST_OK');
})().catch(e=>{console.error(e);process.exitCode=1;});`);
"""
    script=tmp_path/'offline.js';script.write_text(harness)
    result=subprocess.run(['node',str(script),str(source)],capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr
    assert 'OFFLINE_TEST_OK' in result.stdout

@pytest.mark.skipif(shutil.which("node") is None, reason="node required")
def test_failed_live_sensor_does_not_block_other_sensor(tmp_path):
    source = Path("src/python/web_static/app.js").resolve()
    harness = r"""
const fs = require('fs');
const source = fs.readFileSync(process.argv[2], 'utf8');
const start = source.indexOf('async function refreshLiveHomeAssistantCards(entityIds) {');
const end = source.indexOf('\nfunction scheduleLiveRefresh(event) {', start);
let latestTuyaDevices = [{id:'sensor.failed', value:11}];
let rendered = 0;
const renderTuyaDevices = () => rendered++;
const renderDevicesOverview = () => {}, renderHomeView = () => {}, refreshActiveDynamicGroupPanel = () => {};
const apiStatus = {textContent:'Some data unavailable'};
const statusDot = {classList:{add(){throw Error('Live sensor changed local connection status')}}};
function requestJson(url) {
  return url.includes('sensor.failed')
    ? Promise.reject(Error('sensor unavailable'))
    : Promise.resolve({card:{id:'sensor.healthy',value:42}});
}
eval(source.slice(start,end)+`
(async()=>{
 await refreshLiveHomeAssistantCards(['sensor.failed','sensor.healthy']);
 if(latestTuyaDevices.find(x=>x.id==='sensor.failed')?.value!==11) throw Error('Old failed sensor reading lost');
 if(latestTuyaDevices.find(x=>x.id==='sensor.healthy')?.value!==42) throw Error('Healthy sensor not refreshed');
 if(rendered!==1 || apiStatus.textContent!=='Some data unavailable') throw Error('Incorrect render or connection status');
 console.log('LIVE_SENSOR_TEST_OK');
})().catch(e=>{console.error(e);process.exitCode=1;});`);
"""
    script = tmp_path / "live_sensor.js"
    script.write_text(harness)
    result = subprocess.run(["node", str(script), str(source)], capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert "LIVE_SENSOR_TEST_OK" in result.stdout
