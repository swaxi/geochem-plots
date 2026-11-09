"""
Geochemistry Plotting Tools - Symbology Bridge
===============================================
Translates categorical styling between a QGIS layer's Categorised renderer
(QgsCategorizedSymbolRenderer) and the plugin's per-category plot styles,
so that map and plot colours/markers can match.

Plot category styles are plain dicts, as used by the dock's interactive
category panel:
    {'color': '#rrggbb', 'marker': 'o', 'markersize': 8.0 (points),
     'linewidth': 1.5, 'alpha': 1.0, 'fill': 'full' | 'hollow'}
Styles imported from a layer additionally carry 'label' (the renderer
category label), 'visible' (the category's renderState) and
'source': 'layer'.

Everything that touches QGIS is imported lazily, so the pure translation
helpers (marker shapes, size units, category keys) can be unit tested
without a QGIS installation. Works with QGIS 3.x (Qt5) and QGIS 4.x (Qt6):
marker shapes and units are read/written through their string encodings
(QgsSimpleMarkerSymbolLayerBase.encodeShape / QgsUnitTypes.encodeUnit and
QgsSimpleMarkerSymbolLayer.create properties), with an enum-based fallback
that accepts both Qgis.MarkerShape and QgsSimpleMarkerSymbolLayerBase.Shape.
"""

import json
import math
from datetime import datetime

LOG_TAG = 'Geochemistry Plotting Tools'

# Layer custom property recording the plugin bubble-size settings behind a
# data-defined size exported by "Apply to layer", so importing it back
# restores them exactly rather than approximately.
BUBBLE_PROPERTY_KEY = 'geochem_plotting/bubble_size'

# 1 mm = 72 / 25.4 typographic points (matplotlib marker sizes are in points).
POINTS_PER_MM = 72.0 / 25.4
# QGIS "pixel" sizes are converted assuming a standard 96 dpi screen.
POINTS_PER_PIXEL = 72.0 / 96.0
POINTS_PER_INCH = 72.0

DEFAULT_MARKERSIZE = 8.0

# QGIS simple-marker shape (encodeShape() name) -> matplotlib marker. Shapes
# whose look depends on rotation are resolved in qgis_shape_to_marker().
QGIS_TO_MPL_SHAPES = {
    'circle': 'o',
    'square': 's',
    'rounded_square': 's',
    'square_with_corners': 's',
    'diamond': 'D',
    'pentagon': 'p',
    'hexagon': 'h',
    'octagon': '8',
    'star': '*',
    'diamond_star': '*',
    'asterisk_fill': '*',
    'cross_fill': 'P',
    'cross': 'P',
    'cross2': 'X',
}
_TRIANGLE_SHAPES = ('triangle', 'equilateral_triangle')
# Triangle rotation (QGIS angle, degrees clockwise) -> matplotlib marker.
_TRIANGLE_BY_ANGLE = {0: '^', 90: '>', 180: 'v', 270: '<'}

# matplotlib marker -> (QGIS shape name, rotation angle in degrees).
MPL_TO_QGIS_SHAPES = {
    'o': ('circle', 0.0),
    '.': ('circle', 0.0),
    's': ('square', 0.0),
    '^': ('equilateral_triangle', 0.0),
    '>': ('equilateral_triangle', 90.0),
    'v': ('equilateral_triangle', 180.0),
    '<': ('equilateral_triangle', 270.0),
    'D': ('diamond', 0.0),
    'd': ('diamond', 0.0),
    'p': ('pentagon', 0.0),
    'h': ('hexagon', 0.0),
    'H': ('hexagon', 30.0),
    '8': ('octagon', 0.0),
    '*': ('star', 0.0),
    'P': ('cross_fill', 0.0),
    '+': ('cross', 0.0),
    'X': ('cross_fill', 45.0),
    'x': ('cross2', 0.0),
}

# Shapes drawn only with the stroke (no fill), whose visible colour is the
# stroke colour rather than the fill colour.
_STROKE_ONLY_SHAPES = ('cross', 'cross2', 'line', 'arrowhead', 'half_arc',
                       'third_arc', 'quarter_arc')


# -----------------------------------------------------------------------------
# Pure translation helpers (no QGIS needed)
# -----------------------------------------------------------------------------

