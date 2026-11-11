"""A warm Streamlit process must load functions added by a new deployment."""
import ast
import importlib
from pathlib import Path
import unittest

import nuke_pga_data


class PGAImportReloadTests(unittest.TestCase):
    def test_old_cached_helper_is_refreshed_before_function_import(self):
        page=Path(__file__).resolve().parents[1]/"pages/15_PGA_SIM.py"
        nodes=[]
        for node in ast.parse(page.read_text()).body:
            if isinstance(node,ast.Import) and any(x.name in {"importlib","nuke_pga_data"} for x in node.names):
                nodes.append(node)
            elif isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=="reload":
                nodes.append(node)
            elif isinstance(node,ast.ImportFrom) and node.module=="nuke_pga_data":
                nodes.append(node)
        try:
            del nuke_pga_data.parse_austin_pairings
            with self.assertRaises(ImportError):
                exec("from nuke_pga_data import parse_austin_pairings",{})
            env={}
            exec(compile(ast.Module(body=nodes,type_ignores=[]),str(page),"exec"),env)
            self.assertTrue(callable(env["parse_austin_pairings"]))
            self.assertTrue(callable(env["expected_points"]))
            self.assertEqual(env["parse_austin_pairings"]("No tee data"),{})
        finally:
            importlib.reload(nuke_pga_data)


if __name__=="__main__":
    unittest.main()
