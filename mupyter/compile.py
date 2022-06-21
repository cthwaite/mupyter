import ast
import io
import sys
import traceback
from ast import Interactive, Module, PyCF_ONLY_AST
from codeop import Compile
from typing import List, Optional


class StdoutCapture:
    """Capture writes to stdout and redirect them to an `io.StringIO` instance.

    This class is designed for use as a transient context handler, e.g.

    ```
    with StdoutCapture() as cap:
        # do something that writes to stdout
        # ...
        # retrieve the captured output
        out = cap.fake_stdout.getvalue()
    ```
    
    Attributes:
        true_stdout: A handle to sys.stdout.
        fake_stdout: An io.StringIO instance used to capture writes to stdout.
    """

    def __init__(self):
        self.true_stdout = None
        self.fake_stdout = io.StringIO()

    def __enter__(self) -> "StdoutCapture":
        self.true_stdout = sys.stdout
        sys.stdout = self.fake_stdout
        return self

    def __exit__(self, *_):
        sys.stdout = self.true_stdout


class CompileCtx:
    """A minimal compilation context for mupyter cells.

    Attributes:
        global_scope: Globally-scoped name storage
        local_scope
        compiler
        _compile_count: Running count of compiled cells.
    """

    def __init__(self):
        self.global_scope = {}
        self.local_scope = {}
        self.compiler = Compile()
        self._compile_count = 0

    def _run_node(self, mod, name: str, mode: str) -> str:
        """Run a top-level AST node, and return the captured output as a string.
        """
        cmp = self.compiler(mod, name, mode)
        with StdoutCapture() as cap:
            exec(cmp, self.global_scope, self.local_scope)
        return cap.fake_stdout.getvalue()

    def run_nodes(self, nodelist: List[ast.AST], cell_id: str) -> List[str]:
        """Run a list of AST nodes.

        Args:
            nodelist
            cell_id

        Returns:
            list of strings representing the outputs of each node
        """
        res = []
        final_expr = None
        # if the last node is an expression, store it to print as cell output
        if isinstance(nodelist[-1] , ast.Expr):
            final_expr = nodelist.pop()
        if nodelist:
            # the second argument is a (mandatory) list of TypeIgnore objects indicating
            # which lines have `type: ignore` comments
            mod = Module(nodelist, [])
            out = self._run_node(mod, cell_id, 'exec')
            if out:
                res.append(out)
        # if we have a terminating expression, run it as an 'interactive' node
        if final_expr is not None:
            mod = Interactive([final_expr])
            out = self._run_node(mod, cell_id, 'single')
            if out:
                res.append(out)
        return res

    def run_cell(self, cell_code: str, filename: Optional[str] = None):
        """Run a 'cell', or block of code.

        Args:
            cell_code: Python code from a mupyter cell.
            filename
        """
        filename = filename or f"<mupyter-input-{self._compile_count}>"
        self._compile_count += 1
        cell = compile(cell_code, filename, "exec", PyCF_ONLY_AST)
        return self.run_nodes(cell.body, filename)


def main():
    """A simple REPL using `CompileCtx`."""
    print("µpyter")
    print("---")
    ctx = CompileCtx()
    while True:
        try:
            data = input("> ")
        except EOFError:
            print("\n", end="")
            return
        try:
            out = ctx.run_cell(data, filename='<stdin>')
            for item in out:
                print(item, end="")
        except Exception as e:
            etype, evalue, tb = sys.exc_info()
            traceback.print_exception(etype, evalue, tb)


if __name__ == "__main__":
    main()
