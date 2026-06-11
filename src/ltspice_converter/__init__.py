"""ltspice-converter — convert LTspice .asc and SPICE .cir files
to/from schemdraw Python scripts.

Public API
----------
- netlist_to_schemdraw(netlist, name) -> str
- schemdraw_to_netlist(script, title) -> str
- netlist_to_asc(netlist) -> str
- asc_to_netlist(asc_text, use_ltspice=None) -> str   # None = auto (LTspice if installed)
- topology_signature(netlist) -> str            (node-rename-invariant)
- topology_equivalent(netlist_a, netlist_b) -> (bool, info)

CLI / MCP server
----------------
- mcp-ltspice                (FastMCP stdio server)
"""
from __future__ import annotations

from .conversion import (
    netlist_to_schemdraw,
    schemdraw_to_netlist,
    netlist_to_asc,
    asc_to_netlist,
)
from .topology import topology_signature, topology_equivalent

__all__ = [
    "netlist_to_schemdraw",
    "schemdraw_to_netlist",
    "netlist_to_asc",
    "asc_to_netlist",
    "topology_signature",
    "topology_equivalent",
]

__version__ = "0.4.0"
