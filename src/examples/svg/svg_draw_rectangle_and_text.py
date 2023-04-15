from typing import Dict, List, Tuple, Callable
from enum import Enum, auto
import io
import gzip
import re
import math
import numpy
import svgwrite
import svgwrite.base
import svgwrite.container
import svgwrite.elementfactory
from svgwrite.extensions import Inkscape
import shapely
import shapely.geometry
import shapely.wkt
import svgpathtools
import svgpathtools.path
import svgpathtools.paths2svg
import svgpath2mpl
import matplotlib.path
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen


INPUT_FILE_LOREM_IPSUM = "data/input/example/txt/Lorem_ipsum_10000.txt"
OUTPUT_FILE = "data/output/example/svg/din_a4_page_rectangle_and_text.svg"

CANVAS_UNIT = "mm"  # Units for CANVAS dimensions
CANVAS_WIDTH = 210  # DIN A4 page width in mm
CANVAS_HEIGHT = 297  # DIN A4 page height in mm

RECT_WIDTH = 140  # rectangle width in mm
RECT_HEIGHT = 100  # rectangle height in mm

VB_RATIO = 1 / RECT_WIDTH  # multiply each dimension with this ratio

FONT_FILENAME = "fonts/RobotoFlex-VariableFont_GRAD,XTRA," + \
                "YOPQ,YTAS,YTDE,YTFI,YTLC,YTUC,opsz,slnt,wdth,wght.ttf"
# FONT_FILENAME = "fonts/Recursive-VariableFont_CASL,CRSV,MONO,slnt,wght.ttf"
# FONT_FILENAME = "fonts/NotoSansMono-VariableFont_wdth,wght.ttf"

FONT_SIZE = VB_RATIO * 3  # in mm


class Polygonize(Enum):
    BY_ANGLE = auto()
    UNIFORM = auto()


POLYGONIZE_UNIFORM_NUM_POINTS = 10  # minimum 2 = (start, end)
POLYGONIZE_ANGLE_MAX_DEGREE = 5  # 2 # difference of two derivatives less than
POLYGONIZE_ANGLE_MAX_STEPS = 9  # 9
POLYGONIZE_TYPE = Polygonize.BY_ANGLE


class AVGlyph:
    def real_width(self, font_size: float) -> float:
        pass

    def real_sidebearing_left(self, font_size: float) -> float:
        pass

    def real_sidebearing_right(self, font_size: float) -> float:
        pass

    def path_string(self, x_pos: float, y_pos: float, font_size: float) -> str:
        pass

    def svg_path(self, dwg: svgwrite.Drawing,
                 x_pos: float, y_pos: float,
                 font_size: float, **svg_properties) \
            -> svgwrite.elementfactory.ElementBuilder:
        pass

    def svg_text(self, dwg: svgwrite.Drawing,
                 x_pos: float, y_pos: float,
                 font_size: float, **svg_properties) \
            -> svgwrite.elementfactory.ElementBuilder:
        pass

    def rect_em(self, x_pos: float, y_pos: float,
                ascent: float, descent: float,
                real_width: float, font_size: float) \
            -> Tuple[float, float, float, float]:
        # returns (x_pos_left_corner, y_pos_top_corner, width, height)
        pass

    def rect_em_width(self, x_pos: float, y_pos: float,
                      ascent: float, descent: float,
                      font_size: float) \
            -> Tuple[float, float, float, float]:
        # returns (x_pos_left_corner, y_pos_top_corner, width, height)
        pass

    def rect_given_ascent_descent(self, x_pos: float, y_pos: float,
                                  ascent: float, descent: float,
                                  font_size: float) \
            -> Tuple[float, float, float, float]:
        # returns (x_pos_left_corner, y_pos_top_corner, width, height)
        pass

    def rect_font_ascent_descent(self, x_pos: float, y_pos: float,
                                 font_size: float) \
            -> Tuple[float, float, float, float]:
        # returns (x_pos_left_corner, y_pos_top_corner, width, height)
        pass

    def rect_bounding_box(self, x_pos: float, y_pos: float, font_size: float) \
            -> Tuple[float, float, float, float]:
        # returns (x_pos_left_corner, y_pos_top_corner, width, height)
        pass

    def svg_rect(self, dwg: svgwrite.Drawing,
                 rect: Tuple[float, float, float, float],
                 stroke: str, stroke_width: float, **svg_properties) \
            -> svgwrite.elementfactory.ElementBuilder:
        pass


