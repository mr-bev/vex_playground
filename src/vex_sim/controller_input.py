"""Process-global controller input buffer.

Render mode populates this each frame from pygame keyboard events; the
:class:`vex_sim.api.Controller` API reads from it. In headless mode
nothing populates it, so every controller method returns 0/False --
deterministic, no warnings, no surprises.

Not for assessment
------------------

The Controller surface exists so VEX programs that include
driver-control code (typical pattern: "calibrate, then loop reading
controller axes and forwarding to the drivetrain") can run under the
simulator. There is no automated grading of driver-control behaviour
here; the value is in letting students drive their robot for fun and
visualise the physics.

Keyboard mapping (render mode)
------------------------------

* axis1 (right-stick X): A / D
* axis2 (right-stick Y): W / S
* axis3 (left-stick Y):  arrow Up / Down
* axis4 (left-stick X):  arrow Left / Right
* buttonA / buttonB:     J / K
* buttonL1 / buttonL2:   Q / E
* buttonR1 / buttonR2:   U / O
* buttonL3 / buttonR3:   Z / X
* buttonUp / buttonDown: I / ,
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Axis range: VEX controllers report -100..+100. We keep the same
# convention so student code reads identical values.
_AXIS_MAX = 100


@dataclass
class ControllerInputState:
    axes: dict[str, int] = field(
        default_factory=lambda: {"axis1": 0, "axis2": 0, "axis3": 0, "axis4": 0}
    )
    buttons: dict[str, bool] = field(
        default_factory=lambda: {
            "buttonA": False,
            "buttonB": False,
            "buttonUp": False,
            "buttonDown": False,
            "buttonL1": False,
            "buttonL2": False,
            "buttonL3": False,
            "buttonR1": False,
            "buttonR2": False,
            "buttonR3": False,
        }
    )

    def reset(self) -> None:
        for k in self.axes:
            self.axes[k] = 0
        for k in self.buttons:
            self.buttons[k] = False

    def axis_position(self, name: str) -> int:
        return self.axes.get(name, 0)

    def button_pressing(self, name: str) -> bool:
        return self.buttons.get(name, False)


CONTROLLER_INPUT = ControllerInputState()


# -----------------------------------------------------------------------------
# Render-side helpers (called from vex_sim.render's pygame loop)
# -----------------------------------------------------------------------------


def keyboard_to_axes_buttons(pygame_module) -> tuple[dict[str, int], dict[str, bool]]:
    """Translate the current pygame keyboard state into axes + buttons.

    Held-key polling (``pygame.key.get_pressed``) gives steady-state
    values without needing edge-event bookkeeping; combined with
    +100/-100 axis encoding this matches a VEX joystick at full
    deflection. Diagonals work because each key contributes
    independently to its axis.
    """
    pressed = pygame_module.key.get_pressed()
    K = pygame_module

    def _axis(neg: int, pos: int) -> int:
        v = 0
        if pressed[neg]:
            v -= _AXIS_MAX
        if pressed[pos]:
            v += _AXIS_MAX
        return v

    axes = {
        "axis1": _axis(K.K_a, K.K_d),
        "axis2": _axis(K.K_s, K.K_w),
        "axis3": _axis(K.K_DOWN, K.K_UP),
        "axis4": _axis(K.K_LEFT, K.K_RIGHT),
    }
    buttons = {
        "buttonA": bool(pressed[K.K_j]),
        "buttonB": bool(pressed[K.K_k]),
        "buttonUp": bool(pressed[K.K_i]),
        "buttonDown": bool(pressed[K.K_COMMA]),
        "buttonL1": bool(pressed[K.K_q]),
        "buttonL2": bool(pressed[K.K_e]),
        "buttonL3": bool(pressed[K.K_z]),
        "buttonR1": bool(pressed[K.K_u]),
        "buttonR2": bool(pressed[K.K_o]),
        "buttonR3": bool(pressed[K.K_x]),
    }
    return axes, buttons
