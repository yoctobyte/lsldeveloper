import math
import uuid
from dataclasses import dataclass, field
from typing import List, Any, Union

# LSL constants
NULL_KEY = "00000000-0000-0000-0000-000000000000"

@dataclass(frozen=True)
class LSLVector:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, other):
        if isinstance(other, LSLVector):
            return LSLVector(self.x + other.x, self.y + other.y, self.z + other.z)
        return NotImplemented

    def __sub__(self, other):
        if isinstance(other, LSLVector):
            return LSLVector(self.x - other.x, self.y - other.y, self.z - other.z)
        return NotImplemented

    def __mul__(self, other):
        # Dot product if vector * vector
        if isinstance(other, LSLVector):
            return self.x * other.x + self.y * other.y + self.z * other.z
        # Scaling if vector * float/int
        if isinstance(other, (int, float)):
            return LSLVector(self.x * other, self.y * other, self.z * other)
        return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            return LSLVector(self.x / other, self.y / other, self.z / other)
        return NotImplemented

    def __xor__(self, other):
        # Cross product if vector ^ vector
        if isinstance(other, LSLVector):
            return LSLVector(
                self.y * other.z - self.z * other.y,
                self.z * other.x - self.x * other.z,
                self.x * other.y - self.y * other.x
            )
        return NotImplemented

    def __str__(self):
        return f"<{self.x:f}, {self.y:f}, {self.z:f}>"

    def magnitude(self):
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

@dataclass(frozen=True)
class LSLRotation:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    s: float = 1.0

    def __mul__(self, other):
        # Quaternion multiplication if rotation * rotation
        if isinstance(other, LSLRotation):
            return LSLRotation(
                self.s * other.x + self.x * other.s + self.y * other.z - self.z * other.y,
                self.s * other.y + self.y * other.s + self.z * other.x - self.x * other.z,
                self.s * other.z + self.z * other.s + self.x * other.y - self.y * other.x,
                self.s * other.s - self.x * other.x - self.y * other.y - self.z * other.z
            )
        # Rotation of vector if rotation * vector
        if isinstance(other, LSLVector):
            # LSL vector rotation: v' = q * v * q^-1
            # Simplified for unit quaternions: v' = v + 2 * q.xyz cross (q.xyz cross v + q.s * v)
            q_xyz = LSLVector(self.x, self.y, self.z)
            t = 2.0 * (q_xyz ^ other)
            res = other + (self.s * t) + (q_xyz ^ t)
            return res
        return NotImplemented

    def __str__(self):
        return f"<{self.x:f}, {self.y:f}, {self.z:f}, {self.s:f}>"

class LSLList(list):
    def __add__(self, other):
        if isinstance(other, LSLList):
            return LSLList(super().__add__(other))
        # LSL hack: list + value appends the value
        new_list = LSLList(self)
        new_list.append(other)
        return new_list

    def __radd__(self, other):
        # value + list prepends the value
        new_list = LSLList([other])
        new_list.extend(self)
        return new_list

    def __str__(self):
        return "[" + ", ".join(map(lsl_format, self)) + "]"

def lsl_format(val) -> str:
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (LSLVector, LSLRotation, LSLList)):
        return str(val)
    if isinstance(val, str):
        return f'"{val}"'
    if isinstance(val, float):
        return f"{val:f}"
    return str(val)

def cast_to_lsl_type(val, target_type: str):
    if target_type == "string":
        return lsl_format(val)
    if target_type == "integer":
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str):
            try:
                return int(val)
            except ValueError:
                return 0
        return 0
    if target_type == "float":
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                return 0.0
        return 0.0
    if target_type == "vector":
        if isinstance(val, str):
            # Parse "<x,y,z>"
            try:
                parts = val.strip("<>").split(",")
                return LSLVector(float(parts[0]), float(parts[1]), float(parts[2]))
            except:
                return LSLVector()
        return LSLVector()
    if target_type == "rotation":
        if isinstance(val, str):
            try:
                parts = val.strip("<>").split(",")
                return LSLRotation(float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))
            except:
                return LSLRotation()
        return LSLRotation()
    if target_type == "list":
        return LSLList([val])
    return val
