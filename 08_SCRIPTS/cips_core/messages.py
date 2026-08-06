from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
from .utils import generate_id, utc_now_iso
class MessageType(str,Enum): COMMAND="command"; EVENT="event"; RESULT="result"; ERROR="error"; AUDIT="audit"
class MessagePriority(int,Enum): LOW=10; NORMAL=20; HIGH=30; CRITICAL=40
@dataclass(slots=True)
class Message:
    topic:str; payload:dict[str,Any]; message_type:MessageType=MessageType.EVENT; priority:MessagePriority=MessagePriority.NORMAL
    source:str=""; target:str=""; correlation_id:str=""; message_id:str=field(default_factory=lambda:generate_id("msg")); created_at:str=field(default_factory=utc_now_iso)
class MessageBus:
    def __init__(self): self._subscribers={}; self._history=[]
    def subscribe(self,topic,handler): self._subscribers.setdefault(topic,[]).append(handler)
    def publish(self,message):
        self._history.append(message)
        for h in list(self._subscribers.get(message.topic,[])): h(message)
    def history(self): return list(self._history)
