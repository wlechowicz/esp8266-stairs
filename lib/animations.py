import asyncio
import time

# TODO:
# - what would be the best was if the PCA9685 would allow a bulk update of all channels at once, but it doesn't, then we would have animation frames and it would be so much better


class Animations:
    def __init__(self, animation, state, set_channel_value, get_channel_value):
        self.animation = animation
        self.set_channel = set_channel_value
        self.get_channel = get_channel_value
        self.main_state = state

    async def wave_in(self):
        print("animation wave in started")

        a = self.animation

        start_time = time.ticks_ms()

        num_chan = len(self.main_state["channels_low"])

        indexes = range(num_chan)

        channel_indexes = indexes if a["direction"] == "forward" else reversed(indexes)

        channel_dur = a["duration"] * 120 // num_chan

        end_level = a["level_max"]

        for i in channel_indexes:
            # read current level from memory
            initial_level = self.get_channel(i)
            # start from current level, if above min level (error correction)
            start_level = max(initial_level, a["level_min"])
            # skip if channel is already at target
            if end_level == start_level:
                continue
            step = (end_level - start_level) // channel_dur if channel_dur > 0 else 1
            # pull to end_level
            levels = list(range(start_level, end_level, step))
            levels[-1] = end_level
            for level in levels:
                # break out if animation was terminated
                if a["state"] != "animate_in":
                    print("animation wave in terminated")
                    return
                # pull to max level so they aren't stuck not fully lit
                self.set_channel(i, level)
                await asyncio.sleep_ms(1)
        print(
            "animation wave in took ",
            time.ticks_diff(time.ticks_ms(), start_time),
            "ms",
        )

    async def wave_out(self):
        print("animation wave out started")

        a = self.animation

        start_time = time.ticks_ms()

        idles = self.main_state["channels_low"]

        num_chan = len(idles)

        indexes = range(num_chan)

        channel_indexes = indexes if a["direction"] == "forward" else reversed(indexes)

        channel_dur = a["duration"] * 120 // num_chan

        for i in channel_indexes:
            start_level = self.get_channel(i)
            end_level = idles[i]
            if end_level == start_level:
                continue
            step = (start_level - end_level) // channel_dur if channel_dur > 0 else 1

            levels = list(range(start_level, end_level, -step))
            # pull to min level so they aren't stuck not fully off
            levels[-1] = end_level
            for level in levels:
                # break out if animation was terminated
                if a["state"] != "animate_out":
                    print("animation wave out terminated")
                    return
                self.set_channel(i, level)
                await asyncio.sleep_ms(1)

        print(
            "animation wave out took ",
            time.ticks_diff(time.ticks_ms(), start_time),
            "ms",
        )

    async def breathe_in(self):
        print("animation breathe in started")

        a = self.animation

        start_time = time.ticks_ms()

        num_chan = len(self.main_state["channels_low"])

        delta_level = a["level_max"] - a["level_min"]

        if delta_level == 0:
            return

        iter_time_ms = num_chan + 1

        # animation duration = delta level * iteration time / level step
        # so
        # step = delta level * iteration time / animation duration

        a_duration_ms = a["duration"] * 1000

        step = delta_level * iter_time_ms // a_duration_ms

        levels = list(range(a["level_min"], a["level_max"], step))
        levels[-1] = a["level_max"]

        for level in levels:
            for i in range(num_chan):
                # break out if animation was terminated
                if a["state"] != "animate_in":
                    print("animation breathe in terminated")
                    return
                # start higher if channel isn't initially at min level
                self.set_channel(i, max(level, self.get_channel(i)))
            await asyncio.sleep_ms(1)
        print(
            "animation breathe in took ",
            time.ticks_diff(time.ticks_ms(), start_time),
            "ms",
        )

    async def breathe_out(self):
        print("animation breathe out started")

        a = self.animation
        idles = self.main_state["channels_low"]

        start_time = time.ticks_ms()

        num_chan = len(idles)

        delta_level = a["level_max"] - a["level_min"]

        if delta_level == 0:
            return

        iter_time_ms = num_chan + 1

        a_duration_ms = a["duration"] * 1000

        step = delta_level * iter_time_ms // a_duration_ms

        levels = list(range(a["level_max"], a["level_min"], -step))
        # pull to min level so they aren't stuck not fully off
        levels[-1] = a["level_min"]

        for level in levels:
            for i in range(num_chan):
                # break out if animation was terminated
                if a["state"] != "animate_out":
                    print("animation breathe out terminated")
                    return
                # start lower if channel isn't initially at max
                # but don't go lower than idle value
                self.set_channel(i, max(min(level, self.get_channel(i)), idles[i]))
            await asyncio.sleep_ms(1)
        print(
            "animation breathe in took ",
            time.ticks_diff(time.ticks_ms(), start_time),
            "ms",
        )

    async def rain(self):
        print("animation rain started")

        # num_chan = len(self.main_state["channels_low"])

        # sequence = noise_data
        # dir = True
        # num_rows = len(sequence)
        # indexes = range(num_rows)
        # while True:
        #     for row in indexes:
        #         for i in range(num_chan):
        #             self.set_channel(i, sequence[row if dir else num_rows - row - 1][i])
        #         await asyncio.sleep_ms(10)
        #     dir = not dir
        #     print("ding", dir)