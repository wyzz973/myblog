import { describe, it, expect } from 'vitest';
import { stripFrontmatter, mdToPlain, countWords, readingMinutes } from './wordCount.js';

describe('wordCount.stripFrontmatter', () => {
  it('drops the leading --- block', () => {
    const md = '---\nid: x\nn: "001"\n---\n\nhello world';
    expect(stripFrontmatter(md)).toBe('\nhello world');
  });
  it('returns input unchanged when no frontmatter', () => {
    expect(stripFrontmatter('hello')).toBe('hello');
  });
  it('handles non-string input', () => {
    expect(stripFrontmatter(null)).toBe('');
  });
});

describe('wordCount.mdToPlain', () => {
  it('drops fence markers but keeps inner text', () => {
    expect(mdToPlain('```js\nlet x = 1;\n```')).toMatch(/let x = 1;/);
  });
  it('keeps link / image text without the URL', () => {
    expect(mdToPlain('see [here](https://example.com)').trim()).toBe('see here');
    expect(mdToPlain('![alt text](u.png)').trim()).toBe('alt text');
  });
  it('strips emphasis wrappers', () => {
    expect(mdToPlain('**bold** _italic_ `code`').trim()).toBe('bold italic code');
  });
  it('drops list bullets', () => {
    expect(mdToPlain('- one\n- two').trim()).toBe('one\ntwo');
  });
});

describe('wordCount.countWords', () => {
  it('counts ASCII words', () => {
    expect(countWords('hello world from vitest')).toBe(4);
  });
  it('counts each CJK char as 1', () => {
    expect(countWords('你好世界')).toBe(4);
  });
  it('mixes ASCII + CJK', () => {
    expect(countWords('hello 世界')).toBe(3); // hello + 世 + 界
  });
  it('strips frontmatter before counting', () => {
    const md = '---\nid: x\n---\n\nhello world';
    expect(countWords(md)).toBe(2);
  });
  it('returns 0 for empty', () => {
    expect(countWords('')).toBe(0);
    expect(countWords(null)).toBe(0);
  });
});

describe('wordCount.readingMinutes', () => {
  it('floors at 1', () => {
    expect(readingMinutes(0)).toBe(1);
    expect(readingMinutes(1)).toBe(1);
    expect(readingMinutes(239)).toBe(1);
  });
  it('uses 240 wpm cutoff', () => {
    expect(readingMinutes(240)).toBe(1);
    expect(readingMinutes(241)).toBe(2);
    expect(readingMinutes(480)).toBe(2);
    expect(readingMinutes(481)).toBe(3);
  });
});
