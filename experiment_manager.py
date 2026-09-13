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
    def __init__(self, mode, stimuli, trigger_manager=None, feedback_receiver=None,
                 flicker_duration=1.0, rest_interval=1.0, continuous_interval=1.3,
                 offline_rounds=5, offline_order='clockwise'):
        if flicker_duration <= 0 or rest_interval <= 0 or continuous_interval <= 0:
            raise ValueError('Stim 时长与间隔参数必须大于 0 秒')
        if offline_rounds < 1:
            raise ValueError('离线采集轮数必须至少为 1')
        if offline_order not in ('clockwise', 'random'):
            raise ValueError("Stim 采集顺序必须是 'clockwise' 或 'random'")
        self.mode = mode
        self.stimuli = stimuli
        self.trigger = trigger_manager
        self.feedback_receiver = feedback_receiver
        self.feedback_flash_duration = 0.4
        
        # State constants
        self.STATE_IDLE = 0
        self.STATE_REST = 1
        self.STATE_CUE = 2
        self.STATE_FLICKER = 3
        self.STATE_FEEDBACK = 4
        self.STATE_WAIT = 5 # Wait for classifier result (Online Discrete)
        self.STATE_PAUSE = 6 # Initial pause before experiment starts

        self.state = self.STATE_IDLE
        self.state_start_time = 0
        self.state_start_frame = 0
        self.target_idx = -1
        
        # Timing Configuration (Seconds)
        self.t_rest = float(rest_interval)
        self.t_cue = 1.0
        self.t_flicker = float(flicker_duration)
        self.t_feedback = 0.5
        self.t_continuous_tag_interval = float(continuous_interval)

        # Offline Sequence
        self.offline_sequence = []
        self.current_trial_idx = 0
        self.TOTAL_OFFLINE_ROUNDS = int(offline_rounds)
        self.offline_order = offline_order

        # Continuous State
        self.last_tag_time = 0

    def start(self):
        self.state_start_time = time.time()
        print(f"Starting Experiment Mode: {self.mode}")
        
        if self.mode == 'offline':
            # Generate random target sequence
            # E.g. block of 10 trials, randomized targets
            self._generate_offline_sequence(rounds=self.TOTAL_OFFLINE_ROUNDS)
            self.current_trial_idx = 0
            # Start in PAUSE
            self._enter_state(self.STATE_PAUSE)
            print("Press SPACE to start Offline Experiment...")
            
        elif self.mode == 'online_discrete':
            # Start in PAUSE
            self._enter_state(self.STATE_PAUSE)
            print("Press SPACE to start Online Discrete Experiment...")
            
        elif self.mode == 'online_continuous':
            # Start in PAUSE
            self._enter_state(self.STATE_PAUSE)
            print("Press SPACE to start Online Continuous Experiment...")

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
        
        # state_names = {0:'IDLE', 1:'REST', 2:'CUE', 3:'FLICKER', 4:'FEEDBACK', 5:'WAIT'}
        # print(f"[State] -> {state_names.get(new_state, 'UNKNOWN')}")

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
                if self.current_trial_idx < len(self.offline_sequence):
                    # Calculate Round info
                    num_stim = len(self.stimuli)
                    current_round = (self.current_trial_idx // num_stim) + 1
                    trial_in_round = (self.current_trial_idx % num_stim) + 1
                    print(f"Round {current_round}/{self.TOTAL_OFFLINE_ROUNDS}, Trial {trial_in_round}/{num_stim} (Global: {self.current_trial_idx + 1})")

                    self.target_idx = self.offline_sequence[self.current_trial_idx]
                    self._enter_state(self.STATE_CUE, frame_count)
                else:
                    self._enter_state(self.STATE_IDLE)
                    print("Offline Session Complete")

        elif self.state == self.STATE_CUE:
            if elapsed > self.t_cue:
                self._enter_state(self.STATE_FLICKER, frame_count)

        elif self.state == self.STATE_FLICKER:
            if elapsed > self.t_flicker:
                self.current_trial_idx += 1
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
        if self.state == self.STATE_PAUSE:
            return

        # Always flickering
        # Send periodic tags
        if current_time - self.last_tag_time > self.t_continuous_tag_interval:
            print(f"[Continuous] Sending Tag 4")
            if self.trigger:
                self.trigger.write_event(4)
            self.last_tag_time = current_time

            # Consume latest feedback label aligned with each tag period.
            # Flicker keeps running; we only paint a green border on the chosen target.
            if self.feedback_receiver is not None:
                label = self.feedback_receiver.pop_latest_label()
                if label is not None and 1 <= label <= len(self.stimuli):
                    target = self.stimuli[label - 1]
                    target.border_flash_duration = self.feedback_flash_duration
                    target.trigger_border_flash(color=(0.0, 1.0, 0.0))
                    print(f"[Continuous] Feedback label={label} -> stim[{label-1}]")

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

    def resume(self):
        """ Resume from PAUSE state manually (e.g. key press) """
        if self.state == self.STATE_PAUSE:
            if self.mode == 'offline':
                self._enter_state(self.STATE_REST)
            elif self.mode == 'online_discrete':
                self._enter_state(self.STATE_REST)
            elif self.mode == 'online_continuous':
                self._enter_state(self.STATE_FLICKER)
                # For continuous, we need to explicitly start flicker here now
                for s in self.stimuli:
                    s.set_flicker(freq=s.flicker_freq, current_frame=0)
                self.last_tag_time = time.time()

    def _generate_offline_sequence(self, rounds=5):
        # 'clockwise'（默认）：每轮按 上→右→下→左 的固定顺时针顺序提示；
        # 'random'：块内随机化（旧行为），避免被试对顺序产生预期效应。
        self.offline_sequence = []
        ids = list(range(len(self.stimuli)))

        if self.offline_order == 'clockwise' and len(ids) == 4:
            # stimuli 位置顺序为 [上, 左, 右, 下]，顺时针即 [上, 右, 下, 左]
            clockwise = [ids[0], ids[2], ids[3], ids[1]]
            for r in range(rounds):
                self.offline_sequence.extend(clockwise)
        else:
            for r in range(rounds):
                # Shuffle a copy of ids for this round
                r_ids = ids[:]
                random.shuffle(r_ids)
                self.offline_sequence.extend(r_ids)

        print(f"Generated Sequence ({rounds} rounds, {len(self.offline_sequence)} trials): {self.offline_sequence}")
