"""
Dynamic/runtime architecture analyzer.

Uses Python's built-in sys.setprofile() mechanism to observe
function calls during program execution.

The analyzer converts observed function calls into runtime
module-to-module relationships.

Example:

    analyzer = RuntimeAnalyzer()

    runtime_architecture = analyzer.run(
        lambda: my_application_function()
    )

The resulting architecture can contain relationships such as:

    analyzer -> parser
    parser -> database
    analyzer -> database

These relationships represent behavior actually observed
during execution, rather than relationships inferred only
from static imports.
"""

import os
import sys
from types import FrameType
from typing import Callable, Optional, Set, Tuple

from architecture_model.runtime_model import (
    RuntimeArchitecture,
    RuntimeCall,
)


class RuntimeAnalyzer:
    """
    Captures Python function calls during program execution.

    The analyzer is intentionally lightweight so it can be used
    without installing additional packages.
    """

    def __init__(
        self,
        include_prefixes: Optional[list] = None,
        exclude_prefixes: Optional[list] = None,
    ):
        """
        Parameters
        ----------
        include_prefixes:
            Optional list of module prefixes that should be traced.

            Example:
                ["architecture_model", "features"]

            If None, all Python modules are considered.

        exclude_prefixes:
            Optional list of module prefixes that should not be traced.

            Example:
                ["streamlit", "sqlite3"]
        """

        self.include_prefixes = include_prefixes or []

        self.exclude_prefixes = exclude_prefixes or [
            "streamlit",
        ]

        self.runtime_architecture = RuntimeArchitecture()

        self._active = False

    # ------------------------------------------------------------------
    # Module identification
    # ------------------------------------------------------------------

    def _module_name(self, frame: FrameType) -> str:
        """
        Get the Python module name associated with a frame.
        """

        module_name = frame.f_globals.get("__name__")

        if module_name:
            return module_name

        return "<unknown>"

    def _file_name(self, frame: FrameType) -> str:
        """
        Get the source file associated with a frame.
        """

        filename = frame.f_globals.get("__file__")

        if filename:
            return os.path.abspath(filename)

        return ""

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _should_trace_module(self, module_name: str) -> bool:
        """
        Determine whether a module should be included in
        runtime analysis.
        """

        if not module_name:
            return False

        # Ignore Python internals.
        if module_name.startswith("<"):
            return False

        # Ignore excluded modules.
        for prefix in self.exclude_prefixes:
            if module_name == prefix:
                return False

            if module_name.startswith(prefix + "."):
                return False

        # If include prefixes are provided, only trace those modules.
        if self.include_prefixes:
            for prefix in self.include_prefixes:
                if module_name == prefix:
                    return True

                if module_name.startswith(prefix + "."):
                    return True

            return False

        return True

    # ------------------------------------------------------------------
    # Profile callback
    # ------------------------------------------------------------------

    def _profile(
        self,
        frame: FrameType,
        event: str,
        arg,
    ):
        """
        Called by Python whenever a profiled function executes.
        """

        if event != "call":
            return

        if not self._active:
            return

        callee_module = self._module_name(frame)

        if not self._should_trace_module(callee_module):
            return

        callee_function = frame.f_code.co_name

        caller_frame = frame.f_back

        if caller_frame is None:
            return

        caller_module = self._module_name(caller_frame)

        if not self._should_trace_module(caller_module):
            return

        caller_function = caller_frame.f_code.co_name

        caller_file = self._file_name(caller_frame)
        callee_file = self._file_name(frame)

        runtime_call = RuntimeCall(
            caller_module=caller_module,
            caller_function=caller_function,
            callee_module=callee_module,
            callee_function=callee_function,
            caller_file=caller_file,
            callee_file=callee_file,
        )

        self.runtime_architecture.add_call(runtime_call)

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Start collecting runtime calls.
        """

        if self._active:
            return

        self.runtime_architecture = RuntimeArchitecture()

        self._active = True

        sys.setprofile(self._profile)

    def stop(self) -> RuntimeArchitecture:
        """
        Stop collecting runtime calls and return the result.
        """

        sys.setprofile(None)

        self._active = False

        return self.runtime_architecture

    # ------------------------------------------------------------------
    # Run a callable
    # ------------------------------------------------------------------

    def run(
        self,
        target: Callable,
        *args,
        entry_point: Optional[str] = None,
        **kwargs,
    ) -> RuntimeArchitecture:
        """
        Execute a callable while collecting runtime information.

        Example
        -------
        analyzer = RuntimeAnalyzer(
            include_prefixes=["architecture_model"]
        )

        result = analyzer.run(my_function)

        Parameters
        ----------
        target:
            Function that should be executed.

        *args:
            Positional arguments passed to target.

        entry_point:
            Optional name for the execution entry point.

        **kwargs:
            Keyword arguments passed to target.
        """

        self.start()

        if entry_point:
            self.runtime_architecture.entry_point = entry_point
        else:
            self.runtime_architecture.entry_point = getattr(
                target,
                "__name__",
                str(target),
            )

        try:
            target(*args, **kwargs)

        finally:
            self.stop()

        return self.runtime_architecture

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def get_relationships(self):
        """
        Return aggregated runtime relationships.
        """

        return self.runtime_architecture.get_relationships()

    def get_relationship_count(self) -> int:
        return self.runtime_architecture.get_relationship_count()

    def get_module_count(self) -> int:
        return self.runtime_architecture.get_module_count()

    def get_total_calls(self) -> int:
        return self.runtime_architecture.total_calls

    def get_architecture(self) -> RuntimeArchitecture:
        return self.runtime_architecture


# ----------------------------------------------------------------------
# Helper function
# ----------------------------------------------------------------------

def analyze_runtime(
    target: Callable,
    *args,
    include_prefixes: Optional[list] = None,
    exclude_prefixes: Optional[list] = None,
    entry_point: Optional[str] = None,
    **kwargs,
) -> RuntimeArchitecture:
    """
    Convenience function for one-off runtime analysis.

    Example:

        architecture = analyze_runtime(
            my_function,
            include_prefixes=["architecture_model"],
        )
    """

    analyzer = RuntimeAnalyzer(
        include_prefixes=include_prefixes,
        exclude_prefixes=exclude_prefixes,
    )

    return analyzer.run(
        target,
        *args,
        entry_point=entry_point,
        **kwargs,
    )