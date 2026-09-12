"""Four pixel-square SSVEP targets outside an untouched native camera window."""
import json
import math
from pathlib import Path


def load_viewport(path):
    value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if value.get('schema_version') != 1:
        raise ValueError('Unsupported viewport schema')
    rect = value['rect']
    for key in ('x', 'y', 'width', 'height'):
        if type(rect.get(key)) is not int:
            raise ValueError('Viewport coordinates must be integer screen pixels')
    if not 120 <= rect['width'] <= 8192 or not 120 <= rect['height'] <= 8192:
        raise ValueError('Viewport dimensions are out of range')
    frame = value.get('frame', rect)
    if any(type(frame.get(key)) is not int for key in ('x', 'y', 'width', 'height')):
        raise ValueError('Camera frame coordinates must be integer screen pixels')
    if (frame['x'] > rect['x'] or frame['y'] > rect['y'] or
            frame['x'] + frame['width'] < rect['x'] + rect['width'] or
            frame['y'] + frame['height'] < rect['y'] + rect['height']):
        raise ValueError('Camera frame must contain the image client area')
    square = float(value.get('square_ratio', 0.14))
    margin = float(value.get('margin_ratio', 0.03))
    if not math.isfinite(square) or not 0.04 <= square <= 0.3:
        raise ValueError('Invalid square ratio')
    if not math.isfinite(margin) or not 0 <= margin <= 0.15:
        raise ValueError('Invalid viewport margin')
    value.update(square_ratio=square, margin_ratio=margin)
    return value


def overlay_layout(viewport):
    rect = viewport['rect']
    frame = viewport.get('frame', rect)
    width, height = rect['width'], rect['height']
    square_ratio = viewport.get('square_ratio', 0.14)
    margin_ratio = viewport.get('margin_ratio', 0.03)
    side = max(8, round(min(width, height) * square_ratio))
    margin = max(2, round(min(width, height) * margin_ratio))
    padding = side + margin
    bounds = {'x': frame['x'] - padding, 'y': frame['y'] - padding,
              'width': frame['width'] + 2 * padding,
              'height': frame['height'] + 2 * padding}
    centered_x = round(rect['x'] + (width - side) / 2)
    centered_y = round(rect['y'] + (height - side) / 2)
    positions = [(centered_x, frame['y'] - padding),
                 (frame['x'] - padding, centered_y),
                 (frame['x'] + frame['width'] + margin, centered_y),
                 (centered_x, frame['y'] + frame['height'] + margin)]
    targets, regions = [], []
    for screen_x, screen_y in positions:
        x, y = screen_x - bounds['x'], screen_y - bounds['y']
        center_x, center_y = x + side / 2, y + side / 2
        regions.append((x, y, x + side, y + side))
        targets.append({'x': 2 * center_x / bounds['width'] - 1,
                        'y': 1 - 2 * center_y / bounds['height'],
                        'scale_x': 2 * side / bounds['width'],
                        'scale_y': 2 * side / bounds['height'],
                        'screen_rect': {'x': screen_x, 'y': screen_y, 'width': side, 'height': side},
                        'side_px': side})
    return {'rect': bounds, 'targets': targets, 'regions': regions}


def apply_targets(stimuli, viewport):
    if len(stimuli) != 4 or any(type(item).__name__ != 'Square' for item in stimuli):
        raise ValueError('Camera alignment requires exactly four Square stimuli in label order')
    layout = overlay_layout(viewport)
    for stimulus, target in zip(stimuli, layout['targets']):
        stimulus.x, stimulus.y = target['x'], target['y']
        stimulus.viewport_scale = (target['scale_x'], target['scale_y'])
    return layout