def qgis_shape_to_marker(shape_name, angle=0.0):
    """Return (matplotlib_marker, exact) for a QGIS shape name.

    `exact` is False when there is no equivalent marker and the circle
    fallback was used, so the caller can log it.
    """
    name = (shape_name or '').strip().lower()
    if name in _TRIANGLE_SHAPES:
        try:
            snapped = int(round(float(angle or 0.0) / 90.0)) * 90 % 360
        except (TypeError, ValueError):
            snapped = 0
        return _TRIANGLE_BY_ANGLE[snapped], True
    if name in ('cross_fill', 'cross') and _angle_is(angle, 45):
        return 'X', True
    if name in QGIS_TO_MPL_SHAPES:
        return QGIS_TO_MPL_SHAPES[name], True
    return 'o', False


def marker_to_qgis_shape(marker):
    """Return (qgis_shape_name, angle, exact) for a matplotlib marker."""
    if marker in MPL_TO_QGIS_SHAPES:
        name, angle = MPL_TO_QGIS_SHAPES[marker]
        return name, angle, True
    return 'circle', 0.0, False


def _angle_is(angle, target):
    try:
        return abs((float(angle or 0.0) - target) % 360.0) < 1e-6
    except (TypeError, ValueError):
        return False


def size_to_points(size, unit_name):
    """Convert a QGIS symbol size to matplotlib points.

    `unit_name` is a QgsUnitTypes.encodeUnit() string ('MM', 'Point',
    'Pixel', 'Inch', 'MapUnit', ...). Map-unit based sizes cannot be
    translated to a fixed plot size, so None is returned for them.
    """
    try:
        size = float(size)
    except (TypeError, ValueError):
        return None
    if size <= 0:
        return None
    unit = (unit_name or 'MM').strip().lower()
    if unit in ('mm', 'millimeters', 'millimeter'):
        return size * POINTS_PER_MM
    if unit in ('point', 'points', 'pt'):
        return size
    if unit in ('pixel', 'pixels', 'px'):
        return size * POINTS_PER_PIXEL
    if unit in ('inch', 'inches', 'in'):
        return size * POINTS_PER_INCH
    return None


def points_to_mm(points):
    """Convert a matplotlib marker size (points) to millimetres."""
    return float(points) / POINTS_PER_MM


def is_null_value(value):
    """True for NULL / None / empty values (QVariant NULL in QGIS 3,
    None in QGIS 4)."""
    if value is None:
        return True
    try:
        if hasattr(value, 'isNull') and value.isNull():
            return True
    except Exception:  # nosec B110 - non-QVariant objects may expose an unrelated isNull
        pass
    return isinstance(value, str) and value == ''


def category_keys(value):
    """Return the plot category keys (strings) covered by a renderer
    category value, or [] for the renderer's "all other values" category.

    The plot keys categories by str(feature[field]), so renderer values are
    stringified the same way. List values (multi-value categories) map to
    one key per item.
    """
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if not is_null_value(v)]
    if is_null_value(value):
        return []
    return [str(value)]


def colour_to_hex_alpha(red, green, blue, alpha=255):
    """Return ('#rrggbb', alpha 0-1) from 0-255 RGBA components."""
    return '#{:02x}{:02x}{:02x}'.format(int(red), int(green), int(blue)), max(0.0, min(1.0, alpha / 255.0))


def expr_number(value):
    """Format a number as a QGIS expression literal (plain decimal, no
    exponent notation)."""
    value = float(value)
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return ('%.15f' % value).rstrip('0').rstrip('.')


