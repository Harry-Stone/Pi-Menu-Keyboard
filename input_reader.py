from pydualsense import *
import math
import threading


# Stick values from pydualsense are normally around -128..127.
# This is used as the release threshold by the overlay; the overlay uses a
# higher activation threshold to add hysteresis.
deadzone = 18.0


class ControllerInput:
    """Thread-safe DualSense state cache.

    pydualsense emits joystick/button callbacks from its own input thread.  The
    Qt overlay should read a coherent snapshot from those callbacks instead of
    repeatedly touching dualsense.state from the Qt thread.
    """

    def __init__(self, deadzone: float = deadzone, verbose: bool = False):
        self.deadzone = deadzone
        self.dualsense = pydualsense(verbose)
        self.dualsense.init()

        self.lock = threading.Lock()
        self.left_state = (0.0, 0.0)
        self.right_state = (0.0, 0.0)
        self.r1_state = False

        # Seed the cache once in case the sticks/buttons are already non-zero
        # before the first change callback is emitted.
        self._read_initial_state()

        self.dualsense.left_joystick_changed += self._on_left
        self.dualsense.right_joystick_changed += self._on_right
        self.dualsense.r1_changed += self._on_r1

        # Expose the original pydualsense events for any other code that wants
        # to attach extra handlers.
        self.left_joystick_changed = self.dualsense.left_joystick_changed
        self.right_joystick_changed = self.dualsense.right_joystick_changed
        self.cross_pressed = self.dualsense.cross_pressed
        self.circle_pressed = self.dualsense.circle_pressed
        self.dpad_down = self.dualsense.dpad_down
        self.gyro_changed = self.dualsense.gyro_changed
        self.r1_changed = self.dualsense.r1_changed

    def _read_initial_state(self):
        try:
            s = self.dualsense.state
            with self.lock:
                self.left_state = (float(s.LX), float(s.LY))
                self.right_state = (float(s.RX), float(s.RY))
                self.r1_state = bool(s.R1)
        except Exception:
            # Keep zero defaults if the library has not populated state yet.
            pass

    def _on_left(self, x, y):
        with self.lock:
            self.left_state = (float(x), float(y))

    def _on_right(self, x, y):
        with self.lock:
            self.right_state = (float(x), float(y))

    def _on_r1(self, pressed):
        with self.lock:
            self.r1_state = bool(pressed)

    def get_controller_state(self):
        """Return ((LX, LY), (RX, RY), R1) as one locked snapshot."""
        with self.lock:
            return self.left_state, self.right_state, self.r1_state

    def close(self):
        self.dualsense.close()


def normalize_joystick(x, y):
    magnitude = math.sqrt(x**2 + y**2)
    angle_rad = math.atan2(y, x)
    return angle_rad, magnitude


def cross_down(state):
    print(f"cross {state}")


def circle_down(state):
    print(f"circle {state}")


def dpad_down(state):
    print(f"dpad {state}")


def joystick(stateX, stateY):
    magnitude = math.sqrt(stateX**2 + stateY**2)
    angle = math.atan2(stateY, stateX) * (180 / math.pi)
    print(f"lj angle {angle} magnitude {magnitude}")


def rightJoystick(stateX, stateY):
    magnitude = math.sqrt(stateX**2 + stateY**2)
    angle = math.atan2(stateY, stateX) * (180 / math.pi)
    print(f"rj angle {angle} magnitude {magnitude}")


if __name__ == "__main__":
    dualsense = pydualsense()
    dualsense.init()

    dualsense.left_joystick_changed += joystick
    dualsense.right_joystick_changed += rightJoystick

    try:
        while not dualsense.state.R1:
            pass
    finally:
        dualsense.close()
