// Run through Vite at /tests/game-artwork.html. Uses only self-authored images.
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import GameArtwork from '../src/GameArtwork';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const host = document.getElementById('artwork');
const output = document.getElementById('results');
const root = createRoot(host);
const image = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="460" height="215"><rect width="460" height="215" fill="purple"/></svg>');
const game = { source: 'self-authored-browser-test', slug: 'one', title: 'Same title', imageUrl: image };
const results = [];
function assert(condition, message) {
  if (!condition) throw new Error(message);
}
async function render(value) {
  await act(async () => root.render(<GameArtwork game={value} />));
}
async function test(name, body) {
  await body();
  results.push(name);
  output.textContent = results.map(name => `PASS ${name}`).join('\n');
}
async function run() {
  try {
    await test('real component decodes a self-authored image with accessible, deferred loading', async () => {
      await render(game);
      const img = host.querySelector('img');
      await img.decode();
      assert(img.naturalWidth === 460, 'image did not decode');
      assert(img.alt === 'Cover artwork for Same title', 'missing title-specific alt text');
      assert(img.loading === 'lazy' && img.decoding === 'async', 'loading must stay deferred');
      assert(img.referrerPolicy === 'no-referrer', 'artwork must not send a referrer');
      assert(img.width === 460 && img.height === 215, 'image dimensions must reserve layout space');
    });
    await test('an image error shows a titled accessible placeholder', async () => {
      await act(async () => host.querySelector('img').dispatchEvent(new Event('error')));
      assert(!host.querySelector('img'), 'failed image still rendered');
      assert(host.querySelector('[role="img"]').getAttribute('aria-label') === 'Artwork unavailable for Same title', 'missing fallback label');
      assert(host.textContent.includes('Same title') && host.textContent.includes('Artwork unavailable'), 'missing visible fallback');
    });
    await test('rerendering the same failed identity does not loop retries', async () => {
      await render({ ...game });
      assert(!host.querySelector('img'), 'same failed image was retried');
    });
    await test('another game with the same title resets the failure', async () => {
      await render({ ...game, slug: 'two' });
      assert(host.querySelector('img'), 'failure leaked across game IDs');
    });
    await test('a changed URL for the same game resets the failure', async () => {
      await act(async () => host.querySelector('img').dispatchEvent(new Event('error')));
      await render({ ...game, slug: 'two', imageUrl: image + '#new' });
      assert(host.querySelector('img'), 'updated image URL was not retried');
    });
    await test('missing artwork uses a placeholder without an image request', async () => {
      await render({ ...game, imageUrl: null });
      assert(!host.querySelector('img'), 'missing artwork created an image');
      assert(host.querySelector('[role="img"]'), 'missing placeholder');
    });
    const fallbackGame = { ...game, imageFallbackUrl: image + '#capsule' };
    await test('a failed header tries the same-game fallback once', async () => {
      await render(fallbackGame);
      await act(async () => host.querySelector('img').dispatchEvent(new Event('error')));
      const img = host.querySelector('img');
      assert(img?.getAttribute('src') === fallbackGame.imageFallbackUrl, 'fallback was not attempted');
      await img.decode();
      assert(img.naturalWidth === 460 && img.alt === 'Cover artwork for Same title', 'fallback did not decode with the same title');
    });
    await test('failure of both candidates ends in a placeholder without a retry loop', async () => {
      await act(async () => host.querySelector('img').dispatchEvent(new Event('error')));
      assert(!host.querySelector('img'), 'exhausted fallback still rendered an image');
      await render({ ...fallbackGame });
      assert(!host.querySelector('img'), 'exhausted candidates retried on rerender');
    });
    await test('a changed fallback URL resets an exhausted game', async () => {
      await render({ ...fallbackGame, imageFallbackUrl: image + '#updated-capsule' });
      assert(host.querySelector('img'), 'updated fallback did not reset the failure');
    });
    await test('identical candidate URLs are attempted only once', async () => {
      await render({ ...game, imageFallbackUrl: image });
      await act(async () => host.querySelector('img').dispatchEvent(new Event('error')));
      assert(!host.querySelector('img'), 'duplicate URL was retried');
    });
    document.documentElement.dataset.testStatus = 'passed';
  } catch (error) {
    output.textContent += '\nFAIL ' + error.message;
    document.documentElement.dataset.testStatus = 'failed';
    throw error;
  } finally {
    await act(async () => root.unmount());
  }
}
run();