def bubble_size_expression(value_expression, vmin, vmax, min_area, max_area, method='linear'):
    """QGIS expression giving the plot's bubble marker diameter in mm.

    Mirrors the plugin's bubble_size_fraction()/bubble_symbol_size(): the
    marker *area* (matplotlib `s`, pt^2) goes from min_area to max_area as
    the value goes from vmin to vmax ('linear', 'log10' or 'exponential'
    curve, clamped to [0, 1]); NULL values get min_area. The diameter is
    sqrt(area) points, converted to millimetres.
    """
    v = '@bubble_value'
    vmin, vmax = float(vmin), float(vmax)
    if vmax <= vmin:
        fraction = '1'
    elif method == 'log10':
        if vmin <= 0 or vmax <= 0:
            fraction = '0'
        else:
            lo, span = math.log10(vmin), math.log10(vmax) - math.log10(vmin)
            fraction = (f'if({v} > 0, (log10({v}) - ({expr_number(lo)})) / {expr_number(span)}, 0)'
                        if span > 0 else '1')
    elif method == 'exponential':
        fraction = (f'(exp(3 * ({v} - ({expr_number(vmin)})) / {expr_number(vmax - vmin)}) - 1)'
                    f' / {expr_number(math.exp(3.0) - 1.0)}')
    else:
        fraction = f'({v} - ({expr_number(vmin)})) / {expr_number(vmax - vmin)}'
    a0, delta = expr_number(min_area), expr_number(float(max_area) - float(min_area))
    return (f"with_variable('bubble_value', {value_expression}, "
            f"if({v} IS NULL, sqrt({a0}), sqrt({a0} + clamp(0, {fraction}, 1) * ({delta})))"
            f" / {expr_number(POINTS_PER_MM)})")


def plugin_method_for_exponent(exponent):
    """Closest plugin bubble scaling for a QGIS size-scale exponent
    (diameter ~ t^exponent, i.e. area ~ t^(2*exponent))."""
    if abs(exponent - 0.5) < 0.1:
        return 'linear'
    return 'exponential' if exponent > 0.5 else 'log10'


# -----------------------------------------------------------------------------
# QGIS helpers
# -----------------------------------------------------------------------------

def log(message, warning=False):
    """Write to the QGIS message log (falls back to print outside QGIS)."""
    try:
        from qgis.core import Qgis, QgsMessageLog
        level_enum = getattr(Qgis, 'MessageLevel', Qgis)
        level = getattr(level_enum, 'Warning' if warning else 'Info')
        QgsMessageLog.logMessage(message, LOG_TAG, level)
    except Exception:
        print(f'[{LOG_TAG}] {message}')


def _shape_name(symbol_layer):
    """Return the encodeShape() name of a QgsSimpleMarkerSymbolLayer."""
    from qgis.core import QgsSimpleMarkerSymbolLayerBase
    shape = symbol_layer.shape()
    try:
        name = QgsSimpleMarkerSymbolLayerBase.encodeShape(shape)
        if name:
            return name
    except Exception:  # nosec B110 - fall through to the enum lookup below
        pass
    # Enum fallback: Qgis.MarkerShape (QGIS >= 3.24, and 4.x) or the older
    # QgsSimpleMarkerSymbolLayerBase.Shape / unscoped members.
    for enum_owner in _marker_shape_enums():
        for attr in dir(enum_owner):
            if attr.startswith('_'):
                continue
            try:
                if getattr(enum_owner, attr) == shape:
                    return _camel_to_snake(attr)
            except Exception:  # nosec B112 - skip non-comparable attributes
                continue
    return ''


def _marker_shape_enums():
    """The marker-shape enum containers available in this QGIS version."""
    owners = []
    try:
        from qgis.core import Qgis
        if hasattr(Qgis, 'MarkerShape'):
            owners.append(Qgis.MarkerShape)
    except Exception:  # nosec B110 - older QGIS without Qgis.MarkerShape
        pass
    try:
        from qgis.core import QgsSimpleMarkerSymbolLayerBase
        if hasattr(QgsSimpleMarkerSymbolLayerBase, 'Shape'):
            owners.append(QgsSimpleMarkerSymbolLayerBase.Shape)
        owners.append(QgsSimpleMarkerSymbolLayerBase)
    except Exception:  # nosec B110 - no simple marker base class available
        pass
    return owners


def _camel_to_snake(name):
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i and not name[i - 1].isupper():
            out.append('_')
        out.append(ch.lower())
    snake = ''.join(out)
    return {'cross2': 'cross2', 'arrow_head': 'arrowhead',
            'arrow_head_filled': 'filled_arrowhead'}.get(snake, snake)


def _unit_name(unit):
    try:
        from qgis.core import QgsUnitTypes
        return QgsUnitTypes.encodeUnit(unit)
    except Exception:
        return 'MM'


