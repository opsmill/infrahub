import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {join} from 'node:path';
const sourceSha = '4391f3da665fdf50b6810c1a66712fb9ba21aa93';
const sourceDir = process.env.STALE_SOURCE_DIR;
assert.ok(sourceDir, 'Set STALE_SOURCE_DIR to an isolated directory containing the pinned source files');
const expectedSources = {
  'infrahub-stale-processor.ts': '9545917e652b88e06a64c8c9c10645b25cba5659a91901ef5981a2a227c920d1',
  'infrahub-stale-date.ts': 'f4bbd5da44a0ecf45795729181436c17bc16ded2d991706397f892d7c05d1070',
  'infrahub-stale-state.ts': '3c5f33059183508162d0b6a67b8edae37dfa953d3fad5883c8f4c4965fc52cdb',
};
console.log(`Verifying actions/stale source at ${sourceSha}`);
for (const [file, hash] of Object.entries(expectedSources)) {
  assert.equal(createHash('sha256').update(readFileSync(join(sourceDir, file))).digest('hex'), hash, file);
}

import {stripTypeScriptTypes} from 'node:module';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source = readFileSync(join(sourceDir, 'infrahub-stale-processor.ts'), 'utf8').replace(/^import .*?;\n/gms, '').replace('export class IssuesProcessor', 'class IssuesProcessor');
const dates = readFileSync(join(sourceDir, 'infrahub-stale-date.ts'), 'utf8').replaceAll('export function', 'function');
const logger = new Proxy({}, {get: () => (...args) => args[0]});
const sandbox = {
  Logger: class { info() {} warning() {} },
  IssueLogger: class { info() {} createOptionLink() {} },
  LoggerService: logger,
  Option: {},
  isBoolean: value => typeof value === "boolean",
  cleanLabel: value => value.trim().toLowerCase(),
};
vm.createContext(sandbox);
vm.runInContext(stripTypeScriptTypes(dates + '\n' + source + '\nglobalThis.Processor = IssuesProcessor;'), sandbox);
const P = sandbox.Processor;
const daysAgo = n => new Date(Date.now() - n * 86400000).toISOString();
let passed = 0;
function check(name, actual, expected) { assert.equal(actual, expected, name); console.log('PASS ' + name); passed++; }
check('61-day inactive PR exceeds 60-day threshold', P._updatedSince(daysAgo(61),60), false);
check('weekly bot comment prevents 60-day stale threshold', P._updatedSince(daysAgo(6),60), true);
async function run({bot=false,human=false,remove=true,updated=15,events='label',fresh=false,closeDays=14,gateDays=15}={}) {
  const p = Object.create(P.prototype);
  p.options = {daysBeforePrClose:closeDays,removeStaleWhenUpdated:remove};
  p.getLabelCreationDate = async () => ({creationDate:daysAgo(gateDays), events: events === 'label' ? [{event:'labeled',label:{name:'stale'},created_at:daysAgo(15)}] : [{event:'commented',created_at:daysAgo(updated)}]});
  p.listIssueComments = async () => human ? [{user:{type:'User'},body:'Still working'}] : bot ? [{user:{type:'Bot'},body:'Reminder'}] : [];
  let outcome = 'open';
  p._removeStaleLabel = async () => { outcome='unstaled'; };
  p._removeLabelsOnStatusTransition = async () => {};
  p._addLabelsWhenUnstale = async () => {};
  p._closeIssue = async () => { outcome='closed'; };
  await p._processStaleIssue({isPullRequest:true, updated_at:daysAgo(updated), markedStaleThisRun:fresh}, 'stale','Initial warning',[],[],[]);
  return outcome;
}
check('no updates after warning allows closure',await run(), 'closed');
check('bot reminder blocks closure even if only label events are returned',await run({bot:true,updated:1}), 'open');
check('bot reminder with an additional event removes stale label',await run({bot:true,updated:1,events:'comment'}), 'unstaled');
check('disabling stale removal still lets bot reminder postpone closure',await run({bot:true,updated:1,remove:false}), 'open');
check('human comment cancels warning',await run({human:true,updated:1}), 'unstaled');
check('commit/update with non-label event cancels warning',await run({updated:1,events:'comment'}), 'unstaled');
check('freshly marked timestamp prevents same-run closure',await run({fresh:true,updated:0}), 'open');
console.log(`${passed} assertions passed against pinned upstream method bodies; API responses are fixtures, no GitHub writes.`);
const stateSource = readFileSync(join(sourceDir, 'infrahub-stale-state.ts'),'utf8').replace(/^import .*?;\n/gms,'').replaceAll('export ', '');
sandbox.core = {debug(){},info(){},warning(){}};
sandbox.wordsToList = () => [];
sandbox.IssueLogger.prototype.grouping = async (label, fn) => fn();
vm.runInContext(stripTypeScriptTypes(stateSource+'\nglobalThis.State=State;'),sandbox);
let saved='';
const storage={save:async value=>{saved=value;},restore:async()=>saved};
async function scan(storage,budget=2){
 const state=new sandbox.State(storage,{debugOnly:false});await state.restore();
 const p=Object.create(P.prototype);let remaining=budget;const processed=[];
 p.options={};p.state=state;p._logger={info(){},warning(){},createOptionLink(){}};
 p.operations={hasRemainingOperations:()=>remaining>0,getRemainingOperationsCount:()=>remaining};
 p.getIssues=async page=>page===1?[1,2,3,4,5].map(number=>({number})):[];
 p.processIssue=async issue=>{remaining--;processed.push(issue.number);};
 await p.processIssues();await state.persist();return processed.join(',');
}
check('low-budget first scan persists progress',await scan(storage),'1,2');
check('second scan advances to previously unprocessed items',await scan(storage),'3,4');
check('third scan reaches tail',await scan(storage),'5');
check('complete scan resets saved state',saved,'');
check('lost cache with sufficient budget covers all items',await scan(storage,6),'1,2,3,4,5');
saved='1|2';
const brokenStorage={restore:async()=>saved,save:async()=>{}};
check('failed cache replacement processes same slice first time',await scan(brokenStorage),'3,4');
check('failed cache replacement processes same slice again',await scan(brokenStorage),'3,4');
console.log(`${passed} total fixture assertions passed. Cache service/token permissions remain unverified locally.`);