class AVFont:
    def __init__(self, ttfont: TTFont):
        # ttfont is already configured with the given axes_values
        self.ttfont = ttfont
        self.ascender = self.ttfont['hhea'].ascender  # in unitsPerEm
        self.descender = self.ttfont['hhea'].descender  # in unitsPerEm
        self.line_gap = self.ttfont['hhea'].lineGap  # in unitsPerEm
        self.x_height = self.ttfont["OS/2"].sxHeight  # in unitsPerEm
        self.cap_height = self.ttfont["OS/2"].sCapHeight  # in unitsPerEm
        self.units_per_em = self.ttfont['head'].unitsPerEm
        self.family_name = self.ttfont['name'].getDebugName(1)
        self.subfamily_name = self.ttfont['name'].getDebugName(2)
        self.full_name = self.ttfont['name'].getDebugName(4)
        self.license_description = self.ttfont['name'].getDebugName(13)
        self._glyph_cache: Dict[str, AVGlyph] = {}  # character->AVGlyph

    # def real_ascender(self, font_size: float) -> float:
    #     return self.ascender * font_size / self.units_per_em

    # def real_descender(self, font_size: float) -> float:
    #     return self.descender * font_size / self.units_per_em

    # def real_line_gap(self, font_size: float) -> float:
    #     return self.line_gap * font_size / self.units_per_em

    # def real_x_height(self, font_size: float) -> float:
    #     return self.x_height * font_size / self.units_per_em

    # def real_cap_height(self, font_size: float) -> float:
    #     return self.cap_height * font_size / self.units_per_em

    def glyph(self, character: str) -> AVGlyph:
        glyph = self._glyph_cache.get(character, None)
        if not glyph:
            glyph = AVGlyph(self, character)
            self._glyph_cache[character] = glyph
        return glyph

    def glyph_ascent_descent_of(self, characters: str) -> Tuple[float, float]:
        (ascent, descent) = (0.0, 0.0)
        for char in characters:
            if bounding_box := self.glyph(char).bounding_box:
                (_, descent, _, ascent) = bounding_box
                break
        for char in characters:
            if bounding_box := self.glyph(char).bounding_box:
                (_, y_min, _, y_max) = bounding_box
                ascent = max(ascent, y_max)
                descent = min(descent, y_min)
        return (ascent, descent)

    def real_dash_thickness(self, font_size: float) -> float:
        glyph: AVGlyph = self.glyph("-")
        if glyph.bounding_box:
            thickness = glyph.bounding_box[3] - glyph.bounding_box[1]
            return thickness * font_size / self.units_per_em
        return 0.0

    @staticmethod
    def default_axes_values(ttfont: TTFont) -> Dict[str, float]:
        axes_values: Dict[str, float] = {}
        for axis in ttfont['fvar'].axes:
            axes_values[axis.axisTag] = axis.defaultValue
        return axes_values

    @staticmethod
    def real_value(ttfont: TTFont, font_size: float, value: float) -> float:
        units_per_em = ttfont['head'].unitsPerEm
        return value * font_size / units_per_em


