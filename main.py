from machine import Pin, I2C, PWM
import asyncio
import gc
from ujson import loads
from lib.pca9685 import PCA9685
from lib.animations import Animations
from lib.primitives.pushbutton import Pushbutton
from lib.hass import Hass

CONFIG = loads(open("config.json").read())

# TODO:
# - day and night mode based on RTC

print("Start")

# HW config
led_pin = Pin(2, Pin.OUT)
trigger1_pin = Pin(14, Pin.IN, Pin.PULL_UP)
trigger2_pin = Pin(27, Pin.IN, Pin.PULL_UP)
sda = Pin(21)
scl = Pin(22)

i2c = I2C(0, scl=scl, sda=sda)

pca = PCA9685(i2c, address=0x40)
pca.freq(1000)

# zero based channel indexes
num_output_channels = 17

pwm0 = PWM(Pin(12), freq=2000, duty=0)

# end HW config

last_channel = num_output_channels - 1


# was in boot, but it takes too long and it's more important to set up HW asap
async def wifi_connect():
    import network

    ssid = CONFIG["ssid"]
    psk = CONFIG["ssid_password"]
    sta_if = network.WLAN(network.STA_IF)
    ap_if = network.WLAN(network.AP_IF)
    if ap_if.active():
        ap_if.active(False)
    if not sta_if.isconnected():
        print("Connecting to network...")
        sta_if.active(True)
        sta_if.connect(ssid, psk)
        while not sta_if.isconnected():
            await asyncio.sleep_ms(200)
            pass
    print("Network config:", sta_if.ifconfig())


# animation config
animation = {
    "level_min": 0,
    "level_max": 4095,
    "edge_glow": 120,
    "direction": "forward",
    "duration": 2,
    "pause_time": 15,
    "pause_timer_ms": 15000,
    "effect": "breathe",
    "state": "idle",
    "animate_in": False,
    "animate_out": False,
}

# mirroring channel state in local memory because it's slow to read from PCA9685
state = {
    "on": True,
    # animations iterate over this
    "active_channels": [animation["level_min"]] * num_output_channels,
    # target channel values (to accommodate edge glow)
    "channels_low": [animation["level_min"]] * num_output_channels,
}


def update_state_idle_channels():
    state["channels_low"] = [animation["level_min"]] * num_output_channels
    if animation["edge_glow"] > animation["level_min"]:
        state["channels_low"][0] = animation["edge_glow"]
        state["channels_low"][-1] = animation["edge_glow"]


update_state_idle_channels()


def set_channel_value(index, value):
    state["active_channels"][index] = value
    if index < 16:
        pca.duty(index, value)
    else:
        pwm0.duty_u16(16 * value)


def get_channel_value(index):
    return state["active_channels"][index]


animations = Animations(animation, state, set_channel_value, get_channel_value)

all_animations = {
    "wave": [animations.wave_in, animations.wave_out, b"Wave"],
    "breathe": [animations.breathe_in, animations.breathe_out, b"Breathe"],
    "breathe_wave": [
        animations.breathe_in,
        animations.wave_out,
        b"Breathe In, Wave Out",
    ],
    "wave_breathe": [
        animations.wave_in,
        animations.breathe_out,
        b"Wave In, Breathe Out",
    ],
}

# end animation config

hass = Hass(state, animation, all_animations)


def set_idle_brightness_cb(idle_brightness=0):
    animation["level_min"] = min(max(idle_brightness, 0), animation["level_max"])
    if animation["state"] == "idle":
        set_idle_levels()
    else:
        update_state_idle_channels()


hass.set_idle_brightness_cb(set_idle_brightness_cb)


def set_edge_glow_cb(edge_glow_level=0):
    animation["edge_glow"] = min(max(edge_glow_level, 0), animation["level_max"])
    if animation["state"] == "idle":
        set_idle_levels()
    else:
        update_state_idle_channels()


hass.set_edge_glow_cb(set_edge_glow_cb)


def set_enabled_state_cb(enabled):
    if state["on"] != enabled:
        state["on"] = enabled
        animation["state"] = "idle"
        animation["animate_in"] = False
        animation["animate_out"] = False
        set_idle_levels()


