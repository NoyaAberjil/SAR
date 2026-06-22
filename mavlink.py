from pymavlink import mavutil
import math
import time
from logger import logger
BAUD_RATE=921600

class NotGuidedException(Exception):
    def __init__(self, message="Drone not in GUIDED mode"):
        self.message = message
        super().__init__(self.message)


class MavLinkCommandError(Exception):
    def __init__(self, message="MavLink command failed"):
        self.message = message
        super().__init__(self.message)

class MavLinkHandler:
    def __init__(self, connection_string,msg_frq=1): # msg freq in Hz
        self._last_pos = 0
        self._connection = self._connect(connection_string,msg_frq)
        
    def _check_guided_mode(self):
        mode = self.get_curr_mode()
        logger.debug(f"mode={mode}")
        if mode!=4:
            raise NotGuidedException
        else:
            return True 
    def check_until_guided(self):
        mode = self.get_curr_mode()
        logger.debug(f"mode={mode}")
        while mode != 4:
            mode = self.get_curr_mode()
            logger.debug(f"mode={mode}")



    def get_gps_coordinates(self,connection_string, timeout=10):
        """
        :param connection_string: The connection endpoint (e.g., 'udpin:localhost:14550', '/dev/ttyUSB0')
        :param timeout: How long to wait for a message in seconds
        :return: Tuple of (latitude, longitude, altitude_in_meters) or (None, None, None)
        """
        try:

            # 3. Request the GLOBAL_POSITION_INT message
            # blocking=True ensures we wait until the specific message arrives
            msg = self._connection.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=timeout)
            
            if msg is not None:
                #Convert MAVLink integer format to decimal degrees
                # lat and lon are sent as degrees * 1E7
                lat_decimal = msg.lat / 1e7
                lon_decimal = msg.lon / 1e7

                alt_meters = msg.alt / 1000.0 #converting to meters
                return lat_decimal, lon_decimal, alt_meters
            else:
                print("Timeout: Did not receive GLOBAL_POSITION_INT message.")
                return None, None, None
                
        except Exception as e:
            print(f"Error connecting or reading MAVLink: {e}")
            return None, None, None


    # wait for the next message of type. msg_type can be str or list of str. passing empty string will return the next message of any type
    # for list of message type in ardupilot: https://ardupilot.org/copter/docs/ArduCopter_MAVLink_Messages.html#requestable-messages
    # some common ones: ATTITUDE, RAW_IMU, HEARTBEAT, WIND, RC_CHANNELS
    def _get_message(self, msg_type:str):
        if msg_type == "" or msg_type is None:
            msg = self._connection.recv_match(blocking=True)
            if msg is None:
                logger.warning("Timeout waiting for any message")
                return None
            logger.debug(msg.get_type())
            return msg

        # Get the first message of the type (blocking)
        msg = self._connection.recv_match(type=msg_type, blocking=True)
        if msg is None:
            logger.warning(f"Timeout waiting for message of type {msg_type}")
            return None

        # Drain the buffer for the same type to get the most recent one
        while True:
            next_msg = self._connection.recv_match(type=msg_type, blocking=False)
            if next_msg is None:
                break
            msg = next_msg

        return msg        

    def set_motor_relay(self,relay,state):
        """
        state: 1 for ON, 0 for OFF
        """
        # MAV_CMD_DO_SET_RELAY (index 181)
        # Param 1: Relay number (0 for Relay1, 1 for Relay2, etc.)
        # Param 2: Setting (1 for ON, 0 for OFF)
        self._connection.mav.command_long_send(
            self._connection.target_system,
            self._connection.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_RELAY,
            0,      # Confirmation
            relay,      # Relay Instance (0 = RELAY1)
            state,  # 1 = ON, 0 = OFF
            0, 0, 0, 0, 0
        )
        status = "ON" if state == 1 else "OFF"
        logger.info(f"Motor Relay set to {status}")


    def send_text(self,msg):
        # ******* Send TEXT messages ********
        # how to send text that will show up on mission planner
        # use MAV_SEVERITY_WARNING. if you use MAV_SEVERITY_CRITICAL than it will not arm / takeoff. and MAV_SEVERITY_INFO will not always show up
        # can also use as b"Hello"
        self._connection.mav.statustext_send(mavutil.mavlink.MAV_SEVERITY_WARNING, bytes(msg,'utf-8'))
        logger.debug(msg)

    def change_flight_mode(self,mode:int):
        # ******* Change flight mode ********
        # Change flight mode. 0-Stabilize, 4-Guided, 5-Loiter, 6-RTL, 9-Land
        # mode values: https://ardupilot.org/copter/docs/parameters.html#fltmode1
        # see also https://ardupilot.org/dev/docs/mavlink-get-set-flightmode.html &
        self._connection.mav.command_long_send(self._connection.target_system, self._connection.target_component,
                                                mavutil.mavlink.MAV_CMD_DO_SET_MODE, 0, 1, mode, 0, 0, 0, 0, 0)
        msg = self._connection.recv_match(type='COMMAND_ACK',blocking=True)
        if msg is None:
            error_msg = f"Timeout waiting for ACK to change mode to {mode}"
            self.send_text(error_msg)
            raise MavLinkCommandError(error_msg)
        elif msg.result != 0:
            error_msg = f"Unable to change to mode {mode}"
            self.send_text(error_msg)
            raise MavLinkCommandError(error_msg)
        else:
            self.send_text(f"Mode changed to {mode}")


    def arm(self):
        # ******* ARM ********
        self._connection.mav.command_long_send(self._connection.target_system, self._connection.target_component,
                                                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0)
        msg = self._connection.recv_match(type='COMMAND_ACK',blocking=True)
        if msg is None:
            error_msg = "Timeout waiting for ARM ACK"
            self.send_text(error_msg)
            raise MavLinkCommandError(error_msg)
        elif msg.result != 0:
            error_msg = "Unable to ARM"
            self.send_text(f"{error_msg}. Exiting !!!")
            raise MavLinkCommandError(error_msg)
        else:
            self.send_text("ARMED !!!!")

    def get_curr_mode(self):
        msg=self._get_message("HEARTBEAT")
        while msg.type ==6: # 6 is type GCS, we want to ignore these
            msg=self._get_message("HEARTBEAT")
        return msg.custom_mode
        

    def fly_gps_pos(self,lat,lon):
        self._check_guided_mode()
        # ******* Fly to lat long ********
        # in mission planner in full prarameter list, update WPNAV_SPEED !! to make sure we don't fly too fast
        # see https://www.youtube.com/watch?v=yyt4VjBRG_Y
        # https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html
        # https://mavlink.io/en/messages/common.html#SET_POSITION_TARGET_LOCAL_NED
        self._connection.mav.send(mavutil.mavlink.MAVLink_set_position_target_global_int_message(10, self._connection.target_system,
                                self._connection.target_component, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, int(0b110111111000), int(lat * 10 ** 7), int(lon * 10 ** 7), 10, 0, 0, 0, 0, 0, 0, 1.57, 0.5))

        self.send_text("Flying to target...")
        # we notice we get a few zero wp_dist - so wait until we get non zero wp_dist 
        msg = self._connection.recv_match(type='NAV_CONTROLLER_OUTPUT', blocking=True)
        wp_dist = msg.wp_dist
        max_tries=0
        while max_tries<20 and wp_dist==0 and self._check_guided_mode():
            max_tries+=1
            # msg = the_connection.recv_match(type='LOCAL_POSITION_NED', blocking=True)
            msg = self._connection.recv_match(type='NAV_CONTROLLER_OUTPUT', blocking=True)
            wp_dist = msg.wp_dist
            # logger.debug(msg)
            self.send_text("distance to target:"+str(msg.wp_dist))

        # wait until we reach the wp (wp_dist=0)
        while wp_dist>0 and self._check_guided_mode():
            # msg = the_connection.recv_match(type='LOCAL_POSITION_NED', blocking=True)
            msg = self._connection.recv_match(type='NAV_CONTROLLER_OUTPUT', blocking=True)
            wp_dist = msg.wp_dist
            # logger.debug(msg)
            self.send_text("distance to target:"+str(msg.wp_dist))

        self.send_text("Target reached !")


    def _connect(self,connection_string,msg_frq):
        the_connection = mavutil.mavlink_connection(connection_string,source_system=1,baud=BAUD_RATE)
        the_connection.wait_heartbeat()
        logger.info("Heartbeat from system (system %u component %u)" % (the_connection.target_system, the_connection.target_component))

        # ask to get all messages in a rate of msg_frq Hz
        data_rate = msg_frq # Hz
        the_connection.mav.request_data_stream_send(the_connection.target_system, the_connection.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL, data_rate, 1)
        return the_connection
