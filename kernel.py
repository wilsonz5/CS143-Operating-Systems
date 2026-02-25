### Fill in the following information before submitting
# Group id: 44
# Members: Save Soukkaseum, Wilson Zheng

from collections import deque
import heapq

# PID is just an integer, but it is used to make it clear when a integer is expected to be a valid PID.
PID = int

# This class represents the PCB of processes.
# It is only here for your convinience and can be modified however you see fit.
class PCB:
    pid: PID

    def __init__(self, pid: PID):
        self.pid = pid

        # additional fields for project 2:
        self.priority = 0
        self.process_type = "None"

# This class represents the Kernel of the simulation.
# The simulator will create an instance of this object and use it to respond to syscalls and interrupts.
# DO NOT modify the name of this class or remove it.
class Kernel:
    scheduling_algorithm: str
    ready_queue: deque[PCB]
    waiting_queue: deque[PCB]
    running: PCB
    idle_pcb: PCB

    # Called before the simulation begins.
    # Use this method to initilize any variables you need throughout the simulation.
    # logger is provided which allows you to include your own print statements in the
    #   output logs. These will not impact grading.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def __init__(self, scheduling_algorithm: str, logger):
        self.scheduling_algorithm = scheduling_algorithm
        # self.ready_queue = deque()
        self.waiting_queue = deque()
        self.idle_pcb = PCB(0)
        self.running = self.idle_pcb

        # additional initializations for project 2:
        # for Time Tracking
        self.tick_count = 0
        self.rr_ticks = 0
        self.level_ticks = 0

        # queues
        self.ready_queue = deque()              # RR Single queue
        self.priority_queue = []                # Priority Queue (min-heap)
        self.fg_queue = deque()                 # Multilevel's Foreground (RR)
        self.bg_queue = deque()                 # Multilevel's Background (FCFS)

        # for MLFQ
        self.current_level = "Foreground"

        # for synchronization primitives
        self.semaphores = {}    # sempahores = {semaphore_id: (value: int, wait: list[PCB])}
        self.mutexes = {}       # mutexes = {mutex_id: (locked: bool, owner: PID|None, wait: list[PCB])}


    # This method is triggered every time a new process has arrived.
    # new_process is this process's PID.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def new_process_arrived(self, new_process: PID, priority: int, process_type: str) -> PID:
        pcb = PCB(new_process)
        pcb.priority = priority
        pcb.process_type = process_type

        if self.scheduling_algorithm == "Priority":
            heapq.heappush(self.priority_queue, (pcb.priority, pcb.pid, pcb))

            # if cpu is idle, run the new process immediately
            if self.running.pid == 0:
                self.running = self.choose_next_process()
                return self.running.pid
            
            # preempt if new process has higher priority than currently running process
            if (pcb.priority < self.running.priority) or (pcb.priority == self.running.priority and pcb.pid < self.running.pid):
                heapq.heappush(self.priority_queue, (self.running.priority, self.running.pid, self.running))
                self.running = self.choose_next_process()

        elif self.scheduling_algorithm == "RR":
            self.ready_queue.append(pcb)
            if self.running.pid == 0:
                self.running = self.choose_next_process()

        elif self.scheduling_algorithm == "Multilevel":
            if process_type == "Foreground":
                self.fg_queue.append(pcb)
            else: # process_type == "Background"
                self.bg_queue.append(pcb)
            
        elif self.scheduling_algorithm == "FCFS":
            self.ready_queue.append(pcb)
            if self.running.pid == 0:
                self.running = self.choose_next_process()

        # universal behavior: if cpu is idle, run the new process immediately
        if self.running.pid == 0:
            self.running = self.choose_next_process()

        return self.running.pid


    # This method is triggered every time the current process performs an exit syscall.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_exit(self) -> PID:
        self.running = self.idle_pcb
        self.running = self.choose_next_process()
        return self.running.pid
    

    # This is where you can select the next process to run.
    # This method is not directly called by the simulator and is purely for your convinience.
    # Feel free to modify this method as you see fit.
    # It is not required to actually use this method but it is recommended.
    def choose_next_process(self):
        
        if self.scheduling_algorithm == "Priority":
            if len(self.priority_queue) == 0:
                return self.idle_pcb
            _, _, next_pcb = heapq.heappop(self.priority_queue)
            return next_pcb
        elif self.scheduling_algorithm == "FCFS":
            if len(self.ready_queue) == 0:
                return self.idle_pcb
            return self.ready_queue.popleft()
        elif self.scheduling_algorithm == "RR":
            if len(self.ready_queue) == 0:
                return self.idle_pcb
            self.rr_ticks = 0
            return self.ready_queue.popleft()
        elif self.scheduling_algorithm == "Multilevel":
            if self.current_level == "Foreground":
                if len(self.fg_queue) == 0:
                    if len(self.bg_queue) == 0:
                        return self.idle_pcb
                    self.current_level = "Background"
                    self.level_ticks = 0
                    return self.bg_queue.popleft()

                self.rr_ticks = 0
                return self.fg_queue.popleft()

            else:  # Background
                if len(self.bg_queue) == 0:
                    if len(self.fg_queue) == 0:
                        return self.idle_pcb
                    self.current_level = "Foreground"
                    self.level_ticks = 0
                    self.rr_ticks = 0
                    return self.fg_queue.popleft()
                return self.bg_queue.popleft()



    # This method is triggered when the currently running process requests to change its priority.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_set_priority(self, new_priority: int) -> PID:
        if self.scheduling_algorithm != "Priority":
            self.running.priority = new_priority
            return self.running.pid

        # Update running process priority
        self.running.priority = new_priority

        # Check if someone else should run
        if len(self.priority_queue) > 0:
            top_priority, top_pid, top_pcb = self.priority_queue[0]

            if (top_priority < self.running.priority) or \
            (top_priority == self.running.priority and top_pid < self.running.pid):

                # Preempt running process
                heapq.heappush(
                    self.priority_queue,
                    (self.running.priority, self.running.pid, self.running)
                )

                self.running = self.choose_next_process()

        return self.running.pid


    # This function represents the hardware timer interrupt.
    # It is triggered every 10 milliseconds and is the only way a kernel can track passing time.
    # Do not use real time to track how much time has passed as time is simulated.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def timer_interrupt(self) -> PID:
        # FCFS must never be time-preempted
        if self.scheduling_algorithm == "FCFS":
            return self.running.pid
        if self.scheduling_algorithm == "RR":
            # if idle, nothing to do
            if self.running.pid == 0:
                return self.running.pid

            self.rr_ticks += 1

            # quantum = 4 ticks (40ms)
            if self.rr_ticks >= 4:
                # move current process to end of queue
                self.ready_queue.append(self.running)
                # pick next process
                self.running = self.choose_next_process()

        elif self.scheduling_algorithm == "Multilevel":
            if self.running.pid == 0:
                return self.running.pid

            self.level_ticks += 1

            # Foreground (RR)
            if self.current_level == "Foreground":
                self.rr_ticks += 1

                # Level switch has priority over RR
                if self.level_ticks >= 20 and len(self.bg_queue) > 0:
                    self.fg_queue.append(self.running)
                    self.current_level = "Background"
                    self.level_ticks = 0
                    self.rr_ticks = 0
                    self.running = self.choose_next_process()
                    return self.running.pid

                # RR quantum = 4 ticks
                if self.rr_ticks >= 4:
                    self.fg_queue.append(self.running)
                    self.running = self.choose_next_process()
                    return self.running.pid

            else:  # Background (FCFS)
                # 1️Level switch back to FG after 20 ticks if FG has work
                if self.level_ticks >= 20 and len(self.fg_queue) > 0:
                    self.bg_queue.appendleft(self.running)  # FCFS → resume later
                    self.current_level = "Foreground"
                    self.level_ticks = 0
                    self.rr_ticks = 0
                    self.running = self.choose_next_process()
                    return self.running.pid


        return self.running.pid

    # This method is triggered when the currently running process requests to initialize a new semaphore.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_init_semaphore(self, semaphore_id: int, initial_value: int):
        self.semaphores[semaphore_id] = { "value": initial_value, "wait": deque() }
        return
    
    # This method is triggered when the currently running process calls p() on an existing semaphore.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_semaphore_p(self, semaphore_id: int) -> PID:
        sem = self.semaphores[semaphore_id]
        sem["value"] -= 1

        if sem["value"] < 0:
            return self.block_running_process(sem["wait"])

        return self.running.pid

    # This method is triggered when the currently running process calls v() on an existing semaphore.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_semaphore_v(self, semaphore_id: int) -> PID:
        sem = self.semaphores[semaphore_id]
        sem["value"] += 1

        if sem["value"] <= 0:
            pcb = self.select_unblock_process(sem["wait"])
            if pcb:
                if self.scheduling_algorithm == "FCFS":
                    self.add_to_ready(pcb, front=True)
                else:
                    self.add_to_ready(pcb)

                # Preemption rules
                if self.scheduling_algorithm == "Priority":
                    if (pcb.priority < self.running.priority) or \
                    (pcb.priority == self.running.priority and pcb.pid < self.running.pid):
                        heapq.heappush(self.priority_queue, (self.running.priority, self.running.pid, self.running))
                        self.running = self.choose_next_process()

                # FCFS → NON-PREEMPTIVE → do nothing
                # RR → do nothing (will run when scheduled)

        return self.running.pid

    # This method is triggered when the currently running process requests to initialize a new mutex.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_init_mutex(self, mutex_id: int):
        self.mutexes[mutex_id] = { "locked": False, "owner": None, "wait": deque() }

    # This method is triggered when the currently running process calls lock() on an existing mutex.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_mutex_lock(self, mutex_id: int) -> PID:
        mutex = self.mutexes[mutex_id]

        # If mutex is free → acquire and continue running
        if not mutex["locked"]:
            mutex["locked"] = True
            mutex["owner"] = self.running.pid
            return self.running.pid

        # Otherwise → block current process
        return self.block_running_process(mutex["wait"])


    # This method is triggered when the currently running process calls unlock() on an existing mutex.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_mutex_unlock(self, mutex_id: int) -> PID:
        mutex = self.mutexes[mutex_id]

        # Only owner can unlock (simulator likely guarantees this)
        if mutex["wait"]:
            pcb = self.select_unblock_process(mutex["wait"])

            # Transfer lock to unblocked process
            mutex["owner"] = pcb.pid
            if self.scheduling_algorithm == "FCFS":
                self.add_to_ready(pcb, front=True)
            else:
                self.add_to_ready(pcb)

            # Priority preemption check
            if self.scheduling_algorithm == "Priority":
                if (pcb.priority < self.running.priority) or \
                (pcb.priority == self.running.priority and pcb.pid < self.running.pid):
                    heapq.heappush(self.priority_queue,
                                (self.running.priority, self.running.pid, self.running))
                    self.running = self.choose_next_process()
        else:
            mutex["locked"] = False
            mutex["owner"] = None

        return self.running.pid



    def block_running_process(self, wait_list):
        wait_list.append(self.running)
        self.running = self.idle_pcb
        self.running = self.choose_next_process()
        return self.running.pid


    def add_to_ready(self, pcb: PCB, front=False):
        if self.scheduling_algorithm == "Priority":
            heapq.heappush(self.priority_queue, (pcb.priority, pcb.pid, pcb))
        elif self.scheduling_algorithm == "RR":
            self.ready_queue.append(pcb)
        elif self.scheduling_algorithm == "FCFS":
            if front:
                self.ready_queue.appendleft(pcb)
            else:
                self.ready_queue.append(pcb)

    def select_unblock_process(self, wait_list):
        if not wait_list:
            return None

        if self.scheduling_algorithm == "Priority":
            best = min(wait_list, key=lambda pcb: (pcb.priority, pcb.pid))
            wait_list.remove(best)
            return best

        # FCFS and RR → arrival order
        return wait_list.popleft()