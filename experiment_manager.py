import time
import random

class ExperimentManager:
    """
    Manages the state and timing of different experiment modes.
    Modes:
        1. 'online_discrete': Fixed flicker -> Feedback (Green)
        2. 'offline': Cue (Red) -> Flicker (Tag=Target) -> Rest
        3. 'online_continuous': Continuous flicker -> Periodic Tags
    """
    def __init__(self, mode, stimuli, trigger_manager=None):
        self.mode = mode
        self.stimuli = stimuli
        self.trigger = trigger_manager
        
        # State constants
        self.STATE_IDLE = 0
        self.STATE_REST = 1
        self.STATE_CUE = 2
        self.STATE_FLICKER = 3
        self.STATE_FEEDBACK = 4
        self.STATE_WAIT = 5 # Wait for classifier result (Online Discrete)

        self.state = self.STATE_IDLE
        self.state_start_time = 0
        self.state_start_frame = 0
        self.target_idx = -1
        
        # Timing Configuration (Seconds)
        self.t_rest = 1.0
        self.t_cue = 1.0
        self.t_flicker = 2.0
        self.t_feedback = 0.5
        self.t_continuous_tag_interval = 2.0 
        
        # Offline Sequence
        self.offline_sequence = []
        self.offline_round = 0
        self.TOTAL_OFFLINE_ROUNDS = 5 # Default, can be tailored

        # Continuous State
        self.last_tag_time = 0

    def start(self):
        self.state_start_time = time.time()
        print(f"Starting Experiment Mode: {self.mode}")
        
        if self.mode == 'offline':
            # Generate random target sequence
            # E.g. block of 10 trials, randomized targets
            self._generate_offline_sequence(count=self.TOTAL_OFFLINE_ROUNDS)
            self.offline_round = 0
            self._enter_state(self.STATE_REST)
            
        elif self.mode == 'online_discrete':
            self._enter_state(self.STATE_REST)
            
        elif self.mode == 'online_continuous':
            self._enter_state(self.STATE_FLICKER)
            # Start all flicker immediately
            for s in self.stimuli:
                 s.set_flicker(freq=s.flicker_freq, current_frame=0) 
            self.last_tag_time = time.time()

    def update(self, current_time, frame_count):
        elapsed = current_time - self.state_start_time
        
        if self.mode == 'offline':
            self._update_offline(elapsed, current_time, frame_count)
        elif self.mode == 'online_discrete':
            self._update_online_discrete(elapsed, current_time, frame_count)
        elif self.mode == 'online_continuous':
            self._update_online_continuous(elapsed, current_time, frame_count)

    def _enter_state(self, new_state, frame_count=0):
        self.state = new_state
        self.state_start_time = time.time()
        self.state_start_frame = frame_count
        
        state_names = {0:'IDLE', 1:'REST', 2:'CUE', 3:'FLICKER', 4:'FEEDBACK', 5:'WAIT'}
        print(f"[State] -> {state_names.get(new_state, 'UNKNOWN')}")

        if new_state == self.STATE_REST:
            self._stop_all_flicker()
            
        elif new_state == self.STATE_CUE:
            # Show Red Border on target
            target = self.stimuli[self.target_idx]
            target.trigger_border_flash(color=(1.0, 0.0, 0.0))
            # Duration of border flash handled by stimulus object itself usually, 
            # but we might want to ensure it matches t_cue. 
            # Stimulus.trigger_border_flash sets a start time. 
            # We can update Stimulus to allow updating duration or just rely on default.
            target.border_flash_duration = self.t_cue

        elif new_state == self.STATE_FLICKER:
            # Start Flicker
            for s in self.stimuli:
                s.set_flicker(freq=s.flicker_freq, current_frame=frame_count)
            
            # Send Tag
            if self.trigger:
                if self.mode == 'offline':
                    # Tag = Target ID (1-based)
                    self.trigger.write_event(self.target_idx + 1)
                elif self.mode == 'online_discrete':
                    # Typical start tag for trial
                    self.trigger.write_event(100) 
                
        elif new_state == self.STATE_FEEDBACK:
            self._stop_all_flicker()
            # Show Green Border on Result
            # Result should have been set before entering state
            result_stim = self.stimuli[self.target_idx] # reusing target_idx for result
            result_stim.trigger_border_flash(color=(0.0, 1.0, 0.0))
            result_stim.border_flash_duration = self.t_feedback
            
    def _update_offline(self, elapsed, current_time, frame_count):
        if self.state == self.STATE_REST:
            if elapsed > self.t_rest:
                if self.offline_round < len(self.offline_sequence):
                    self.target_idx = self.offline_sequence[self.offline_round]
                    self._enter_state(self.STATE_CUE, frame_count)
                else:
                    self._enter_state(self.STATE_IDLE)
                    print("Offline Session Complete")

        elif self.state == self.STATE_CUE:
            if elapsed > self.t_cue:
                self._enter_state(self.STATE_FLICKER, frame_count)

        elif self.state == self.STATE_FLICKER:
            if elapsed > self.t_flicker:
                self.offline_round += 1
                self._enter_state(self.STATE_REST, frame_count)

    def _update_online_discrete(self, elapsed, current_time, frame_count):
        if self.state == self.STATE_REST:
            if elapsed > self.t_rest:
                self._enter_state(self.STATE_FLICKER, frame_count)
        
        elif self.state == self.STATE_FLICKER:
            if elapsed > self.t_flicker:
                self._stop_all_flicker()
                self._enter_state(self.STATE_WAIT, frame_count)
                print("Waiting for feedback command...")

        elif self.state == self.STATE_WAIT:
            # Blocking wait for external command usually.
            # Timeout or manual trigger? 
            # For now, let's just wait indefinitely or check manual input from main loop via a method
            pass 

        elif self.state == self.STATE_FEEDBACK:
            if elapsed > self.t_feedback:
                self._enter_state(self.STATE_REST, frame_count)

    def _update_online_continuous(self, elapsed, current_time, frame_count):
        # Always flickering
        # Send periodic tags
        if current_time - self.last_tag_time > self.t_continuous_tag_interval:
            print(f"[Continuous] Sending Tag 100")
            if self.trigger:
                self.trigger.write_event(100)
            self.last_tag_time = current_time

    def trigger_feedback(self, result_idx):
        """ Call this from main loop when classifier result is received """
        if self.mode == 'online_discrete' and self.state == self.STATE_WAIT:
            if 0 <= result_idx < len(self.stimuli):
                self.target_idx = result_idx # Reuse this field
                self._enter_state(self.STATE_FEEDBACK)
            else:
                print(f"Invalid result index: {result_idx}")

    def _stop_all_flicker(self):
        for s in self.stimuli:
            s.stop_flicker()

    def _generate_offline_sequence(self, count=10):
        # Random sequence
        ids = list(range(len(self.stimuli)))
        self.offline_sequence = [random.choice(ids) for _ in range(count)]
        print(f"Generated Sequence: {self.offline_sequence}")
