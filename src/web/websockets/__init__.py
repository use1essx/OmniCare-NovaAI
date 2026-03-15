"""
WebSocket Integration Module - Healthcare AI V2
===============================================

WebSocket endpoints and handlers for real-time communication
with Live2D frontend and other client applications.
"""

from .chat import live2d_chat_handler, Live2DChatHandler

__all__ = [
    "live2d_chat_handler",
    "Live2DChatHandler"
]
