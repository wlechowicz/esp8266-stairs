from umqtt.robust import MQTTClient
from ujson import loads, dumps
import asyncio

CONFIG = loads(open("config.json").read())

# TODO:
# - (not needed with the below) send full state to HA when requested (when HA restarts) - done, but needs fix in HA
# - switch to MQTT Light JSON schema
# - - flash time short could be animation duration, long could be pause time
# - - min_mireds and max_mireds could be level_min and edge_low, respectively
# - - brightness is already done
# - - effect is already done
# - - if step is removed then everything is done via built-in properties so most of the automation can be removed
# - - including all the property topics and handle_properties


# MQTT topics
state_request_topic = b"home/stairs_light_ctrl/state_request"
state_response_topic = b"home/stairs_light_ctrl/state_response"
# every settable property has its own topic, like home/stairs_light_ctrl/properties/max_brightness/set

# MQTT Light topics, TODO: would be simpler to use MQTT Light JSON schema
command_topic = b"home/stairs_light_ctrl/set"
state_topic = b"home/stairs_light_ctrl/state"
brightness_command_topic = b"home/stairs_light_ctrl/brightness/set"
brightness_state_topic = b"home/stairs_light_ctrl/brightness/state"
effect_state_topic = b"home/stairs_light_ctrl/effect/state"
effect_command_topic = b"home/stairs_light_ctrl/effect/set"

# inverse state update - ESP tells HA it's state so HA can update controls after restart
state_request_topic_ha = b"home/stairs_light_ctrl/state_request_ha"
state_response_topic_ha = b"home/stairs_light_ctrl/state_response_ha"


class Hass:
    def __init__(self, state, animation, all_animations):
        self.state = state
        self.animation = animation
        self.all_animations = all_animations

    def connect(self):
        try:
            self.client = MQTTClient(
                CONFIG["client_id"],
                CONFIG["broker"],
                user=CONFIG["username"],
                password=CONFIG["password"],
            )
            self.client.connect()
            print("Connected to MQTT broker")
        except Exception as e:
            print("Failed to connect to MQTT broker:", e)
            return
        self.client.set_callback(self.callback)
        # subscribe to each property topic
        for key in self.get_full_state().keys():
            self.client.subscribe(b"home/stairs_light_ctrl/properties/" + key + b"/set")
        self.client.subscribe(command_topic)
        self.client.subscribe(brightness_command_topic)
        self.client.subscribe(effect_command_topic)
        self.client.subscribe(state_response_topic)
        self.client.subscribe(state_request_topic_ha)
        print("Subscribed to topics")
        print("Requesting property state from HA")
        self.client.publish(state_request_topic, "request_state")
        asyncio.create_task(self.publish_light_state_to_HA())

    async def publish_light_state_to_HA(self, delay=True):
        # push current state to MQTT Light
        if delay:
            await asyncio.sleep(5)
        print("Sending command state updates to MQTT Light")
        self.client.publish(state_topic, b"ON" if self.state["on"] else b"OFF")
        self.client.publish(brightness_state_topic, str(self.animation["level_max"]))
        self.client.publish(effect_state_topic, self.get_current_effect_name())

    def check_msg(self):
        self.client.check_msg()

    def callback(self, topic, msg):
        print("Received message from topic", topic, ":", msg)
        if topic.startswith(b"home/stairs_light_ctrl/properties"):
            self.handle_properties(topic, msg)
        elif topic == command_topic:
            self.handle_command(msg)
        elif topic == brightness_command_topic:
            self.handle_brightness_command(msg)
        elif topic == effect_command_topic:
            self.handle_effect_command(msg)
        elif topic == state_response_topic:
            if len(msg) > 0:
                try:
                    state = loads(bytearray(msg))
                    print("Received full state:", state)
                    self.set_full_state(state)
                except Exception as e:
                    print("Failed to parse state response:", e)
        elif topic == state_request_topic_ha:
            if msg == b"request_status":
                state = self.get_full_state()
                self.client.publish(state_response_topic_ha, dumps(state))
                asyncio.create_task(self.publish_light_state_to_HA(False))
                print("Sent state to HA")

    def set_idle_brightness_cb(self, cb):
        self.idle_brightness_cb = cb

    def set_edge_glow_cb(self, cb):
        self.edge_glow_cb = cb

    def set_enabled_state_cb(self, cb):
        self.enabled_state_cb = cb

    def set_full_state(self, state):
        # need to call set_idle_levels for idle and edge, so we can set one directly, but one must go through a cb
        if "idle_brightness" in state:
            self.idle_brightness_cb(state["idle_brightness"])
        if "edge_glow" in state:
            self.edge_glow_cb(state["edge_glow"])
        if "duration" in state:
            self.animation["duration"] = state["animation_duration"]
        if "animation_pause" in state:
            self.animation["pause_time"] = state["animation_pause"]
        
        # pull current state from MQTT Light before ESP overwrites it in HA
        if "effect" in state:
            self.handle_effect_command(state["effect"].encode('ascii'))
        if "max_brightness" in state:
            self.animation["level_max"] = state["max_brightness"]

    def get_full_state(self):
        return {
            b"idle_brightness": self.animation["level_min"],
            b"edge_glow": self.animation["edge_glow"],
            b"animation_duration": self.animation["duration"],
            b"animation_pause": self.animation["pause_time"],
            # removed inputs, as they are now handled by MQTT Light
            # "max_brightness": self.animation["level_max"],
            # "effect": self.animation["effect"],
        }

    def handle_properties(self, topic, msg):
        key = topic.split(b"/properties/")[1].split(b"/set")[0]
        print("Received property", key, "with value", msg)
        if key == b"idle_brightness":
            value = int(msg)
            self.idle_brightness_cb(value)
        elif key == b"max_brightness":
            value = int(msg)
            self.animation["level_max"] = max(min(value, 4095), 0)
            self.client.publish(brightness_state_topic, str(self.animation["level_max"]))
        elif key == b"edge_glow":
            value = int(msg)
            self.edge_glow_cb(value)
        elif key == b"animation_duration":
            value = int(msg)
            self.animation["duration"] = min(max(value, 1), 60)
        elif key == b"animation_pause":
            value = int(msg)
            self.animation["pause_time"] = min(max(value, 1), 600)
        print("Set", key, "to", value)

    def handle_command(self, msg):
        self.enabled_state_cb(msg == b"ON")
        self.client.publish(state_topic, msg)

    def handle_brightness_command(self, msg):
        value = int(msg)
        self.animation["level_max"] = max(min(value, 4095), 0)
        self.client.publish(brightness_state_topic, str(value))

    def get_current_effect_name(self):
        return self.all_animations[self.animation["effect"]][2]

    def handle_effect_command(self, msg):
        print("Received effect command", msg)
        for key, value in self.all_animations.items():
            if value[2] == msg:
                self.animation["effect"] = key
                self.client.publish(effect_state_topic, msg)
                return

        # got unknown effect request, report back current effect
        self.client.publish(effect_state_topic, self.get_current_effect_name())
