"""Test module for the ave.svgpath module.

This module contains unit tests for the ave.svgpath module.

The tests are grouped into test cases, each of which is a subclass of
unittest.TestCase.  Each test case contains one or more test methods, each
of which is a method of the test case class that starts with the name
"test_".  The test methods are called by the test runner.

The tests are run using the unittest.main() function.
"""

import unittest

from ave.svgpath import AvSvgPath  # replace with the actual module name


class TestTransformPathString(unittest.TestCase):
    """
    Test case class for the AvSvgPath.transform_path_string function.

    This class contains test methods that verify the correctness of the
    AvSvgPath.transform_path_string function, which applies an affine
    transformation to an SVG path string.
    """

    def test_transform_path_string_absolute_coordinates(self):
        """Test that the function does not change absolute coordinates."""
        input_path_string = "M 10 20 L 30 40"
        affine_trafo = [1, 0, 0, 1, 0, 0]
        expected_result = "M10 20 L30 40"
        self.assertEqual(AvSvgPath.transform_path_string(input_path_string, affine_trafo), expected_result)

    def test_horizontal_line(self):
        """Test that the function does not change absolute horizontal coordinates."""
        input_path_string = "H 10"
        affine_trafo = [1, 0, 0, 1, 0, 0]
        expected_result = "H10"
        self.assertEqual(AvSvgPath.transform_path_string(input_path_string, affine_trafo), expected_result)

    def test_vertical_line(self):
        """Test that the function does not change absolute vertical coordinates."""
        input_path_string = "V 20"
        affine_trafo = [1, 0, 0, 1, 0, 0]
        expected_result = "V20"
        self.assertEqual(
            AvSvgPath.transform_path_string(input_path_string, affine_trafo),
            expected_result,
        )

    def test_transform_elliptical_arc(self):
        """Test that the function does not change absolute elliptical arc coordinates."""
        input_path_string = "A 10 20 30 40 50 60 70"
        affine_trafo = [1, 0, 0, 1, 0, 0]
        expected_result = "A10 20 30 40 50 60 70"
        self.assertEqual(
            AvSvgPath.transform_path_string(input_path_string, affine_trafo),
            expected_result,
        )

    def test_identity_affine_transformation(self):
        """Test that the function does not change absolute coordinates."""
        path_string = "M 10 20 L 30 40"
        affine_trafo = [1, 0, 0, 1, 0, 0]
        expected_result = "M10 20 L30 40"
        self.assertEqual(
            AvSvgPath.transform_path_string(path_string, affine_trafo),
            expected_result,
        )

    def test_non_identity_affine_transformation(self):
        """Test that the function transforms absolute coordinates correctly."""
        input_path_string = "M 10 20 L 30 40"
        affine_transformation = [2, 0, 0, 2, 10, 20]
        expected_result = "M30 60 L70 100"
        self.assertEqual(
            AvSvgPath.transform_path_string(input_path_string, affine_transformation),
            expected_result,
        )


if __name__ == "__main__":
    unittest.main()