check('fresh gate allows stock zero-day closure after bot reminder',await run({closeDays:0,gateDays:0,updated:0.0001,bot:true,remove:false}), 'closed');
check('human comment after gate prevents stock closure',await run({closeDays:0,gateDays:0,updated:0.0001,human:true,remove:false}), 'open');
check('arbitrary recent update does not stop zero-day closer',await run({closeDays:0,gateDays:0,updated:0.000001,remove:false}), 'closed');
check('future updated timestamp defers closure',await run({closeDays:0,gateDays:0,updated:-0.001,remove:false}), 'open');
console.log(`${passed} assertions passed including gate integration`);
sandbox.wordsToList = value => (value || '').split(',').map(s=>s.trim()).filter(Boolean);
sandbox.isLabeled = (issue,label) => issue.labels.includes(label);
sandbox.shouldMarkWhenStale = days => days >= 0;
sandbox.Milestones = class {shouldExemptMilestones(){return false}};
sandbox.Assignees = class {shouldExemptAssignees(){return false}};
sandbox.ExemptDraftPullRequest = class {async shouldExemptDraftPullRequest(){return false}};
async function processGate({labels=['gate-123-1'], human=false, cached=false}={}) {
 const p=Object.create(P.prototype);
 p.options=new Proxy({daysBeforePrStale:-1, daysBeforePrClose:0, stalePrLabel:'gate-123-1', onlyPrLabels:'gate-123-1', exemptPrLabels:'keep-open', removeStaleWhenUpdated:false},{get:(obj,k)=>obj[k]??''});
 p.getLabelCreationDate=async()=>({creationDate:daysAgo(0.0001),events:[]});
 p.listIssueComments=async()=>human?[{user:{type:'User'},body:'Human activity'}]:[];
 let outcome='open';p._closeIssue=async()=>{outcome='closed'};
 const issue={number:7,isPullRequest:true,isStale:labels.includes('gate-123-1'),state:'open',labels,assignees:[],updated_at:daysAgo(0.0001), operations:{getConsumedOperationsCount:()=>0}};
 p.getIssues=async page=>page===1?[issue]:[];
 p._logger={info(){},warning(){},createOptionLink(){}};
 p.operations={hasRemainingOperations:()=>true,getRemainingOperationsCount:()=>100};
 p.state={isIssueProcessed:()=>cached,addIssueToProcessed(){},reset(){}};
 await p.processIssues();return outcome;
}
check('full processor closes a currently gated PR',await processGate(),'closed');
check('full processor excludes legacy stale-only PR',await processGate({labels:['stale']}),'open');
check('full processor excludes prior-attempt gate',await processGate({labels:['gate-123-0']}),'open');
check('full processor keep-open label prevents closure',await processGate({labels:['gate-123-1','keep-open']}),'open');
check('full processor human comment since gate vetoes closure',await processGate({human:true}),'open');
check('full processor cached ID skips newly eligible gate',await processGate({cached:true}),'open');
console.log(`${passed} assertions passed including full processor gating`);

