"""MCP server for ltspice-converter.

Exposes the four conversion functions as MCP tools so AI agents (Claude
Code, Cursor, etc.) can convert LTspice .asc, SPICE .cir, and schemdraw
Python scripts on demand.

Run via the console script ``mcp-ltspice`` (installed by
``pip install ltspice-converter``).
"""
from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from . import conversion


mcp = FastMCP("mcp-ltspice")


@mcp.tool()
def netlist_to_schemdraw(netlist: str, name: str = "circuit") -> str:
    """Convert a SPICE netlist to a runnable schemdraw Python script.

    Args:
        netlist: SPICE netlist text (with .end). E.g.
            'V1 in 0 AC 1\\nR1 in out 1k\\nC1 out 0 1u\\n.ac dec 20 1 100k\\n.end'
        name: Circuit name for the output file (default 'circuit').

    Returns:
        Runnable Python script that uses schemdraw to draw the circuit.
        Supported elements: R, C, L, V, I, D, BJT (NPN/PNP), MOSFET,
        JFET, opamp.
    """
    return conversion.netlist_to_schemdraw(netlist, name)


@mcp.tool()
def schemdraw_to_netlist(script: str, title: str = "circuit") -> str:
    """Convert a schemdraw Python script to a SPICE netlist.

    Args:
        script: schemdraw Python script text (must create a Drawing).
        title: Title for the netlist (default 'circuit').

    Returns:
        SPICE netlist (.cir) text ready for LTspice simulation.
    """
    return conversion.schemdraw_to_netlist(script, title)


@mcp.tool()
def netlist_to_asc(netlist: str) -> str:
    """Convert a SPICE netlist (.cir) to an LTspice schematic (.asc).

    Args:
        netlist: SPICE netlist text.

    Returns:
        LTspice .asc schematic text. Can be saved as a .asc file and
        opened in LTspice.
    """
    return conversion.netlist_to_asc(netlist)


@mcp.tool()
def asc_to_netlist(asc_text: str, use_ltspice: bool = False) -> str:
    """Convert an LTspice schematic (.asc) to a SPICE netlist.

    Args:
        asc_text: LTspice .asc schematic text.
        use_ltspice: If True and LTspice.exe is detected, use LTspice's
            -netlist mode for canonical anonymous-node numbering. Default
            False (pure-Python, no external dependency).

    Returns:
        SPICE netlist (.cir) text.
    """
    return conversion.asc_to_netlist(asc_text, use_ltspice=use_ltspice)


def main() -> int:
    """Entry point for the ``mcp-ltspice`` console script."""
    try:
        mcp.run()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
