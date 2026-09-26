const assert = require('node:assert/strict');
const { test } = require('node:test');
const catalog = require('../AppCatalog.js');

const apps = [
  { id: 'org.example.Editor', name: 'Code Editor', execString: '/usr/bin/editor' },
  { id: 'cloud.lazycat.todo', name: '懒猫清单', execString: '/usr/bin/todo' },
  { id: 'org.example.Hidden', name: 'Hidden App', execString: '/bin/hidden', noDisplay: true },
];

test('filters apps by name, id, and multiple words', () => {
  assert.equal(catalog.filtered(apps, 'code')[0].entry.id, 'org.example.Editor');
  assert.equal(catalog.filtered(apps, 'example editor')[0].entry.id, 'org.example.Editor');
  assert.equal(catalog.filtered(apps, '懒猫')[0].entry.id, 'cloud.lazycat.todo');
});

test('does not offer hidden desktop entries', () => {
  assert.equal(catalog.filtered(apps, 'hidden').length, 0);
});
