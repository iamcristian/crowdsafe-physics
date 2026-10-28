/* Pure exit editing rules, shared by canvas actions and numeric properties. */
const exitGeometry = (() => {
  const tolerance = 1e-9;
  const sides = ['left', 'right', 'top', 'bottom'];
  function wallLength(room, side) {
    if (!sides.includes(side)) throw Error('Choose a valid wall for the exit.');
    return side === 'left' || side === 'right' ? room.height : room.width;
  }
  function fit(room, exit) {
    const length = wallLength(room, exit.side);
    if (!Number.isFinite(exit.width) || exit.width <= 0 || !Number.isFinite(exit.center)) {
      throw Error('Exit width must be positive and its center must be finite.');
    }
    if (exit.width > length + tolerance) {
      throw Error(`A ${exit.width} m exit cannot fit the ${length} m ${exit.side} wall. Reduce the width to ${length} m or less.`);
    }
    const width = Math.min(exit.width, length);
    return {...exit, width, center: Math.max(width / 2, Math.min(length - width / 2, exit.center))};
  }
  function validate(room, exits) {
    exits.forEach((exit, index) => {
      const length = wallLength(room, exit.side);
      const low = exit.center - exit.width / 2, high = exit.center + exit.width / 2;
      if (!Number.isFinite(exit.width) || exit.width <= 0 || !Number.isFinite(exit.center)) {
        throw Error(`Exit ${index + 1} needs a positive finite width and a finite center.`);
      }
      if (low < -tolerance || high > length + tolerance) {
        throw Error(`Exit ${index + 1} on the ${exit.side} wall spans ${low.toFixed(2)}–${high.toFixed(2)} m; the wall runs from 0 to ${length} m. Move its center or reduce its width.`);
      }
      for (let other = 0; other < index; other++) {
        const previous = exits[other];
        if (previous.side === exit.side && Math.min(high, previous.center + previous.width / 2) - Math.max(low, previous.center - previous.width / 2) > tolerance) {
          throw Error(`Exit ${index + 1} overlaps exit ${other + 1} on the ${exit.side} wall. Select the existing exit to resize it, or move the new exit to a clear part of the wall.`);
        }
      }
    });
  }
  function update(room, exits, index, exit) {
    const fitted = fit(room, exit), next = exits.map(e => ({...e}));
    if (index === next.length) next.push(fitted); else next[index] = fitted;
    validate(room, next);
    return {exits: next, index, exit: fitted};
  }
  function place(room, exits, side, center, width) {
    // Clicking anywhere on an existing opening edits it instead of duplicating it.
    const existing = exits.findIndex(exit => exit.side === side && Math.abs(exit.center - center) <= exit.width / 2 + tolerance);
    return update(room, exits, existing < 0 ? exits.length : existing,
      {side, center: existing < 0 ? center : exits[existing].center, width});
  }
  return {wallLength, fit, validate, update, place};
})();
if (typeof module !== 'undefined' && module.exports) module.exports = exitGeometry;
