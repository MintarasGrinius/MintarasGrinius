import unittest
import xml.etree.ElementTree as ET

from banner import render_banner


class BannerTests(unittest.TestCase):
    def test_all_variants_are_self_contained_accessible_svg(self):
        for theme in ("light", "dark"):
            for mobile in (False, True):
                with self.subTest(theme=theme, mobile=mobile):
                    svg = render_banner({}, theme, mobile)
                    root = ET.fromstring(svg)
                    expected = ("560", "720") if mobile else ("1000", "470")
                    self.assertEqual((root.get("width"), root.get("height")), expected)
                    self.assertEqual(root.get("viewBox"), "0 0 " + " ".join(expected))
                    self.assertEqual(root.get("aria-labelledby"), "title description")
                    tags = {element.tag.split("}")[-1] for element in root.iter()}
                    self.assertTrue({"title", "desc", "path", "text"}.issubset(tags))
                    self.assertFalse({"script", "foreignObject", "image", "animate"} & tags)
                    self.assertNotIn("href=", svg)
                    self.assertIn("Fullstack Developer at trip1", svg)

    def test_configuration_text_is_escaped(self):
        config = {"display_name": "Mintaras & <friends>", "current_role": "Build <things> & ship"}
        svg = render_banner(config, "light")
        root = ET.fromstring(svg)
        self.assertIn("Mintaras & <friends>", "".join(root.itertext()))
        self.assertIn("Build <things> & ship", "".join(root.itertext()))
        self.assertNotIn("<friends>", svg)

    def test_wireframe_stays_inside_art_panel(self):
        from banner import torus

        for x, y, size in ((644, 80, 320), (266, 388, 258)):
            root = ET.fromstring(torus(x, y, size))
            for path in root:
                for point in path.get("d").replace("M", "").split(" L"):
                    px, py = map(float, point.split(","))
                    self.assertTrue(x <= px <= x + size)
                    self.assertTrue(y <= py <= y + size)


if __name__ == "__main__":
    unittest.main()