class AVPathPolygon:
    @staticmethod
    def multipolygon_to_path_string(multipolygon: shapely.geometry.MultiPolygon
                                    ) -> List[str]:
        svg_string = multipolygon.svg()
        path_strings = re.findall(r'd="([^"]+)"', svg_string)
        return path_strings

    @staticmethod
    def deepcopy(geometry: shapely.geometry.base.BaseGeometry) \
            -> shapely.geometry.base.BaseGeometry:
        return shapely.wkt.loads(geometry.wkt)

    @staticmethod
    def polygonize_uniform(segment,
                           num_points: int =
                           POLYGONIZE_UNIFORM_NUM_POINTS) -> str:
        # *segment* most likely of type QuadraticBezier or CubicBezier
        # create points ]start,...,end]
        ret_string = ""
        poly = segment.poly()
        points = [poly(i/(num_points-1)) for i in range(1, num_points-1)]
        for point in points:
            ret_string += f'L{point.real:g},{point.imag:g}'
        ret_string += f'L{segment.end.real:g},{segment.end.imag:g}'
        return ret_string

    @staticmethod
    def polygonize_by_angle(segment,
                            max_angle_degree: float =
                            POLYGONIZE_ANGLE_MAX_DEGREE,
                            max_steps: int =
                            POLYGONIZE_ANGLE_MAX_STEPS) -> str:
        # *segment* most likely of type QuadraticBezier or CubicBezier
        # create points ]start,...,end]
        params = [0, 0.5, 1]  # [0, 1/3, 0.5, 2/3, 1]
        points = [segment.point(t) for t in params]
        tangents = [segment.unit_tangent(t) for t in params]
        angle_limit = math.cos(max_angle_degree * math.pi/180)

        for _ in range(1, max_steps):
            (new_params, new_points, new_tangents) = ([], [], [])
            updated = False
            for (param, point, tangent) in zip(params, points, tangents):
                if not new_points:  # nps is empty, i.e. first iteration
                    (new_params, new_points, new_tangents) = (
                        [param], [point], [tangent])
                else:
                    dot_product = new_tangents[-1].real*tangent.real + \
                        new_tangents[-1].imag*tangent.imag
                    if dot_product < angle_limit:
                        new_param = (new_params[-1] + param) / 2
                        new_params.append(new_param)
                        new_points.append(segment.point(new_param))
                        new_tangents.append(segment.unit_tangent(new_param))
                        updated = True
                    new_params.append(param)
                    new_points.append(point)
                    new_tangents.append(tangent)
            params = new_params
            points = new_points
            tangents = new_tangents
            if not updated:
                break
        ret_string = ""
        for point in points[1:]:
            ret_string += f'L{point.real:g},{point.imag:g}'
        return ret_string

    @staticmethod
    def polygonize_path(path_string: str,
                        polygonize_segment_func: Callable) -> str:
        def moveto(coord: complex) -> str:
            return f'M{coord.real:g},{coord.imag:g}'

        def lineto(coord: complex) -> str:
            return f'L{coord.real:g},{coord.imag:g}'

        ret_path_string = ""
        path_collection = svgpathtools.parse_path(path_string)
        for sub_path in path_collection.continuous_subpaths():
            ret_path_string += moveto(sub_path.start)
            for segment in sub_path:
                if isinstance(segment, svgpathtools.CubicBezier) or \
                        isinstance(segment, svgpathtools.QuadraticBezier):
                    ret_path_string += polygonize_segment_func(segment)
                elif isinstance(segment, svgpathtools.Line):
                    ret_path_string += lineto(segment.end)
                else:
                    print("ERROR during polygonizing: " +
                          "not supported segment: " + segment)
                    ret_path_string += lineto(segment.end)
            if sub_path.isclosed():
                ret_path_string += "Z "
        return ret_path_string

    def __init__(self, multipolygon: shapely.geometry.MultiPolygon = None):
        self.multipolygon: shapely.geometry.MultiPolygon = \
            shapely.geometry.MultiPolygon()
        if multipolygon:
            self.multipolygon = multipolygon

    def add_polygon_arrays(self, polygon_arrays: list[numpy.ndarray]):
        # first polygon_array is always additive.
        # All other arrays are additive, if same orient like first array.
        first_is_ccw = True
        for index, polygon_array in enumerate(polygon_arrays):
            polygon = shapely.Polygon(polygon_array)
            polygon_ccw = polygon.exterior.is_ccw
            polygon = polygon.buffer(0)  # get rid of self-intersections (4,9)
            if index == 0:  # first array, so store its orientation
                first_is_ccw = polygon_ccw
            if self.multipolygon.is_empty:  # just add first polygon
                self.multipolygon = shapely.geometry.MultiPolygon([polygon])
            else:
                if polygon_ccw == first_is_ccw:  # same orient --> add to...
                    self.multipolygon = self.multipolygon.union(polygon)
                else:  # different orient --> substract from existing...
                    self.multipolygon = self.multipolygon.difference(polygon)

    def add_path_string(self, path_string: str):
        mpl_path: matplotlib.path.Path = svgpath2mpl.parse_path(path_string)
        polygon_arrays: numpy.ndarray = mpl_path.to_polygons()
        self.add_polygon_arrays(polygon_arrays)

    def path_strings(self) -> List[str]:
        return AVPathPolygon.multipolygon_to_path_string(self.multipolygon)

    def svg_paths(self, dwg: svgwrite.Drawing, **svg_properties) \
            -> List[svgwrite.elementfactory.ElementBuilder]:
        svg_paths = []
        path_strings = self.path_strings()
        for path_string in path_strings:
            svg_paths.append(dwg.path(path_string, **svg_properties))
        return svg_paths


