import serial
import time

class SerialTrigger:
    def __init__(self, port, bps=115200):
        self._port = port
        self._bps = bps
        try:
            self._trigger = serial.Serial(port=self._port, baudrate=self._bps, timeout=1)
            # Reset state
            self._trigger.write(bytearray([0]))
            print(f"Trigger serial initialized on {self._port} at {self._bps} bps")
        except Exception as e:
            print(f"Warning: Could not open serial port {port}: {e}")
            self._trigger = None

    def write_event(self, event_id, follow_zero=True):
        """
        Writes an event tag to the serial port.
        Ensures a zero is sent before the event to ensure a transition.
        If follow_zero is True, sends a zero after a small delay.
        """
        if self._trigger is None:
            return

        try:
            # Pre-reset
            self._trigger.write(bytearray([0]))
            # Send event
            self._trigger.write(bytearray([event_id & 0xFF]))
            
            if follow_zero:
                # Small sleep to ensure the hardware registers the pulse
                # Note: This blocks for 2ms. For highly sensitive timing, 
                # this might be moved to a thread, but for most SSVEP it's acceptable.
                time.sleep(0.002)
                self._trigger.write(bytearray([0]))
        except Exception as e:
            print(f"Serial write error: {e}")

    def close(self):
        if self._trigger:
            self._trigger.close()
