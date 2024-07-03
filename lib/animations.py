import asyncio
import time

# TODO:
# - animation step size can be calculated automatically based on duration and level range
# - (done in wave in)
# - could add an auto-correct that calculates how long iterations actually take and adjusts step size accordingly
# - right now it's assumed that each iteration takes 1ms to update the channel plus 1ms sleep
# - not sure if worth it, because right now (with dynamic step) wave in takes 3063ms for 3s, 5050ms for 5s and 22540ms for 20s duration, but they will never be this long
# FIXME: 
# - latest changes to wave in introduced a wave out bug, every other time it doesn't go to min level (all channels remain glowing)
# - wave out animation is very choppy/flashy on low brigthness with step = 50, becomes smooth with step = 10 but timings is whack, maybe fixed with automatic step?
# - - due to the above, auto step size as in wave in won't work if the duration is too short, because of constant cost of about 2ms of write and sleep per iteration step
# - - sleep is a must to make animation non-blocking to the asyncio scheduler, but sleep cannot go lower than 1ms which is a bummer
# - - AI says: maybe a better approach would be to calculate the time it takes to update all channels and sleep for the remaining time
# - what would be the best was if the PCA9685 would allow a bulk update of all channels at once, but it doesn't, then we would have animation frames and it would be so much better

class AnimationTarget:
    def __init__(self, set_channel_value, get_channel_value, num_channels):
        self.set_channel = set_channel_value
        self.get_channel = get_channel_value
        self.channels = num_channels
        

class Animations:
    def __init__(self, AnimationTarget, animation):
        self.target = AnimationTarget
        self.animation = animation

    async def wave_in(self):
        print("animation wave in started")

        a = self.animation

        start_time = time.ticks_ms()

        indexes = range(self.target.channels)

        channels = indexes if a["direction"] == 'forward' else reversed(indexes)

        channel_dur = a["duration"] * 300 // self.target.channels

        end_level = a["level_max"]

        for i in channels:
            # read current level from memory
            initial_level = self.target.get_channel(i)
            # start from current level, if above min level (error correction)
            start_level = max(initial_level, a["level_min"])
            step = (end_level - start_level) // channel_dur if channel_dur > 0 else 1
            for level in range(start_level, end_level, step):
                # break out if animation was terminated
                if (a["state"] != "animate_in"):
                    print("animation wave in terminated")
                    return
                # pull to max level so they aren't stuck not fully lit
                level = level if level <= end_level - step else end_level
                self.target.set_channel(i, level)
                await asyncio.sleep_ms(1)
        print("animation wave in took ", time.ticks_diff(time.ticks_ms(), start_time), "ms")
        
    async def wave_out(self):
        print("animation wave out started")

        a = self.animation

        num_steps = ((a["level_max"] - a["level_min"]) // a["step"]) * self.target.channels
        step_delay_ms = max(a["duration"] * 1000 // num_steps, 1) if num_steps > 0 else 1

        print("wave out step delay: ", step_delay_ms)

        glow_enabled = a["edge_glow"] > a["level_min"]

        last_channel = self.target.channels - 1

        start_time = time.ticks_ms()

        indexes = range(self.target.channels)

        loop_range = indexes if a["direction"] == 'forward' else reversed(indexes)

        for i in loop_range:
            initial_level = self.target.get_channel(i)
            # if glow enabled, don't go below glow level
            final_level = a["edge_glow"] if glow_enabled and (i == 0 or i == last_channel) else a["level_min"]
            for level in range(initial_level, final_level, -a["step"]):
                # break out if animation was terminated
                if (a["state"] != "animate_out"):
                    print("animation wave out terminated")
                    return
                # clamp to zero so they aren't stuck glowing
                level = level if level >= a["step"] else 0
                self.target.set_channel(i, level)
                await asyncio.sleep_ms(step_delay_ms)
        
        print("animation wave out took ", time.ticks_diff(time.ticks_ms(), start_time), "ms")

    async def breathe_in(self):
        print("animation breathe in started")

        a = self.animation

        num_steps = ((a["level_max"] - a["level_min"]) // a["step"])
        step_delay_ms = max(a["duration"] * 1000 // num_steps, 1) if num_steps > 0 else 1

        start_time = time.ticks_ms()

        for level in range(a["level_min"], a["level_max"], a["step"]):
            level = level if level <= a["level_max"] - a["step"] else a["level_max"]
            for i in range(self.target.channels):
                # break out if animation was terminated
                if (a["state"] != "animate_in"):
                    print("animation breathe in terminated")
                    return
                # start higher if channel isn't initially at min level
                new_level = max(level, self.target.get_channel(i))
                self.target.set_channel(i, new_level)
            await asyncio.sleep_ms(step_delay_ms)
        print("animation breathe in took ", time.ticks_diff(time.ticks_ms(), start_time), "ms")

    async def breathe_out(self):
        print("animation breathe out started")

        a = self.animation

        num_steps = ((a["level_max"] - a["level_min"]) // a["step"])
        step_delay_ms = max(a["duration"] * 1000 // num_steps, 1) if num_steps > 0 else 1

        glow_enabled = a["edge_glow"] > a["level_min"]

        last_channel = self.target.channels - 1

        start_time = time.ticks_ms()

        for level in range(a["level_max"], a["level_min"], -a["step"]):
            level = a["level_min"] if level < a["level_min"] + a["step"] else level
            for i in range(self.target.channels):
                # break out if animation was terminated
                if (a["state"] != "animate_out"):
                    print("animation breathe out terminated")
                    return
                # start lower if channel isn't initially at max
                new_level = min(level, self.target.get_channel(i))
                # if glow enabled, don't go below glow on edges
                new_level = max(level, a["edge_glow"]) if (i == 0 or i == last_channel) and glow_enabled else level
                self.target.set_channel(i, new_level)
            await asyncio.sleep_ms(step_delay_ms)
        print("animation breathe out took ", time.ticks_diff(time.ticks_ms(), start_time), "ms")
