"""
Tests for symbology_bridge.

The translation helpers are tested without QGIS. The renderer round-trip
tests need QGIS's Python (e.g. run with the python-qgis launcher from the
OSGeo4W shell) and are skipped when qgis cannot be imported:

    python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import symbology_bridge as sb  # noqa: E402

try:
    from qgis.core import (
        QgsApplication, QgsCategorizedSymbolRenderer, QgsExpression, QgsExpressionContext,
        QgsExpressionContextUtils, QgsFeature, QgsField, QgsGeometry, QgsMarkerSymbol,
        QgsPointXY, QgsProperty, QgsRendererCategory, QgsSimpleMarkerSymbolLayer,
        QgsSingleSymbolRenderer, QgsSizeScaleTransformer, QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import QVariant
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


class TranslationTests(unittest.TestCase):

    def test_shapes_with_equivalents(self):
        for shape, marker in [('circle', 'o'), ('square', 's'), ('diamond', 'D'),
                              ('pentagon', 'p'), ('hexagon', 'h'), ('octagon', '8'),
                              ('star', '*'), ('cross_fill', 'P'), ('cross2', 'X')]:
            self.assertEqual(sb.qgis_shape_to_marker(shape), (marker, True), shape)

    def test_triangle_rotation(self):
        self.assertEqual(sb.qgis_shape_to_marker('triangle', 0)[0], '^')
        self.assertEqual(sb.qgis_shape_to_marker('equilateral_triangle', 90)[0], '>')
        self.assertEqual(sb.qgis_shape_to_marker('triangle', 180)[0], 'v')
        self.assertEqual(sb.qgis_shape_to_marker('triangle', -90)[0], '<')
        self.assertEqual(sb.qgis_shape_to_marker('cross_fill', 45)[0], 'X')

    def test_unknown_shape_falls_back_to_circle(self):
        self.assertEqual(sb.qgis_shape_to_marker('heart'), ('o', False))
        self.assertEqual(sb.qgis_shape_to_marker(''), ('o', False))

    def test_marker_round_trip(self):
        for marker in ('o', 's', '^', 'v', '<', '>', 'D', 'p', 'h', '8', '*', 'P', 'X'):
            name, angle, exact = sb.marker_to_qgis_shape(marker)
            self.assertTrue(exact, marker)
            self.assertEqual(sb.qgis_shape_to_marker(name, angle)[0], marker)
        self.assertEqual(sb.marker_to_qgis_shape('$x$'), ('circle', 0.0, False))

    def test_sizes(self):
        self.assertAlmostEqual(sb.size_to_points(2, 'MM'), 2 * 72 / 25.4)
        self.assertEqual(sb.size_to_points(6, 'Point'), 6)
        self.assertAlmostEqual(sb.size_to_points(8, 'Pixel'), 6)
        self.assertIsNone(sb.size_to_points(10, 'MapUnit'))
        self.assertIsNone(sb.size_to_points(0, 'MM'))
        self.assertAlmostEqual(sb.points_to_mm(sb.size_to_points(3, 'MM')), 3)

    def test_category_keys(self):
        self.assertEqual(sb.category_keys('arc'), ['arc'])
        self.assertEqual(sb.category_keys(3), ['3'])
        self.assertEqual(sb.category_keys(''), [])
        self.assertEqual(sb.category_keys(None), [])
        self.assertEqual(sb.category_keys(['a', 'b']), ['a', 'b'])

    def test_expr_number_has_no_exponent(self):
        self.assertEqual(sb.expr_number(1e-7), '0.0000001')
        self.assertEqual(sb.expr_number(400.0), '400')
        self.assertEqual(sb.expr_number(-2.5), '-2.5')

    def test_exponent_to_method(self):
        self.assertEqual(sb.plugin_method_for_exponent(0.5), 'linear')
        self.assertEqual(sb.plugin_method_for_exponent(0.57), 'linear')
        self.assertEqual(sb.plugin_method_for_exponent(1.0), 'exponential')
        self.assertEqual(sb.plugin_method_for_exponent(0.2), 'log10')

    def test_merge_keeps_defaults_for_missing_categories(self):
        defaults = {'a': {'color': '#111111', 'marker': 'o'},
                    'b': {'color': '#222222', 'marker': 's'}}
        merged = sb.merge_layer_styles(defaults, {'a': {'color': '#ff0000', 'source': 'layer'}})
        self.assertEqual(merged['a']['color'], '#ff0000')
        self.assertEqual(merged['a']['marker'], 'o')
        self.assertEqual(merged['b'], defaults['b'])
        self.assertEqual(defaults['a']['color'], '#111111')  # inputs untouched


@unittest.skipUnless(QGIS_AVAILABLE, 'QGIS Python bindings not available')
class RendererTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QgsApplication([], False)
        cls.app.initQgis()

    def _layer(self):
        layer = QgsVectorLayer('Point?crs=EPSG:4326', 'samples', 'memory')
        provider = layer.dataProvider()
        provider.addAttributes([QgsField('zone', QVariant.String), QgsField('code', QVariant.Int)])
        layer.updateFields()
        features = []
        for i, (zone, code) in enumerate([('arc', 1), ('rift', 2), ('plume', 3), (None, 4)]):
            feature = QgsFeature(layer.fields())
            feature.setAttributes([zone, code])
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(i, i)))
            features.append(feature)
        provider.addFeatures(features)
        return layer

    @staticmethod
    def _symbol(props):
        return QgsMarkerSymbol([QgsSimpleMarkerSymbolLayer.create(props)])

    def test_status(self):
        layer = self._layer()
        self.assertFalse(sb.layer_symbology_status(layer, 'zone')[0])  # single symbol
        layer.setRenderer(QgsCategorizedSymbolRenderer('code', []))
        usable, reason = sb.layer_symbology_status(layer, 'zone')
        self.assertFalse(usable)
        self.assertIn("'code'", reason)
        self.assertTrue(sb.layer_symbology_status(layer, 'code')[0])
        self.assertFalse(sb.layer_symbology_status(layer, None)[0])

    def test_read_styles(self):
        layer = self._layer()
        categories = [
            QgsRendererCategory('arc', self._symbol(
                {'name': 'triangle', 'angle': '180', 'color': '255,0,0,255', 'size': '4',
                 'size_unit': 'MM'}), 'Arc volcanics', True),
            QgsRendererCategory('rift', self._symbol(
                {'name': 'heart', 'color': '0,0,255,255', 'size': '10', 'size_unit': 'Point'}),
                'rift', False),
            QgsRendererCategory('', self._symbol({'name': 'square'}), 'all other values', True),
        ]
        layer.setRenderer(QgsCategorizedSymbolRenderer('zone', categories))
        styles = sb.read_layer_category_styles(layer, 'zone')
        self.assertEqual(set(styles), {'arc', 'rift'})  # "all other values" skipped
        arc = styles['arc']
        self.assertEqual((arc['marker'], arc['color'], arc['label'], arc['visible']),
                         ('v', '#ff0000', 'Arc volcanics', True))
        self.assertAlmostEqual(arc['markersize'], 4 * 72 / 25.4, places=1)
        rift = styles['rift']
        self.assertEqual((rift['marker'], rift['visible'], rift['markersize']), ('o', False, 10))
        self.assertEqual(sb.read_layer_category_styles(layer, 'code'), {})

    def test_hollow_marker(self):
        layer = self._layer()
        layer.setRenderer(QgsCategorizedSymbolRenderer('zone', [QgsRendererCategory(
            'arc', self._symbol({'name': 'circle', 'color': '0,0,0,0',
                                 'outline_color': '0,128,0,255'}), 'arc')]))
        arc = sb.read_layer_category_styles(layer, 'zone')['arc']
        self.assertEqual((arc['fill'], arc['color']), ('hollow', '#008000'))

    def test_export_round_trip(self):
        layer = self._layer()
        styles = {
            'arc': {'color': '#ff0000', 'marker': 'v', 'markersize': 8.0, 'alpha': 1.0,
                    'fill': 'full', 'label': 'Arc volcanics'},
            'rift': {'color': '#0000ff', 'marker': 'p', 'markersize': 6.0, 'alpha': 0.5,
                     'fill': 'hollow'},
            'NULL': {'color': '#00ff00', 'marker': 'o', 'markersize': 8.0},
        }
        backup = sb.apply_plot_styles_to_layer(
            layer, 'zone', ['arc', 'rift', 'NULL'], styles, {'arc': True, 'rift': False})
        self.assertTrue(backup)
        self.assertIn(backup, layer.styleManager().styles())
        renderer = layer.renderer()
        self.assertIsInstance(renderer, QgsCategorizedSymbolRenderer)
        self.assertEqual(renderer.classAttribute(), 'zone')
        values = [c.value() for c in renderer.categories()]
        self.assertEqual(values, ['arc', 'rift', ''])  # NULL left to "all other values"

        back = sb.read_layer_category_styles(layer, 'zone')
        self.assertEqual((back['arc']['marker'], back['arc']['color'], back['arc']['label']),
                         ('v', '#ff0000', 'Arc volcanics'))
        self.assertAlmostEqual(back['arc']['markersize'], 8.0, places=1)
        self.assertEqual((back['rift']['marker'], back['rift']['fill'], back['rift']['visible']),
                         ('p', 'hollow', False))
        self.assertAlmostEqual(back['rift']['alpha'], 0.5, places=2)

        # Restoring the backup brings the original single-symbol style back.
        layer.styleManager().setCurrentStyle(backup)
        self.assertIsInstance(layer.renderer(), QgsSingleSymbolRenderer)

    @staticmethod
    def _plugin_bubble_diameter_mm(value, vmin, vmax, a0, a1, method):
        """The plugin's bubble_symbol_size() (geochem_dock), as a diameter in mm."""
        import math
        if value is None:
            return math.sqrt(a0) / sb.POINTS_PER_MM
        if vmax <= vmin:
            t = 1.0
        elif method == 'log10':
            t = 0.0 if value <= 0 else (math.log10(value) - math.log10(vmin)) / (
                math.log10(vmax) - math.log10(vmin))
        elif method == 'exponential':
            t = (math.exp(3 * (value - vmin) / (vmax - vmin)) - 1) / (math.exp(3) - 1)
        else:
            t = (value - vmin) / (vmax - vmin)
        t = max(0.0, min(1.0, t))
        return math.sqrt(a0 + t * (a1 - a0)) / sb.POINTS_PER_MM

    def test_bubble_size_expression_matches_plot(self):
        layer = self._layer()
        for method in ('linear', 'log10', 'exponential'):
            expression = QgsExpression(sb.bubble_size_expression('("code" * 10)', 10, 30, 20, 400, method))
            self.assertFalse(expression.hasParserError(), expression.parserErrorString())
            context = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
            for feature in layer.getFeatures():
                context.setFeature(feature)
                got = expression.evaluate(context)
                self.assertFalse(expression.hasEvalError(), expression.evalErrorString())
                expected = self._plugin_bubble_diameter_mm(feature['code'] * 10, 10, 30, 20, 400, method)
                self.assertAlmostEqual(got, expected, places=6, msg=f'{method} code={feature["code"]}')

    def test_bubble_export_and_exact_reimport(self):
        layer = self._layer()
        bubble = {'value_expression': '"code"', 'size_field': 'code', 'vmin': 1, 'vmax': 4,
                  'min_size': 30.0, 'max_size': 500.0, 'method': 'log10'}
        sb.apply_plot_styles_to_layer(layer, 'zone', ['arc', 'rift'],
                                      {'arc': {'color': '#ff0000'}, 'rift': {'color': '#00ff00'}},
                                      bubble=bubble)
        for category in layer.renderer().categories():
            self.assertTrue(category.symbol().dataDefinedSize().isActive(), category.value())
        settings = sb.bubble_settings_from_layer(layer, 'zone')
        self.assertEqual((settings['size_field'], settings['method'], settings['min_size'],
                          settings['max_size'], settings['exact']),
                         ('code', 'log10', 30.0, 500.0, True))
        # Exporting without bubble sizing clears the data-defined size again.
        sb.apply_plot_styles_to_layer(layer, 'zone', ['arc'], {'arc': {'color': '#ff0000'}})
        self.assertIsNone(sb.bubble_settings_from_layer(layer, 'zone'))

    def test_bubble_import_from_size_assistant(self):
        layer = self._layer()
        prop = QgsProperty.fromField('code')
        transformer_type = getattr(QgsSizeScaleTransformer, 'ScaleType', QgsSizeScaleTransformer)
        prop.setTransformer(QgsSizeScaleTransformer(transformer_type.Area, 1, 4, 2, 8, 0, 0.5))
        symbol = self._symbol({'name': 'circle', 'size': '2'})
        symbol.setDataDefinedSize(prop)
        layer.setRenderer(QgsCategorizedSymbolRenderer('zone', [QgsRendererCategory('arc', symbol, 'arc')]))
        settings = sb.bubble_settings_from_layer(layer, 'zone')
        self.assertEqual((settings['size_field'], settings['method'], settings['exact']),
                         ('code', 'linear', False))
        self.assertAlmostEqual(settings['min_size'], (2 * sb.POINTS_PER_MM) ** 2, places=0)
        self.assertAlmostEqual(settings['max_size'], (8 * sb.POINTS_PER_MM) ** 2, places=0)
        self.assertIn('Area', settings['note'])

    def test_export_keeps_numeric_field_type(self):
        layer = self._layer()
        sb.apply_plot_styles_to_layer(layer, 'code', ['1', '2'],
                                      {'1': {'color': '#ff0000'}, '2': {'color': '#00ff00'}})
        self.assertEqual([c.value() for c in layer.renderer().categories()][:2], [1, 2])


if __name__ == '__main__':
    unittest.main()
