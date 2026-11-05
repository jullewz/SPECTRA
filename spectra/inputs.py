"""Keyboard, mouse and gamepad, mapped to a few abstract actions.

created by jullewz
"""

import math

import pygame

KEYMAP = {
    "up": (pygame.K_UP, pygame.K_w),
    "down": (pygame.K_DOWN, pygame.K_s),
    "left": (pygame.K_LEFT, pygame.K_a),
    "right": (pygame.K_RIGHT, pygame.K_d),
    "confirm": (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER),
    "back": (pygame.K_ESCAPE, pygame.K_BACKSPACE),
    "pause": (pygame.K_ESCAPE, pygame.K_p),
    "reroll": (pygame.K_r,),
    "skip": (pygame.K_x,),
    "fullscreen": (pygame.K_F11,),
    "fps": (pygame.K_F3,),
    "screenshot": (pygame.K_F12,),
}

# Xbox-style layout (SDL game controller order)
PAD_BUTTONS = {0: ("confirm",), 1: ("back",), 2: ("reroll",), 3: ("skip",), 7: ("pause",), 6: ("back",)}
DEADZONE = 0.28


class Input:
    def __init__(self):
        self.pressed = set()
        self.mouse_pos = (0, 0)
        self.mouse_moved = False
        self.clicked = False
        self.wheel = 0
        self.sticks = []
        self._axis_state = {}
        self.forced_move = None   # set by the bot / tests
        try:
            pygame.joystick.init()
            for i in range(pygame.joystick.get_count()):
                self._add_stick(i)
        except pygame.error:
            pass

    def _add_stick(self, index):
        try:
            js = pygame.joystick.Joystick(index)
            js.init()
            self.sticks.append(js)
        except pygame.error:
            pass

    def begin_frame(self):
        self.pressed.clear()
        self.clicked = False
        self.mouse_moved = False
        self.wheel = 0

    def handle(self, event):
        t = event.type
        if t == pygame.KEYDOWN:
            for action, keys in KEYMAP.items():
                if event.key in keys:
                    self.pressed.add(action)
        elif t == pygame.MOUSEMOTION:
            self.mouse_pos = event.pos
            self.mouse_moved = True
        elif t == pygame.MOUSEBUTTONDOWN:
            self.mouse_pos = event.pos
            if event.button == 1:
                self.clicked = True
            elif event.button == 4:
                self.wheel -= 1
            elif event.button == 5:
                self.wheel += 1
        elif t == pygame.JOYBUTTONDOWN:
            for action in PAD_BUTTONS.get(event.button, ()):
                self.pressed.add(action)
        elif t == pygame.JOYHATMOTION:
            hx, hy = event.value
            if hx < 0:
                self.pressed.add("left")
            elif hx > 0:
                self.pressed.add("right")
            if hy > 0:
                self.pressed.add("up")
            elif hy < 0:
                self.pressed.add("down")
        elif t == pygame.JOYAXISMOTION and event.axis in (0, 1):
            # turn stick flicks into menu presses (with hysteresis)
            key = (event.joy if hasattr(event, "joy") else 0, event.axis)
            prev = self._axis_state.get(key, 0)
            now = -1 if event.value < -0.6 else (1 if event.value > 0.6 else (0 if abs(event.value) < 0.3 else prev))
            if now != prev and now != 0:
                if event.axis == 0:
                    self.pressed.add("left" if now < 0 else "right")
                else:
                    self.pressed.add("up" if now < 0 else "down")
            self._axis_state[key] = now
        elif t == getattr(pygame, "JOYDEVICEADDED", -1):
            self._add_stick(event.device_index)

    def hit(self, action):
        return action in self.pressed

    def move(self):
        """The movement direction from keys and the left stick, length <= 1."""
        if self.forced_move is not None:
            return self.forced_move
        keys = pygame.key.get_pressed()
        x = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        y = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        for js in self.sticks:
            try:
                ax, ay = js.get_axis(0), js.get_axis(1)
            except pygame.error:
                continue
            if math.hypot(ax, ay) > DEADZONE:
                x, y = ax, ay
        d = math.hypot(x, y)
        if d > 1:
            x, y = x / d, y / d
        return float(x), float(y)
