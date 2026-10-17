(() => {
  const gallery = document.querySelector('.profile-photo');
  if (!gallery) return;
  const photos = [...gallery.querySelectorAll('.profile-photo-slide')];
  if (photos.length < 2) return;

  const previous = gallery.querySelector('.profile-photo-prev');
  const next = gallery.querySelector('.profile-photo-next');
  const status = gallery.querySelector('.profile-photo-status');
  let current = 0;
  let moving = false;
  const below = 'translate(-18%, 30%) scale(.88) rotate(7deg)';
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  function pose(index) {
    const depth = (index - current + photos.length) % photos.length;
    if (depth === 0) return { transform: 'translate(0, 0) scale(1) rotate(0deg)', opacity: 1, zIndex: 10 };
    const layer = Math.min(depth - 1, 2);
    return {
      transform: `translate(${12 + layer * 4}%, ${-34 - layer * 9}%) scale(${.82 - layer * .09}) rotate(${-6 - layer * 2}deg)`,
      opacity: [.38, .24, .14][layer],
      zIndex: Math.max(1, 7 - depth),
    };
  }

  function updatePhotos() {
    photos.forEach((photo, index) => {
      const active = index === current;
      photo.hidden = false;
      photo.classList.toggle('is-current', active);
      photo.setAttribute('aria-hidden', String(!active));
      // Fade the image over its solid white backing, never the whole card.
      const { opacity, ...placement } = pose(index);
      Object.assign(photo.style, placement);
      photo.querySelector('img').style.opacity = opacity;
    });
  }

  async function showPhoto(step) {
    if (moving) return;
    const outgoing = photos[current];
    const oldPoses = photos.map((_, index) => pose(index));
    current = (current + step + photos.length) % photos.length;
    const incoming = photos[current];
    updatePhotos();
    status.textContent = `Photo ${current + 1} of ${photos.length}`;
    if (reducedMotion.matches) return;

    moving = true;
    const timing = { duration: 720, easing: 'cubic-bezier(.22,.68,.22,1)' };
    await Promise.allSettled(photos.flatMap((photo, index) => {
      const frames = [oldPoses[index]];
      if (step > 0 && photo === outgoing) {
        frames.push({ transform: below, opacity: .15, zIndex: 1, offset: .55 });
      } else if (step < 0 && photo === incoming) {
        frames.push({ transform: below, opacity: .65, zIndex: 10, offset: .45 });
      }
      frames.push(pose(index));
      const placementFrames = frames.map(({ opacity, ...placement }) => placement);
      const imageFrames = frames.map(({ opacity, offset }) => (
        offset === undefined ? { opacity } : { opacity, offset }
      ));
      return [
        photo.animate(placementFrames, timing).finished,
        photo.querySelector('img').animate(imageFrames, timing).finished,
      ];
    }));
    moving = false;
  }

  gallery.classList.add('is-stacked');
  updatePhotos();
  previous.hidden = false;
  next.hidden = false;
  previous.addEventListener('click', () => showPhoto(-1));
  next.addEventListener('click', () => showPhoto(1));
  gallery.addEventListener('keydown', (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    showPhoto(event.key === 'ArrowRight' ? 1 : -1);
  });
})();
