const test = require('node:test');
const assert = require('node:assert/strict');
const exits = require('../src/visualization/exit-geometry.js');
const room = {width:8,height:8};

test('clicking the default exit resizes it to 3 m without adding another exit', () => {
  const original=[{side:'right',center:4,width:1.2}];
  const result=exits.place(room,original,'right',4,3);
  assert.deepEqual(result.exits,[{side:'right',center:4,width:3}]);
  assert.equal(original[0].width,1.2);
  assert.equal(result.index,0);
});

test('new exit near a corner slides inside an 8 m wall', () => {
  for(const side of ['left','right','top','bottom']){
    const low=exits.place(room,[],side,.2,3).exit;
    const high=exits.place(room,[],side,7.9,3).exit;
    assert.equal(low.center,1.5);assert.equal(high.center,6.5);
    assert.doesNotThrow(()=>exits.validate(room,[low,high]));
  }
});

test('full-wall exit uses the wall center and wider-than-wall exit fails', () => {
  assert.deepEqual(exits.place(room,[],'right',1,8).exit,{side:'right',center:4,width:8});
  assert.throws(()=>exits.place(room,[],'right',4,9),/cannot fit the 8 m right wall/);
});

test('other exits are preserved and true overlap is rejected without mutation', () => {
  const original=[{side:'right',center:2,width:2},{side:'right',center:6,width:2}];
  assert.throws(()=>exits.update(room,original,0,{side:'right',center:4,width:3}),/overlaps exit/);
  assert.deepEqual(original,[{side:'right',center:2,width:2},{side:'right',center:6,width:2}]);
  assert.equal(exits.place(room,original,'left',4,3).exits.length,3);
});

test('rectangular rooms use the chosen wall length and touching exits are legal', () => {
  assert.throws(()=>exits.place({width:8,height:4},[],'right',2,5),/4 m right wall/);
  assert.equal(exits.place({width:8,height:4},[],'top',4,5).exit.width,5);
  assert.doesNotThrow(()=>exits.validate(room,[{side:'top',center:2,width:4},{side:'top',center:6,width:4}]));
});

test('numeric invalid extents and nonfinite values fail with actionable messages', () => {
  assert.throws(()=>exits.validate(room,[{side:'right',center:7,width:3}]),/spans 5.50–8.50 m/);
  assert.throws(()=>exits.place(room,[],'right',4,NaN),/positive/);
});
