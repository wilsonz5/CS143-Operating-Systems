### Fill in the following information before submitting
# Group id: 78618535, 34588968, 45441829
# Members: Darren Hu, Save Soukkaseum, Wilson Zheng

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
            # TODO: Multilevel scheduling later
            if process_type == "Foreground":
                self.fg_queue.append(pcb)
            else: # process_type == "Background"
                self.bg_queue.append(pcb)

        # universal behavior: if cpu is idle, run the new process immediately
        if self.running.pid == 0:
            self.running = self.choose_next_process()

        return self.running.pid


    # This method is triggered every time the current process performs an exit syscall.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_exit(self) -> PID:
        # current process is exiting, choose next process to run
        next_pcb = self.choose_next_process()
        self.running = next_pcb
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
        elif self.scheduling_algorithm == "RR":
            if len(self.ready_queue) == 0:
                return self.idle_pcb
            self.rr_ticks = 0
            return self.ready_queue.popleft()
        # TODO:
        # Multilevel later
        return self.running

    # This method is triggered when the currently running process requests to change its priority.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def syscall_set_priority(self, new_priority: int) -> PID:
        self.running.priority = new_priority
        next_pcb = self.choose_next_process()
        self.running = next_pcb
        return self.running.pid


    # This function represents the hardware timer interrupt.
    # It is triggered every 10 milliseconds and is the only way a kernel can track passing time.
    # Do not use real time to track how much time has passed as time is simulated.
    # DO NOT rename or delete this method. DO NOT change its arguments.
    def timer_interrupt(self) -> PID:
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

        return self.running.pid