def _first_simple_marker_layer(symbol):
    from qgis.core import QgsSimpleMarkerSymbolLayer
    for i in range(symbol.symbolLayerCount()):
        symbol_layer = symbol.symbolLayer(i)
        if isinstance(symbol_layer, QgsSimpleMarkerSymbolLayer):
            return symbol_layer
    return None


def categorized_renderer(layer):
    """Return the layer's QgsCategorizedSymbolRenderer, or None."""
    from qgis.core import QgsCategorizedSymbolRenderer
    if layer is None or not hasattr(layer, 'renderer'):
        return None
    renderer = layer.renderer()
    if isinstance(renderer, QgsCategorizedSymbolRenderer):
        return renderer
    return None


def layer_symbology_status(layer, field_name):
    """Return (usable, reason) for importing the layer's symbology for the
    plot Category field `field_name`. `reason` is a short, user-facing
    explanation (suitable for a tooltip) when not usable."""
    if layer is None:
        return False, 'No layer selected.'
    if not field_name:
        return False, 'Choose a Category field to use the layer symbology.'
    renderer = categorized_renderer(layer)
    if renderer is None:
        return False, ("The layer's symbology is not 'Categorized', so there are no "
                       "per-category styles to import.")
    class_attribute = renderer.classAttribute()
    if class_attribute != field_name:
        return False, (f"The layer is categorized by '{class_attribute}', not by the "
                       f"selected Category field '{field_name}'.")
    return True, (f"Take each category's colour, marker, size and label from the "
                  f"layer's Categorized symbology on '{field_name}'.")


def symbol_to_style(symbol):
    """Translate a QgsSymbol into a partial plot style dict.

    Returns (style, note): `note` is a log message when something had to
    fall back (non-simple marker, unknown shape, map-unit size), else ''.
    """
    notes = []
    style = {}
    if symbol is None:
        return style, 'category has no symbol'

    opacity = 1.0
    try:
        opacity = float(symbol.opacity())
    except Exception:  # nosec B110 - older symbol classes without opacity()
        pass

    colour = symbol.color()
    size, unit = None, 'MM'
    marker_layer = _first_simple_marker_layer(symbol) if hasattr(symbol, 'symbolLayerCount') else None
    if marker_layer is not None:
        shape_name = _shape_name(marker_layer)
        marker, exact = qgis_shape_to_marker(shape_name, marker_layer.angle())
        if not exact:
            notes.append(f"marker shape '{shape_name or 'unknown'}' has no plot equivalent, using a circle")
        style['marker'] = marker
        fill = marker_layer.fillColor()
        stroke = marker_layer.strokeColor()
        if shape_name in _STROKE_ONLY_SHAPES:
            colour = stroke
        elif fill.alpha() == 0:
            colour = stroke
            style['fill'] = 'hollow'
        else:
            colour = fill
            style['fill'] = 'full'
        size, unit = marker_layer.size(), _unit_name(marker_layer.sizeUnit())
    else:
        style['marker'] = 'o'
        notes.append('symbol has no simple marker layer (e.g. SVG/font marker or '
                     'line/fill symbol), using a circle')
        if hasattr(symbol, 'size'):
            try:
                size, unit = symbol.size(), _unit_name(symbol.sizeUnit())
            except Exception:  # nosec B110 - line/fill symbols have no size
                pass

    hex_colour, colour_alpha = colour_to_hex_alpha(
        colour.red(), colour.green(), colour.blue(), colour.alpha())
    style['color'] = hex_colour
    style['alpha'] = max(0.05, min(1.0, colour_alpha * opacity))

    points = size_to_points(size, unit) if size is not None else None
    if points is not None:
        style['markersize'] = round(points, 2)
    elif size is not None:
        notes.append(f"symbol size unit '{unit}' cannot be translated, keeping the default plot size")
    return style, '; '.join(notes)


def read_layer_category_styles(layer, field_name):
    """Read per-category plot styles from the layer's Categorised renderer.

    Returns {category_key: partial_style} for every renderer category with a
    concrete value; the "all other values" category (empty value) is skipped
    so those categories keep the plugin's default styling. Returns {} when
    the renderer isn't categorised on `field_name`.
    """
    usable, _reason = layer_symbology_status(layer, field_name)
    if not usable:
        return {}
    styles = {}
    for renderer_category in categorized_renderer(layer).categories():
        keys = category_keys(renderer_category.value())
        if not keys:
            continue
        style, note = symbol_to_style(renderer_category.symbol())
        label = renderer_category.label()
        style['visible'] = bool(renderer_category.renderState())
        style['source'] = 'layer'
        if note:
            log(f"Layer '{layer.name()}', category '{label or keys[0]}': {note}.")
        for key in keys:
            entry = dict(style)
            # A multi-value category shares one label; show it only when it
            # is not simply the value itself.
            entry['label'] = label if label and len(keys) == 1 else key
            styles.setdefault(key, entry)
    return styles