async function shiftingScan({count, cached='', budget=1000, failClose=false}) {
  let persisted=cached;
  const cache={restore:async()=>persisted,save:async value=>{persisted=value}};
  const open=new Set(Array.from({length:count},(_,i)=>i+1));
  const passes=[];
  for(let pass=1;pass<=3 && open.size;pass++) {
    const state=new sandbox.State(cache,{debugOnly:false});await state.restore();
    const p=Object.create(P.prototype);let remaining=budget;
    p.options={};p.state=state;p.closedIssues=[];
    p._logger={info(){},warning(){},createOptionLink(){}};
    p.operations={hasRemainingOperations:()=>remaining>0,getRemainingOperationsCount:()=>remaining};
    p.getIssues=async page=>Array.from(open).slice((page-1)*100,page*100).map(number=>({number}));
    p._consumeIssueOperation=()=>{remaining--};
    p.client={rest:{issues:{update:async({issue_number})=>{
      if(failClose) throw Error('fixture denied');
      open.delete(issue_number);
    }}}};
    p.processIssue=async issue=>p._closeIssue(issue);
    await p.processIssues();await state.persist();
    passes.push({attempted:p.closedIssues.length,remaining:open.size});
  }
  return {passes,remaining:open.size};
}
sandbox.context={repo:{owner:'fixture',repo:'fixture'}};
sandbox.IssueLogger.prototype.error=()=>{};
for(const count of [116,574]) {
  const result=await shiftingScan({count});
  check(`mutable pagination covers ${count} candidates within three passes`, result.remaining,0);
  check(`mutable pagination ${count} needs continuation`,result.passes.length>1,true);
}
check('interrupted state containing newly due IDs requires fresh sweep',
  (await shiftingScan({count:116,cached:Array.from({length:116},(_,i)=>i+1).join('|')})).remaining,0);
check('expired cache restarts safely from full inventory',
  (await shiftingScan({count:116,cached:''})).remaining,0);
const failedClose=await shiftingScan({count:1,failClose:true});
check('upstream reports attempted close despite swallowed API failure',failedClose.passes[0].attempted,1);
check('independent candidate read detects swallowed close failure',failedClose.remaining,1);
console.log(`${passed} assertions passed; processor pagination, cache loss, and close failure use pinned upstream bodies.`);