class AVGlyph:  # pylint: disable=function-redefined
    def __init__(self, avfont: AVFont, character: str):
        self._avfont: AVFont = avfont
        self.character: str = character
        bounds_pen = BoundsPen(self._avfont.ttfont.getGlyphSet())
        glyph_name = self._avfont.ttfont.getBestCmap()[ord(character)]
        self._glyph_set = self._avfont.ttfont.getGlyphSet()[glyph_name]
        self._glyph_set.draw(bounds_pen)
        self.bounding_box = bounds_pen.bounds  # (x_min, y_min, x_max, y_max)
        self.width = self._glyph_set.width

    def real_width(self, font_size: float) -> float:
        return self.width * font_size / self._avfont.units_per_em

    def real_dash_thickness(self, font_size: float) -> float:
        return self._avfont.real_dash_thickness(font_size)

    def real_sidebearing_left(self, font_size: float) -> float:
        if self.bounding_box:
            return self.bounding_box[0] * font_size / self._avfont.units_per_em
        return 0.0

    def real_sidebearing_right(self, font_size: float) -> float:
        if self.bounding_box:
            sidebearing_right = self.width - self.bounding_box[2]
            return sidebearing_right * font_size / self._avfont.units_per_em
        return 0.0

    def path_string(self, x_pos: float, y_pos: float, font_size: float) -> str:
        svg_pen = SVGPathPen(self._avfont.ttfont.getGlyphSet())
        scale = font_size / self._avfont.units_per_em
        trafo_pen = TransformPen(svg_pen, (scale, 0, 0, -scale, x_pos, y_pos))
        self._glyph_set.draw(trafo_pen)
        path_string = svg_pen.getCommands()
        if not path_string:
            path_string = f"M{x_pos} {y_pos}"
        else:
            polygon = AVPathPolygon()
            poly_func = None
            match POLYGONIZE_TYPE:
                case Polygonize.UNIFORM:
                    poly_func = AVPathPolygon.polygonize_uniform
                case Polygonize.BY_ANGLE:
                    poly_func = AVPathPolygon.polygonize_by_angle
            path_string = AVPathPolygon.polygonize_path(path_string, poly_func)
            polygon.add_path_string(path_string)
            path_strings = polygon.path_strings()
            path_string = " ".join(path_strings)
        return path_string

    def svg_path(self, dwg: svgwrite.Drawing,
                 x_pos: float, y_pos: float,
                 font_size: float, **svg_properties) \
            -> svgwrite.elementfactory.ElementBuilder:
        path_string = self.path_string(x_pos, y_pos, font_size)
        svg_path = dwg.path(path_string, **svg_properties)
        return svg_path

    def svg_text(self, dwg: svgwrite.Drawing,
                 x_pos: float, y_pos: float,
                 font_size: float, **svg_properties) \
            -> svgwrite.elementfactory.ElementBuilder:
        text_properties = {"insert": (x_pos, y_pos),
                           "font_family": self._avfont.family_name,
                           "font_size": font_size}
        text_properties.update(svg_properties)
        ret_text = dwg.text(self.character, **text_properties)
        return ret_text

    def rect_em(self, x_pos: float, y_pos: float,
                ascent: float, descent: float,
                real_width: float, font_size: float) \
            -> Tuple[float, float, float, float]:
        # returns (x_pos_left_corner, y_pos_top_corner, width, height)
        units_per_em = self._avfont.units_per_em
        middle_of_em = 0.5 * (ascent + descent) * font_size / units_per_em

        rect = (x_pos,
                y_pos - middle_of_em - 0.5 * font_size,
                real_width,
                font_size)
        return rect

    def rect_em_width(self, x_pos: float, y_pos: float,
                      ascent: float, descent: float,
                      font_size: float) \
            -> Tuple[float, float, float, float]:
        # returns (x_pos_left_corner, y_pos_top_corner, width, height)
        return self.rect_em(x_pos, y_pos, ascent, descent,
                            self.real_width(font_size), font_size)

    def rect_given_ascent_descent(self, x_pos: float, y_pos: float,
                                  ascent: float, descent: float,
                                  font_size: float) \
            -> Tuple[float, float, float, float]:
        # returns (x_pos_left_corner, y_pos_top_corner, width, height)
        units_per_em = self._avfont.units_per_em
        rect = (x_pos,
                y_pos - ascent * font_size / units_per_em,
                self.real_width(font_size),
                font_size - descent * font_size / units_per_em)
        return rect

    def rect_font_ascent_descent(self, x_pos: float, y_pos: float,
                                 font_size: float) \
            -> Tuple[float, float, float, float]:
        # returns (x_pos_left_corner, y_pos_top_corner, width, height)
        ascent = self._avfont.ascender
        descent = self._avfont.descender
        return self.rect_given_ascent_descent(x_pos, y_pos,
                                              ascent, descent,
                                              font_size)

    def rect_bounding_box(self, x_pos: float, y_pos: float, font_size: float) \
            -> Tuple[float, float, float, float]:
        # returns (x_pos_left_corner, y_pos_top_corner, width, height)
        rect = (0.0, 0.0, 0.0, 0.0)
        if self.bounding_box:
            units_per_em = self._avfont.units_per_em
            (x_min, y_min, x_max, y_max) = self.bounding_box
            rect = (x_pos + x_min * font_size / units_per_em,
                    y_pos - y_max * font_size / units_per_em,
                    (x_max - x_min) * font_size / units_per_em,
                    (y_max - y_min) * font_size / units_per_em)
        return rect

    def svg_rect(self, dwg: svgwrite.Drawing,
                 rect: Tuple[float, float, float, float],
                 stroke: str, stroke_width: float, **svg_properties) \
            -> svgwrite.elementfactory.ElementBuilder:
        (x_pos, y_pos, width, height) = rect
        rect_properties = {"insert": (x_pos, y_pos),
                           "size": (width, height),
                           "stroke": stroke,
                           "stroke_width": stroke_width,
                           "fill": "none"}
        rect_properties.update(svg_properties)
        return dwg.rect(**rect_properties)