def _data_defined_size(renderer):
    """Return (QgsProperty, symbol) for the first active data-defined size
    among the renderer's marker symbols, or (None, None)."""
    for renderer_category in renderer.categories():
        symbol = renderer_category.symbol()
        if symbol is None or not hasattr(symbol, 'dataDefinedSize'):
            continue
        prop = symbol.dataDefinedSize()
        if prop is not None and prop.isActive():
            # categories() returns temporary copies that own their symbols,
            # so hand back an independent clone.
            return prop, symbol.clone()
    return None, None


def _size_scale_type_name(transformer):
    """'Linear', 'Area', 'Flannery' or 'Exponential' for a
    QgsSizeScaleTransformer (enum location differs between QGIS versions)."""
    from qgis.core import QgsSizeScaleTransformer
    owner = getattr(QgsSizeScaleTransformer, 'ScaleType', QgsSizeScaleTransformer)
    scale_type = transformer.type()
    for name in ('Linear', 'Area', 'Flannery', 'Exponential'):
        if getattr(owner, name, None) == scale_type:
            return name
    return ''


def bubble_settings_from_layer(layer, field_name):
    """Translate a data-defined symbol size on the layer's Categorised
    renderer (on `field_name`) into plugin bubble-size settings.

    Returns None when there is no data-defined size, else a dict:
      'size_field': plugin "Size by" value (layer field or plugin species),
                    or None when it cannot be determined,
      'method': 'linear' | 'log10' | 'exponential', or None to keep current,
      'min_size', 'max_size': marker areas in pt^2, or None to keep current,
      'exact': True when the size was exported by this plugin,
      'note': explanation of any approximation ('' when exact).
    """
    usable, _reason = layer_symbology_status(layer, field_name)
    if not usable:
        return None
    prop, symbol = _data_defined_size(categorized_renderer(layer))
    if prop is None:
        return None

    expression = prop.expressionString() or ''
    stored = layer.customProperty(BUBBLE_PROPERTY_KEY)
    if stored:
        try:
            stored = json.loads(stored)
        except (TypeError, ValueError):
            stored = None
    if isinstance(stored, dict) and stored.get('expression') and \
            stored['expression'].replace(' ', '') in expression.replace(' ', ''):
        return {'size_field': stored.get('size_field'), 'method': stored.get('method'),
                'min_size': stored.get('min_size'), 'max_size': stored.get('max_size'),
                'exact': True, 'note': ''}

    field = prop.field() or ''
    if not field and expression:
        from qgis.core import QgsExpression
        columns = [c for c in QgsExpression(expression).referencedColumns() if c]
        if len(columns) == 1:
            field = columns[0]
    settings = {'size_field': field or None, 'method': None, 'min_size': None,
                'max_size': None, 'exact': False}

    marker_layer = _first_simple_marker_layer(symbol)
    unit = _unit_name(marker_layer.sizeUnit() if marker_layer else symbol.sizeUnit())
    transformer = prop.transformer()
    scale_name = _size_scale_type_name(transformer) if transformer is not None and \
        hasattr(transformer, 'minSize') else ''
    if scale_name:
        exponent = {'Area': 0.5, 'Flannery': 0.5716, 'Linear': 1.0}.get(
            scale_name, transformer.exponent())
        settings['method'] = plugin_method_for_exponent(exponent)
        min_pt = size_to_points(transformer.minSize(), unit)
        max_pt = size_to_points(transformer.maxSize(), unit)
        if min_pt and max_pt:
            settings['min_size'], settings['max_size'] = round(min_pt ** 2, 1), round(max_pt ** 2, 1)
        settings['note'] = (
            f"QGIS '{scale_name}' size scaling on '{field}' mapped to the plugin's "
            f"'{settings['method']}' bubble scaling; the plot scales between the minimum and "
            f"maximum of the plotted data rather than the QGIS values "
            f"{transformer.minValue():g}-{transformer.maxValue():g}.")
    elif prop.field() and marker_layer is not None:
        # Size read straight from the field (value = diameter in symbol units).
        index = layer.fields().indexOf(field)
        low = size_to_points(layer.minimumValue(index), unit) if index >= 0 else None
        high = size_to_points(layer.maximumValue(index), unit) if index >= 0 else None
        settings['method'] = 'exponential'
        if low and high:
            settings['min_size'], settings['max_size'] = round(low ** 2, 1), round(high ** 2, 1)
        settings['note'] = (f"Symbol size taken directly from '{field}' approximated by the "
                            f"plugin's 'exponential' bubble scaling.")
    else:
        settings['note'] = (f"Data-defined size expression '{expression}' cannot be translated "
                            f"exactly; only its field ({field or 'none found'}) is used.")
    return settings


