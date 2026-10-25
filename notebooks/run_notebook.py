"""Headless runner for ``model_full.ipynb`` (no Jupyter kernel required).

Executes every code cell of the notebook, in order, sharing one namespace,
and streams the cell stdout. This is how the project confirms the notebook
logic runs end-to-end with plain ``python``. To run:

    python notebooks/run_notebook.py

Markdown cells are printed as section headers so the output reads like the
notebook. Each code cell is run with ``__file__`` pointing at the notebook so
the cell-1 path resolution works exactly as it would in Jupyter.
"""

from __future__ import annotations

import io
import sys
import traceback
from pathlib import Path

import nbformat

# The notebook prints unicode glyphs (arrows, em-dashes). Force UTF-8 on
# stdout/stderr so this works on Windows consoles that default to cp1252.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, io.UnsupportedOperation):
        pass


def main() -> int:
    nb_path = Path(__file__).resolve().parent / "model_full.ipynb"
    nb = nbformat.read(nb_path, as_version=4)

    print("# " + nb_path.name + " (headless run)\n")
    namespace: dict = {}
    failures = 0
    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        print("=" * 78)
        print(f"[cell {i}]\n{cell.source}\n" + "-" * 78)
        cell_ns = {
            "__file__": str(nb_path),
            "__name__": "__main__",
        }
        cell_ns.update(namespace)
        try:
            exec(compile(cell.source, str(nb_path), "exec"), cell_ns)
            # capture anything the cell added/changed
            for k, v in cell_ns.items():
                if k not in namespace:
                    namespace[k] = v
                elif namespace.get(k) is not v:
                    namespace[k] = v
        except Exception:
            failures += 1
            print("!! cell " + str(i) + " raised:")
            traceback.print_exc()
            # continue so one bad cell does not hide later output
            namespace.update(cell_ns)

    print("\n" + "#" * 78)
    print(f"# done: {failures} failing cell(s) of "
          f"{sum(1 for c in nb.cells if c.cell_type == 'code')}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