class SVGoutput:
    def __init__(self,
                 canvas_width_mm: float, canvas_height_mm: float,
                 viewbox_x: float, viewbox_y: float,
                 viewbox_width: float, viewbox_height: float):
        self.drawing: svgwrite.Drawing = svgwrite.Drawing(
            size=(f"{canvas_width_mm}mm", f"{canvas_height_mm}mm"),
            viewBox=(f"{viewbox_x} {viewbox_y} " +
                     f"{viewbox_width} {viewbox_height}"),
            profile='full')
        self._inkscape: Inkscape = Inkscape(self.drawing)
        # main   -- editable->locked=False  --  hidden->display="block"
        # debug  -- editable->locked=False  --  hidden->display="none"
        #    glyph
        #       bounding_box
        #       em_width
        #       font_ascent_descent
        #       sidebearing
        #    background
        self.layer_debug: \
            svgwrite.container.Group = self._inkscape.layer(
                label="Layer debug", locked=False, display="none")
        self.drawing.add(self.layer_debug)

        self.layer_debug_glyph_background: \
            svgwrite.container.Group = self._inkscape.layer(
                label="Layer background", locked=True)
        self.layer_debug.add(self.layer_debug_glyph_background)

        self.layer_debug_glyph: \
            svgwrite.container.Group = self._inkscape.layer(
                label="Layer glyph", locked=True)
        self.layer_debug.add(self.layer_debug_glyph)

        self.layer_debug_glyph_sidebearing: \
            svgwrite.container.Group = self._inkscape.layer(
                label="Layer sidebearing", locked=True)  # yellow, orange
        self.layer_debug_glyph.add(self.layer_debug_glyph_sidebearing)

        self.layer_debug_glyph_font_ascent_descent: \
            svgwrite.container.Group = self._inkscape.layer(
                label="Layer font_ascent_descent", locked=True)  # green
        self.layer_debug_glyph.add(self.layer_debug_glyph_font_ascent_descent)

        self.layer_debug_glyph_em_width: \
            svgwrite.container.Group = self._inkscape.layer(
                label="Layer em_width", locked=True)  # blue
        self.layer_debug_glyph.add(self.layer_debug_glyph_em_width)

        self.layer_debug_glyph_bounding_box: \
            svgwrite.container.Group = self._inkscape.layer(
                label="Layer bounding_box", locked=True)  # red
        self.layer_debug_glyph.add(self.layer_debug_glyph_bounding_box)

        self.layer_main: \
            svgwrite.container.Group = self._inkscape.layer(
                label="Layer main", locked=False)
        self.drawing.add(self.layer_main)

    def saveas(self, filename: str, pretty: bool = False, indent: int = 2,
               compressed: bool = False):
        svg_buffer = io.StringIO()
        self.drawing.write(svg_buffer, pretty=pretty, indent=indent)
        output_data = svg_buffer.getvalue().encode('utf-8')
        if compressed:
            output_data = gzip.compress(output_data)
        with open(filename, 'wb') as svg_file:
            svg_file.write(output_data)

    def add_glyph_sidebearing(self, glyph: AVGlyph,
                              x_pos: float, y_pos: float, font_size: float):
        sb_left = glyph.real_sidebearing_left(font_size)
        sb_right = glyph.real_sidebearing_right(font_size)

        rect_bb = glyph.rect_bounding_box(x_pos, y_pos, font_size)
        rect = (x_pos, rect_bb[1], sb_left, rect_bb[3])
        self.layer_debug_glyph_sidebearing.add(
            glyph.svg_rect(self.drawing, rect, "none", 0, fill="yellow"))

        rect = (x_pos + glyph.real_width(font_size) - sb_right,
                rect_bb[1], sb_right, rect_bb[3])
        self.layer_debug_glyph_sidebearing.add(
            glyph.svg_rect(self.drawing, rect, "none", 0, fill="orange"))

    def add_glyph_font_ascent_descent(self, glyph: AVGlyph,
                                      x_pos: float, y_pos: float,
                                      font_size: float):
        stroke_width = glyph.real_dash_thickness(font_size)
        rect = glyph.rect_font_ascent_descent(x_pos, y_pos, font_size)
        self.layer_debug_glyph_font_ascent_descent.add(
            glyph.svg_rect(self.drawing, rect, "green", 0.3*stroke_width))

    def add_glyph_em_width(self, glyph: AVGlyph, x_pos: float, y_pos: float,
                           font_size: float, ascent: float, descent: float):
        stroke_width = glyph.real_dash_thickness(font_size)
        rect = glyph.rect_em_width(x_pos, y_pos, ascent, descent, font_size)
        self.layer_debug_glyph_em_width.add(
            glyph.svg_rect(self.drawing, rect, "blue", 0.2*stroke_width))

    def add_glyph_bounding_box(self, glyph: AVGlyph,
                               x_pos: float, y_pos: float, font_size: float):
        stroke_width = glyph.real_dash_thickness(font_size)
        rect = glyph.rect_bounding_box(x_pos, y_pos, font_size)
        self.layer_debug_glyph_bounding_box.add(
            glyph.svg_rect(self.drawing, rect, "red", 0.1*stroke_width))

    def add_glyph(self, glyph: AVGlyph,
                  x_pos: float, y_pos: float, font_size: float,
                  ascent: float = None, descent: float = None):
        if ascent and descent:
            self.add_glyph_em_width(glyph, x_pos, y_pos,
                                    font_size, ascent, descent)
        self.add_glyph_sidebearing(glyph, x_pos, y_pos, font_size)
        self.add_glyph_font_ascent_descent(glyph, x_pos, y_pos, font_size)
        self.add_glyph_bounding_box(glyph, x_pos, y_pos, font_size)
        self.add(glyph.svg_path(self.drawing, x_pos, y_pos, font_size))

    def add(self, element: svgwrite.base.BaseElement):
        return self.layer_main.add(element)