def merge_layer_styles(default_styles, layer_styles):
    """Overlay imported layer styles onto the plugin's default styles.

    Categories missing from the renderer keep their default style.
    Returns a new {category: style} dict; the inputs are not modified.
    """
    merged = {}
    for category, default_style in default_styles.items():
        style = dict(default_style)
        imported = layer_styles.get(str(category))
        if imported:
            style.update(imported)
        merged[category] = style
    return merged


# -----------------------------------------------------------------------------
# Plot -> map
# -----------------------------------------------------------------------------

def _encode_colour(hex_colour, alpha=1.0):
    from qgis.PyQt.QtGui import QColor
    from qgis.core import QgsSymbolLayerUtils
    colour = QColor(hex_colour)
    colour.setAlphaF(max(0.0, min(1.0, float(alpha))))
    return QgsSymbolLayerUtils.encodeColor(colour)


def style_to_symbol(style, geometry_type=None):
    """Build a QgsSymbol from a plot style dict.

    Point layers get a simple marker with the matching shape, size and
    colour; other geometry types get their default symbol recoloured.
    Returns (symbol, note) like symbol_to_style().
    """
    from qgis.core import QgsMarkerSymbol, QgsSimpleMarkerSymbolLayer, QgsSymbol

    colour = style.get('color', '#000000')
    alpha = float(style.get('alpha', 1.0))
    if geometry_type is not None and not _is_point_geometry(geometry_type):
        symbol = QgsSymbol.defaultSymbol(geometry_type)
        from qgis.PyQt.QtGui import QColor
        symbol.setColor(QColor(colour))
        symbol.setOpacity(alpha)
        return symbol, ''

    marker = style.get('marker', 'o')
    shape_name, angle, exact = marker_to_qgis_shape(marker)
    note = '' if exact else f"plot marker '{marker}' has no QGIS equivalent, using a circle"
    hollow = style.get('fill') == 'hollow'
    stroke_only = shape_name in _STROKE_ONLY_SHAPES
    size_mm = points_to_mm(float(style.get('markersize', DEFAULT_MARKERSIZE)))
    props = {
        'name': shape_name,
        'angle': str(angle),
        'size': f'{size_mm:.3f}',
        'size_unit': 'MM',
        'color': _encode_colour('#ffffff' if hollow else colour, 0.0 if hollow else 1.0),
        # Filled plot markers have a thin black outline; hollow and
        # stroke-only markers are outlined in the category colour.
        'outline_color': _encode_colour(colour if (hollow or stroke_only) else '#000000'),
        'outline_width': '0.4' if (hollow or stroke_only) else '0.2',
        'outline_width_unit': 'MM',
    }
    symbol = QgsMarkerSymbol([QgsSimpleMarkerSymbolLayer.create(props)])
    symbol.setOpacity(alpha)
    return symbol, note


def _is_point_geometry(geometry_type):
    try:
        from qgis.core import Qgis
        if hasattr(Qgis, 'GeometryType'):
            return geometry_type == Qgis.GeometryType.Point
    except Exception:  # nosec B110 - fall back to QgsWkbTypes below
        pass
    from qgis.core import QgsWkbTypes
    point = getattr(getattr(QgsWkbTypes, 'GeometryType', QgsWkbTypes), 'PointGeometry', None)
    return point is None or geometry_type == point