hass.set_enabled_state_cb(set_enabled_state_cb)


def set_idle_levels():
    if not state["on"]:
        for i in range(num_output_channels):
            set_channel_value(i, 0)
        return

    update_state_idle_channels()

    for i in range(num_output_channels):
        set_channel_value(i, state["channels_low"][i])


animation["pause_timer_ms"] = animation["pause_time"] * 1000


def should_terminate_out_anim():
    return animation["state"] != "animate_out"


def reset_pause_timer(animation):
    animation["pause_timer_ms"] = animation["pause_time"] * 1000


def start_animating(animation, direction="forward"):
    reset_pause_timer(animation)
    if animation["state"] == "idle" or animation["state"] == "animate_out":
        animation["direction"] = direction
        animation["animate_in"] = True
        animation["animate_out"] = False

    if animation["state"] == "animate_out":
        animation["state"] = "override"


def handle_trigger1_fire():
    print("Trigger 1 fired")
    if state["on"]:
        start_animating(animation, "reversed")
    return True


def handle_trigger2_fire():
    print("Trigger 2 fired")
    if state["on"]:
        start_animating(animation, "forward")
    return True


async def blink_led(led_pin):
    import network
    sta_if = network.WLAN(network.STA_IF)
    while True:
        led_pin.off()

        if not sta_if.isconnected():
            await asyncio.sleep_ms(100)
            led_pin.on()
            await asyncio.sleep_ms(100)
            led_pin.off()
            continue


        if not state["on"]:
            await asyncio.sleep_ms(600)
            led_pin.on()
            await asyncio.sleep_ms(100)
            led_pin.off()
            await asyncio.sleep_ms(200)
            led_pin.on()
            await asyncio.sleep_ms(100)
            continue

        await asyncio.sleep_ms(1000)
        led_pin.on()
        await asyncio.sleep_ms(1000)


async def check_state(animation):
    interval_ms = 500
    while True:
        print(
            "state:",
            "On" if state["on"] else "Off",
            "animation state:",
            animation["state"],
        )
        if animation["state"] == "pause":
            animation["pause_timer_ms"] -= interval_ms
            if animation["pause_timer_ms"] <= 0:
                reset_pause_timer(animation)
                animation["animate_out"] = True
        await asyncio.sleep_ms(interval_ms)


async def run_animation_in(animation):
    while True:
        if (
            state["on"]
            and animation["animate_in"]
            and (animation["state"] == "idle" or animation["state"] == "override")
        ):
            print("run_animation_in")
            animation["state"] = "animate_in"
            animation["animate_in"] = False
            await all_animations[animation["effect"]][0]()
            animation["state"] = "pause"
        else:
            await asyncio.sleep_ms(100)


async def run_animation_out(animation):
    while True:
        if state["on"] and animation["animate_out"] and animation["state"] == "pause":
            print("run_animation_out")
            animation["animate_out"] = False
            animation["state"] = "animate_out"
            await all_animations[animation["effect"]][1]()
            animation["state"] = "idle"
        else:
            await asyncio.sleep_ms(100)


async def check_mqtt_msg():
    while True:
        hass.check_msg()
        await asyncio.sleep_ms(500)


async def my_app():
    # let me know you're alive LED
    asyncio.create_task(blink_led(led_pin))

    set_idle_levels()

    # animation tasks
    asyncio.create_task(check_state(animation))
    asyncio.create_task(run_animation_in(animation))
    asyncio.create_task(run_animation_out(animation))

    # Trigger handlers
    trigger1 = Pushbutton(trigger1_pin)
    trigger1.press_func(handle_trigger1_fire)
    trigger2 = Pushbutton(trigger2_pin)
    trigger2.press_func(handle_trigger2_fire)

    await wifi_connect()

    gc.collect()

    # Home Asistant stuff
    hass.connect()
    asyncio.create_task(check_mqtt_msg())

    # asyncio.create_task(animations.rain())

    # run forever
    while True:
        await asyncio.sleep(1)


try:
    asyncio.run(my_app())
finally:
    asyncio.new_event_loop()  # Clear retained state
