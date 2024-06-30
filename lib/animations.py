import asyncio
import time

class AnimationTarget:
    def __init__(self, set_channel_value, get_channel_value, num_channels, level_min, level_max, edge_glow=0):
        self.set_channel = set_channel_value
        self.get_channel = get_channel_value
        self.channels = num_channels
        self.level_min = level_min
        self.level_max = level_max
        self.edge_glow = edge_glow

class Animations:
    def __init__(self, AnimationTarget):
        self.target = AnimationTarget

    async def wave_in(self, duration, step, direction):
        print("animation wave in started")
        
        num_steps = ((self.target.level_max - self.target.level_min) // step) * self.target.channels
        step_delay_ms = max(duration * 1000 // num_steps, 1)

        print("wave in step delay: ", step_delay_ms)

        start_time = time.ticks_ms()

        indexes = range(self.target.channels)

        loop_range = indexes if direction == 'forward' else reversed(indexes)

        for i in loop_range:
            # read current level from memory
            initial_level = self.target.get_channel(i)
            # start from current level, if above min level (error correction)
            start_level = max(initial_level, self.target.level_min)
            for level in range(start_level, self.target.level_max, step):
                # clamp to max level so they aren't stuck not fully lit
                level = level if level <= self.target.level_max - step else self.target.level_max
                self.target.set_channel(i, level)
                await asyncio.sleep_ms(step_delay_ms)
        print("animation wave in took ", time.ticks_diff(time.ticks_ms(), start_time), "ms")
        
    async def wave_out(self, duration, step, direction, terminate):
        print("animation wave out started")

        num_steps = ((self.target.level_max - self.target.level_min) // step) * self.target.channels
        step_delay_ms = max(duration * 1000 // num_steps, 1)

        print("wave out step delay: ", step_delay_ms)

        glow_enabled = self.target.edge_glow > self.target.level_min

        last_channel = self.target.channels - 1

        start_time = time.ticks_ms()

        indexes = range(self.target.channels)

        loop_range = indexes if direction == 'forward' else reversed(indexes)

        for i in loop_range:
            initial_level = self.target.get_channel(i)
            # if glow enabled, don't go below glow level
            final_level = self.target.edge_glow if glow_enabled and (i == 0 or i == last_channel) else self.target.level_min
            for level in range(initial_level, final_level, -step):
                # break out if animation was terminated
                if (terminate()):
                    print("animation wave out terminated")
                    return
                # clamp to zero so they aren't stuck glowing
                level = level if level >= step else 0
                self.target.set_channel(i, level)
                await asyncio.sleep_ms(step_delay_ms)
        
        print("animation wave out took ", time.ticks_diff(time.ticks_ms(), start_time), "ms")

    async def breathe_in(self, duration, step, direction):
        print("animation breathe in started")

        num_steps = ((self.target.level_max - self.target.level_min) // step)
        step_delay_ms = max(duration * 1000 // num_steps, 1)

        start_time = time.ticks_ms()

        for level in range(self.target.level_min, self.target.level_max, step):
            level = level if level <= self.target.level_max - step else self.target.level_max
            for i in range(self.target.channels):
                # start higher if channel isn't initially at min level
                new_level = max(level, self.target.get_channel(i))
                self.target.set_channel(i, new_level)
            await asyncio.sleep_ms(step_delay_ms)
        print("animation breathe in took ", time.ticks_diff(time.ticks_ms(), start_time), "ms")

    async def breathe_out(self, duration, step, direction, terminate):
        print("animation breathe out started")

        num_steps = ((self.target.level_max - self.target.level_min) // step)
        step_delay_ms = max(duration * 1000 // num_steps, 1)

        glow_enabled = self.target.edge_glow > self.target.level_min

        last_channel = self.target.channels - 1

        start_time = time.ticks_ms()

        for level in range(self.target.level_max, self.target.level_min, -step):
            level = self.target.level_min if level < self.target.level_min + step else level
            for i in range(self.target.channels):
                # break out if animation was terminated
                if (terminate()):
                    print("animation breathe out terminated")
                    return
                # start lower if channel isn't initially at max
                new_level = min(level, self.target.get_channel(i))
                # if glow enabled, don't go below glow on edges
                new_level = max(level, self.target.edge_glow) if (i == 0 or i == last_channel) and glow_enabled else level
                self.target.set_channel(i, new_level)
            await asyncio.sleep_ms(step_delay_ms)
        print("animation breathe out took ", time.ticks_diff(time.ticks_ms(), start_time), "ms")
