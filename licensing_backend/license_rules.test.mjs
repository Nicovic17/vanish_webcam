import {readFileSync} from 'node:fs';
import {after, before, beforeEach, test} from 'node:test';
import assert from 'node:assert/strict';
import {initializeTestEnvironment, assertFails, assertSucceeds} from '@firebase/rules-unit-testing';
import {doc, getDoc, getDocs, collection, setDoc, deleteDoc, writeBatch,
        serverTimestamp, Timestamp} from 'firebase/firestore';

let env;
const email = 'cliente@example.com';
const hashA = 'a'.repeat(64), hashB = 'b'.repeat(64);
const sessionA = '1'.repeat(64), sessionB = '2'.repeat(64);
const ref = (db, collectionName) => doc(db, collectionName, email);
const sessionData = (uid='pc-a', deviceId=hashA, sessionId=sessionA, extra={}) => ({
  uid, deviceId, sessionId, mode:'full', released:false, lastSeenAt:serverTimestamp(), ...extra,
});
function bindAndAcquire(db, uid='pc-a', deviceId=hashA, sessionId=sessionA) {
  const batch = writeBatch(db);
  batch.set(ref(db,'licenseBindings'), {uid,deviceId,createdAt:serverTimestamp()});
  batch.set(ref(db,'licenseSessions'), sessionData(uid,deviceId,sessionId));
  return batch.commit();
}
async function owner(work) { return env.withSecurityRulesDisabled(context=>work(context.firestore())); }
before(async()=>{
  env = await initializeTestEnvironment({projectId:'demo-vanishcam-licenses',
    firestore:{host:'127.0.0.1',port:8089,rules:readFileSync(new URL('./firestore.rules',import.meta.url),'utf8')}});
});
beforeEach(async()=>{
  await env.clearFirestore();
  await owner(db=>setDoc(ref(db,'licenses'),{email,active:true}));
});
after(async()=>{ await env?.cleanup(); });
const pcA=()=>env.authenticatedContext('pc-a',{firebase:{sign_in_provider:'anonymous'}}).firestore();
const pcB=()=>env.authenticatedContext('pc-b',{firebase:{sign_in_provider:'anonymous'}}).firestore();

