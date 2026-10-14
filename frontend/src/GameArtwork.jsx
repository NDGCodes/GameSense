import React, { useState } from 'react';

function Artwork({ game }) {
  const [failed, setFailed] = useState(false);
  const available = game.imageUrl && !failed;

  return <div className="game-artwork">
    {available ? <img
      src={game.imageUrl}
      alt={`Cover artwork for ${game.title}`}
      width="460"
      height="215"
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    /> : <div className="artwork-fallback" role="img" aria-label={`Artwork unavailable for ${game.title}`}>
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true"><rect x="6" y="12" width="36" height="24" rx="8" /><path d="M13 24h10m-5-5v10m14-8h.01M36 27h.01" /></svg>
      <span>{game.title}</span>
      <small>Artwork unavailable</small>
    </div>}
  </div>;
}

export default function GameArtwork({ game }) {
  // Remount when identity or URL changes so an earlier failure cannot leak to another game.
  return <Artwork key={JSON.stringify([game.source, game.slug, game.imageUrl])} game={game} />;
}