def main():
    # Center the rectangle horizontally and vertically on the page
    vb_w = VB_RATIO * CANVAS_WIDTH
    vb_h = VB_RATIO * CANVAS_HEIGHT
    vb_x = -VB_RATIO * (CANVAS_WIDTH - RECT_WIDTH) / 2
    vb_y = -VB_RATIO * (CANVAS_HEIGHT - RECT_HEIGHT) / 2

    # Set up the SVG canvas:
    # Define viewBox so that "1" is the width of the rectangle
    # Multiply a dimension with "VB_RATIO" to get the size regarding viewBox
    svg_output = SVGoutput(CANVAS_WIDTH, CANVAS_HEIGHT, vb_x, vb_y, vb_w, vb_h)
    # Draw the rectangle
    svg_output.add(
        svg_output.drawing.rect(
            insert=(0, 0),
            size=(VB_RATIO*RECT_WIDTH, VB_RATIO*RECT_HEIGHT),  # = (1.0, xxxx)
            stroke="black",
            stroke_width=0.1*VB_RATIO,
            fill="none"
        )
    )

    ttfont = TTFont(FONT_FILENAME)
    font = AVFont(ttfont)

    x_pos = VB_RATIO * 10  # in mm
    y_pos = VB_RATIO * 10  # in mm

    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ " + \
           "abcdefghijklmnopqrstuvwxyz " + \
           "ÄÖÜ äöü ß€µ@²³~^°\\ 1234567890 " + \
           ',.;:+-*#_<> !"§$%&/()=?{}[]'

    (ascent, descent) = font.glyph_ascent_descent_of(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ " +
        "abcdefghijklmnopqrstuvwxyz ")

    c_x_pos = x_pos
    c_y_pos = y_pos
    for character in text:
        glyph: AVGlyph = font.glyph(character)
        svg_output.add_glyph(glyph, c_x_pos, c_y_pos, FONT_SIZE,
                             ascent, descent)
        c_x_pos += glyph.real_width(FONT_SIZE)

    c_x_pos = x_pos
    c_y_pos = y_pos - FONT_SIZE
    for character in text:
        glyph: AVGlyph = font.glyph(character)
        svg_output.add_glyph(glyph, c_x_pos, c_y_pos, FONT_SIZE)
        c_x_pos += glyph.real_width(FONT_SIZE)

    c_x_pos = x_pos
    c_y_pos = y_pos + FONT_SIZE
    for character in text:
        glyph: AVGlyph = font.glyph(character)
        svg_output.add_glyph(glyph, c_x_pos, c_y_pos, FONT_SIZE)
        c_x_pos += glyph.real_width(FONT_SIZE)

    # # check an instantiated font:
    # axes_values = AVFont.default_axes_values(ttfont)
    # axes_values.update({"wght": 700, "wdth": 25, "GRAD": 100})
    # ttfont = instancer.instantiateVariableFont(ttfont, axes_values)
    # font = AVFont(ttfont)

    # c_x_pos = x_pos
    # c_y_pos = y_pos + 3 * FONT_SIZE
    # for character in text:
    #     glyph: AVGlyph = font.glyph(character)
    #     svg_output.add_glyph(glyph, c_x_pos, c_y_pos, FONT_SIZE,
    #                          ascent, descent)
    #     c_x_pos += glyph.real_width(FONT_SIZE)

    # Save the SVG file
    # svg_output.saveas(OUTPUT_FILE, pretty=True, indent=2)
    svg_output.saveas(OUTPUT_FILE+"z", pretty=True, indent=2, compressed=True)

    # which glyphs are constructed using several paths?
    for character in text:
        glyph: AVGlyph = font.glyph(character)
        glyph_path_string = glyph.path_string(0, 0, 1)
        parsed_path = svgpathtools.parse_path(glyph_path_string)
        num_parsed_sub_paths = len(parsed_path.continuous_subpaths())
        if num_parsed_sub_paths > 1:
            areas = [path.area() for path in parsed_path.continuous_subpaths()]
            areas = [f"{(a):+04.2f}" for a in areas]
            print(f"{character:1} : {num_parsed_sub_paths:2} - {areas}")

    # glyph: AVGlyph = font.glyph("Ä")
    # print(type(glyph._avfont.ttfont.getGlyphSet()))
    # print(dir(glyph._avfont.ttfont.getGlyphSet()))
    # print(vars(glyph._avfont.ttfont.getGlyphSet()))
    # print("--------------------------------------------------------")
    # glyph_name = glyph._avfont.ttfont.getBestCmap()[ord(character)]
    # glyph_set = glyph._avfont.ttfont.getGlyphSet()[glyph_name]
    # print(vars(glyph_set))

    # with open(INPUT_FILE_LOREM_IPSUM, 'r', encoding="utf-8") as file:
    #     lorem_ipsum = file.read()
    #     print(lorem_ipsum)


if __name__ == "__main__":
    main()