test('only the owner can create or activate licenses; lists and unauthenticated reads denied',async()=>{
  const db=pcA();
  await assertSucceeds(getDoc(ref(db,'licenses')));
  await assertFails(setDoc(ref(db,'licenses'),{email,active:true}));
  await assertFails(deleteDoc(ref(db,'licenses')));
  await assertFails(getDocs(collection(db,'licenses')));
  await assertFails(getDoc(ref(env.unauthenticatedContext().firestore(),'licenses')));
});
test('inactive or missing email cannot bind or start',async()=>{
  await owner(db=>setDoc(ref(db,'licenses'),{email,active:false}));
  await assertFails(bindAndAcquire(pcA()));
  await owner(db=>deleteDoc(ref(db,'licenses')));
  await assertFails(bindAndAcquire(pcA()));
});
test('first device binding and session are accepted atomically',async()=>{
  const db=pcA();
  await assertSucceeds(bindAndAcquire(db));
  assert.equal((await getDoc(ref(db,'licenseBindings'))).data().uid,'pc-a');
});
test('racing PCs cannot both acquire the first binding',async()=>{
  const results=await Promise.allSettled([bindAndAcquire(pcA()),bindAndAcquire(pcB(),'pc-b',hashB,sessionB)]);
  assert.equal(results.filter(r=>r.status==='fulfilled').length,1);
});
test('another UID cannot claim a bound device even with the copied device hash',async()=>{
  await bindAndAcquire(pcA());
  await assertFails(setDoc(ref(pcB(),'licenseSessions'),sessionData('pc-b',hashA,sessionB)));
  await assertFails(setDoc(ref(pcB(),'licenseBindings'),{uid:'pc-b',deviceId:hashA,createdAt:serverTimestamp()}));
});
test('two editions on the same PC cannot have different active sessions',async()=>{
  const db=pcA(); await bindAndAcquire(db);
  await assertFails(setDoc(ref(db,'licenseSessions'),sessionData('pc-a',hashA,sessionB)));
});
test('heartbeat accepts only current device, session and server timestamp',async()=>{
  const db=pcA(); await bindAndAcquire(db);
  await assertSucceeds(setDoc(ref(db,'licenseSessions'),sessionData()));
  await assertFails(setDoc(ref(db,'licenseSessions'),sessionData('pc-a',hashB)));
  await assertFails(setDoc(ref(db,'licenseSessions'),sessionData('pc-a',hashA,sessionA,{lastSeenAt:Timestamp.fromMillis(Date.now()+3600000)})));
  await assertFails(setDoc(ref(db,'licenseSessions'),sessionData('pc-a',hashA,sessionA,{active:true})));
});
test('normal close frees session immediately; stale process cannot release the new one',async()=>{
  const db=pcA(); await bindAndAcquire(db);
  await assertSucceeds(setDoc(ref(db,'licenseSessions'),sessionData('pc-a',hashA,sessionA,{released:true})));
  await assertSucceeds(setDoc(ref(db,'licenseSessions'),sessionData('pc-a',hashA,sessionB)));
  await assertFails(setDoc(ref(db,'licenseSessions'),sessionData('pc-a',hashA,sessionA,{released:true})));
});
test('crashed session can be replaced only after the server-side lease expires',async()=>{
  const db=pcA(); await bindAndAcquire(db);
  await owner(admin=>setDoc(ref(admin,'licenseSessions'),sessionData('pc-a',hashA,sessionA,{lastSeenAt:Timestamp.fromMillis(Date.now()-130000)})));
  await assertSucceeds(setDoc(ref(db,'licenseSessions'),sessionData('pc-a',hashA,sessionB)));
});
test('manual deactivation denies renewals and fresh acquisitions',async()=>{
  const db=pcA(); await bindAndAcquire(db);
  await owner(admin=>setDoc(ref(admin,'licenses'),{email,active:false}));
  await assertFails(setDoc(ref(db,'licenseSessions'),sessionData()));
  await assertFails(setDoc(ref(db,'licenseSessions'),sessionData('pc-a',hashA,sessionB)));
});
test('unknown modes cannot renew a licensed session',async()=>{
  const db=pcA(); await bindAndAcquire(db);
  await assertFails(setDoc(ref(db,'licenseSessions'),sessionData('pc-a',hashA,sessionA,{mode:'unknown-effect'})));
});
test('Itachi mode can renew only the same licensed session',async()=>{
  const db=pcA(); await bindAndAcquire(db);
  await assertSucceeds(setDoc(ref(db,'licenseSessions'),sessionData('pc-a',hashA,sessionA,{mode:'itachi'})));
  await assertFails(setDoc(ref(db,'licenseSessions'),sessionData('pc-a',hashA,sessionB,{mode:'itachi'})));
});
test('device reset waits out the old lease and old UID cannot renew after transfer',async()=>{
  const a=pcA(),b=pcB(); await bindAndAcquire(a);
  await owner(admin=>deleteDoc(ref(admin,'licenseBindings')));
  await assertFails(setDoc(ref(a,'licenseSessions'),sessionData()));
  await assertFails(bindAndAcquire(b,'pc-b',hashB,sessionB));
  await owner(admin=>setDoc(ref(admin,'licenseSessions'),sessionData('pc-a',hashA,sessionA,{lastSeenAt:Timestamp.fromMillis(Date.now()-130000)})));
  await assertSucceeds(bindAndAcquire(b,'pc-b',hashB,sessionB));
  await assertFails(setDoc(ref(a,'licenseSessions'),sessionData()));
});
test('clients cannot delete binding or session, enumerate devices, or write unknown collections',async()=>{
  const db=pcA(); await bindAndAcquire(db);
  await assertFails(deleteDoc(ref(db,'licenseBindings')));
  await assertFails(deleteDoc(ref(db,'licenseSessions')));
  await assertFails(getDocs(collection(db,'licenseSessions')));
  await assertFails(setDoc(doc(db,'admin','settings'),{active:true}));
});
