from machine import Pin, I2C
import asyncio
from lib.pca9685 import PCA9685
from lib.animations import Animations, AnimationTarget
from lib.primitives.pushbutton import Pushbutton

# TODO:
# - animation direction matching trigger side
# - day and night mode based on RTC

print("Start")

# HW config
sda = Pin(12)
scl = Pin(14)

i2c = I2C(sda=sda, scl=scl)

pca = PCA9685(i2c, address=0x40)
pca.freq(1000)

# zero based channel indexes
num_output_channels = 10

# end HW config

# animation config
level_min = 0
level_max = 4095
step = 50
edge_glow = 120

animation_duration = 2
animation_pause_time = 5

# end animation config

last_channel = num_output_channels - 1

# mirroring channel state in local memory because it's slow to read from PCA9685
channels_state = [level_min] * num_output_channels


def set_channel_value(index, value):
    channels_state[index] = value
    pca.duty(index, value)


def get_channel_value(index):
    return channels_state[index]


def print_channels_state(who_called):
    print("channel state", who_called, channels_state)


for i in range(num_output_channels):
    if edge_glow != level_min and i == 0 or i == last_channel:
        level = max(edge_glow, level_min)
        set_channel_value(i, level)
    else:
        set_channel_value(i, level_min)

animate_in = False
animate_out = False
animation_running = False

state = "idle"

target = AnimationTarget(
    set_channel_value,
    get_channel_value,
    num_output_channels,
    level_min,
    level_max,
    edge_glow,
)
animations = Animations(target)

pause_timer_ms = animation_pause_time * 1000


def should_terminate_out_anim():
    return state != "animate_out"


def reset_pause_timer():
    global pause_timer_ms
    pause_timer_ms = animation_pause_time * 1000


def handle_button1_press():
    print("Button 1 pressed")
    global state
    global animate_in
    global animate_out
    reset_pause_timer()
    if state == "idle" or state == "animate_out":
        animate_in = True
        animate_out = False
        state = "override"


async def blink_led(led_pin):
    while True:
        led_pin.value(1)
        await asyncio.sleep_ms(1000)
        led_pin.value(0)
        await asyncio.sleep_ms(1000)


async def check_state():
    global state
    global pause_timer_ms
    interval_ms = 500
    while True:
        print("state: ", state)
        if state == "pause":
            pause_timer_ms -= interval_ms
            if pause_timer_ms <= 0:
                reset_pause_timer()
                global animate_out
                animate_out = True
        await asyncio.sleep_ms(interval_ms)


all_animations = {
    "wave": [animations.wave_in, animations.wave_out],
    "breathe": [animations.breathe_in, animations.breathe_out],
    "breathe_wave": [animations.breathe_in, animations.wave_out],
    "wave_breathe": [animations.wave_in, animations.breathe_out],
}

selected_animation = all_animations["breathe_wave"]


async def run_animation_in():
    global animate_in
    global selected_animation
    global state
    while True:
        if animate_in and (state == "idle" or state == "override"):
            print("run_animation_in")
            state = "animate_in"
            animate_in = False
            await selected_animation[0](animation_duration, step, "reversed")
            state = "pause"
        else:
            await asyncio.sleep_ms(100)


async def run_animation_out():
    global animate_out
    global selected_animation
    global state
    while True:
        if animate_out and state == "pause":
            print("run_animation_out")
            animate_out = False
            state = "animate_out"
            await selected_animation[1](
                animation_duration, step, "reversed", should_terminate_out_anim
            )
            state = "idle"
        else:
            await asyncio.sleep_ms(100)


async def my_app():
    led_pin = Pin(2, Pin.OUT)

    asyncio.create_task(blink_led(led_pin))
    asyncio.create_task(check_state())
    asyncio.create_task(run_animation_in())
    asyncio.create_task(run_animation_out())

    button1_pin = Pin(5, Pin.IN, Pin.PULL_UP)
    button1 = Pushbutton(button1_pin)
    button1.press_func(handle_button1_press)

    # run forever
    while True:
        await asyncio.sleep(1)


try:
    asyncio.run(my_app())
finally:
    asyncio.new_event_loop()  # Clear retained state
