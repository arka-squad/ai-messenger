import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { EN, FR } from './index.ts';

describe('le dictionnaire bilingue', () => {
  it('a exactement les mêmes clés en français et en anglais', () => {
    assert.deepEqual(Object.keys(EN).sort(), Object.keys(FR).sort());
  });

  it('ne laisse aucune valeur vide', () => {
    for (const cle of Object.keys(FR)) {
      assert.notEqual(FR[cle as keyof typeof FR].trim(), '', `clé FR vide : ${cle}`);
      assert.notEqual(EN[cle as keyof typeof FR].trim(), '', `clé EN vide : ${cle}`);
    }
  });
});
