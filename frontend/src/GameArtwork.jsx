import React, { useState } from 'react';

function Artwork({ game, preferPortrait }) {
  const [attempt, setAttempt] = useState(0);
  const portraitUrl = preferPortrait && /^\d+$/.test(game.steamAppId || '')
    ? `https://cdn.akamai.steamstatic.com/steam/apps/${game.steamAppId}/library_600x900.jpg`
    : null;
  const urls = [...new Set([portraitUrl, game.imageUrl, game.imageFallbackUrl].filter(Boolean))];
  const imageUrl = urls[attempt];

  return <div className="game-artwork">
    {imageUrl ? <img
      key={imageUrl}
      src={imageUrl}
      alt={`Cover artwork for ${game.title}`}
      width="460"
      height="215"
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setAttempt(attempt + 1)}
    /> : <div className="artwork-fallback" role="img" aria-label={`Artwork unavailable for ${game.title}`}>
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true"><rect x="6" y="12" width="36" height="24" rx="8" /><path d="M13 24h10m-5-5v10m14-8h.01M36 27h.01" /></svg>
      <span>{game.title}</span>
      <small>Artwork unavailable</small>
    </div>}
  </div>;
}

export default function GameArtwork({ game, preferPortrait = false }) {
  // Remount when identity or candidate URLs change so an earlier failure cannot leak.
  return <Artwork key={JSON.stringify([game.source, game.slug, game.steamAppId, game.imageUrl, game.imageFallbackUrl, preferPortrait])} game={game} preferPortrait={preferPortrait} />;
}