def _native_values_by_key(layer, field_name):
    """Map str(value) -> the layer's own attribute value for `field_name`,
    so renderer categories keep the field's native type (e.g. int 3, not
    '3'), which the renderer needs to match features."""
    index = layer.fields().indexOf(field_name)
    if index < 0:
        return {}
    values = {}
    for value in layer.uniqueValues(index):
        if not is_null_value(value):
            values.setdefault(str(value), value)
    return values


def build_categorized_renderer(layer, field_name, categories, styles, visible=None,
                               size_expression=None):
    """Build a QgsCategorizedSymbolRenderer on `field_name` from plot styles.

    `categories` is the plot's category keys in display order; `styles` is
    {category: style}; `visible` is {category: bool} (hidden categories are
    added unchecked). Categories with no matching value in the layer (e.g.
    'NULL') are left to a trailing "all other values" category that keeps a
    neutral grey symbol, so no feature disappears from the map.

    `size_expression` (see bubble_size_expression()) makes every marker
    symbol's size data-defined, reproducing the plot's bubble sizing.
    """
    from qgis.core import QgsCategorizedSymbolRenderer, QgsProperty, QgsRendererCategory

    visible = visible or {}
    geometry_type = layer.geometryType() if hasattr(layer, 'geometryType') else None
    native = _native_values_by_key(layer, field_name)

    def _sized(symbol):
        if size_expression and hasattr(symbol, 'setDataDefinedSize'):
            symbol.setDataDefinedSize(QgsProperty.fromExpression(size_expression))
        return symbol

    renderer_categories = []
    for category in categories:
        key = str(category)
        if key not in native:
            continue
        style = styles.get(category) or {}
        symbol, note = style_to_symbol(style, geometry_type)
        if note:
            log(f"Layer '{layer.name()}', category '{key}': {note}.")
        label = style.get('label') or key
        renderer_categories.append(
            QgsRendererCategory(native[key], _sized(symbol), label, bool(visible.get(category, True))))

    other_symbol, _note = style_to_symbol(
        {'color': '#a0a0a0', 'marker': 'o', 'markersize': DEFAULT_MARKERSIZE * 0.75},
        geometry_type)
    renderer_categories.append(QgsRendererCategory('', _sized(other_symbol), 'all other values', True))
    return QgsCategorizedSymbolRenderer(field_name, renderer_categories)


def apply_plot_styles_to_layer(layer, field_name, categories, styles, visible=None, bubble=None):
    """Replace the layer's renderer with one built from the plot styles.

    `bubble`, when the plot uses bubble sizing, is a dict with
    'value_expression' (QGIS expression for the plotted size value) and the
    plugin settings 'size_field', 'vmin', 'vmax', 'min_size', 'max_size' and
    'method'; the markers then get the matching data-defined size, and the
    settings are recorded on the layer for an exact round trip.

    The layer's current style is first saved in its style manager (Layer
    Properties > Symbology > Style > <backup name>), so the change can be
    undone by switching back to it. Returns the backup style name, or None
    if the backup could not be made.
    """
    size_expression = None
    if bubble:
        size_expression = bubble_size_expression(
            bubble['value_expression'], bubble['vmin'], bubble['vmax'],
            bubble['min_size'], bubble['max_size'], bubble.get('method', 'linear'))
    renderer = build_categorized_renderer(layer, field_name, categories, styles, visible,
                                          size_expression=size_expression)
    backup_name = None
    try:
        manager = layer.styleManager()
        backup_name = f"Before plot style export {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        if not manager.addStyleFromLayer(backup_name):
            backup_name = None
    except Exception as exc:
        log(f"Could not back up the style of layer '{layer.name()}': {exc}", warning=True)
        backup_name = None
    layer.setRenderer(renderer)
    if size_expression:
        layer.setCustomProperty(BUBBLE_PROPERTY_KEY, json.dumps({
            'expression': size_expression,
            'size_field': bubble.get('size_field'), 'method': bubble.get('method', 'linear'),
            'min_size': bubble['min_size'], 'max_size': bubble['max_size'],
        }))
    else:
        layer.removeCustomProperty(BUBBLE_PROPERTY_KEY)
    layer.triggerRepaint()
    return backup_name
